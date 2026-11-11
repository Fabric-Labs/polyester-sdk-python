import json
from decimal import Decimal

import pytest
from google.protobuf.json_format import MessageToDict, ParseDict

from polyester import AsyncPolyester, Quantity
from polyester.codecs.decode.balances import equity_history_from_proto
from polyester.codecs.decode.transfers import transfers_list_from_proto
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.codecs.wire_decode import decode_equity_history, decode_transfers_list
from polyester.gen.ledger.read.v1 import ledger_read_pb2 as ledger
from polyester.gen.orders.v1 import orders_pb2 as orders
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)


@pytest.mark.parametrize("token", ["eyJ2IjoxfQ==", "000123", "0", ""])
@pytest.mark.parametrize("json_wire", [False, True])
def test_transfer_token_is_opaque(token, json_wire):
    raw = ledger.ListTransfersResponse(
        transfers=[ledger.TransferRow(asset_id=1, ts_us=999)], next_page_token=token
    )
    raw = (
        ParseDict(MessageToDict(raw), ledger.ListTransfersResponse())
        if json_wire
        else (ledger.ListTransfersResponse.FromString(raw.SerializeToString()))
    )
    result = transfers_list_from_proto(raw)
    assert len(result.transfers) == 1
    assert result.transfers[0].timestamp == 999
    assert result.next_page_token == token
    assert decode_transfers_list(MessageToDict(raw)).next_page_token == token


@pytest.mark.parametrize("prices", [[60000000000001, 61000000000009], []])
@pytest.mark.parametrize("json_wire", [False, True])
def test_equity_btc_prices_preserved(prices, json_wire):
    raw = ledger.GetEquityHistorySeriesResponse(
        start_ts_sec=100,
        end_ts_sec=400,
        bucket="5m",
        points=2,
        quote_asset="USDT",
        series=[ledger.EquitySeries(equity_q=[12345, -6789])],
        btc_prices_q=prices,
    )
    raw = (
        ParseDict(MessageToDict(raw), ledger.GetEquityHistorySeriesResponse())
        if json_wire
        else (ledger.GetEquityHistorySeriesResponse.FromString(raw.SerializeToString()))
    )
    for result in [equity_history_from_proto(raw), decode_equity_history(MessageToDict(raw))]:
        assert result.points == 2
        assert result.series[0].equity_q == [12345, -6789]
        assert result.btc_prices_q == prices
        assert result.start_ts_sec == 100 and result.end_ts_sec == 400
        if prices:
            assert Decimal(result.btc_prices_q[0]) / 10**9 == Decimal("60000.000000001")
    assert equity_history_from_proto(ledger.GetEquityHistorySeriesResponse()).btc_prices_q == []


