"""Batch rejection details, unresolved cancel IDs, TWAP fire prices and sell caps.

POLY-8960: each rejected batch item keeps the server's field violations.
POLY-8920: a rejected batch cancel that resolved no order keeps its ID empty.
POLY-8959: a TWAP slice sent without a fire price keeps it absent.
POLY-8961: a sell TWAP market slice takes at most 9999 bps; a buy, 10000.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import msgspec
import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.realtime_decode import decode_trigger_event_batch_bytes
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import ClientOrderId, OrderId
from polyester.services.orders import AsyncOrdersService
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary

TICK_FIELD = "order.attached_risk.take_profit.trigger_price_ticks"
TICK_MESSAGE = "Take-profit trigger price must be a multiple of the tick size."
QTY_FIELD = "order.base_qty_scaled"
QTY_MESSAGE = "Quantity is below the minimum."


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return catalogs


def _tick_violation() -> list[orders_pb2.FieldViolation]:
    return [
        orders_pb2.FieldViolation(field_path=TICK_FIELD, rule_id="tick_size", message=TICK_MESSAGE)
    ]


def _qty_violation() -> list[orders_pb2.FieldViolation]:
    return [orders_pb2.FieldViolation(field_path=QTY_FIELD, rule_id="minimum", message=QTY_MESSAGE)]


def _violations(field: str, rule: str, message: str) -> list[dict[str, str]]:
    return [{"field_path": field, "rule_id": rule, "message": message}]


def _public(item: Any) -> dict[str, Any]:
    builtins = msgspec.to_builtins(item)
    assert isinstance(builtins, dict)
    return builtins


@pytest.mark.asyncio
async def test_batch_create_keeps_each_rejections_field_violations() -> None:
    capture = CaptureUnary(
        orders_pb2.BatchCreateOrdersResponse(
            results=[
                orders_pb2.BatchCreateResultItem(
                    client_order_id="passive",
                    accepted=orders_pb2.BatchCreateAccepted(order_id=42),
                ),
                orders_pb2.BatchCreateResultItem(
                    client_order_id="off-tick",
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(
                            code=orders_pb2.ERROR_CODE_PRICE_TICK_SIZE,
                            violations=_tick_violation(),
                        )
                    ),
                ),
                orders_pb2.BatchCreateResultItem(
                    client_order_id="tiny",
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(
                            code=orders_pb2.ERROR_CODE_MIN_QTY, violations=_qty_violation()
                        )
                    ),
                ),
                orders_pb2.BatchCreateResultItem(
                    client_order_id="plain",
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_BAD_PRICE)
                    ),
                ),
            ],
            accepted_count=1,
            rejected_count=3,
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    items: list[Any] = [
        {
            "symbol": "BTC-USDT",
            "side": "buy",
            "order_type": "limit",
            "qty": "0.001",
            "price": "100",
            "client_order_id": cid,
        }
        for cid in ("passive", "off-tick", "tiny", "plain")
    ]
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        result = await service.batch_create(items=items, allow_partial=True)

    assert capture.calls == 1
    assert (result.accepted_count, result.rejected_count) == (1, 3)
    assert [_public(item) for item in result.results] == [
        {"status": "accepted", "order_id": format_id(42), "client_order_id": "passive"},
        {
            "status": "rejected",
            "client_order_id": "off-tick",
            "code": "error_code_price_tick_size",
            "violations": _violations(TICK_FIELD, "tick_size", TICK_MESSAGE),
        },
        {
            "status": "rejected",
            "client_order_id": "tiny",
            "code": "error_code_min_qty",
            "violations": _violations(QTY_FIELD, "minimum", QTY_MESSAGE),
        },
        {"status": "rejected", "client_order_id": "plain", "code": "error_code_bad_price"},
    ]


@pytest.mark.asyncio
async def test_batch_cancel_and_replace_keep_each_rejections_field_violations() -> None:
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    cancel = CaptureUnary(
        orders_pb2.BatchCancelOrdersResponse(
            results=[
                orders_pb2.BatchCancelResultItem(
                    status=orders_pb2.BatchCancelResultItem.ACCEPTED, order_id=42
                ),
                orders_pb2.BatchCancelResultItem(
                    status=orders_pb2.BatchCancelResultItem.REJECTED,
                    order_id=45,
                    code="INVALID_ARGUMENT",
                    error=orders_pb2.ErrorDetail(
                        code=orders_pb2.ERROR_CODE_MIN_QTY, violations=_qty_violation()
                    ),
                ),
            ],
            accepted_count=1,
            rejected_count=1,
        )
    )
    with patch("polyester.services.orders.unary_auth_decoded", cancel):
        canceled = await service.batch_cancel(
            items=[{"key": OrderId(format_id(42))}, {"key": OrderId(format_id(45))}]
        )
    assert [_public(item) for item in canceled.results] == [
        {"status": "accepted", "order_id": format_id(42)},
        {
            "status": "rejected",
            "order_id": format_id(45),
            "code": "INVALID_ARGUMENT",
            "violations": _violations(QTY_FIELD, "minimum", QTY_MESSAGE),
        },
    ]

    replace = CaptureUnary(
        orders_pb2.BatchReplaceOrdersResponse(
            batch_request_id=9,
            status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED,
            results=[
                orders_pb2.BatchReplaceAdmissionItem(
                    item_index=0,
                    status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                    old_order_id=42,
                    replacement_order_id=43,
                    action_taken=orders_pb2.REPLACED,
                ),
                orders_pb2.BatchReplaceAdmissionItem(
                    item_index=1,
                    status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED,
                    old_order_id=44,
                    code="PRICE_TICK_SIZE",
                    error=orders_pb2.ErrorDetail(
                        code=orders_pb2.ERROR_CODE_PRICE_TICK_SIZE, violations=_tick_violation()
                    ),
                ),
            ],
            accepted_count=1,
            rejected_count=1,
        )
    )
    with patch("polyester.services.orders.unary_auth_decoded", replace):
        replaced = await service.batch_replace(
            symbol="BTC-USDT",
            items=[
                {"key": OrderId(format_id(42)), "new_price": "101"},
                {"key": OrderId(format_id(44)), "new_price": "101"},
            ],
        )
    admitted, rejected = replaced.results
    assert _public(admitted).get("violations") is None
    assert _public(rejected)["violations"] == _violations(TICK_FIELD, "tick_size", TICK_MESSAGE)
    assert (rejected.old_order_id, rejected.code) == (format_id(44), "PRICE_TICK_SIZE")


@pytest.mark.asyncio
async def test_batch_cancel_keeps_an_unresolved_order_id_empty() -> None:
    capture = CaptureUnary(
        orders_pb2.BatchCancelOrdersResponse(
            results=[
                orders_pb2.BatchCancelResultItem(
                    status=orders_pb2.BatchCancelResultItem.ACCEPTED, order_id=42
                ),
                orders_pb2.BatchCancelResultItem(
                    status=orders_pb2.BatchCancelResultItem.REJECTED,
                    client_order_id="missing",
                    code="ORDER_UNKNOWN",
                ),
                orders_pb2.BatchCancelResultItem(
                    status=orders_pb2.BatchCancelResultItem.REJECTED,
                    order_id=77,
                    code="ORDER_NOT_OPEN",
                ),
            ],
            accepted_count=1,
            rejected_count=2,
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        result = await service.batch_cancel(
            items=[
                {"key": OrderId(format_id(42))},
                {"key": ClientOrderId("missing")},
                {"key": OrderId(format_id(77))},
            ]
        )
    assert [item.order_id for item in result.results] == [format_id(42), "", format_id(77)]
    assert (result.results[1].client_order_id, result.results[1].code) == (
        "missing",
        "ORDER_UNKNOWN",
    )


def _scheduled_slices() -> list[triggers_pb2.TriggerEvent]:
    return [
        triggers_pb2.TriggerEvent(
            trigger_id=9,
            trigger_type=triggers_pb2.TWAP,
            event_type=triggers_pb2.EVENT_FIRED,
            child_seq=1,
            child_order_id=101,
        ),
        triggers_pb2.TriggerEvent(
            trigger_id=9,
            trigger_type=triggers_pb2.TWAP,
            event_type=triggers_pb2.EVENT_FIRED,
            child_seq=2,
            child_order_id=102,
            fire_price_ticks=123,
        ),
    ]


@pytest.mark.asyncio
async def test_list_events_and_stream_keep_an_absent_fire_price_absent() -> None:
    capture = CaptureUnary(triggers_pb2.ListTriggerEventsResponse(events=_scheduled_slices()))
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.triggers.unary_auth_decoded_retry_unavailable", capture):
        listed = (await service.list_events(trigger_id=format_id(9))).events
    streamed = decode_trigger_event_batch_bytes(
        triggers_pb2.TriggerEventBatch(events=_scheduled_slices()).SerializeToString()
    )
    for events in (listed, streamed):
        scheduled, priced = events
        assert scheduled.child_order_id == format_id(101)
        assert scheduled.fire_price is None
        assert priced.fire_price is not None and priced.fire_price.ticks == 123


@pytest.mark.parametrize(
    ("side", "bps", "refusal"),
    [
        ("buy", 50, None),
        ("buy", 9_999, None),
        ("buy", 10_000, None),
        ("buy", 10_001, "between 1 and"),
        ("sell", 50, None),
        ("sell", 9_999, None),
        ("sell", 10_000, "between 1 and 9999"),
        ("sell", 10_001, "between 1 and"),
    ],
)
@pytest.mark.asyncio
async def test_twap_market_slippage_caps_by_side(side: str, bps: int, refusal: str | None) -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=9))
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)

    async def create() -> None:
        await service.create(
            symbol="BTC-USDT",
            trigger_type="twap",
            side=side,
            qty="0.00036",
            twap_duration_ms=60_000,
            twap_slice_interval_ms=30_000,
            max_slippage_bps=bps,
        )

    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        if refusal is None:
            await create()
            assert capture.calls == 1
            assert capture.request is not None
            assert capture.request.trigger.twap.market_ioc.max_slippage_bps == bps  # type: ignore[attr-defined]
        else:
            with pytest.raises(PolyesterValidationError, match=refusal):
                await create()
            assert capture.calls == 0
