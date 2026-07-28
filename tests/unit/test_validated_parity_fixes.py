from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester import (
    AssetAmount,
    PolyesterResponseContractError,
    PolyesterValidationError,
    Price,
    Quantity,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.auth import ApiKeyCredentials
from polyester.codecs.decode.internal_transfers import internal_transfer_from_proto
from polyester.codecs.decode.orders import (
    batch_create_from_proto,
    cancel_all_from_proto,
    modify_order_from_proto,
    order_mutation_from_proto,
)
from polyester.codecs.decode.withdraw import withdraw_intent_from_proto
from polyester.codecs.orders import risk_policy_from_dict
from polyester.codecs.withdraw import str_to_u128_proto, trading_withdraw_payload_to_proto
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.models import OrderId
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription
from polyester.services.internal_transfers import AsyncInternalTransfersService
from polyester.services.orders import AsyncOrdersService
from polyester.services.withdraw import AsyncWithdrawService, PreparedTradingWithdraw


def _u128(value) -> int:
    return (value.hi << 64) | value.lo


def test_api_key_prepared_withdraw_signs_exact_deterministic_payload() -> None:
    private = bytes(range(32))
    credentials = ApiKeyCredentials("ak_test", private)
    service = AsyncWithdrawService(SimpleNamespace(credentials=credentials), None)

    prepared = service.prepare_api_key_to_funding(
        asset_id=7,
        quantity=AssetAmount.from_scaled(125, scale=2),
        amount_scale=2,
        idempotency_key="wd-stable",
        deadline_ts_sec=1234,
        nonce=99,
    )

    restored = PreparedTradingWithdraw.from_request_bytes(prepared.request_bytes)
    assert restored == prepared
    assert "signature" not in repr(restored)
    assert repr(restored) == "PreparedTradingWithdraw()"
    assert _u128(restored._request().payload.amount_e18) == 1_250_000_000_000_000_000
    Ed25519PrivateKey.from_private_bytes(private).public_key().verify(
        restored.payload_signature,
        restored.deterministic_payload_bytes,
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request: request.ClearField("payload"),
        lambda request: setattr(request, "payload_signature", b""),
        lambda request: setattr(request.payload, "deadline_ts_sec", 0),
        lambda request: setattr(request.payload, "action", withdraw_pb2.ACTION_UNSPECIFIED),
    ],
)
def test_restored_prepared_withdraw_validates_invariants(mutate) -> None:
    request = withdraw_pb2.CreateTradingWithdrawRequest(
        payload=trading_withdraw_payload_to_proto(
            action="to_funding",
            asset_id=7,
            amount="1",
            idempotency_key="wd",
            deadline_ts_sec=123,
            nonce=9,
        ),
        payload_signature=b"signature",
    )
    mutate(request)
    with pytest.raises(PolyesterValidationError):
        PreparedTradingWithdraw.from_request_bytes(
            request.SerializeToString(deterministic=True)
        )


def test_precomputed_withdraw_requires_explicit_deadline() -> None:
    service = AsyncWithdrawService(None, None)
    with pytest.raises(PolyesterValidationError, match="precomputed"):
        asyncio.run(
            service.create_to_funding(
                asset_id=7,
                quantity="1",
                payload_signature=b"sig",
                idempotency_key="wd",
                nonce=1,
            )
        )


def test_unknown_withdraw_action_is_validation_error() -> None:
    with pytest.raises(PolyesterValidationError, match="unknown"):
        trading_withdraw_payload_to_proto(
            action="future_action",
            asset_id=7,
            amount="1",
            idempotency_key="wd",
            deadline_ts_sec=1,
            nonce=1,
        )


def test_amount_e18_exact_rescaling_and_downscale_rejection() -> None:
    assert _u128(
        str_to_u128_proto(AssetAmount.from_scaled(125, scale=2), scale=2)
    ) == 1_250_000_000_000_000_000
    with pytest.raises(PolyesterValidationError, match="exactly"):
        str_to_u128_proto(
            AssetAmount.from_scaled(1, scale=19),
            scale=19,
        )


@pytest.mark.asyncio
async def test_internal_transfer_rescales_declared_input_scale(monkeypatch) -> None:
    captured = {}

    async def fake_unary(_transport, _client, _invoke, request, _decode):
        captured["request"] = request
        return SimpleNamespace()

    monkeypatch.setattr(
        "polyester.services.internal_transfers.unary_auth_decoded", fake_unary
    )
    service = AsyncInternalTransfersService(None, SimpleNamespace(), None)
    await service.create(
        asset_id=7,
        quantity=AssetAmount.from_scaled(125, scale=2),
        quantity_scale=2,
        destination_account_id="2",
        idempotency_key="xfer",
    )
    assert _u128(captured["request"].amount_e18) == 1_250_000_000_000_000_000