@pytest.mark.parametrize("identity", ["id", "symbol", "explicit"])
@pytest.mark.parametrize("json_wire", [False, True])
async def test_preview_resolves_id_quantity_scale(identity, json_wire):
    seen = []

    async def handler(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/PreviewOrder")
        request = (
            ParseDict(json.loads(req.body), orders.PreviewOrderRequest())
            if json_wire
            else orders.PreviewOrderRequest.FromString(req.body)
        )
        seen.append(request)
        response = orders.PreviewOrderResponse(resolved_base_qty_scaled=16000)
        response.evaluated_at.seconds = 1
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
    client.catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    kwargs = {"symbol": "BTC-USDT"} if identity == "symbol" else {"symbol_id": 1}
    qty = Quantity.from_scaled(16000, scale=8 if identity == "explicit" else None)
    try:
        result = await client.orders.preview(
            **kwargs, side="buy", order_type="limit", qty=qty, price="100"
        )
        assert len(seen) == 1
        assert seen[0].order.symbol_id == 1
        assert seen[0].order.base_qty_scaled == 16000
        assert result.resolved_base_qty.scaled == 16000
        assert result.resolved_base_qty.as_decimal() == Decimal("0.00016")
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("token", ["eyJ2IjoxfQ==", "000123", ""])
def test_market_overview_token_is_opaque(token):
    from polyester.codecs.decode.market_overview import market_overview_list_from_proto
    from polyester.codecs.wire_decode import decode_market_overview_list
    from polyester.gen.marketoverview.v1 import marketoverview_pb2 as overview

    raw = overview.ListMarketOverviewResponse(
        markets=[overview.MarketOverview(symbol_id=1)], next_page_token=token
    )
    for result in [
        market_overview_list_from_proto(raw),
        decode_market_overview_list(MessageToDict(raw)),
    ]:
        assert len(result.markets) == 1
        assert result.next_page_token == token


@pytest.mark.parametrize("token", ["eyJ2IjoxfQ==", "000123", ""])
def test_candle_tokens_are_opaque(token):
    from polyester.codecs.decode.market_data import candles_columns_from_proto, candles_from_proto
    from polyester.codecs.wire_decode import decode_candles_list
    from polyester.gen.marketdata.v1 import marketdata_pb2 as market

    raw = market.GetCandlesResponse(candles=[market.CandlePoint(ts_sec=100)], next_page_token=token)
    columns = market.GetCandlesColumnsResponse(
        ts_sec=[100], open=[1], high=[1], low=[1], close=[1], volume=[1], next_page_token=token
    )
    for result in [
        candles_from_proto(raw, volume_scale=8),
        candles_columns_from_proto(columns, volume_scale=8),
        decode_candles_list(MessageToDict(raw), volume_scale=8),
    ]:
        assert len(result.candles) == 1
        assert result.next_page_token == token


@pytest.mark.parametrize("operation", ["transfers", "overview", "candles", "columns"])
@pytest.mark.parametrize("json_wire", [False, True])
async def test_public_helpers_follow_opaque_token_with_unchanged_filters(operation, json_wire):
    from polyester.gen.marketdata.v1 import marketdata_pb2 as market
    from polyester.gen.marketoverview.v1 import marketoverview_pb2 as overview

    seen = []
    token = "eyJ2IjoxfQ=="
    request_type = {
        "transfers": ledger.ListTransfersRequest,
        "overview": overview.ListMarketOverviewRequest,
        "candles": market.GetCandlesRequest,
        "columns": market.GetCandlesColumnsRequest,
    }[operation]

    async def handler(req: ParsedRequest) -> HttpScript:
        request = (
            ParseDict(json.loads(req.body), request_type())
            if json_wire
            else request_type.FromString(req.body)
        )
        seen.append(request)
        index = len(seen)
        next_token = token if index == 1 else ""
        if operation == "transfers":
            response = ledger.ListTransfersResponse(
                transfers=[ledger.TransferRow(ts_us=999, transfer_id=str(index))],
                next_page_token=next_token,
            )
        elif operation == "overview":
            response = overview.ListMarketOverviewResponse(
                markets=[overview.MarketOverview(symbol_id=index)], next_page_token=next_token
            )
        elif operation == "candles":
            response = market.GetCandlesResponse(
                candles=[market.CandlePoint(ts_sec=100)], next_page_token=next_token
            )
        else:
            response = market.GetCandlesColumnsResponse(
                ts_sec=[100],
                open=[1],
                high=[1],
                low=[1],
                close=[1],
                volume=[1],
                next_page_token=next_token,
            )
        return (
            HttpScript.json(200, MessageToDict(response))
            if json_wire
            else connect_proto_response(response.SerializeToString())
        )

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    client.catalogs.hydrate_spot_config(
        {
            "assets": [{"asset": "BTC", "market_data_volume_scale": 8}],
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_asset": "BTC",
                    "base_quantity_scale": 8,
                }
            ],
        }
    )
    if operation == "transfers":
        call = client.transfers.list
        kwargs = {
            "limit": 1,
            "reversed": True,
            "since": 100,
            "sub_account_id": format_uint64_id(42),
        }
    elif operation == "overview":
        call = client.market_overview.list
        kwargs = {"limit": 1, "symbols": ["BTC-USDT"]}
    else:
        call = (
            client.market_data.get_candles
            if operation == "candles"
            else client.market_data.get_candles_columns
        )
        kwargs = {"limit": 1, "symbol_id": 1, "timeframe": "5m"}
    try:
        first = await call(**kwargs)
        assert first.next_page_token == token
        second = await call(**kwargs, page_token=first.next_page_token)
        assert second.next_page_token == ""
        assert len(seen) == 2
        assert seen[0].page_token == ""
        assert seen[1].page_token == token
        seen[1].page_token = ""
        assert seen[0] == seen[1]
        if operation == "transfers":
            assert seen[0].subaccount_id == 42 and seen[0].ts_min_us == 100
            assert first.transfers[0].timestamp == second.transfers[0].timestamp == 999
            assert first.transfers[0].transfer_id != second.transfers[0].transfer_id
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("explicit", [False, True])
async def test_preview_without_catalog_requires_explicit_scale(explicit):
    from polyester.errors import PolyesterValidationError

    seen = []

    async def handler(req: ParsedRequest) -> HttpScript:
        seen.append(req)
        response = orders.PreviewOrderResponse(resolved_base_qty_scaled=16000)
        response.evaluated_at.seconds = 1
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        kwargs = {
            "symbol_id": 1,
            "side": "buy",
            "order_type": "limit",
            "price": "100",
            "qty": Quantity.from_scaled(16000, scale=8 if explicit else None),
        }
        if explicit:
            result = await client.orders.preview(**kwargs)
            assert result.resolved_base_qty.as_decimal() == Decimal("0.00016")
            assert len(seen) == 1
        else:
            with pytest.raises(PolyesterValidationError, match="explicit scale"):
                await client.orders.preview(**kwargs)
            assert seen == []
    finally:
        await client.aclose()
        await http.aclose()
