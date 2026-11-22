"""send_calls keeps the UserOperation hash once the send may have been accepted.

A local mock plays the chain RPC, the bundler and the paymaster on 127.0.0.1
and stores every UserOperation it accepts. It computes each operation's hash
itself, from the JSON the SDK sent, so the hash the SDK reports is checked
against what the bundler holds. No chain is contacted; the owner key is a
throwaway test value.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from eth_abi import encode
from eth_hash.auto import keccak

from polyester.chain import (
    POLYESTER_DEVNET_ENVIRONMENT,
    ChainCall,
    EntryPointConfig,
    PolyesterSmartAccount,
    UserOperationReceipt,
)
from polyester.chain.rpc import JsonRpcError
from polyester.chain.userop import _user_operation_hash, pack_paymaster_and_data
from polyester.errors import is_retryable_error, mutation_outcome_unknown

_OWNER_KEY = "0x" + "4f" * 32  # throwaway test key
_WITHDRAW = ChainCall(
    to="0x1111111111111111111111111111111111111111",
    data=bytes.fromhex("deadbeef"),
    value=0,
)


def _b(value: str) -> bytes:
    return bytes.fromhex(value[2:])


def _i(value: str) -> int:
    return int(value, 16)


def _mock_user_operation_hash(op: dict[str, Any], entry_point: str, chain_id: int) -> str:
    """EntryPoint v0.7 getUserOpHash of a JSON UserOperation, as a bundler computes it."""
    init_code = _b(op["factory"]) + _b(op["factoryData"]) if "factory" in op else b""
    paymaster_and_data = b""
    if "paymaster" in op:
        paymaster_and_data = (
            _b(op["paymaster"])
            + _i(op["paymasterVerificationGasLimit"]).to_bytes(16, "big")
            + _i(op["paymasterPostOpGasLimit"]).to_bytes(16, "big")
            + _b(op["paymasterData"])
        )
    packed = encode(
        ["address", "uint256", "bytes32", "bytes32", "bytes32", "uint256", "bytes32", "bytes32"],
        [
            op["sender"],
            _i(op["nonce"]),
            keccak(init_code),
            keccak(_b(op["callData"])),
            _i(op["verificationGasLimit"]).to_bytes(16, "big")
            + _i(op["callGasLimit"]).to_bytes(16, "big"),
            _i(op["preVerificationGas"]),
            _i(op["maxPriorityFeePerGas"]).to_bytes(16, "big")
            + _i(op["maxFeePerGas"]).to_bytes(16, "big"),
            keccak(paymaster_and_data),
        ],
    )
    return (
        "0x"
        + keccak(
            encode(["bytes32", "address", "uint256"], [keccak(packed), entry_point, chain_id])
        ).hex()
    )


@dataclass
class _Bundler:
    """Mock chain RPC + bundler + paymaster state and failure switches."""

    entry_point: str
    chain_id: int
    # Operations accepted by eth_sendUserOperation, by hash, in arrival order.
    operations: dict[str, dict[str, Any]] = field(default_factory=dict)
    # (A) receipt polls answer HTTP 503 this many times.
    receipt_503s: int = 0
    # (B) the send's answer is delayed this many seconds after it is stored.
    send_delay_s: float = 0.0
    # (C) the send is stored, then answered with this HTTP status.
    send_status: int | None = None
    # A definite refusal: the send is answered with this JSON-RPC error, not stored.
    send_error: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def handle(self, method: str, params: list[Any]) -> tuple[int, Any, float]:
        """Return (HTTP status, JSON-RPC result or error, delay before answering)."""
        if method == "eth_getCode":
            return 200, {"result": "0x"}, 0.0
        if method == "eth_call":
            # getNonce(sender, key): sequence 0 under the requested key.
            key = int.from_bytes(_b(params[0]["data"])[36:68], "big")
            return 200, {"result": "0x" + (key << 64).to_bytes(32, "big").hex()}, 0.0
        if method == "pimlico_getUserOperationGasPrice":
            tier = {"maxFeePerGas": "0x3b9aca00", "maxPriorityFeePerGas": "0x3b9aca00"}
            return 200, {"result": {"slow": tier, "standard": tier, "fast": tier}}, 0.0
        if method == "pm_sponsorUserOperation":
            return (
                200,
                {
                    "result": {
                        "callGasLimit": "0x186a0",
                        "verificationGasLimit": "0x30d40",
                        "preVerificationGas": "0xc350",
                        "paymasterVerificationGasLimit": "0xea60",
                        "paymasterPostOpGasLimit": "0x1",
                        "paymaster": "0x3333333333333333333333333333333333333333",
                        "paymasterData": "0x1234",
                    }
                },
                0.0,
            )
        if method == "eth_sendUserOperation":
            if self.send_error is not None:
                return 200, {"error": self.send_error}, 0.0
            op, entry_point = params
            user_op_hash = _mock_user_operation_hash(op, entry_point, self.chain_id)
            with self.lock:
                self.operations[user_op_hash] = op
            if self.send_status is not None:
                return self.send_status, None, 0.0
            return 200, {"result": user_op_hash}, self.send_delay_s
        if method == "eth_getUserOperationReceipt":
            with self.lock:
                if self.receipt_503s > 0:
                    self.receipt_503s -= 1
                    return 503, None, 0.0
                known = params[0] in self.operations
            if not known:
                return 200, {"result": None}, 0.0
            receipt = {
                "userOpHash": params[0],
                "success": True,
                "receipt": {"transactionHash": "0x" + "ab" * 32, "status": "0x1"},
            }
            return 200, {"result": receipt}, 0.0
        if method == "pimlico_getUserOperationStatus":
            return 200, {"result": {"status": "not_found", "transactionHash": None}}, 0.0
        return 200, {"error": {"code": -32601, "message": f"method {method} not found"}}, 0.0


@pytest.fixture
def bundler() -> Iterator[tuple[_Bundler, str]]:
    environment = POLYESTER_DEVNET_ENVIRONMENT
    state = _Bundler(
        entry_point=environment.account_abstraction.entry_point.address,
        chain_id=environment.chain_id,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            status, answer, delay = state.handle(body["method"], body["params"])
            if delay:
                time.sleep(delay)
            payload = b"upstream unavailable"
            if answer is not None:
                payload = json.dumps({"jsonrpc": "2.0", "id": body["id"], **answer}).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except OSError:
                pass  # the client gave up waiting (mode B)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _account(url: str, *, timeout: float = 2.0) -> PolyesterSmartAccount:
    environment = POLYESTER_DEVNET_ENVIRONMENT
    environment = replace(
        environment,
        rpc_url=url,
        account_abstraction=replace(
            environment.account_abstraction, bundler_url=url, paymaster_url=url
        ),
    )
    return PolyesterSmartAccount(
        owner_private_key=_OWNER_KEY, environment=environment, timeout=timeout
    )


def _send(account: PolyesterSmartAccount) -> UserOperationReceipt:
    result = account.send_calls([_WITHDRAW], receipt_timeout_s=3.0)
    assert isinstance(result, UserOperationReceipt)
    return result


def _assert_unknown_with_hash(error: BaseException, state: _Bundler) -> str:
    """The error names the one stored operation's hash and reads as outcome unknown."""
    assert len(state.operations) == 1
    (stored_hash,) = state.operations
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)
    assert getattr(error, "user_operation_hash", None) == stored_hash
    assert stored_hash in str(error)
    return stored_hash


