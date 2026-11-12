"""Public contract 78792a5: iceberg display, static peg, quote-proceeds sizing,
DECREMENT self-trade prevention, price bands, new cancel and trigger failure
reasons, ended-trigger refusals, spot-trade permission refusals, price-alert
policy actions and the assistant changelog surface."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester import (
    TRIGGER_STATUS_INVALID,
    AsyncPolyester,
    PolyesterApiError,
    PolyesterAuthError,
    Quantity,
    is_retryable_error,
    is_trigger_already_ended,
    mutation_outcome_unknown,
)
from polyester._contract_codes import is_recognised_rest_code
from polyester._wire import map_connect_error, protobuf_to_public_dict
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.changelog import changelog_change_from_proto, changelog_post_from_proto
from polyester.codecs.decode.orders import (
    batch_create_from_proto,
    order_from_proto,
    order_mutation_from_proto,
    preview_order_from_proto,
)
from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.decode.triggers import (
    trigger_event_from_proto,
    trigger_events_list_from_proto,
    trigger_from_proto,
)
from polyester.codecs.oco import create_oco_to_proto
from polyester.codecs.orders import (
    batch_create_orders_to_proto,
    normalize_create_order_request,
    order_intent_from_request,
)
from polyester.codecs.spot_config import spot_config_from_dict
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import ORDER_PERMISSION_REFUSAL_CODES, PolyesterValidationError
from polyester.gen.auth.v1 import policies_pb2
from polyester.gen.changelog.v1 import changelog_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import CreateOrderRequest, OrderPeg, PriceBand
from polyester.services.changelog import _enum_values
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)
from tests.unit.test_auth_error_codes import _rest_error

BASE_SCALE = 8
QUOTE_SCALE = 6
GTD_EXPIRY = "2099-01-01T00:00:00Z"


def _intent(**fields: Any) -> orders_pb2.OrderIntent:
    request = {"symbol": "BTC-USDT", "symbol_id": 1, "side": "buy", "order_type": "limit"}
    request.update(fields)
    return order_intent_from_request(
        normalize_create_order_request(request),
        quantity_scale=BASE_SCALE,
        quote_quantity_scale=QUOTE_SCALE,
    )


# --- iceberg display (LimitGtc / LimitGtd display_qty_scaled) ----------------------------------


def test_display_qty_is_sent_at_the_base_scale_on_limit_gtc() -> None:
    intent = _intent(qty="1", price="61000", display_qty="0.1")

    assert intent.WhichOneof("execution") == "limit_gtc"
    assert intent.base_qty_scaled == 100_000_000
    assert intent.limit_gtc.display_qty_scaled == 10_000_000


def test_display_qty_is_sent_on_limit_gtd() -> None:
    intent = _intent(
        qty="1",
        price="61000",
        tif="gtd",
        expires_at=_gtd_expiry(),
        display_qty=Quantity.from_scaled(25_000_000, scale=BASE_SCALE),
    )

    assert intent.WhichOneof("execution") == "limit_gtd"
    assert intent.limit_gtd.display_qty_scaled == 25_000_000


def _gtd_expiry() -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_plain_limit_order_sends_no_display() -> None:
    intent = _intent(qty="1", price="61000")
    assert intent.limit_gtc.display_qty_scaled == 0


@pytest.mark.parametrize(
    "fields",
    [
        {"order_type": "market"},
        {"tif": "ioc"},
        {"tif": "fok"},
    ],
)
def test_display_qty_is_refused_where_the_contract_has_no_display(fields: dict) -> None:
    with pytest.raises(PolyesterValidationError, match="display_qty is only valid for limit GTC"):
        _intent(
            qty="1",
            price=None if fields.get("order_type") else "61000",
            display_qty="0.1",
            **fields,
        )


@pytest.mark.parametrize("display", ["0", "-0.1"])
def test_display_qty_must_be_positive(display: str) -> None:
    with pytest.raises(PolyesterValidationError, match="display_qty"):
        _intent(qty="1", price="61000", display_qty=display)


def test_display_qty_rules_of_the_pair_are_left_to_the_api() -> None:
    # At or above qty, and more than 100 parts: the API answers
    # ICEBERG_DISPLAY_INVALID / ICEBERG_DISPLAY_TOO_SMALL.
    assert _intent(qty="1", price="61000", display_qty="2").limit_gtc.display_qty_scaled == (
        200_000_000
    )
    assert (
        _intent(qty="1", price="61000", display_qty="0.00000001").limit_gtc.display_qty_scaled == 1
    )


def test_display_qty_float_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="display_qty must be a decimal string"):
        normalize_create_order_request(
            symbol="BTC-USDT", side="buy", order_type="limit", qty="1", display_qty=0.1
        )


# --- static peg (OrderIntent.peg) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("peg", "reference", "offset"),
    [
        (OrderPeg(reference="best_bid"), orders_pb2.BEST_BID, 0),
        (OrderPeg(reference="BEST_ASK", offset_ticks=-2), orders_pb2.BEST_ASK, -2),
        ({"reference": "Best_Bid", "offset_ticks": 3}, orders_pb2.BEST_BID, 3),
        ({"reference": "best_ask", "offsetTicks": -1}, orders_pb2.BEST_ASK, -1),
        ({"reference": "best_ask"}, orders_pb2.BEST_ASK, 0),
    ],
)
def test_peg_is_sent_with_its_signed_offset_as_given(peg: Any, reference: int, offset: int) -> None:
    intent = _intent(qty="1", price="61000", post_only=True, peg=peg)

    assert intent.HasField("peg")
    assert intent.peg.reference == reference
    # A count of the pair's tick-size increments, never rescaled.
    assert intent.peg.offset_ticks == offset
    # The limit price stays: the BUY cap.
    assert intent.limit_gtc.price_ticks == 61_000_000_000_000


@pytest.mark.parametrize("tif", ["gtc", "ioc", "fok"])
def test_peg_works_with_every_limit_execution(tif: str) -> None:
    intent = _intent(side="sell", qty="1", price="60000", tif=tif, peg={"reference": "best_ask"})
    assert intent.WhichOneof("execution") == f"limit_{tif}"
    assert intent.peg.reference == orders_pb2.BEST_ASK


@pytest.mark.parametrize(
    ("peg", "message"),
    [
        ({"reference": "mid"}, "peg reference must be 'best_bid' or 'best_ask'"),
        ({"reference": ""}, "peg reference must be"),
        ({"offset_ticks": 1}, "peg requires reference"),
        ({"reference": "best_bid", "offset_ticks": 1.5}, "offset_ticks must be an integer"),
        ({"reference": "best_bid", "offset_ticks": True}, "offset_ticks must be an integer"),
        ({"reference": "best_bid", "offset_ticks": 1 << 63}, "outside int64"),
        ({"reference": "best_bid", "levels": 1}, "peg has unsupported fields: levels"),
        ("best_bid", "peg must be an OrderPeg or a dict"),
    ],
)
def test_bad_peg_is_refused_before_sending(peg: Any, message: str) -> None:
    with pytest.raises(PolyesterValidationError, match=message):
        _intent(qty="1", price="61000", peg=peg)


def test_peg_on_a_market_order_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="market order cannot carry a peg"):
        _intent(order_type="market", qty="1", peg={"reference": "best_bid"})


def test_peg_with_quote_sizing_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="quote sizing"):
        _intent(tif="ioc", price="61000", max_quote_debit="100", peg={"reference": "best_ask"})
    with pytest.raises(PolyesterValidationError, match="quote sizing"):
        _intent(
            side="sell",
            tif="ioc",
            price="60000",
            quote_proceeds="100",
            peg={"reference": "best_bid"},
        )


def test_peg_with_attached_risk_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="peg cannot be combined with attached_risk"):
        _intent(
            qty="1",
            price="61000",
            peg=OrderPeg(reference="best_bid"),
            attached_risk={"stop_loss": {"trigger_price": "55000"}},
        )


# --- quote-proceeds sizing (OrderIntent.quote_proceeds_scaled) ---------------------------------


@pytest.mark.parametrize(
    ("fields", "execution"),
    [
        ({"order_type": "market"}, "market_ioc"),
        ({"tif": "ioc", "price": "60000"}, "limit_ioc"),
    ],
)
def test_sell_ioc_is_sized_by_quote_proceeds_at_the_quote_scale(
    fields: dict, execution: str
) -> None:
    intent = _intent(side="sell", quote_proceeds="100", **fields)

    assert intent.WhichOneof("sizing") == "quote_proceeds_scaled"
    assert intent.quote_proceeds_scaled == 100_000_000
    assert intent.WhichOneof("execution") == execution


def test_quote_proceeds_takes_a_typed_quote_quantity() -> None:
    proceeds = Quantity.from_quote_decimal_str("12.5", QUOTE_SCALE, symbol="BTC-USDT")
    intent = _intent(side="sell", order_type="market", quote_proceeds=proceeds)
    assert intent.quote_proceeds_scaled == 12_500_000


@pytest.mark.parametrize(
    "fields",
    [
        {"side": "buy", "order_type": "market"},
        {"side": "sell", "price": "60000"},
        {"side": "sell", "price": "60000", "tif": "gtd", "expires_at": GTD_EXPIRY},
        {"side": "sell", "price": "60000", "tif": "fok"},
    ],
)
def test_quote_proceeds_is_refused_unless_sell_ioc(fields: dict) -> None:
    with pytest.raises(
        PolyesterValidationError,
        match="quote_proceeds is only valid for sell market or limit IOC orders",
    ):
        _intent(quote_proceeds="100", **fields)


@pytest.mark.parametrize(
    "sizing",
    [
        {"qty": "1", "quote_proceeds": "100"},
        {"max_quote_debit": "100", "quote_proceeds": "100"},
        {},
    ],
)
def test_exactly_one_sizing(sizing: dict) -> None:
    with pytest.raises(
        PolyesterValidationError,
        match="exactly one of qty, max_quote_debit or quote_proceeds",
    ):
        _intent(side="sell", order_type="market", **sizing)


def test_quote_proceeds_must_be_positive_and_needs_the_quote_scale() -> None:
    with pytest.raises(PolyesterValidationError, match="quote_proceeds must be positive"):
        _intent(side="sell", order_type="market", quote_proceeds="0")
    with pytest.raises(
        PolyesterValidationError, match="quote quantity scale is required for quote_proceeds"
    ):
        order_intent_from_request(
            CreateOrderRequest(symbol_id=1, side="sell", order_type="market", quote_proceeds="100"),
            quantity_scale=BASE_SCALE,
        )


def test_quote_proceeds_with_attached_risk_is_left_to_the_api() -> None:
    intent = _intent(
        side="sell",
        order_type="market",
        quote_proceeds="100",
        attached_risk={"stop_loss": {"trigger_price": "70000"}},
    )
    assert intent.HasField("attached_risk")


# --- DECREMENT self-trade prevention ------------------------------------------------------------


@pytest.mark.parametrize("label", ["decrement", "DECREMENT", "Decrement"])
def test_orders_take_decrement(label: str) -> None:
    intent = _intent(
        qty="1",
        price="61000",
        self_trade_prevention_mode=label,
        attached_risk={"stop_loss": {"trigger_price": "55000"}},
    )
    assert intent.self_trade_prevention_mode == orders_pb2.DECREMENT == 4


def test_trigger_create_takes_decrement() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="stop_loss",
        side="sell",
        qty="0.1",
        trigger_price="55000",
        quantity_scale=BASE_SCALE,
        self_trade_prevention_mode="decrement",
    )
    assert proto.trigger.self_trade_prevention_mode == orders_pb2.DECREMENT


def test_oco_create_passes_decrement_through() -> None:
    proto = create_oco_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        side="sell",
        qty="0.1",
        take_profit={"trigger_price": "70000"},
        stop_loss={"trigger_price": "55000"},
        quantity_scale=BASE_SCALE,
        self_trade_prevention_mode="decrement",
    )
    assert proto.oco.self_trade_prevention_mode == orders_pb2.DECREMENT


def test_unknown_mode_error_lists_decrement() -> None:
    with pytest.raises(PolyesterValidationError, match="expire_both, or decrement"):
        _intent(qty="1", price="61000", self_trade_prevention_mode="decrease")


def test_order_and_trigger_reads_label_decrement() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=1, symbol_id=1, self_trade_prevention_mode=orders_pb2.DECREMENT
        )
    )
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=1, symbol_id=1, self_trade_prevention_mode=orders_pb2.DECREMENT
        )
    )
    assert order.self_trade_prevention_mode == "decrement"
    assert trigger.self_trade_prevention_mode == "decrement"


# --- batch create items ----------------------------------------------------------------------


def test_batch_create_items_take_the_new_keys() -> None:
    proto = batch_create_orders_to_proto(
        items=[
            {
                "symbol_id": 1,
                "side": "buy",
                "order_type": "limit",
                "qty": "1",
                "price": "61000",
                "display_qty": "0.1",
                "peg": {"reference": "best_bid", "offset_ticks": -1},
                "self_trade_prevention_mode": "decrement",
            },
            {"symbol_id": 1, "side": "sell", "order_type": "market", "quote_proceeds": "250"},
        ],
        item_scales=[(BASE_SCALE, QUOTE_SCALE), (BASE_SCALE, QUOTE_SCALE)],
    )
    first, second = proto.items
    assert first.limit_gtc.display_qty_scaled == 10_000_000
    assert (first.peg.reference, first.peg.offset_ticks) == (orders_pb2.BEST_BID, -1)
    assert first.self_trade_prevention_mode == orders_pb2.DECREMENT
    assert second.quote_proceeds_scaled == 250_000_000


def test_batch_create_item_refusals_match_single_create() -> None:
    with pytest.raises(PolyesterValidationError, match="display_qty is only valid"):
        batch_create_orders_to_proto(
            items=[
                {
                    "symbol_id": 1,
                    "side": "buy",
                    "order_type": "limit",
                    "tif": "ioc",
                    "qty": "1",
                    "price": "61000",
                    "display_qty": "0.1",
                }
            ],
            item_scales=[(BASE_SCALE, QUOTE_SCALE)],
        )


# --- service round trip: scales, echoes ----------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="function")
async def order_client():
    seen: list[Any] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/CreateOrder"):
            request = orders_pb2.CreateOrderRequest.FromString(req.body)
            response = orders_pb2.CreateOrderResponse(
                order_id=42,
                resolved_base_qty_scaled=164_000,
                submitted_quote_proceeds_scaled=request.order.quote_proceeds_scaled,
            )
        elif req.path.endswith("/PreviewOrder"):
            request = orders_pb2.PreviewOrderRequest.FromString(req.body)
            response = orders_pb2.PreviewOrderResponse(admissible=True)
            response.evaluated_at.seconds = 1_700_000_000
        elif req.path.endswith("/BatchCreateOrders"):
            request = orders_pb2.BatchCreateOrdersRequest.FromString(req.body)
            response = orders_pb2.BatchCreateOrdersResponse(accepted_count=2)
            for index, item in enumerate(request.items):
                accepted = orders_pb2.BatchCreateAccepted(order_id=100 + index)
                if item.HasField("quote_proceeds_scaled"):
                    accepted.submitted_quote_proceeds_scaled = item.quote_proceeds_scaled
                if item.HasField("max_quote_debit_scaled"):
                    accepted.submitted_max_quote_debit_scaled = item.max_quote_debit_scaled
                response.results.append(orders_pb2.BatchCreateResultItem(accepted=accepted))
        else:
            raise AssertionError(f"unexpected write: {req.path}")
        seen.append(request)
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": BASE_SCALE,
                    "quote_quantity_scale": QUOTE_SCALE,
                },
            ]
        }
    )
    try:
        yield client, seen
    finally:
        await client.aclose()
        await http.aclose()


async def test_create_sends_quote_proceeds_and_reads_the_echo(order_client) -> None:
    client, seen = order_client
    result = await client.orders.create(
        symbol="BTC-USDT", side="sell", order_type="market", quote_proceeds="100"
    )

    assert seen[0].order.quote_proceeds_scaled == 100_000_000
    assert result.submitted_quote_proceeds_scaled == "100000000"
    assert result.submitted_max_quote_debit_scaled == ""


async def test_create_and_preview_send_display_and_peg(order_client) -> None:
    client, seen = order_client
    request = CreateOrderRequest(
        symbol="BTC-USDT",
        side="buy",
        order_type="limit",
        qty="1",
        price="61000",
        display_qty=Decimal("0.2"),
        peg=OrderPeg(reference="best_bid", offset_ticks=-3),
    )
    await client.orders.create(request)
    await client.orders.preview(request)

    for sent in seen:
        assert sent.order.limit_gtc.display_qty_scaled == 20_000_000
        assert sent.order.peg.offset_ticks == -3


async def test_create_refuses_a_quote_proceeds_quantity_of_another_scale(order_client) -> None:
    client, seen = order_client
    with pytest.raises(PolyesterValidationError, match="quantity scale mismatch"):
        await client.orders.create(
            symbol="BTC-USDT",
            side="sell",
            order_type="market",
            quote_proceeds=Quantity.from_quote_scaled(100, 2),
        )
    assert seen == []


async def test_batch_create_reads_both_quote_echoes(order_client) -> None:
    client, seen = order_client
    result = await client.orders.batch_create(
        items=[
            {"symbol": "BTC-USDT", "side": "sell", "order_type": "market", "quote_proceeds": "5"},
            {"symbol": "BTC-USDT", "side": "buy", "order_type": "market", "max_quote_debit": "7"},
        ]
    )

    assert seen[0].items[0].quote_proceeds_scaled == 5_000_000
    first, second = result.results
    assert (first.submitted_quote_proceeds_scaled, first.submitted_max_quote_debit_scaled) == (
        "5000000",
        "",
    )
    assert (second.submitted_quote_proceeds_scaled, second.submitted_max_quote_debit_scaled) == (
        "",
        "7000000",
    )


def test_batch_create_rejection_has_no_quote_echo() -> None:
    result = batch_create_from_proto(
        orders_pb2.BatchCreateOrdersResponse(
            rejected_count=1,
            results=[
                orders_pb2.BatchCreateResultItem(
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(
                            code=orders_pb2.ERROR_CODE_QUOTE_SIZE_TOO_SMALL
                        )
                    )
                )
            ],
        )
    )
    item = result.results[0]
    assert item.code == "error_code_quote_size_too_small"
    assert item.submitted_quote_proceeds_scaled == item.submitted_max_quote_debit_scaled == ""


def test_create_response_echo_is_empty_when_absent() -> None:
    result = order_mutation_from_proto(orders_pb2.CreateOrderResponse(order_id=1))
    assert result.submitted_quote_proceeds_scaled == ""


# --- order reads: display, hidden and submitted proceeds ---------------------------------------


def _iceberg_order(**fields: Any) -> orders_read_pb2.Order:
    values = {
        "order_id": 7,
        "symbol_id": 1,
        "orig_qty_scaled": 100_000_000,
        "leaves_qty_scaled": 90_000_000,
        "display_qty_scaled": 10_000_000,
        "hidden_qty_scaled": 80_000_000,
    }
    values.update(fields)
    return orders_read_pb2.Order(**values)


def test_order_reads_display_and_hidden_at_the_base_scale() -> None:
    order = order_from_proto(_iceberg_order(), quantity_scale=BASE_SCALE)

    assert order.display_qty == Quantity.from_scaled(10_000_000, scale=BASE_SCALE, symbol_id=1)
    assert order.display_qty is not None and order.display_qty.as_decimal() == Decimal("0.1")
    assert order.hidden_qty is not None and order.hidden_qty.as_decimal() == Decimal("0.8")
    assert order.leaves_qty is not None
    # The book shows leaves_qty - hidden_qty.
    assert order.leaves_qty.scaled - order.hidden_qty.scaled == 10_000_000


def test_plain_order_reads_zero_display_and_hidden() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(order_id=7, symbol_id=1, leaves_qty_scaled=5),
        quantity_scale=BASE_SCALE,
    )
    assert order.display_qty is not None and order.display_qty.scaled == 0
    assert order.hidden_qty is not None and order.hidden_qty.scaled == 0
    assert order.submitted_quote_proceeds_scaled == ""


def test_order_reads_submitted_quote_proceeds_as_max_quote_debit_is_read() -> None:
    order = order_from_proto(
        _iceberg_order(submitted_quote_proceeds_scaled=100_000_000, cum_notional=None),
        quantity_scale=BASE_SCALE,
        quote_quantity_scale=QUOTE_SCALE,
    )
    assert order.submitted_quote_proceeds_scaled == "100000000"
    assert order.submitted_max_quote_debit_scaled == ""


def test_private_order_stream_reads_the_same_fields() -> None:
    unit = private_orders_unit_from_proto(
        private_ws_pb2.Unit(orders=[_iceberg_order(submitted_quote_proceeds_scaled=9)]),
        scales=lambda _symbol_id: (BASE_SCALE, QUOTE_SCALE),
    )
    order = unit.orders[0]
    assert order.display_qty is not None and order.display_qty.scaled == 10_000_000
    assert order.hidden_qty is not None and order.hidden_qty.scale == BASE_SCALE
    assert order.submitted_quote_proceeds_scaled == "9"


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (orders_read_pb2.CANCEL_REASON_STP_DECREMENT, "STP_DECREMENT"),
        (orders_read_pb2.CANCEL_REASON_PRICE_BAND, "PRICE_BAND"),
        (orders_read_pb2.CANCEL_REASON_CANCEL_ON_DISCONNECT, "CANCEL_ON_DISCONNECT"),
    ],
)
def test_new_cancel_reasons_read_by_name(value: int, label: str) -> None:
    assert value in (19, 20, 21)
    order = order_from_proto(
        orders_read_pb2.Order(order_id=1, symbol_id=1, status=5, cancel_reason=value)
    )
    assert order.cancel_reason == label
    unit = private_orders_unit_from_proto(
        private_ws_pb2.Unit(
            events=[
                private_ws_pb2.UnitEvent(
                    order=private_ws_pb2.OrderEvent(order_id=1, cancel_reason=value)
                )
            ]
        )
    )
    assert unit.events[0].cancel_reason == label  # type: ignore[union-attr]


# --- spot config price band --------------------------------------------------------------------


def _spot_config() -> marketdata_pb2.GetSpotConfigResponse:
    return marketdata_pb2.GetSpotConfigResponse(
        pairs=[
            marketdata_pb2.PairConfig(
                symbol="BTC-USDT",
                symbol_id=1,
                base_quantity_scale=8,
                quote_quantity_scale=6,
                price_band=marketdata_pb2.PriceBand(
                    lower_bps=500, upper_bps=300, reference_window_ms=1000
                ),
            ),
            marketdata_pb2.PairConfig(
                symbol="ETH-USDT", symbol_id=2, base_quantity_scale=6, quote_quantity_scale=6
            ),
        ]
    )


def test_spot_config_pairs_read_their_price_band() -> None:
    config = spot_config_from_dict(protobuf_to_public_dict(_spot_config()))
    by_symbol = {limits.symbol: limits for limits in config.pair_order_limits}

    assert by_symbol["BTC-USDT"].price_band == PriceBand(
        lower_bps=500, upper_bps=300, reference_window_ms=1000
    )
    assert by_symbol["ETH-USDT"].price_band is None


def test_catalogs_expose_the_price_band() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(protobuf_to_public_dict(_spot_config()))

    limits = catalogs.order_limits_for_symbol_id(1)
    assert limits is not None and limits.price_band is not None
    assert limits.price_band.reference_window_ms == 1000
    eth = catalogs.order_limits_for_symbol("ETH-USDT")
    assert eth is not None and eth.price_band is None


def test_rest_spelling_reads_the_price_band_and_a_zero_window() -> None:
    config = spot_config_from_dict(
        {"pairs": [{"symbol": "BTC-USDT", "symbolId": 1, "priceBand": {"lowerBps": 25}}]}
    )
    assert config.pair_order_limits[0].price_band == PriceBand(lower_bps=25)


def test_malformed_price_band_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="price_band must be an object"):
        spot_config_from_dict({"pairs": [{"symbol": "BTC-USDT", "price_band": 5}]})


# --- triggers -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (triggers_pb2.TRIGGER_FAILURE_REASON_PRICE_BAND_VIOLATION, "price_band_violation"),
        (triggers_pb2.TRIGGER_FAILURE_REASON_QUOTE_SIZE_TOO_SMALL, "quote_size_too_small"),
    ],
)
def test_new_trigger_failure_reasons_read_by_name(value: int, label: str) -> None:
    assert value in (14, 24)
    event = trigger_event_from_proto(
        triggers_pb2.TriggerEvent(
            trigger_id=1, event_type=triggers_pb2.EVENT_FAILED, failure_reason=value
        )
    )
    assert event.failure_reason == label
    trigger = trigger_from_proto(triggers_pb2.Trigger(trigger_id=1, failure_reason=value))
    assert trigger.failure_reason == label


def test_ladder_level_rejected_on_arrival_reads_fired_then_fire_refused() -> None:
    events = trigger_events_list_from_proto(
        triggers_pb2.ListTriggerEventsResponse(
            events=[
                triggers_pb2.TriggerEvent(
                    trigger_id=5,
                    trigger_type=triggers_pb2.LADDER,
                    event_type=triggers_pb2.EVENT_FIRED,
                    child_seq=2,
                    child_order_id=77,
                    fire_price_ticks=60_000_000_000_000,
                ),
                triggers_pb2.TriggerEvent(
                    trigger_id=5,
                    trigger_type=triggers_pb2.LADDER,
                    event_type=triggers_pb2.EVENT_FIRE_REFUSED,
                    child_seq=2,
                    fire_price_ticks=60_000_000_000_000,
                    fire_refusal_reason=triggers_pb2.TRIGGER_FAILURE_REASON_POST_ONLY_CROSS,
                ),
            ]
        )
    ).events

    fired, refused = events
    assert (fired.event_type, refused.event_type) == ("fired", "fire_refused")
    assert fired.trigger_type == refused.trigger_type == "ladder"
    assert fired.child_seq == refused.child_seq == 2
    assert refused.fire_refusal_reason == "post_only_cross"
    assert refused.fire_price is not None and refused.fire_price.ticks == 60_000_000_000_000
    # Placed levels: a fired level followed by fire_refused of its child_seq was not placed.
    refused_seqs = {e.child_seq for e in events if e.event_type == "fire_refused"}
    placed = [e for e in events if e.event_type == "fired" and e.child_seq not in refused_seqs]
    assert placed == []


def _trigger_error(code: int, connect_code: Code = Code.INVALID_ARGUMENT) -> BaseException:
    return map_connect_error(
        ConnectError(connect_code, "refused", details=[orders_pb2.ErrorDetail(code=code)])
    )


def test_ended_trigger_refusal_reads_already_ended_over_connect() -> None:
    ended = _trigger_error(orders_pb2.ERROR_CODE_TRIGGER_STATUS_INVALID)

    assert isinstance(ended, PolyesterApiError)
    assert ended.code == TRIGGER_STATUS_INVALID
    assert is_trigger_already_ended(ended)
    assert not is_retryable_error(ended)
    assert not mutation_outcome_unknown(ended)


async def test_ended_trigger_refusal_reads_already_ended_over_rest(httpserver) -> None:
    ended = await _rest_error(
        httpserver,
        400,
        {
            "status": 400,
            "code": "TRIGGER_STATUS_INVALID",
            "detail": "Trigger has already ended (completed, canceled or failed)",
        },
    )
    assert isinstance(ended, PolyesterApiError)
    assert ended.code == TRIGGER_STATUS_INVALID
    assert is_trigger_already_ended(ended)


def test_trigger_not_found_is_not_already_ended() -> None:
    # It also names an ID that is none of the account's triggers.
    assert not is_trigger_already_ended(
        _trigger_error(orders_pb2.ERROR_CODE_TRIGGER_NOT_FOUND, Code.NOT_FOUND)
    )
    assert not is_trigger_already_ended(
        _trigger_error(orders_pb2.ERROR_CODE_ORDER_ALREADY_TERMINAL, Code.FAILED_PRECONDITION)
    )
    assert not is_trigger_already_ended(ValueError(TRIGGER_STATUS_INVALID))


# --- order permission refusals: one class and code on both transports ---------------------------

PERMISSION_CODES = [
    ("ERROR_CODE_POLICY_MARKET_DENY", 20),
    ("ERROR_CODE_POLICY_SPOT_TRADE_DENY", 23),
    ("ERROR_CODE_API_KEY_POLICY_REQUIRED", 27),
    ("ERROR_CODE_API_KEY_MARKET_DENY", 29),
    ("ERROR_CODE_API_KEY_SPOT_TRADE_DENY", 78),
]


def test_permission_codes_are_the_contract_numbers() -> None:
    assert {name for name, _ in PERMISSION_CODES} == ORDER_PERMISSION_REFUSAL_CODES
    for name, number in PERMISSION_CODES:
        assert orders_pb2.ErrorCode.Value(name) == number


# Other order permission refusals the gateway answers HTTP 403 for.
OTHER_PERMISSION_CODES = [
    ("ERROR_CODE_SUBACCOUNT_READ_FORBIDDEN", 70),
    ("ERROR_CODE_QUICKSWAP_NOT_PERMITTED", 203),
    ("ERROR_CODE_POLICY_TRADING_HALTED", 22),
    ("ERROR_CODE_API_KEY_SPOT_READ_DENY", 72),
]


@pytest.mark.parametrize(("name", "number"), PERMISSION_CODES + OTHER_PERMISSION_CODES)
async def test_permission_refusal_is_the_same_auth_error_on_both_transports(
    httpserver, name: str, number: int
) -> None:
    connect = map_connect_error(
        ConnectError(
            Code.PERMISSION_DENIED, "denied", details=[orders_pb2.ErrorDetail(code=number)]
        )
    )
    rest = await _rest_error(
        httpserver,
        403,
        {"status": 403, "code": name.removeprefix("ERROR_CODE_"), "detail": "denied"},
    )

    for err in (connect, rest):
        assert type(err) is PolyesterAuthError
        assert err.code == name
        assert err.status_code == 403
        assert not is_retryable_error(err)
        assert not mutation_outcome_unknown(err)
    assert (type(connect), connect.code) == (type(rest), rest.code)


@pytest.mark.parametrize(
    "name",
    [
        "API_KEY_SPOT_TRADE_DENY",
        "ICEBERG_NOT_ALLOWED",
        "ICEBERG_DISPLAY_TOO_SMALL",
        "ICEBERG_DISPLAY_INVALID",
        "PEG_LIMIT_VIOLATION",
        "PEG_REFERENCE_UNAVAILABLE",
        "INVALID_PEG",
        "QUOTE_SIZE_TOO_SMALL",
    ],
)
def test_new_order_codes_are_recognised(name: str) -> None:
    assert is_recognised_rest_code(name)
    err = _trigger_error(orders_pb2.ErrorCode.Value(f"ERROR_CODE_{name}"))
    assert err.code == f"ERROR_CODE_{name}"


def test_new_order_code_numbers() -> None:
    assert [
        orders_pb2.ErrorCode.Value(f"ERROR_CODE_{name}")
        for name in (
            "QUOTE_SIZE_TOO_SMALL",
            "ICEBERG_NOT_ALLOWED",
            "ICEBERG_DISPLAY_TOO_SMALL",
            "ICEBERG_DISPLAY_INVALID",
            "PEG_LIMIT_VIOLATION",
            "PEG_REFERENCE_UNAVAILABLE",
            "INVALID_PEG",
        )
    ] == [68, 309, 310, 311, 312, 313, 314]


# --- policies: price-alert actions --------------------------------------------------------------


def test_price_alert_policy_actions_read_by_name() -> None:
    actions = [policies_pb2.READ_PRICE_ALERTS, policies_pb2.MANAGE_PRICE_ALERTS]
    assert actions == [36, 37]
    api = api_policy_from_proto(policies_pb2.ApiPolicyView(id=1, actions=actions))
    sub = subaccount_policy_from_proto(policies_pb2.SubaccountPolicyView(id=1, actions=actions))
    assert api.actions == sub.actions == ["read_price_alerts", "manage_price_alerts"]


# --- changelog: assistant surface ---------------------------------------------------------------


def test_assistant_surface_reads_and_filters() -> None:
    assert changelog_pb2.ASSISTANT == 11
    change = changelog_change_from_proto(
        changelog_pb2.Change(id=1, surfaces=[changelog_pb2.ASSISTANT])
    )
    assert change.surfaces == ["assistant"]
    post = changelog_post_from_proto(
        changelog_pb2.GetPostResponse(
            post=changelog_pb2.Post(
                summary=changelog_pb2.PostSummary(slug="s"),
                sections=[changelog_pb2.Section(heading="AI", surface=changelog_pb2.ASSISTANT)],
            )
        )
    )
    assert post.sections[0].surface == "assistant"
    assert _enum_values(changelog_pb2.Surface, ["assistant"], "surfaces") == [11]


def test_list_changes_filter_takes_all_eleven_surfaces() -> None:
    labels = [name.lower() for name, number in changelog_pb2.Surface.items() if number != 0]
    assert len(labels) == 11
    assert _enum_values(changelog_pb2.Surface, labels, "surfaces") == list(range(1, 12))


# --- attached-risk leg violations (covered with no code change) ---------------------------------

STOP_LOSS_VIOLATION = orders_pb2.FieldViolation(
    field_path="order.attached_risk.stop_loss",
    rule_id="ERROR_CODE_MIN_NOTIONAL",
    message="stop-loss exit below the pair's minimum notional",
)


def test_attached_risk_leg_violation_reads_on_an_error() -> None:
    err = map_connect_error(
        ConnectError(
            Code.INVALID_ARGUMENT,
            "refused",
            details=[
                orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_MIN_NOTIONAL, violations=[STOP_LOSS_VIOLATION]
                )
            ],
        )
    )
    assert isinstance(err, PolyesterApiError)
    assert err.code == "ERROR_CODE_MIN_NOTIONAL"
    assert [(v.field_path, v.rule_id) for v in err.violations] == [
        ("order.attached_risk.stop_loss", "ERROR_CODE_MIN_NOTIONAL")
    ]


def test_attached_risk_leg_violation_reads_on_preview_and_batch_items() -> None:
    preview = orders_pb2.PreviewOrderResponse(
        admissible=False,
        rejection=orders_pb2.ErrorDetail(
            code=orders_pb2.ERROR_CODE_MIN_NOTIONAL, violations=[STOP_LOSS_VIOLATION]
        ),
    )
    preview.evaluated_at.seconds = 1_700_000_000
    decoded = preview_order_from_proto(preview)
    assert decoded.rejection is not None
    assert decoded.rejection.violations[0].field_path == "order.attached_risk.stop_loss"

    batch = batch_create_from_proto(
        orders_pb2.BatchCreateOrdersResponse(
            rejected_count=1,
            results=[
                orders_pb2.BatchCreateResultItem(
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(
                            code=orders_pb2.ERROR_CODE_MIN_NOTIONAL,
                            violations=[STOP_LOSS_VIOLATION],
                        )
                    )
                )
            ],
        )
    )
    assert batch.results[0].violations[0].field_path == "order.attached_risk.stop_loss"
