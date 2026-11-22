"""ERC-4337 EntryPoint v0.7 Safe UserOperation helpers (Pimlico-compatible)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_hash.auto import keccak
from eth_utils import to_checksum_address, to_hex

from polyester.chain.calldata import ChainCall
from polyester.chain.environment import POLYESTER_DEVNET_ENVIRONMENT, PolyesterChainEnvironment
from polyester.chain.rpc import JsonRpcClient, JsonRpcError, JsonRpcHttpError
from polyester.chain.safe import predict_safe_address_with_data
from polyester.codecs.scalars import exact_integer
from polyester.errors import PolyesterTransportError

USER_OPERATION_GAS_BUFFER_BPS = 2_000
USER_OPERATION_MIN_GAS_BUFFER = 50_000

_EXECUTE_USER_OP_SELECTOR = bytes.fromhex("541d63c8")  # executeUserOpWithErrorString
_GET_NONCE_SELECTOR = bytes.fromhex("35567e1a")  # getNonce(address,uint192)

_STUB_ECDSA_SIGNATURE = bytes.fromhex(
    "fffffffffffffffffffffffffffffff000000000000000000000000000000000"
    "7aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1c"
)

EIP712_SAFE_OP_V07 = {
    "types": {
        "EIP712Domain": [
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "SafeOp": [
            {"name": "safe", "type": "address"},
            {"name": "nonce", "type": "uint256"},
            {"name": "initCode", "type": "bytes"},
            {"name": "callData", "type": "bytes"},
            {"name": "verificationGasLimit", "type": "uint128"},
            {"name": "callGasLimit", "type": "uint128"},
            {"name": "preVerificationGas", "type": "uint256"},
            {"name": "maxPriorityFeePerGas", "type": "uint128"},
            {"name": "maxFeePerGas", "type": "uint128"},
            {"name": "paymasterAndData", "type": "bytes"},
            {"name": "validAfter", "type": "uint48"},
            {"name": "validUntil", "type": "uint48"},
            {"name": "entryPoint", "type": "address"},
        ],
    },
    "primaryType": "SafeOp",
}


_UINT48_MAX = 2**48 - 1
_UINT128_MAX = 2**128 - 1
_UINT256_MAX = 2**256 - 1


@dataclass(frozen=True, slots=True)
class UserOperationReceipt:
    user_operation_hash: str
    transaction_hash: str
    success: bool
    raw: dict[str, Any]


class UserOperationOutcomeUnknownError(PolyesterTransportError):
    """A UserOperation was handed to the bundler, but its outcome is unknown.

    ``send_calls`` raises it for any failure once ``eth_sendUserOperation`` was
    attempted: a transport error, a timeout or an HTTP error on the send, or a
    receipt wait that did not end with a receipt. The bundler may hold the
    operation, and it may still execute. :func:`polyester.errors.mutation_outcome_unknown`
    is true and :func:`polyester.errors.is_retryable_error` false.

    ``user_operation_hash`` is the operation's hash. Recover with
    ``wait_for_receipt(error.user_operation_hash)``; never call ``send_calls``
    again for the same calls, which signs a second operation that executes too.
    ``status_code`` and ``retry_after`` are those of the failed answer, when
    there was one, and ``__cause__`` is the underlying failure.
    """

    _outcome_known = False

    def __init__(self, user_operation_hash: str, cause: BaseException) -> None:
        super().__init__(
            f"UserOperation {user_operation_hash} outcome unknown: {cause}; "
            "wait for its receipt instead of sending it again"
        )
        self.user_operation_hash = user_operation_hash
        self.status_code = getattr(cause, "status_code", None)
        self.retry_after = getattr(cause, "retry_after", None)
        self.__cause__ = cause


# The JSON-RPC 2.0 request errors (parse error, invalid request, method not
# found, invalid params) prove any call was refused.
_JSONRPC_REQUEST_REFUSAL_CODES = frozenset({-32700, -32600, -32601, -32602})
# The ERC-7769 rejections prove a refusal of eth_sendUserOperation, the method
# that defines them, only.
_SEND_USER_OPERATION_REFUSAL_CODES = frozenset(
    {-32500, -32501, -32502, -32503, -32504, -32505, -32507, -32508}
)


def _is_jsonrpc_refusal(error: BaseException, method: str) -> bool:
    """Whether ``error`` is a JSON-RPC error answer that proves ``method`` was refused.

    That is a request error for any method, or an ERC-7769 rejection for
    eth_sendUserOperation. An HTTP error, a timeout, a malformed answer, or an
    error object with any other code, such as an internal error (-32603), a
    server error (-32000 to -32099) or an application code, proves nothing
    about the call's outcome.
    """
    if not (
        isinstance(error, JsonRpcError)
        and not isinstance(error, JsonRpcHttpError)
        and type(error.code) is int
    ):
        return False
    return error.code in _JSONRPC_REQUEST_REFUSAL_CODES or (
        method == "eth_sendUserOperation" and error.code in _SEND_USER_OPERATION_REFUSAL_CODES
    )


def _user_operation_hash(
    *,
    environment: PolyesterChainEnvironment,
    sender: str,
    nonce: int,
    init_code: bytes,
    call_data: bytes,
    call_gas_limit: int,
    verification_gas_limit: int,
    pre_verification_gas: int,
    max_fee_per_gas: int,
    max_priority_fee_per_gas: int,
    paymaster_and_data: bytes,
) -> str:
    """EntryPoint v0.7 ``getUserOpHash`` of a UserOperation, as a 0x hex string."""
    packed = encode(
        ["address", "uint256", "bytes32", "bytes32", "bytes32", "uint256", "bytes32", "bytes32"],
        [
            to_checksum_address(sender),
            nonce,
            keccak(init_code),
            keccak(call_data),
            ((verification_gas_limit << 128) | call_gas_limit).to_bytes(32, "big"),
            pre_verification_gas,
            ((max_priority_fee_per_gas << 128) | max_fee_per_gas).to_bytes(32, "big"),
            keccak(paymaster_and_data),
        ],
    )
    entry_point = to_checksum_address(environment.account_abstraction.entry_point.address)
    return to_hex(
        keccak(
            encode(
                ["bytes32", "address", "uint256"],
                [keccak(packed), entry_point, environment.chain_id],
            )
        )
    )


def add_user_operation_gas_buffer(gas: int) -> int:
    percent = (gas * USER_OPERATION_GAS_BUFFER_BPS) // 10_000
    return gas + max(percent, USER_OPERATION_MIN_GAS_BUFFER)


def encode_execute_user_op_call_data(call: ChainCall) -> bytes:
    """Encode Safe4337Module.executeUserOpWithErrorString for a single call."""
    value = exact_integer(call.value, "call.value", min_value=0, max_value=_UINT256_MAX)
    return _EXECUTE_USER_OP_SELECTOR + encode(
        ["address", "uint256", "bytes", "uint8"],
        [bytes.fromhex(call.to[2:] if call.to.startswith("0x") else call.to), value, call.data, 0],
    )


def pack_paymaster_and_data(
    *,
    paymaster: str | None,
    paymaster_verification_gas_limit: int = 0,
    paymaster_post_op_gas_limit: int = 0,
    paymaster_data: bytes = b"",
) -> bytes:
    if not paymaster:
        return b""
    addr = bytes.fromhex(paymaster[2:] if paymaster.startswith("0x") else paymaster)
    verification = exact_integer(
        paymaster_verification_gas_limit,
        "paymaster_verification_gas_limit",
        min_value=0,
        max_value=_UINT128_MAX,
    )
    post_op = exact_integer(
        paymaster_post_op_gas_limit,
        "paymaster_post_op_gas_limit",
        min_value=0,
        max_value=_UINT128_MAX,
    )
    return addr + verification.to_bytes(16, "big") + post_op.to_bytes(16, "big") + paymaster_data


def stub_signature() -> bytes:
    return (0).to_bytes(6, "big") + (0).to_bytes(6, "big") + _STUB_ECDSA_SIGNATURE


def sign_safe_user_operation(
    *,
    owner: Account,
    environment: PolyesterChainEnvironment,
    sender: str,
    nonce: int,
    init_code: bytes,
    call_data: bytes,
    call_gas_limit: int,
    verification_gas_limit: int,
    pre_verification_gas: int,
    max_fee_per_gas: int,
    max_priority_fee_per_gas: int,
    paymaster_and_data: bytes,
    valid_after: int = 0,
    valid_until: int = 0,
) -> bytes:
    """EIP-712 SafeOp signature packed as uint48/uint48/bytes (single EOA owner).

    Every integer is signed exactly as given: a value that is not an exact
    integer in its field's range raises ``PolyesterValidationError`` before
    signing.
    """
    # Ranges are the SafeOp typed-data field types.
    nonce = exact_integer(nonce, "nonce", min_value=0, max_value=_UINT256_MAX)
    pre_verification_gas = exact_integer(
        pre_verification_gas, "pre_verification_gas", min_value=0, max_value=_UINT256_MAX
    )
    call_gas_limit, verification_gas_limit, max_fee_per_gas, max_priority_fee_per_gas = (
        exact_integer(value, name, min_value=0, max_value=_UINT128_MAX)
        for name, value in (
            ("call_gas_limit", call_gas_limit),
            ("verification_gas_limit", verification_gas_limit),
            ("max_fee_per_gas", max_fee_per_gas),
            ("max_priority_fee_per_gas", max_priority_fee_per_gas),
        )
    )
    valid_after = exact_integer(valid_after, "valid_after", min_value=0, max_value=_UINT48_MAX)
    valid_until = exact_integer(valid_until, "valid_until", min_value=0, max_value=_UINT48_MAX)
    module = environment.account_abstraction.safe.safe_4337_module_address
    typed = {
        **EIP712_SAFE_OP_V07,
        "domain": {
            "chainId": environment.chain_id,
            "verifyingContract": to_checksum_address(module),
        },
        "message": {
            "safe": to_checksum_address(sender),
            "nonce": nonce,
            "initCode": init_code,
            "callData": call_data,
            "verificationGasLimit": verification_gas_limit,
            "callGasLimit": call_gas_limit,
            "preVerificationGas": pre_verification_gas,
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "maxFeePerGas": max_fee_per_gas,
            "paymasterAndData": paymaster_and_data,
            "validAfter": valid_after,
            "validUntil": valid_until,
            "entryPoint": to_checksum_address(environment.account_abstraction.entry_point.address),
        },
    }
    signed = owner.sign_message(encode_typed_data(full_message=typed))
    return valid_after.to_bytes(6, "big") + valid_until.to_bytes(6, "big") + bytes(signed.signature)


def _hex_int(value: int) -> str:
    return hex(value)


def _as_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 16) if value.startswith("0x") else int(value)
    raise TypeError(f"cannot convert {type(value)} to int")


class PolyesterSmartAccount:
    """Owner-key smart account: derive Safe, build/sign/submit Funding UserOps."""

    def __init__(
        self,
        *,
        owner_private_key: str,
        environment: PolyesterChainEnvironment | None = None,
        salt_nonce: int = 0,
        timeout: float = 60.0,
    ) -> None:
        key = owner_private_key if owner_private_key.startswith("0x") else f"0x{owner_private_key}"
        self._owner = Account.from_key(key)
        self.environment = environment or POLYESTER_DEVNET_ENVIRONMENT
        self.salt_nonce = salt_nonce
        predicted = predict_safe_address_with_data(
            owners=[self._owner.address],
            salt_nonce=salt_nonce,
            environment=self.environment,
        )
        self.address = predicted.address
        self.owner_address = self._owner.address
        self._initializer = predicted.initializer
        self._factory_calldata = predicted.factory_calldata
        aa = self.environment.account_abstraction
        self._rpc = JsonRpcClient(self.environment.rpc_url, timeout=timeout)
        self._bundler = JsonRpcClient(aa.bundler_url, timeout=timeout)
        self._paymaster = JsonRpcClient(aa.paymaster_url, timeout=timeout)

    def is_deployed(self) -> bool:
        code = self._rpc.request("eth_getCode", [self.address, "latest"])
        return isinstance(code, str) and code not in ("0x", "0x0", "")

    def get_nonce(self, *, key: int | None = None) -> int:
        """Return the next EntryPoint nonce.

        Matches viem/permissionless: when ``key`` is omitted, use a fresh
        timestamp-based nonce key (``Date.now()``) so ops are not stuck on
        key ``0`` (Polyester's bundler rejects some key-0 mempool submissions).
        """
        nonce_key = (
            int(time.time() * 1000)
            if key is None
            else exact_integer(
                key, "nonce key", min_value=0, max_value=(1 << 192) - 1, allow_str=True
            )
        )
        ep = self.environment.account_abstraction.entry_point.address
        data = _GET_NONCE_SELECTOR + encode(
            ["address", "uint192"],
            [bytes.fromhex(self.address[2:]), nonce_key],
        )
        result = self._rpc.request(
            "eth_call",
            [{"to": ep, "data": to_hex(data)}, "latest"],
        )
        return int(result, 16)

    def send_calls(
        self,
        calls: list[ChainCall],
        *,
        wait: bool = True,
        receipt_timeout_s: float = 30.0,
    ) -> UserOperationReceipt | str:
        """Build, sponsor, sign and submit a UserOperation for ``calls``.

        With ``wait`` (the default) it returns the receipt, polling for up to
        ``receipt_timeout_s`` seconds; without it, the operation's hash.

        The operation's hash is computed before sending, and is the hash
        returned or waited on. A JSON-RPC refusal of the send whose code proves
        it (an invalid request or parameters, or an ERC-7769 rejection) raises
        ``JsonRpcError``: nothing was accepted. Any other failure from the send
        on, an answer that does not name that hash included, raises
        :class:`UserOperationOutcomeUnknownError` with the operation's
        ``user_operation_hash``: the bundler may hold the operation, so wait on
        that hash with :meth:`wait_for_receipt` instead of sending again.
        """
        if not calls:
            raise ValueError("at least one call is required")
        if len(calls) != 1:
            raise NotImplementedError(
                "multi-call UserOps are not implemented yet; submit one ChainCall at a time"
            )
        call_data = encode_execute_user_op_call_data(calls[0])
        deployed = self.is_deployed()
        factory = None
        factory_data = None
        init_code = b""
        if not deployed:
            factory = self.environment.account_abstraction.safe.safe_proxy_factory_address
            factory_data = self._factory_calldata
            init_code = bytes.fromhex(factory[2:]) + factory_data

        nonce = self.get_nonce()
        gas_price = self._paymaster.request("pimlico_getUserOperationGasPrice", [])
        fast = gas_price["fast"]
        max_fee = _as_int(fast["maxFeePerGas"])
        max_prio = _as_int(fast["maxPriorityFeePerGas"])

        user_op: dict[str, Any] = {
            "sender": self.address,
            "nonce": _hex_int(nonce),
            "callData": to_hex(call_data),
            "callGasLimit": _hex_int(0),
            "verificationGasLimit": _hex_int(0),
            "preVerificationGas": _hex_int(0),
            "maxFeePerGas": _hex_int(max_fee),
            "maxPriorityFeePerGas": _hex_int(max_prio),
            "signature": to_hex(stub_signature()),
        }
        if factory is not None and factory_data is not None:
            user_op["factory"] = to_checksum_address(factory)
            user_op["factoryData"] = to_hex(factory_data)

        entry_point = self.environment.account_abstraction.entry_point.address

        # Sponsor once for estimates, buffer gas (incl. paymaster), then re-sponsor so
        # paymasterData matches the final limits. Polyester's paymaster often returns
        # paymasterPostOpGasLimit=1; without a floor the bundler accepts then rejects.
        sponsored = self._paymaster.request(
            "pm_sponsorUserOperation",
            [user_op, entry_point],
        )
        call_gas = add_user_operation_gas_buffer(_as_int(sponsored["callGasLimit"]))
        verification_gas = add_user_operation_gas_buffer(_as_int(sponsored["verificationGasLimit"]))
        pre_verification = add_user_operation_gas_buffer(_as_int(sponsored["preVerificationGas"]))
        pm_ver = max(
            add_user_operation_gas_buffer(
                _as_int(sponsored.get("paymasterVerificationGasLimit", 0))
            ),
            USER_OPERATION_MIN_GAS_BUFFER,
        )
        pm_post = max(
            add_user_operation_gas_buffer(_as_int(sponsored.get("paymasterPostOpGasLimit", 0))),
            USER_OPERATION_MIN_GAS_BUFFER * 2,
        )

        buffered_op = {
            **user_op,
            "callGasLimit": _hex_int(call_gas),
            "verificationGasLimit": _hex_int(verification_gas),
            "preVerificationGas": _hex_int(pre_verification),
            "paymasterVerificationGasLimit": _hex_int(pm_ver),
            "paymasterPostOpGasLimit": _hex_int(pm_post),
        }
        sponsored = self._paymaster.request(
            "pm_sponsorUserOperation",
            [buffered_op, entry_point],
        )
        # Keep the exact buffered limits we asked the paymaster to cover. Taking
        # higher sponsor-returned callGas without re-signing paymasterData causes
        # bundler accept-then-reject.
        paymaster = sponsored.get("paymaster")
        pm_data = sponsored.get("paymasterData", "0x")
        if isinstance(pm_data, str):
            pm_data_bytes = bytes.fromhex(pm_data[2:] if pm_data.startswith("0x") else pm_data)
        else:
            pm_data_bytes = b""

        paymaster_and_data = pack_paymaster_and_data(
            paymaster=paymaster,
            paymaster_verification_gas_limit=pm_ver,
            paymaster_post_op_gas_limit=pm_post,
            paymaster_data=pm_data_bytes,
        )
        signature = sign_safe_user_operation(
            owner=self._owner,
            environment=self.environment,
            sender=self.address,
            nonce=nonce,
            init_code=init_code,
            call_data=call_data,
            call_gas_limit=call_gas,
            verification_gas_limit=verification_gas,
            pre_verification_gas=pre_verification,
            max_fee_per_gas=max_fee,
            max_priority_fee_per_gas=max_prio,
            paymaster_and_data=paymaster_and_data,
        )

        final_op: dict[str, Any] = {
            "sender": self.address,
            "nonce": _hex_int(nonce),
            "callData": to_hex(call_data),
            "callGasLimit": _hex_int(call_gas),
            "verificationGasLimit": _hex_int(verification_gas),
            "preVerificationGas": _hex_int(pre_verification),
            "maxFeePerGas": _hex_int(max_fee),
            "maxPriorityFeePerGas": _hex_int(max_prio),
            "signature": to_hex(signature),
        }
        if factory is not None and factory_data is not None:
            final_op["factory"] = to_checksum_address(factory)
            final_op["factoryData"] = to_hex(factory_data)
        if paymaster:
            final_op["paymaster"] = to_checksum_address(paymaster)
            final_op["paymasterVerificationGasLimit"] = _hex_int(pm_ver)
            final_op["paymasterPostOpGasLimit"] = _hex_int(pm_post)
            final_op["paymasterData"] = to_hex(pm_data_bytes)

        # The hash is known before sending: once the send is attempted, every
        # failure names it, so the caller waits on it instead of signing again.
        user_op_hash = _user_operation_hash(
            environment=self.environment,
            sender=self.address,
            nonce=nonce,
            init_code=init_code,
            call_data=call_data,
            call_gas_limit=call_gas,
            verification_gas_limit=verification_gas,
            pre_verification_gas=pre_verification,
            max_fee_per_gas=max_fee,
            max_priority_fee_per_gas=max_prio,
            paymaster_and_data=paymaster_and_data,
        )
        try:
            accepted = self._bundler.request(
                "eth_sendUserOperation",
                [final_op, entry_point],
            )
        except Exception as exc:
            if _is_jsonrpc_refusal(exc, "eth_sendUserOperation"):
                raise  # The bundler refused it: nothing was accepted.
            raise UserOperationOutcomeUnknownError(user_op_hash, exc) from exc
        # The computed hash is the operation's identity: an answer that names
        # another one (or none) does not say what the bundler holds.
        if not isinstance(accepted, str) or accepted.lower() != user_op_hash.lower():
            raise UserOperationOutcomeUnknownError(
                user_op_hash,
                JsonRpcError(
                    "eth_sendUserOperation answered "
                    f"{accepted!r:.80}, not the operation's hash {user_op_hash}"
                ),
            )
        if not wait:
            return user_op_hash
        try:
            return self.wait_for_receipt(user_op_hash, timeout_s=receipt_timeout_s)
        except Exception as exc:
            raise UserOperationOutcomeUnknownError(user_op_hash, exc) from exc

    def wait_for_receipt(
        self,
        user_operation_hash: str,
        *,
        timeout_s: float = 30.0,
        poll_interval_s: float = 1.0,
    ) -> UserOperationReceipt:
        """Poll the bundler for a UserOperation's receipt until ``timeout_s`` passes.

        ``timeout_s`` bounds the whole wait: every request and every pause ends
        by then. A poll that fails without a JSON-RPC refusal (an HTTP error
        such as 503, a timeout or a transport error) is retried until the
        deadline. Raises ``TimeoutError`` at the deadline, from the last failed
        poll if any, and ``RuntimeError`` when the bundler reports the operation
        rejected. A failed wait means no receipt was read in time, not that the
        operation will not execute.
        """
        deadline = time.monotonic() + timeout_s
        last_error: Exception | None = None

        def remaining() -> float:
            return deadline - time.monotonic()

        def pause() -> None:
            time.sleep(max(0.0, min(poll_interval_s, remaining())))

        while remaining() > 0:
            try:
                raw = self._bundler.request(
                    "eth_getUserOperationReceipt",
                    [user_operation_hash],
                    timeout=remaining(),
                )
            except Exception as exc:
                if _is_jsonrpc_refusal(exc, "eth_getUserOperationReceipt"):
                    raise
                last_error = exc
                pause()
                continue
            last_error = None
            if raw:
                receipt = raw.get("receipt") or {}
                success = bool(raw.get("success", receipt.get("status") in (1, "0x1", "0x01")))
                tx_hash = receipt.get("transactionHash") or raw.get("transactionHash") or ""
                return UserOperationReceipt(
                    user_operation_hash=user_operation_hash,
                    transaction_hash=str(tx_hash),
                    success=success,
                    raw=raw,
                )
            if remaining() <= 0:
                break
            try:
                status = self._bundler.request(
                    "pimlico_getUserOperationStatus",
                    [user_operation_hash],
                    timeout=remaining(),
                )
            except Exception:
                status = None
            if isinstance(status, dict) and status.get("status") == "rejected":
                raise RuntimeError(
                    f"bundler rejected UserOperation {user_operation_hash}: {status}"
                )
            pause()
        raise TimeoutError(
            f"timed out waiting for UserOperation receipt {user_operation_hash}"
        ) from last_error
