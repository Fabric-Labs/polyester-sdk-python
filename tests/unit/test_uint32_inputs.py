"""A cancel-all-after timeout or a guard chain ID outside the wire uint32 is
refused before transport, never wrapped (4294967296 would send 0, which
disables the dead-man switch)."""

from __future__ import annotations

from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.gen.chain.guard.v1 import guard_signer_pb2
from polyester.gen.orders.v1 import orders_pb2
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

REQUESTS: dict[str, Any] = {
    "CancelAllAfter": orders_pb2.CancelAllAfterRequest,
    "SignProtectedAction": guard_signer_pb2.SignProtectedActionRequest,
    "BatchSignProtectedActions": guard_signer_pb2.BatchSignProtectedActionsRequest,
}
ADDRESS = "0x0000000000000000000000000000000000000001"
OUT_OF_RANGE = [-1, 2**32, 2**32 + 1, 2**32 + 10, 2**63]


async def _run(call) -> tuple[BaseException | None, list[tuple[str, Any]]]:
    seen: list[tuple[str, Any]] = []

    async def handler(req: ParsedRequest):
        rpc = req.path.rsplit("/", 1)[-1]
        seen.append((rpc, REQUESTS[rpc].FromString(req.body)))
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    error: BaseException | None = None
    try:
        await call(client)
    except Exception as exc:
        error = exc
    finally:
        await client.aclose()
        await http.aclose()
    return error, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_sec", OUT_OF_RANGE + [10.5, True])
async def test_cancel_all_after_refuses_timeouts_outside_uint32(timeout_sec: Any) -> None:
    error, seen = await _run(lambda c: c.orders.cancel_all_after(timeout_sec=timeout_sec))
    assert isinstance(error, ValueError | TypeError), error
    assert seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_sec", [0, 10, 120, 2**32 - 1])
async def test_cancel_all_after_sends_timeouts_unchanged(timeout_sec: int) -> None:
    _, seen = await _run(lambda c: c.orders.cancel_all_after(timeout_sec=timeout_sec))
    assert [(rpc, req.timeout_sec) for rpc, req in seen] == [("CancelAllAfter", timeout_sec)]


@pytest.mark.asyncio
@pytest.mark.parametrize("chain_id", OUT_OF_RANGE + [1.5, 137.0, "137", True])
async def test_guard_signing_refuses_chain_ids_outside_uint32(chain_id: Any) -> None:
    single, single_seen = await _run(
        lambda c: c.guard_signer.sign_protected_action(
            action="funding_add_external_whitelist",
            external_polychain_chain_id=chain_id,
            external_addresses=[ADDRESS],
        )
    )
    batch, batch_seen = await _run(
        lambda c: c.guard_signer.batch_sign_protected_actions(
            actions=[
                {
                    "action": "funding_add_external_whitelist",
                    "external_polychain_chain_id": chain_id,
                    "external_addresses": [ADDRESS],
                }
            ]
        )
    )
    assert isinstance(single, ValueError | TypeError), single
    assert isinstance(batch, ValueError | TypeError), batch
    assert single_seen == [] and batch_seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("chain_id", [137, 2**32 - 1])
async def test_guard_signing_sends_chain_ids_unchanged(chain_id: int) -> None:
    _, seen = await _run(
        lambda c: c.guard_signer.batch_sign_protected_actions(
            actions=[
                {
                    "action": "funding_add_external_whitelist",
                    "external_polychain_chain_id": chain_id,
                    "external_addresses": [ADDRESS],
                }
            ]
        )
    )
    [(_, req)] = seen
    assert req.actions[0].args.external_whitelist.polychain_chain_id == chain_id
