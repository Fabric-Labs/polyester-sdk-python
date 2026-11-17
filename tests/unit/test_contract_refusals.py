"""Inputs the published contract refuses are refused before sending.

Page limits outside the contract's range, a zero or non-positive price the
contract requires to be positive, and public IDs or numbers written with
non-ASCII characters. Also: settlement legs repeated across execution pages
are kept once.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.codecs.bps import validate_bps
from polyester.codecs.oco import create_oco_to_proto
from polyester.codecs.orders import create_order_to_proto, create_order_to_wire
from polyester.codecs.scalars import (
    decimal_to_scaled,
    id_to_int,
    parse_required_uint64_decimal,
    tick_count,
)
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.marketdata.v1 import heatmap_pb2
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import CreateOrderRequest, OrderId
from polyester.models.trading import GetOrderResult, Order, OrderTransfer, UserTrade
from polyester.services.orders import wait_for_order_trades_complete
from polyester.types.money import Price, Quantity
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

_CREDS = make_test_credentials()


@asynccontextmanager
async def _client():
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return HttpScript.json(500, {"code": "internal", "message": "stop"})

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


# --- page limits ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("request_type", "low", "high"),
    [
        # optional uint32 limit {gte: 1, lte: 1000}
        (orders_read_pb2.GetOpenOrdersRequest, 1, 1000),
        (orders_read_pb2.GetOrderHistoryRequest, 1, 1000),
        (orders_read_pb2.GetUserTradesRequest, 1, 1000),
        (orders_read_pb2.GetOrderRequest, 1, 1000),
        # uint32 limit {lte: 1000}: 0 is the server default
        (ledger_read_pb2.ListTransfersRequest, 0, 1000),
        (triggers_pb2.ListTriggersRequest, 0, 1000),
        (triggers_pb2.ListTriggerEventsRequest, 0, 1000),
        # uint32 limit {gte: 1, lte: 20000}
        (heatmap_pb2.GetOrderbookHeatmapRequest, 1, 20000),
    ],
)
def test_page_limit_range_is_read_from_the_contract(
    request_type: type[Message], low: int, high: int
) -> None:
    from polyester.codecs.contract_limits import contract_uint32_range

    assert contract_uint32_range(request_type, "limit") == (low, high)


_ORDER = OrderId("2nsoduvuPJr")

_LIMIT_CALLS: list[tuple[str, Callable[[AsyncPolyester, int], Any], type[Message]]] = [
    (
        "orders.list_open",
        lambda c, n: c.orders.list_open(limit=n),
        orders_read_pb2.GetOpenOrdersRequest,
    ),
    (
        "orders.list_history",
        lambda c, n: c.orders.list_history(limit=n),
        orders_read_pb2.GetOrderHistoryRequest,
    ),
    (
        "orders.get",
        lambda c, n: c.orders.get(key=_ORDER, limit=n),
        orders_read_pb2.GetOrderRequest,
    ),
    ("trades.list", lambda c, n: c.trades.list(limit=n), orders_read_pb2.GetUserTradesRequest),
    (
        "transfers.list",
        lambda c, n: c.transfers.list(limit=n),
        ledger_read_pb2.ListTransfersRequest,
    ),
    ("triggers.list", lambda c, n: c.triggers.list(limit=n), triggers_pb2.ListTriggersRequest),
    (
        "triggers.list_events",
        lambda c, n: c.triggers.list_events(trigger_id="2", limit=n),
        triggers_pb2.ListTriggerEventsRequest,
    ),
]


@pytest.mark.parametrize("limit", [1001, 5000])
@pytest.mark.parametrize(("name", "call", "request_type"), _LIMIT_CALLS)
async def test_page_limit_above_the_contract_maximum_is_refused_before_sending(
    name: str, call: Callable[[AsyncPolyester, int], Any], request_type: type[Message], limit: int
) -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="limit"):
            await call(client, limit)
    assert requests == []


@pytest.mark.parametrize(
    ("name", "call", "request_type"),
    # The calls whose limit the contract bounds from 1 (gte: 1).
    _LIMIT_CALLS[:4],
)
async def test_explicit_zero_limit_is_refused_where_the_contract_requires_one(
    name: str, call: Callable[[AsyncPolyester, int], Any], request_type: type[Message]
) -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="limit"):
            await call(client, 0)
    assert requests == []


@pytest.mark.parametrize("limit", [1, 1000])
@pytest.mark.parametrize(("name", "call", "request_type"), _LIMIT_CALLS)
async def test_page_limit_within_the_contract_range_is_sent_unchanged(
    name: str, call: Callable[[AsyncPolyester, int], Any], request_type: type[Message], limit: int
) -> None:
    async with _client() as (client, requests):
        with pytest.raises(Exception):  # noqa: B017 - the stub answers every call with an error
            await call(client, limit)
    assert len(requests) == 1
    sent = request_type.FromString(requests[0].body)
    assert sent.limit == limit  # type: ignore[attr-defined]


async def test_an_omitted_optional_limit_is_not_sent() -> None:
    async with _client() as (client, requests):
        with pytest.raises(Exception):  # noqa: B017
            await client.orders.list_open()
        with pytest.raises(Exception):  # noqa: B017
            await client.orders.get(key=_ORDER)
    assert not orders_read_pb2.GetOpenOrdersRequest.FromString(requests[0].body).HasField("limit")
    assert not orders_read_pb2.GetOrderRequest.FromString(requests[1].body).HasField("limit")


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.heatmap.get(symbol_id=1, limit=0),
        lambda c: c.heatmap.get(symbol_id=1, limit=20001),
        lambda c: c.market_data.get_trades(symbol_id=1, limit=1001),
        lambda c: c.market_data.get_candles(symbol_id=1, limit=10001),
        lambda c: c.market_overview.list(limit=2001),
        lambda c: c.address_book.list_entries(limit=501),
        lambda c: c.address_book.list_transfer_counterparties(limit=201),
        lambda c: c.address_book.list_transfer_destinations(kind="external", limit=501),
        lambda c: c.address_book.list_internal_transfer_whitelist_entries(limit=501),
        lambda c: c.address_book.get_view(limit=201),
        lambda c: c.lifecycle.list_flows(limit=501),
        lambda c: c.lifecycle.list_flows_by_tx(tx_hash="0x" + "a" * 64, limit=501),
        lambda c: c.sub_accounts.list_activity(sub_account_id="2", limit=201),
        lambda c: c.list_status_events(limit=201),
        lambda c: c.changelog.list_posts(limit=101),
        lambda c: c.changelog.list_deployment_groups(limit=101),
        lambda c: c.changelog.list_changes(limit=501),
        lambda c: c.alerts.list(limit=201),
    ],
)
async def test_every_other_page_limit_follows_its_contract_range(call) -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="limit"):
            await call(client)
    assert requests == []


# --- trigger refusals ----------------------------------------------------------------------------

_BASE = dict(symbol="BTC-USDT", symbol_id=1, side="sell", qty="1", quantity_scale=8)
_ZEROS: list[Any] = ["0", "0.00", Decimal("0"), Price.from_ticks(0)]


@pytest.mark.parametrize("zero", _ZEROS)
def test_ladder_price_min_of_zero_is_refused(zero: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="ladder_price_min"):
        create_trigger_to_proto(
            trigger_type="ladder",
            ladder_price_min=zero,
            ladder_price_max="100",
            ladder_levels=5,
            **_BASE,
        )


@pytest.mark.parametrize("zero", _ZEROS)
def test_ladder_price_max_of_zero_is_refused(zero: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="ladder_price_max"):
        create_trigger_to_proto(
            trigger_type="ladder", ladder_price_max=zero, ladder_levels=5, **_BASE
        )


def test_positive_ladder_prices_still_encode() -> None:
    proto = create_trigger_to_proto(
        trigger_type="ladder",
        ladder_price_min="1",
        ladder_price_max="100",
        ladder_levels=5,
        **_BASE,
    )
    assert proto.trigger.ladder.price_min_ticks == 1_000_000_000


@pytest.mark.parametrize("distance", [0, -5])
def test_modify_refuses_a_non_positive_trailing_distance(distance: int) -> None:
    with pytest.raises(PolyesterValidationError, match="trailing_distance_ticks"):
        modify_trigger_to_proto(trigger_id="2", trailing_distance_ticks=distance)


def test_modify_refuses_a_zero_trailing_distance_in_bps() -> None:
    with pytest.raises(PolyesterValidationError, match="trailing_distance_bps"):
        modify_trigger_to_proto(trigger_id="2", trailing_distance_bps=0)


@pytest.mark.parametrize("zero", _ZEROS)
def test_modify_refuses_a_zero_trigger_price(zero: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="trigger_price"):
        modify_trigger_to_proto(trigger_id="2", trigger_price=zero)


def test_modify_keeps_a_zero_activation_price_which_clears_it() -> None:
    proto = modify_trigger_to_proto(trigger_id="2", activation_price="0")
    assert proto.HasField("activation_price_ticks")
    assert proto.activation_price_ticks == 0


def test_modify_still_sends_valid_patches() -> None:
    proto = modify_trigger_to_proto(trigger_id="2", trailing_distance_ticks=1)
    assert proto.trailing_distance_ticks == 1
    proto = modify_trigger_to_proto(trigger_id="2", trailing_distance_bps=1)
    assert proto.trailing_distance_bps == 1


# --- zero prices on create -----------------------------------------------------------------------

_CREATE_ZERO_CASES: list[tuple[str, dict[str, Any]]] = [
    ("trigger_price", dict(trigger_type="stop_loss")),
    ("trigger_price", dict(trigger_type="take_profit")),
    ("limit_price", dict(trigger_type="stop_loss", trigger_price="10", order_type="limit")),
    (
        "limit_price",
        dict(trigger_type="stop_loss", trigger_price="10", order_type="limit", tif="ioc"),
    ),
    (
        "limit_price",
        dict(trigger_type="take_profit", trigger_price="10", order_type="limit", tif="fok"),
    ),
    (
        "limit_price",
        dict(
            trigger_type="twap",
            order_type="limit",
            twap_duration_ms=60_000,
            twap_slice_interval_ms=1_000,
        ),
    ),
    ("activation_price", dict(trigger_type="trailing_stop", trailing_distance_ticks=5)),
    (
        "limit_price",
        dict(trigger_type="trailing_stop", trailing_distance_ticks=5, side="buy"),
    ),
]


@pytest.mark.parametrize("zero", _ZEROS)
@pytest.mark.parametrize(("field", "kwargs"), _CREATE_ZERO_CASES)
def test_create_trigger_refuses_a_zero_price(field: str, kwargs: dict[str, Any], zero: Any) -> None:
    args = {**_BASE, **kwargs, field: zero}
    with pytest.raises(PolyesterValidationError, match=field):
        create_trigger_to_proto(**args)


def _order(**overrides: Any) -> CreateOrderRequest:
    fields: dict[str, Any] = dict(
        symbol="BTC-USDT",
        symbol_id=1,
        side="buy",
        order_type="limit",
        qty=Quantity.from_scaled(1, scale=8),
        price="10",
    )
    fields.update(overrides)
    return CreateOrderRequest(**fields)


@pytest.mark.parametrize("tif", ["gtc", "ioc", "fok"])
@pytest.mark.parametrize("zero", _ZEROS)
def test_create_order_refuses_a_zero_limit_price(zero: Any, tif: str) -> None:
    with pytest.raises(PolyesterValidationError, match="price"):
        create_order_to_proto(_order(price=zero, tif=tif), quantity_scale=8)


@pytest.mark.parametrize("zero", _ZEROS)
def test_create_order_to_wire_refuses_a_zero_limit_price(zero: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="price"):
        create_order_to_wire(_order(price=zero), quantity_scale=8)


@pytest.mark.parametrize(
    ("risk", "field"),
    [
        ({"take_profit": {"trigger_price": "0"}}, "trigger_price"),
        ({"stop_loss": {"trigger_price": "0.00"}}, "trigger_price"),
        (
            {"take_profit": {"trigger_price": "12", "order_type": "limit", "limit_price": "0"}},
            "limit_price",
        ),
        (
            {"stop_loss": {"trigger_price": "9", "child": {"limit_gtc": {"price": "0"}}}},
            "price",
        ),
        (
            {"trailing_stop": {"trailing_distance_ticks": 5, "activation_price": "0"}},
            "activation_price",
        ),
    ],
)
def test_attached_exits_refuse_a_zero_price(risk: dict[str, Any], field: str) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        create_order_to_proto(_order(attached_risk=risk), quantity_scale=8)


@pytest.mark.parametrize(
    ("take_profit", "stop_loss", "field"),
    [
        ({"trigger_price": "0"}, {"trigger_price": "9"}, "trigger_price"),
        ({"trigger_price": "12"}, {"trigger_price": Decimal("0")}, "trigger_price"),
        (
            {"trigger_price": "12", "order_type": "limit", "limit_price": "0"},
            {"trigger_price": "9"},
            "limit_price",
        ),
    ],
)
def test_oco_legs_refuse_a_zero_price(
    take_profit: dict[str, Any], stop_loss: dict[str, Any], field: str
) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        create_oco_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            side="sell",
            qty="1",
            take_profit=take_profit,
            stop_loss=stop_loss,
            quantity_scale=8,
        )


# --- ASCII-only public IDs and numbers -----------------------------------------------------------

_NON_ASCII_IDS = ["٥", "５", "٢٣", "２３", "๒๓", " 23", "23　", "2​3"]


@pytest.mark.parametrize("value", _NON_ASCII_IDS)
def test_public_id_with_a_non_ascii_character_is_refused(value: str) -> None:
    with pytest.raises(PolyesterValidationError, match="order_id"):
        id_to_int(value, "order_id")


def test_ascii_public_ids_decode_as_before() -> None:
    assert id_to_int("23", "order_id") == 60
    assert id_to_int("2nsoduvuPJr", "order_id") == id_to_int("2nsoduvuPJr", "x")
    assert id_to_int("18446744073709551615", "order_id") == 2**64 - 1
    assert id_to_int(23, "order_id") == 23


@pytest.mark.parametrize(
    "call",
    [
        lambda: create_order_to_proto(_order(sub_account_id="٢٣"), quantity_scale=8),
        lambda: modify_trigger_to_proto(trigger_id="٢٣", trailing_distance_ticks=1),
        lambda: modify_trigger_to_proto(trigger_id="2", sub_account_id="２３", trigger_price="1"),
    ],
)
def test_public_id_paths_refuse_non_ascii_digits(call: Callable[[], Any]) -> None:
    with pytest.raises(PolyesterValidationError):
        call()


@pytest.mark.parametrize("value", ["٥", "５", "²", " 5"])
def test_integer_strings_refuse_non_ascii_characters(value: str) -> None:
    with pytest.raises(PolyesterValidationError):
        tick_count(value, "trailing_distance_ticks")
    with pytest.raises(PolyesterValidationError):
        validate_bps(value, "trailing_distance_bps")
    with pytest.raises(PolyesterValidationError):
        parse_required_uint64_decimal(value, "nonce")


def test_ascii_integer_strings_still_parse() -> None:
    assert tick_count("5", "trailing_distance_ticks") == 5
    assert validate_bps("5", "trailing_distance_bps") == 5
    assert parse_required_uint64_decimal("5", "nonce") == 5


@pytest.mark.parametrize("value", ["٥", "１.5", "1.٥", " 1.5"])
def test_decimal_strings_refuse_non_ascii_characters(value: str) -> None:
    with pytest.raises(PolyesterValidationError, match="price"):
        decimal_to_scaled(value, 9, "price")


def test_ascii_decimal_strings_still_parse() -> None:
    assert decimal_to_scaled(" 1.5 ", 9, "price") == 1_500_000_000


async def test_trades_after_match_id_refuses_non_ascii_digits() -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="after_match_id"):
            await client.trades.list(symbol_id=1, after_match_id="٥")  # type: ignore[arg-type]
    assert requests == []


# --- settlement legs across execution pages ------------------------------------------------------


def _leg(tx_id: str, asset_id: int) -> OrderTransfer:
    return OrderTransfer(match_id="77", symbol_id=1, asset_id=asset_id, tx_id=tx_id)


async def _wait(pages: dict[str | None, GetOrderResult]) -> GetOrderResult:
    async def fake_get(**kwargs: Any) -> GetOrderResult:
        return pages[kwargs.get("page_token")]

    orders = AsyncMock()
    orders.get = AsyncMock(side_effect=fake_get)
    return await wait_for_order_trades_complete(
        orders, key=OrderId(9), timeout=2.0, poll_interval=0.01
    )


def _filled() -> Order:
    return Order(
        order_id="9", symbol_id=1, status="filled", cum_qty=Quantity.from_scaled(100, scale=6)
    )


async def test_legs_of_one_match_on_two_pages_are_kept_once() -> None:
    legs = [_leg("tx-77-base", 1), _leg("tx-77-quote", 2)]
    pages: dict[str | None, GetOrderResult] = {
        None: GetOrderResult(
            order=_filled(),
            trades=[UserTrade(symbol_id=1, match_id="77", qty=Quantity.from_scaled(60, scale=6))],
            transfers=list(legs),
            next_page_token="p2",
        ),
        "p2": GetOrderResult(
            order=_filled(),
            trades=[UserTrade(symbol_id=1, match_id="77", qty=Quantity.from_scaled(40, scale=6))],
            transfers=list(reversed(legs)),
            executions_complete=True,
        ),
    }
    result = await _wait(pages)
    assert len(result.trades) == 2
    assert [leg.tx_id for leg in result.transfers] == ["tx-77-base", "tx-77-quote"]


async def test_distinct_legs_across_pages_are_all_kept() -> None:
    pages: dict[str | None, GetOrderResult] = {
        None: GetOrderResult(
            order=_filled(),
            trades=[UserTrade(symbol_id=1, qty=Quantity.from_scaled(60, scale=6))],
            transfers=[_leg("tx-1", 1), _leg("", 2)],
            next_page_token="p2",
        ),
        "p2": GetOrderResult(
            order=_filled(),
            trades=[UserTrade(symbol_id=1, qty=Quantity.from_scaled(40, scale=6))],
            transfers=[_leg("tx-2", 1), _leg("tx-1", 1), _leg("", 2)],
            executions_complete=True,
        ),
    }
    result = await _wait(pages)
    # A leg without a tx_id has no identity to deduplicate by, so it is kept.
    assert [leg.tx_id for leg in result.transfers] == ["tx-1", "", "tx-2", ""]