def test_response_contract_classification_and_required_entities() -> None:
    error = PolyesterResponseContractError("Mutation", "missing id")
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    with pytest.raises(PolyesterResponseContractError):
        withdraw_intent_from_proto(withdraw_pb2.CreateTradingWithdrawResponse())
    with pytest.raises(PolyesterResponseContractError):
        internal_transfer_from_proto(
            internal_transfer_pb2.CreateInternalTransferResponse()
        )
    with pytest.raises(PolyesterResponseContractError):
        order_mutation_from_proto(orders_pb2.CreateOrderResponse())
    with pytest.raises(PolyesterResponseContractError):
        order_mutation_from_proto(orders_pb2.CancelOrderResponse())
    with pytest.raises(PolyesterResponseContractError):
        modify_order_from_proto(orders_pb2.ModifyOrderResponse())
    with pytest.raises(PolyesterResponseContractError):
        batch_create_from_proto(
            orders_pb2.BatchCreateOrdersResponse(
                results=[orders_pb2.BatchCreateResultItem(client_order_id="missing")]
            )
        )
    with pytest.raises(PolyesterResponseContractError):
        cancel_all_from_proto(
            orders_pb2.CancelAllOrdersResponse(
                status="submitted",
                matched_orders=2,
                submitted_cancels=1,
            )
        )


@pytest.mark.asyncio
async def test_cancel_symbol_routing_rejects_both_and_unknown() -> None:
    service = AsyncOrdersService(None, SimpleNamespace(symbol_id_for_symbol=lambda _s: None), None)
    with pytest.raises(PolyesterValidationError, match="only one"):
        await service.cancel(key=OrderId(1), symbol="BTC-USDT", symbol_id=7)
    with pytest.raises(PolyesterValidationError, match="Unknown symbol"):
        await service.cancel(key=OrderId(1), symbol="UNKNOWN")


@pytest.mark.asyncio
async def test_cancel_requires_typed_order_key() -> None:
    service = AsyncOrdersService(None, SimpleNamespace(symbol_id_for_symbol=lambda _s: 1), None)
    with pytest.raises(TypeError):
        await service.cancel()
    with pytest.raises(PolyesterValidationError, match="OrderKey"):
        await service.cancel(key="not-a-key")  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError, match="non-empty OrderId"):
        await service.cancel(key=OrderId(""))


def test_attached_risk_rejects_dead_trigger_price_source() -> None:
    with pytest.raises(PolyesterValidationError, match="always uses last trade"):
        risk_policy_from_dict(
            {
                "take_profit": {
                    "trigger_price_source": "mark",
                    "trigger_price_ticks": 10,
                }
            }
        )


def test_money_scalars_remain_frozen_and_slotted() -> None:
    values = [
        Price.from_ticks(1),
        Quantity.from_scaled(1, scale=0),
        AssetAmount.from_scaled(1, scale=0),
    ]
    for value in values:
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, next(iter(value.__dataclass_fields__)), 2)


@pytest.mark.asyncio
async def test_post_take_publication_is_drained_before_ready() -> None:
    live: list[bytes] = []
    stream = None

    def apply_snapshot(_snapshot: str, pending: list[bytes]) -> None:
        assert pending == [b"before"]
        assert stream is not None
        stream._handle_publication(b"after-take")

    stream = AsyncSnapshotThenStreamSubscription(
        realtime=SimpleNamespace(),
        channel="public:test",
        decode=lambda value: value,
        fetch_snapshot=lambda: asyncio.sleep(0, result="snapshot"),
        read_publication=lambda value: [value],
        apply_snapshot=apply_snapshot,
        apply_live_publications=live.extend,
    )
    stream._handle_publication(b"before")
    assert await stream.refresh_snapshot()
    assert stream.is_ready()
    assert live == [b"after-take"]


@pytest.mark.asyncio
async def test_requested_refresh_is_single_flight_and_coalesced() -> None:
    fetches = 0

    async def fetch_snapshot() -> str:
        nonlocal fetches
        fetches += 1
        await asyncio.sleep(0)
        return "snapshot"

    stream = AsyncSnapshotThenStreamSubscription(
        realtime=SimpleNamespace(),
        channel="public:test",
        decode=lambda value: value,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda value: [value],
        apply_snapshot=lambda _snapshot, _pending: None,
        apply_live_publications=lambda _pending: None,
    )
    for _ in range(20):
        stream.request_refresh()
    assert stream._request_refresh_task is not None
    await stream._request_refresh_task
    assert fetches == 1
    assert stream.is_ready()


@pytest.mark.asyncio
async def test_requested_refresh_fails_closed_after_bounded_retries(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "polyester.realtime.snapshot_then_stream._REQUEST_REFRESH_INITIAL_BACKOFF",
        0.001,
    )
    monkeypatch.setattr(
        "polyester.realtime.snapshot_then_stream._REQUEST_REFRESH_MAX_BACKOFF",
        0.002,
    )
    fetches = 0

    async def fetch_snapshot() -> str:
        nonlocal fetches
        fetches += 1
        raise RuntimeError("snapshot unavailable")

    stream = AsyncSnapshotThenStreamSubscription(
        realtime=SimpleNamespace(),
        channel="public:test",
        decode=lambda value: value,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda value: [value],
        apply_snapshot=lambda _snapshot, _pending: None,
        apply_live_publications=lambda _pending: None,
    )
    stream.request_refresh()
    assert stream._request_refresh_task is not None
    await stream._request_refresh_task
    assert fetches == 4
    assert stream.is_disposed()
    assert not stream.is_ready()
    assert stream.last_error is not None

