"""Order and trigger reads carry the pair's catalog quantity scales.

With the catalogs loaded, an order read back from ``orders.get``,
``orders.list_open``, ``orders.list_history`` or the private order stream knows
its pair's base and quote quantity scales, so ``cum_qty.as_decimal()``,
``cum_quote()``, ``quote_used()`` and ``quote_unspent()`` need no scale
argument, as on ``orders.create`` and ``orders.preview``. Without catalogs the
explicit-scale behaviour is unchanged.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.private_orders import (
    private_orders_from_proto,
    private_orders_unit_from_proto,
)
from polyester.codecs.realtime_decode import decode_trigger_bytes
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.order_key import OrderId
from polyester.models.trading import Order
from polyester.services.orders import AsyncOrdersService
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

BTC_USDT = {
    "symbol": "BTC-USDT",
    "symbol_id": 1,
    "base_quantity_scale": 8,
    "quote_quantity_scale": 6,
}


def _u128(value: int) -> dict[str, int]:
    return {"hi": value >> 64, "lo": value & ((1 << 64) - 1)}


def _spent_buy(symbol_id: int = 1) -> orders_read_pb2.Order:
    """A market buy of 6000 USDT stopped by its price limit, fees in quote."""
    order = orders_read_pb2.Order(
        order_id=7,
        symbol_id=symbol_id,
        side=orders_pb2.BUY,
        order_type=orders_pb2.MARKET,
        status=orders_read_pb2.CANCELED,
        cum_qty_scaled=4_148_504,
        orig_qty_scaled=4_148_504,
        submitted_max_quote_debit_scaled=6_000_000_000,
        fee_asset=orders_pb2.QUOTE,
    )
    order.cum_notional.CopyFrom(order.cum_notional.__class__(**_u128(321558095317280000000)))
    order.fee_total.qty_scaled = 4_148_504
    order.fee_total.amount_e18.lo = 964674285951840000
    return order


def _assert_scaled(order: Order | None) -> None:
    assert order is not None
    assert order.cum_qty is not None
    assert order.cum_qty.scale == 8
    assert order.cum_qty.as_decimal() == Decimal("0.04148504")
    assert order.orig_qty is not None and order.orig_qty.as_decimal() == Decimal("0.04148504")
    assert order.cum_quote() == Decimal("3215.5809531728")
    assert order.quote_used() == Decimal("3216.54562745875184")
    assert order.quote_unspent() == Decimal("2783.45437254124816")
    assert order.quote_quantity_scale == 6


def _assert_unscaled(order: Order | None) -> None:
    assert order is not None
    assert order.cum_qty is not None and order.cum_qty.scale is None
    assert order.quote_quantity_scale is None
    with pytest.raises(PolyesterValidationError, match="base_quantity_scale is required"):
        order.cum_quote()
    # Explicit scales still work.
    assert order.cum_quote(8) == Decimal("3215.5809531728")
    assert order.quote_unspent(quote_quantity_scale=6, base_quantity_scale=8) == Decimal(
        "2783.45437254124816"
    )


def _trade() -> orders_read_pb2.UserTrade:
    return orders_read_pb2.UserTrade(symbol_id=1, match_id=9, order_id=7, qty_scaled=4_148_504)


RESPONSES: dict[str, Message] = {
    "GetOrder": orders_read_pb2.GetOrderResponse(order=_spent_buy(), trades=[_trade()]),
    "GetOpenOrders": orders_read_pb2.GetOpenOrdersResponse(orders=[_spent_buy()]),
    "GetOrderHistory": orders_read_pb2.GetOrderHistoryResponse(orders=[_spent_buy()]),
}


async def _client(json_wire: bool, *, catalogs: bool) -> tuple[AsyncPolyester, MockHttpServer]:
    async def handler(req: ParsedRequest) -> HttpScript:
        response = RESPONSES[req.path.rsplit("/", 1)[-1]]
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    if catalogs:
        client.catalogs.hydrate_spot_config({"pairs": [BTC_USDT]})
    return client, http


async def _read(client: AsyncPolyester, method: str) -> Order | None:
    if method == "get":
        result = await client.orders.get(key=OrderId(7))
        assert len(result.trades) == 1
        trade_qty = result.trades[0].qty
        assert trade_qty is not None
        if client.catalogs.base_quantity_scale_for_symbol_id(1) is not None:
            assert trade_qty.as_decimal() == Decimal("0.04148504")
        else:
            assert trade_qty.scale is None
        return result.order
    if method == "list_open":
        return (await client.orders.list_open()).orders[0]
    return (await client.orders.list_history()).orders[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("method", ["get", "list_open", "list_history"])
async def test_order_reads_carry_the_catalog_scales(json_wire: bool, method: str) -> None:
    client, http = await _client(json_wire, catalogs=True)
    try:
        _assert_scaled(await _read(client, method))
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("method", ["get", "list_open", "list_history"])
async def test_order_reads_without_catalogs_keep_explicit_scales(
    json_wire: bool, method: str
) -> None:
    client, http = await _client(json_wire, catalogs=False)
    try:
        _assert_unscaled(await _read(client, method))
    finally:
        await client.aclose()
        await http.aclose()


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config({"pairs": [BTC_USDT]})
    return catalogs


def test_order_of_a_pair_the_catalogs_do_not_know_stays_unscaled() -> None:
    from polyester.codecs.decode.orders import orders_list_from_proto

    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    listed = orders_list_from_proto(
        orders_read_pb2.GetOpenOrdersResponse(orders=[_spent_buy(symbol_id=99)]),
        scales=service._order_scales,
    )
    _assert_unscaled(listed.orders[0])


def test_private_order_stream_orders_and_fills_carry_the_catalog_scales() -> None:
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    scales = service._order_scales
    _assert_scaled(private_orders_from_proto([_spent_buy()], scales=scales)[0])

    unit = private_orders_unit_from_proto(
        pb.Unit(
            orders=[_spent_buy()],
            events=[
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=7,
                        version=2,
                        kind=pb.OrderEvent.FILLED,
                        fill=pb.Fill(match_id=77, qty_scaled=4_148_504),
                    )
                )
            ],
        ),
        scales=scales,
    )
    _assert_scaled(unit.orders[0])
    event = unit.events[0]
    assert event.fill is not None  # type: ignore[union-attr]
    assert event.fill.qty.as_decimal() == Decimal("0.04148504")  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_orders_subscribe_decodes_with_the_catalog_scales() -> None:
    realtime = MagicMock()
    realtime.subscribe_private_orders = AsyncMock(return_value="subscription")
    service = AsyncOrdersService(
        MagicMock(), _catalogs(), None, default_account_id="j", realtime=realtime
    )
    assert await service.subscribe() == "subscription"
    realtime.subscribe_private_orders.assert_awaited_once_with(
        "j", order_scales=service._order_scales
    )


def _twap(symbol_id: int = 1) -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=11,
        symbol_id=symbol_id,
        status=triggers_pb2.STATUS_RUNNING,
        qty_scaled=100_000_000,
        twap=triggers_pb2.TwapTrigger(
            side=orders_pb2.BUY,
            duration_ms=60_000,
            slice_interval_ms=5_000,
            market_ioc=triggers_pb2.TwapMarketIoc(),
        ),
        twap_state=triggers_pb2.TwapDetails(
            twap_duration_ms=60_000,
            twap_slice_interval_ms=5_000,
            slice_idx=2,
            slice_count=12,
            executed_qty_scaled=25_000_000,
        ),
        client_trigger_id="twap-1",
    )


def _ladder() -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=12,
        symbol_id=1,
        status=triggers_pb2.STATUS_RUNNING,
        qty_scaled=100_000_000,
        ladder=triggers_pb2.LadderTrigger(side=orders_pb2.BUY),
        ladder_state=triggers_pb2.LadderDetails(
            ladder_levels=4, executed_levels=1, executed_qty_scaled=25_000_000
        ),
        client_trigger_id="ladder-1",
    )


TRIGGER_RESPONSES: dict[str, Any] = {
    "GetTrigger": triggers_pb2.GetTriggerResponse(trigger=_twap()),
    "ListTriggers": triggers_pb2.ListTriggersResponse(triggers=[_twap(), _ladder()]),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("catalogs", [True, False])
async def test_trigger_reads_carry_the_catalog_scales(json_wire: bool, catalogs: bool) -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        response = TRIGGER_RESPONSES[req.path.rsplit("/", 1)[-1]]
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    if catalogs:
        client.catalogs.hydrate_spot_config({"pairs": [BTC_USDT]})
    expected_scale = 8 if catalogs else None
    try:
        got = await client.triggers.get(trigger_id="11")
        listed = (await client.triggers.list()).triggers
        twaps = [got, listed[0]]
        for trigger in twaps:
            assert trigger is not None and trigger.details is not None
            assert trigger.details.twap is not None
            executed = trigger.details.twap.executed_qty
            assert executed is not None and executed.scale == expected_scale
            assert trigger.qty is not None and trigger.qty.scale == expected_scale
        ladder = listed[1].details
        assert ladder is not None and ladder.ladder is not None
        assert ladder.ladder.executed_qty is not None
        assert ladder.ladder.executed_qty.scale == expected_scale
        if catalogs:
            assert twaps[0].details.twap.executed_qty.as_decimal() == Decimal("0.25")  # type: ignore[union-attr]
    finally:
        await client.aclose()
        await http.aclose()


def test_trigger_stream_decodes_with_the_catalog_scales() -> None:
    scales = AsyncOrdersService(MagicMock(), _catalogs(), None)._order_scales
    trigger = decode_trigger_bytes(_twap().SerializeToString(), scales=scales)
    assert trigger.qty is not None and trigger.qty.scale == 8
    assert trigger.details is not None and trigger.details.twap is not None
    executed = trigger.details.twap.executed_qty
    assert executed is not None and executed.as_decimal() == Decimal("0.25")


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("catalogs", [True, False])
async def test_trades_list_carries_the_catalog_scale(json_wire: bool, catalogs: bool) -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/GetUserTrades")
        response = orders_read_pb2.GetUserTradesResponse(trades=[_trade()])
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    if catalogs:
        client.catalogs.hydrate_spot_config({"pairs": [BTC_USDT]})
    try:
        qty = (await client.trades.list()).trades[0].qty
        assert qty is not None and qty.scale == (8 if catalogs else None)
    finally:
        await client.aclose()
        await http.aclose()


def test_trade_stream_decodes_with_the_catalog_scale() -> None:
    from polyester.codecs.realtime_decode import decode_user_trade_batch_bytes

    scales = AsyncOrdersService(MagicMock(), _catalogs(), None)._order_scales
    payload = orders_read_pb2.UserTradeBatch(events=[_trade()]).SerializeToString()
    (trade,) = decode_user_trade_batch_bytes(payload, scales=scales)
    assert not isinstance(trade, Exception)
    assert trade.qty is not None and trade.qty.as_decimal() == Decimal("0.04148504")


@pytest.mark.asyncio
@pytest.mark.parametrize("funding", ["pending", "failed"])
async def test_order_reads_scale_from_the_spot_catalog_without_the_funding_config(
    funding: str,
) -> None:
    """Order, trade and trigger reads need only the spot config: they are
    scaled while the funding (deposit/withdraw) config is still loading or
    after it failed, and never wait for it."""
    import asyncio

    from polyester.errors import PolyesterCatalogHydrationError
    from polyester.gen.marketdata.v1 import marketdata_pb2

    spot = marketdata_pb2.GetSpotConfigResponse()
    pair = spot.pairs.add()
    pair.symbol, pair.symbol_id, pair.base_asset, pair.quote_asset = "BTC-USDT", 1, "BTC", "USDT"
    pair.base_quantity_scale, pair.quote_quantity_scale = 8, 6

    def handler(req: ParsedRequest) -> HttpScript:
        rpc = req.path.rsplit("/", 1)[-1]
        if rpc == "GetSpotConfig":
            return connect_proto_response(spot.SerializeToString())
        if rpc == "GetDepositWithdrawConfig":
            if funding == "pending":
                return HttpScript.never_respond()
            return HttpScript.json(500, b'{"code":"internal","message":"funding down"}')
        if rpc == "GetUserTrades":
            body = orders_read_pb2.GetUserTradesResponse(trades=[_trade()])
            return connect_proto_response(body.SerializeToString())
        if rpc in TRIGGER_RESPONSES:
            return connect_proto_response(TRIGGER_RESPONSES[rpc].SerializeToString())
        return connect_proto_response(RESPONSES[rpc].SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        ws_url="ws://127.0.0.1:9/unused",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        timeout=30.0,
    )
    try:
        if funding == "failed":
            with pytest.raises(PolyesterCatalogHydrationError):
                await client.wait_for_funding_catalog()

        async def reads() -> None:
            for method in ("get", "list_open", "list_history"):
                _assert_scaled(await _read(client, method))
            trade = (await client.trades.list()).trades[0]
            assert trade.qty is not None and trade.qty.scale == 8
            trigger = await client.triggers.get(trigger_id="11")
            assert trigger is not None and trigger.qty is not None and trigger.qty.scale == 8

        # Started right after the client: each read waits for the spot config only.
        await asyncio.wait_for(reads(), 10)
    finally:
        await client.aclose()
        await http.aclose()