def _recover(account: PolyesterSmartAccount, state: _Bundler, user_op_hash: str) -> None:
    """The documented recovery: wait on the hash; never sign a second operation."""
    receipt = account.wait_for_receipt(user_op_hash, timeout_s=3.0, poll_interval_s=0.05)
    assert receipt.user_operation_hash == user_op_hash
    assert receipt.success
    assert list(state.operations) == [user_op_hash]


def test_mode_a_receipt_poll_503_is_retried_and_returns_the_receipt(
    bundler: tuple[_Bundler, str],
) -> None:
    state, url = bundler
    state.receipt_503s = 1
    receipt = _send(_account(url))
    assert list(state.operations) == [receipt.user_operation_hash]
    assert receipt.success
    assert state.receipt_503s == 0


def test_mode_a_receipt_polls_failing_past_the_deadline_keep_the_hash(
    bundler: tuple[_Bundler, str],
) -> None:
    state, url = bundler
    state.receipt_503s = 10**9
    account = _account(url)
    started = time.monotonic()
    with pytest.raises(Exception) as raised:
        account.send_calls([_WITHDRAW], receipt_timeout_s=1.5)
    assert time.monotonic() - started < 10
    user_op_hash = _assert_unknown_with_hash(raised.value, state)
    state.receipt_503s = 0
    _recover(account, state, user_op_hash)


