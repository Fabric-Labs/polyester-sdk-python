"""``polyester.pure`` builds the request ``orders.create`` and ``triggers.create`` send.

Each case runs the SDK's service method (the request it would send, captured)
and the pure builder of the same name on the same arguments: a request the SDK
sends is built field for field (``ParseDict`` into the real message, and its
``MessageToDict`` back), and a refusal is the same message, server code, field
violations and type. Cases are base requests, each crossed with one changed
argument at a time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.pure import polyester as pure
from tests.unit.pure_equivalence import (
    MARKET,
    SYMBOL,
    Expires,
    P,
    Q,
    assert_same,
    materialize,
    now_utc,
    pure_outcome,
    sdk_client,
    sdk_outcome,
)

_UNSET = object()

ORDER_BASES: dict[str, dict[str, Any]] = {
    "limit_gtc": dict(side="buy", order_type="limit", qty="0.5", price="100.25"),
    "limit_ioc_sell": dict(side="sell", order_type="limit", tif="ioc", qty="1", price="99"),
    "limit_fok": dict(side="buy", order_type="limit", tif="fok", qty="0.01", price="101.5"),
    "limit_gtd": dict(
        side="sell", order_type="limit", tif="gtd", qty="0.2", price="100", expires_at=Expires(3600)
    ),
    "market_qty": dict(side="buy", order_type="market", qty="0.3"),
    "market_debit": dict(side="buy", order_type="market", max_quote_debit="250"),
    "market_proceeds": dict(side="sell", order_type="market", quote_proceeds="80.5"),
    "ioc_debit": dict(side="buy", order_type="limit", tif="ioc", max_quote_debit="10", price="5"),
    "iceberg": dict(
        side="buy", order_type="limit", qty="2", price="50", display_qty="0.5", post_only=True
    ),
    "peg": dict(
        side="sell",
        order_type="limit",
        qty="1",
        price="90",
        peg={"reference": "best_ask", "offset_ticks": -2},
    ),
    "risk_sell": dict(
        side="sell",
        order_type="limit",
        qty="1",
        price="100",
        attached_risk={
            "take_profit": {"trigger_price": "80"},
            "trailing_stop": {"trailing_distance_bps": 50, "limit_price": "130"},
        },
    ),
    "risk_buy_oco": dict(
        side="buy",
        order_type="market",
        qty="1",
        attached_risk={
            "take_profit": {"trigger_price": "120", "order_type": "limit", "limit_price": "119"},
            "stop_loss": {"trigger_price": "90", "trigger_price_source": "index"},
            "oco": True,
        },
    ),
}

_RISK_VARIANTS: list[Any] = [
    {},
    {"take_profit": {"trigger_price": "120"}},
    {"takeProfit": {"triggerPrice": "120", "orderType": "LIMIT", "limitPrice": "121"}},
    {"stop_loss": {"trigger_price": "90", "order_type": "limit"}},
    {"stop_loss": {"trigger_price": "90", "order_type": "market", "limit_price": "1"}},
    {"stop_loss": {"trigger_price": "90", "order_type": "stop"}},
    {"take_profit": {"trigger_price": "120"}, "oco": True},
    {"take_profit": {"trigger_price": "120"}, "stop_loss": {"trigger_price": "90"}, "oco": "yes"},
    {"stop_loss": {"trigger_price": "1"}, "trailing_stop": {"trailing_distance_ticks": 5}},
    {"bogus": 1},
    "tp",
    {"take_profit": "120"},
    {"take_profit": {}},
    {"take_profit": {"trigger_price": "120.0000000001"}},
    {"take_profit": {"trigger_price": "0"}},
    {"take_profit": {"trigger_price": 120}},
    {"take_profit": {"trigger_price": 1.5}},
    {"take_profit": {"trigger_price": P(5, symbol="ETH-USDT")}},
    {"take_profit": {"trigger_price": P(5_000_000_000, symbol=SYMBOL)}},
    {"take_profit": {"trigger_price": "1", "trigger_price_ticks": 5}},
    {"take_profit": {"trigger_price_ticks": "500", "child": {"limit_gtc": {"price_ticks": 400}}}},
    {"take_profit": {"trigger_price_ticks": 0}},
    {"take_profit": {"trigger_price_ticks": True}},
    {"take_profit": {"trigger_price": "1", "child": {"execution": {}}}},
    {"take_profit": {"trigger_price": "1", "child": {"marketIoc": {}, "limitGtc": {}}}},
    {"take_profit": {"trigger_price": "1", "child": {"market_ioc": {"x": 1}}}},
    {"take_profit": {"trigger_price": "1", "child": {"market_ioc": 5}}},
    {
        "take_profit": {
            "trigger_price": "1",
            "child": {"limit_gtc": {"price": "1", "price_ticks": 1}},
        }
    },
    {"take_profit": {"trigger_price": "1", "child": {"limit_gtc": {}}}},
    {"take_profit": {"trigger_price": "1", "child": {"limit_gtc": {"price": "1.0000000001"}}}},
    {"take_profit": {"trigger_price": "1", "child": {"limit_gtc": {"price": "0"}}}},
    {"take_profit": {"trigger_price": "1", "child": {"limit_gtc": None}}},
    {"take_profit": {"trigger_price": "1", "child": {"foo": 1}}},
    {"take_profit": {"trigger_price": "1", "child": "x"}},
    {"take_profit": {"trigger_price": "1", "order_type": "limit", "child": {"market_ioc": {}}}},
    {"stop_loss": {"trigger_price": "1", "trigger_price_source": "mark"}},
    {"stop_loss": {"trigger_price": "1", "trigger_price_source": "LAST"}},
    {"stop_loss": {"trigger_price": "1", "trigger_price_source": "spot"}},
    {"trailing_stop": {"trailing_distance_ticks": 100}},
    {"trailing_stop": {"trailing_distance_ticks": 100, "limit_price": "130"}},
    {"trailing_stop": {"distance_bps": 10, "limit_price_ticks": 5}},
    {"trailing_stop": {"trailing_distance_bps": 10001, "limit_price": "1"}},
    {"trailing_stop": {"trailing_distance_ticks": 0, "limit_price": "1"}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "trailing_distance_bps": 1}},
    {"trailing_stop": {}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "order_type": "limit"}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "max_slippage_ticks": 3, "limit_price": "9"}},
    {
        "trailing_stop": {
            "trailing_distance_ticks": 1,
            "max_slippage_bps": 10000,
            "limit_price": "9",
        }
    },
    {"trailing_stop": {"trailing_distance_ticks": 1, "max_slippage_bps": 0, "limit_price": "9"}},
    {
        "trailing_stop": {
            "trailing_distance_ticks": 1,
            "max_slippage_ticks": 1,
            "max_slippage_bps": 1,
        }
    },
    {"trailing_stop": {"trailing_distance_ticks": 1, "activation_price": "10", "limit_price": "9"}},
    {
        "trailing_stop": {
            "trailing_distance_ticks": 1,
            "activation_price_ticks": 3,
            "limit_price": "9",
        }
    },
    {
        "trailing_stop": {
            "trailing_distance_ticks": 1,
            "activation_price": "1",
            "activationPriceTicks": 3,
        }
    },
    {"trailing_stop": {"trailing_distance_ticks": 1, "limit_price": "0"}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "limit_price": "1.0000000001"}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "limit_price": "1", "limit_price_ticks": 1}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "activation_price": "0.0000000001"}},
    {"trailing_stop": {"trailing_distance_ticks": 1, "trigger_price_source": "index"}},
    {"trailing_stop": "x"},
]

ORDER_MUTATIONS: list[tuple[str, Any]] = [
    *[("side", v) for v in ("buy", "sell", "BUY", "short", 5, _UNSET)],
    *[("order_type", v) for v in ("limit", "market", "stop", "MARKET", 1, _UNSET)],
    *[("tif", v) for v in (None, "gtc", "ioc", "fok", "gtd", "GTC", "", 3)],
    *[
        ("qty", v)
        for v in (
            "0.5",
            "1",
            "0",
            "-1",
            "0.00000001",
            "0.123456789",
            "0.1234567800",
            "1e3",
            " 0.5 ",
            "abc",
            "٥",
            "",
            0.5,
            5,
            True,
            Decimal("0.5"),
            Decimal("1E-9"),
            Decimal("1E-8"),
            Decimal("NaN"),
            Decimal("-1"),
            Decimal("1E+30"),
            Decimal("1E+80"),
            "92233720368.54775808",
            Q(50_000_000),
            Q(50_000_000, scale=6),
            Q(50_000_000, scale=None),
            Q(50_000_000, symbol="ETH-USDT"),
            Q(50_000_000, symbol_id=9),
            Q(0),
            Q(50_000_000, quote=True, scale=6),
            None,
        )
    ],
    *[
        ("price", v)
        for v in (
            "100",
            "100.123456789",
            "100.1234567891",
            "0",
            "0.000000001",
            "9223372036.854775807",
            "9223372036.854775808",
            Decimal("100.5"),
            P(10),
            P(0),
            P(10, symbol="ETH-USDT"),
            P(10, symbol=SYMBOL),
            100,
            1.5,
            None,
        )
    ],
    *[
        ("max_quote_debit", v)
        for v in (
            "100",
            "0.0000001",
            "1.5",
            Q(5, quote=True, scale=6),
            Q(5, quote=True, scale=None),
            Q(5, quote=True, scale=8),
            Q(5),
            1.5,
            100,
        )
    ],
    *[("quote_proceeds", v) for v in ("100", Q(5, quote=True, scale=6), Q(5, scale=6), 2.5)],
    *[("post_only", v) for v in (True, False, 1, None)],
    *[
        ("expires_at", v)
        for v in (
            Expires(3600),
            Expires(31 * 86400),
            Expires(-3600),
            "not a date",
            "2026-01-01T00:00:00",
            "",
            1700000000,
            None,
        )
    ],
    *[("fee_asset", v) for v in ("quote", "base", "BASE", "usd", 1)],
    *[("self_trade_prevention_mode", v) for v in ("expire_taker", "DECREMENT", "cancel", 1)],
    *[("max_slippage_ticks", v) for v in (5, "5", 0, -1, True, 2**63, " 5", 1.0)],
    *[("max_slippage_bps", v) for v in (1, 9999, 10000, 0, 10001, "50", True)],
    *[("market_client_ref_price", v) for v in ("100", "0", P(5), 1.5, "1.0000000001")],
    *[("display_qty", v) for v in ("0.1", "0", Q(10_000_000), 0.1, "0.000000001")],
    *[
        ("peg", v)
        for v in (
            {"reference": "best_bid"},
            {"reference": "BEST_ASK", "offsetTicks": 3},
            {"reference": "mid"},
            {"reference": "best_bid", "offset_ticks": 1.5},
            {"reference": "best_bid", "offset_ticks": False},
            {"reference": "best_bid", "offset_ticks": 2**63},
            {"reference": "best_bid", "extra": 1},
            {"offset_ticks": 1},
            {},
            "best_bid",
            None,
        )
    ],
    *[("attached_risk", v) for v in _RISK_VARIANTS],
    *[("symbol", v) for v in (SYMBOL, "ETH-USDT", "")],
    *[("symbol_id", v) for v in (7, 8, 0, -1, 2**32, "7", True, 7.0)],
    ("unexpected", 1),
]


def _order_cases() -> list[tuple[str, dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any]]] = []
    for base_name, base in ORDER_BASES.items():
        cases.append((base_name, {"symbol": SYMBOL, **base}))
        for index, (field, value) in enumerate(ORDER_MUTATIONS):
            args = {"symbol": SYMBOL, **base}
            if value is _UNSET:
                args.pop(field, None)
            else:
                args[field] = value
            cases.append((f"{base_name}-{field}-{index}", args))
    return cases


@pytest.fixture(scope="module")
async def client() -> AsyncIterator[AsyncPolyester]:
    async with sdk_client() as sdk:
        yield sdk


@pytest.mark.parametrize(
    ("name", "args"), _order_cases(), ids=lambda v: v if isinstance(v, str) else ""
)
async def test_orders_create_matches_the_sdk(client: AsyncPolyester, name: str, args: dict) -> None:
    now = now_utc()
    sdk = await sdk_outcome(lambda: client.orders.create(**materialize(args, sdk=True, now=now)))
    built = pure_outcome(
        lambda: pure.orders.create(MARKET, now=now, **materialize(args, sdk=False, now=now))
    )
    assert_same(sdk, built)


TRIGGER_BASES: dict[str, dict[str, Any]] = {
    "stop_market": dict(trigger_type="stop_loss", side="sell", qty="0.1", trigger_price="90"),
    "tp_limit": dict(
        trigger_type="take_profit",
        side="buy",
        qty="0.25",
        trigger_price="110",
        order_type="limit",
        limit_price="109.5",
    ),
    "stop_limit_ioc": dict(
        trigger_type="stop_loss",
        side="buy",
        qty="1",
        trigger_price="105",
        order_type="limit",
        limit_price="106",
        tif="ioc",
    ),
    "trailing_sell": dict(
        trigger_type="trailing_stop", side="sell", qty="0.5", trailing_distance_ticks=500_000_000
    ),
    "trailing_buy": dict(
        trigger_type="trailing_stop",
        side="buy",
        qty="0.5",
        trailing_distance_bps=25,
        limit_price="120",
        activation_price="110",
    ),
    "twap_market": dict(
        trigger_type="twap",
        side="buy",
        qty="3",
        twap_duration_ms=60_000,
        twap_slice_interval_ms=5_000,
    ),
    "twap_limit": dict(
        trigger_type="twap",
        side="sell",
        qty="3",
        order_type="limit",
        limit_price="99",
        twap_duration_ms=10_000,
        twap_slice_interval_ms=1_000,
    ),
    "ladder": dict(
        trigger_type="ladder",
        side="buy",
        qty="2",
        ladder_price_min="90",
        ladder_price_max="100",
        ladder_levels=5,
    ),
}

TRIGGER_MUTATIONS: list[tuple[str, Any]] = [
    *[("trigger_type", v) for v in ("stop_loss", "take-profit", "TWAP", "ladder", "oco", 1)],
    *[("side", v) for v in ("buy", "SELL", "hold", 1)],
    *[
        ("qty", v)
        for v in (
            "1",
            "0",
            "0.123456789",
            0.5,
            2,
            Decimal("0.25"),
            Q(10),
            Q(10, scale=6),
            Q(10, symbol="ETH-USDT"),
            Q(-1),
            "abc",
        )
    ],
    *[
        ("trigger_price", v)
        for v in ("100", "0", "100.0000000001", P(7), P(7, symbol="ETH-USDT"), 1.5, 100, None)
    ],
    *[("order_type", v) for v in ("limit", "market", "LIMIT", "stop", 1, None)],
    *[("limit_price", v) for v in ("50", "0", "1.0000000001", P(3), 2.5, None)],
    *[("trigger_price_source", v) for v in ("last", "index_price", "mark", "x", "", 1, None)],
    *[("tif", v) for v in ("gtc", "ioc", "fok", "gtd", "GTC", 1, None)],
    *[("post_only", v) for v in (True, False)],
    *[("fee_asset", v) for v in ("quote", "BASE", "x")],
    *[("self_trade_prevention_mode", v) for v in ("decrement", "x")],
    *[("trailing_distance_ticks", v) for v in (5, 0, "7", True, None)],
    *[("trailing_distance_bps", v) for v in (1, 10000, 10001, 0, None)],
    *[("activation_price", v) for v in ("100", "130", "0", P(1), None)],
    *[("max_slippage_ticks", v) for v in (5, 0, "3", -2)],
    *[("max_slippage_bps", v) for v in (1, 9999, 10000, 10001, 0, "x")],
    *[("twap_duration_ms", v) for v in (1000, 999, "60000", 60_000.0, True, 2**63, None)],
    *[("twap_slice_interval_ms", v) for v in (100, 99, 120_000, "5000", None)],
    *[("ladder_price_min", v) for v in ("95", "100", "0", P(1), None)],
    *[("ladder_price_max", v) for v in ("200", "90", "0", None)],
    *[("ladder_levels", v) for v in (2, 100, 1, 101, "5", 5.0, None)],
    *[("ladder_distribution", v) for v in ("linear", "LINEAR", "geometric")],
    *[("symbol", v) for v in (SYMBOL, "ETH-USDT", "")],
]


def _trigger_cases() -> list[tuple[str, dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any]]] = []
    for base_name, base in TRIGGER_BASES.items():
        cases.append((base_name, {"symbol": SYMBOL, **base}))
        for index, (field, value) in enumerate(TRIGGER_MUTATIONS):
            cases.append((f"{base_name}-{field}-{index}", {"symbol": SYMBOL, **base, field: value}))
    return cases


@pytest.mark.parametrize(
    ("name", "args"), _trigger_cases(), ids=lambda v: v if isinstance(v, str) else ""
)
async def test_triggers_create_matches_the_sdk(
    client: AsyncPolyester, name: str, args: dict
) -> None:
    now = now_utc()
    sdk = await sdk_outcome(lambda: client.triggers.create(**materialize(args, sdk=True, now=now)))
    built = pure_outcome(
        lambda: pure.triggers.create(MARKET, **materialize(args, sdk=False, now=now))
    )
    assert_same(sdk, built, generated=(("trigger.client_trigger_id", "trg-"),))
