"""A Price or Quantity bound to another market is refused wherever the market is known."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import AttachedRisk, OrderId, RiskLeg
from polyester.services.orders import AsyncOrdersService
from polyester.services.triggers import AsyncTriggersService
from polyester.types.money import Price, Quantity
from tests.unit.support import CaptureUnary

SOL_PRICE = Price.from_ticks(46_000_000_000_000, symbol="SOL-USDT")
BTC_PRICE = Price.from_ticks(47_000_000_000_000, symbol="BTC-USDT")
SOL_QTY = Quantity.from_scaled(20_000, scale=8, symbol="SOL-USDT")


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
                {
                    "symbol": "SOL-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
            ]
        }
    )
    return catalogs


def _triggers() -> AsyncTriggersService:
    return AsyncTriggersService(MagicMock(), _catalogs(), None)


def _orders() -> AsyncOrdersService:
    return AsyncOrdersService(MagicMock(), _catalogs(), None)


async def _refused(
    module: str, response: Any, call: Callable[[], Awaitable[object]], match: str
) -> None:
    capture = CaptureUnary(response)
    with (
        patch(f"{module}.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match=match),
    ):
        await call()
    assert capture.calls == 0


async def _sent(module: str, response: Any, call: Callable[[], Awaitable[object]]) -> Any:
    capture = CaptureUnary(response)
    with patch(f"{module}.unary_auth_decoded", capture):
        await call()
    assert capture.calls == 1
    return capture.request


TRIGGERS = "polyester.services.triggers"
ORDERS = "polyester.services.orders"
MODIFIED = triggers_pb2.ModifyTriggerResponse(trigger_id=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["trigger_price", "activation_price"])
@pytest.mark.parametrize(
    "selector", [{"symbol": "BTC-USDT"}, {"symbol_id": 1}], ids=["symbol", "symbol_id"]
)
async def test_trigger_modify_refuses_a_price_for_another_market(
    field: str, selector: dict[str, Any]
) -> None:
    service = _triggers()
    await _refused(
        TRIGGERS,
        MODIFIED,
        lambda: service.modify(trigger_id=5, **selector, **{field: SOL_PRICE}),
        "price symbol mismatch: value is for SOL-USDT, destination is BTC-USDT",
    )


@pytest.mark.asyncio
async def test_trigger_modify_keeps_a_price_for_its_market() -> None:
    service = _triggers()
    request = await _sent(
        TRIGGERS,
        MODIFIED,
        lambda: service.modify(trigger_id=5, symbol="BTC-USDT", trigger_price=BTC_PRICE),  # type: ignore[arg-type]
    )
    assert request.trigger_price_ticks == BTC_PRICE.ticks
    assert request.symbol_id == 1


@pytest.mark.asyncio
async def test_trigger_modify_without_a_market_sends_the_price() -> None:
    # No symbol or symbol_id: the trigger's own market is not known here.
    service = _triggers()
    request = await _sent(
        TRIGGERS,
        MODIFIED,
        lambda: service.modify(trigger_id=5, trigger_price=SOL_PRICE),  # type: ignore[arg-type]
    )
    assert request.trigger_price_ticks == SOL_PRICE.ticks
    assert request.symbol_id == 0


def _sol_only_catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "SOL-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    return catalogs


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["trigger_price", "activation_price"])
@pytest.mark.parametrize("price", [SOL_PRICE, BTC_PRICE], ids=["sol_bound", "btc_bound"])
@pytest.mark.parametrize(
    "catalogs", [_sol_only_catalogs, lambda: None], ids=["missing_market", "no_catalogs"]
)
async def test_trigger_modify_refuses_a_bound_price_it_cannot_check(
    field: str, price: Price, catalogs: Callable[[], CatalogManager | None]
) -> None:
    # symbol_id 1 is not in the catalogs, so its name is unknown and a bound
    # price can't be checked against it.
    service = AsyncTriggersService(MagicMock(), catalogs(), None)  # type: ignore[arg-type]
    await _refused(
        TRIGGERS,
        MODIFIED,
        lambda: service.modify(trigger_id=5, symbol_id=1, **{field: price}),
        "cannot check a price bound to",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["trigger_price", "activation_price"])
@pytest.mark.parametrize(
    "catalogs", [_sol_only_catalogs, lambda: None], ids=["missing_market", "no_catalogs"]
)
async def test_trigger_modify_sends_an_unbound_price_for_an_unknown_market(
    field: str, catalogs: Callable[[], CatalogManager | None]
) -> None:
    service = AsyncTriggersService(MagicMock(), catalogs(), None)  # type: ignore[arg-type]
    unbound = Price.from_ticks(46_000_000_000_000)
    request = await _sent(
        TRIGGERS, MODIFIED, lambda: service.modify(trigger_id=5, symbol_id=1, **{field: unbound})
    )
    assert request.symbol_id == 1
    assert getattr(request, f"{field}_ticks") == unbound.ticks


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["trigger_price", "activation_price"])
async def test_trigger_modify_keeps_a_bound_price_for_its_market_by_id(field: str) -> None:
    service = _triggers()
    request = await _sent(
        TRIGGERS, MODIFIED, lambda: service.modify(trigger_id=5, symbol_id=1, **{field: BTC_PRICE})
    )
    assert request.symbol_id == 1
    assert getattr(request, f"{field}_ticks") == BTC_PRICE.ticks


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["trigger_price", "activation_price", "limit_price"])
async def test_trigger_create_refuses_a_price_for_another_market(field: str) -> None:
    service = _triggers()
    params: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "side": "sell",
        "qty": "0.0002",
        "trigger_type": "stop_loss",
        "trigger_price": "45000",
    }
    if field == "activation_price":
        params.update(trigger_type="trailing_stop", trigger_price=None, trailing_distance_bps=50)
    if field == "limit_price":
        params.update(order_type="limit")
    params[field] = SOL_PRICE
    await _refused(
        TRIGGERS,
        triggers_pb2.CreateTriggerResponse(trigger_id=5),
        lambda: service.create(**params),
        "price symbol mismatch",
    )


@pytest.mark.asyncio
async def test_trigger_create_refuses_a_quantity_for_another_market() -> None:
    service = _triggers()
    await _refused(
        TRIGGERS,
        triggers_pb2.CreateTriggerResponse(trigger_id=5),
        lambda: service.create(
            symbol="BTC-USDT",
            side="sell",
            qty=SOL_QTY,  # type: ignore[arg-type]
            trigger_type="stop_loss",
            trigger_price="45000",
        ),
        "quantity symbol mismatch",
    )


def _create_params(selector: dict[str, Any], **changes: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        **selector,
        "side": "buy",
        "order_type": "limit",
        "tif": "gtc",
        "qty": "0.0002",
        "price": "45000",
    }
    params.update(changes)
    return params


CREATE_CASES = [
    pytest.param({"price": SOL_PRICE}, "price symbol mismatch", id="price"),
    pytest.param({"qty": SOL_QTY}, "quantity symbol mismatch", id="qty"),
    pytest.param(
        {"attached_risk": AttachedRisk(stop_loss=RiskLeg(trigger_price=SOL_PRICE))},
        "price symbol mismatch",
        id="attached_risk",
    ),
]
SELECTORS = [
    pytest.param({"symbol": "BTC-USDT"}, id="symbol"),
    pytest.param({"symbol_id": 1}, id="symbol_id"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", SELECTORS)
@pytest.mark.parametrize(("changes", "match"), CREATE_CASES)
async def test_order_create_refuses_values_for_another_market(
    selector: dict[str, Any], changes: dict[str, Any], match: str
) -> None:
    service = _orders()
    params = _create_params(selector, **changes)
    await _refused(
        ORDERS,
        orders_pb2.CreateOrderResponse(order_id=42),
        lambda: service.create(**params),
        match,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", SELECTORS)
@pytest.mark.parametrize(("changes", "match"), CREATE_CASES)
async def test_order_preview_refuses_values_for_another_market(
    selector: dict[str, Any], changes: dict[str, Any], match: str
) -> None:
    service = _orders()
    params = _create_params(selector, **changes)
    await _refused(
        ORDERS,
        orders_pb2.PreviewOrderResponse(),
        lambda: service.preview_order(**params),
        match,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", SELECTORS)
@pytest.mark.parametrize(("changes", "match"), CREATE_CASES)
async def test_batch_create_refuses_values_for_another_market(
    selector: dict[str, Any], changes: dict[str, Any], match: str
) -> None:
    service = _orders()
    items = [_create_params(selector, **changes)]
    await _refused(
        ORDERS,
        orders_pb2.BatchCreateOrdersResponse(),
        lambda: service.batch_create(items=items),
        match,
    )


MODIFY_CASES = [
    pytest.param({"new_price": SOL_PRICE}, "price symbol mismatch", id="new_price"),
    pytest.param({"new_qty": SOL_QTY}, "quantity symbol mismatch", id="new_qty"),
    pytest.param(
        {"new_attached_risk": AttachedRisk(stop_loss=RiskLeg(trigger_price=SOL_PRICE))},
        "price symbol mismatch",
        id="new_attached_risk",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("changes", "match"), MODIFY_CASES)
async def test_order_modify_refuses_values_for_another_market(
    changes: dict[str, Any], match: str
) -> None:
    service = _orders()
    await _refused(
        ORDERS,
        orders_pb2.ModifyOrderResponse(old_order_id=42, final_order_id=42, action_taken=1),
        lambda: service.modify(key=OrderId(42), symbol="BTC-USDT", **changes),
        match,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("changes", "match"), MODIFY_CASES)
async def test_batch_replace_refuses_values_for_another_market(
    changes: dict[str, Any], match: str
) -> None:
    service = _orders()
    await _refused(
        ORDERS,
        orders_pb2.BatchReplaceOrdersResponse(batch_request_id=9, status=1),
        lambda: service.batch_replace(symbol="BTC-USDT", items=[{"key": OrderId(42), **changes}]),
        match,
    )