def test_mode_b_send_answer_after_client_timeout_keeps_the_hash(
    bundler: tuple[_Bundler, str],
) -> None:
    state, url = bundler
    state.send_delay_s = 1.5
    account = _account(url, timeout=0.5)
    with pytest.raises(Exception) as raised:
        account.send_calls([_WITHDRAW], receipt_timeout_s=3.0)
    user_op_hash = _assert_unknown_with_hash(raised.value, state)
    state.send_delay_s = 0.0
    _recover(account, state, user_op_hash)


def test_mode_c_send_answered_504_keeps_the_hash(bundler: tuple[_Bundler, str]) -> None:
    state, url = bundler
    state.send_status = 504
    account = _account(url)
    with pytest.raises(Exception) as raised:
        account.send_calls([_WITHDRAW], receipt_timeout_s=3.0)
    user_op_hash = _assert_unknown_with_hash(raised.value, state)
    assert getattr(raised.value, "status_code", None) == 504
    _recover(account, state, user_op_hash)


def test_without_wait_returns_the_hash_the_bundler_holds(bundler: tuple[_Bundler, str]) -> None:
    state, url = bundler
    user_op_hash = _account(url).send_calls([_WITHDRAW], wait=False)
    assert list(state.operations) == [user_op_hash]


@pytest.mark.parametrize(
    "error",
    [
        {"code": -32602, "message": "invalid UserOperation"},
        {"code": -32500, "message": "AA23 reverted"},
    ],
)
def test_definite_refusal_of_the_send_is_not_outcome_unknown(
    bundler: tuple[_Bundler, str], error: dict[str, Any]
) -> None:
    state, url = bundler
    state.send_error = error
    with pytest.raises(JsonRpcError) as raised:
        _account(url).send_calls([_WITHDRAW], receipt_timeout_s=3.0)
    assert raised.value.code == error["code"]
    assert not mutation_outcome_unknown(raised.value)
    assert getattr(raised.value, "user_operation_hash", None) is None
    assert state.operations == {}


def test_internal_error_answer_to_the_send_keeps_the_hash(bundler: tuple[_Bundler, str]) -> None:
    state, url = bundler
    state.send_error = {"code": -32603, "message": "internal error"}
    with pytest.raises(Exception) as raised:
        _account(url).send_calls([_WITHDRAW], receipt_timeout_s=3.0)
    assert mutation_outcome_unknown(raised.value)
    assert isinstance(raised.value.__cause__, JsonRpcError)
    assert getattr(raised.value, "user_operation_hash", "").startswith("0x")


@pytest.mark.parametrize(
    ("with_factory_and_paymaster", "expected"),
    [
        (True, "0xec0c13a94cb1a6c84a85cf970fe0ce14164dbb8c24db022e46315ed4631aa9cd"),
        (False, "0x3a04aade54da78403e340bc7112c76296af9658ec85525ceb7ad9f18021e6c85"),
    ],
)
def test_user_operation_hash_matches_entry_point_v07(
    with_factory_and_paymaster: bool, expected: str
) -> None:
    # Reference values: viem getUserOperationHash, entryPointVersion "0.7".
    environment = replace(
        POLYESTER_DEVNET_ENVIRONMENT,
        chain_id=31337,
        account_abstraction=replace(
            POLYESTER_DEVNET_ENVIRONMENT.account_abstraction,
            entry_point=EntryPointConfig(
                address="0x0000000071727De22E5E9d8BAf0edAc6f37da032", version="0.7"
            ),
        ),
    )
    init_code = b""
    paymaster_and_data = b""
    if with_factory_and_paymaster:
        init_code = bytes.fromhex("22" * 20 + "deadbeef")
        paymaster_and_data = pack_paymaster_and_data(
            paymaster="0x" + "33" * 20,
            paymaster_verification_gas_limit=60_000,
            paymaster_post_op_gas_limit=100_000,
            paymaster_data=bytes.fromhex("1234"),
        )
    assert (
        _user_operation_hash(
            environment=environment,
            sender="0x" + "11" * 20,
            nonce=(123456789 << 64) | 7,
            init_code=init_code,
            call_data=bytes.fromhex("abcdef01"),
            call_gas_limit=100_000,
            verification_gas_limit=200_000,
            pre_verification_gas=50_000,
            max_fee_per_gas=3_000_000_000,
            max_priority_fee_per_gas=1_000_000_000,
            paymaster_and_data=paymaster_and_data,
        )
        == expected
    )
