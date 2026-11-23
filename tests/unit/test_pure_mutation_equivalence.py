"""``polyester.pure`` builds the requests of ``orders.modify``, ``orders.cancel``,
``triggers.create_oco``, ``triggers.cancel`` and ``triggers.modify`` as the SDK
sends them, and refuses as the SDK refuses.

As in ``test_pure_create_equivalence``: base requests, each with one argument
changed at a time, run through the SDK's service method and the pure builder.
IDs the SDK generates and the host fills instead (a modify's ``request_id``,
an OCO's ``client_list_id``) are checked for their prefix and left out.
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
    Key,
    P,
    Q,
    assert_same,
    materialize,
    now_utc,
    pure_outcome,
    sdk_client,
    sdk_outcome,
)
from tests.unit.test_pure_create_equivalence import _RISK_VARIANTS

_UNSET = object()
_KEYS = [
    Key("2gX"),
    Key(5),
    Key(2**64 - 1),
    Key(2**64),
    Key(0),
    Key("1"),
    Key("12gX"),
    Key("0OIl"),
    Key(""),
    Key(" 2gX"),
    Key(True),
    Key(None),
    Key("bot-1", client=True),
    Key("a" * 37, client=True),
    Key("bad id", client=True),
    Key("", client=True),
    Key(" x ", client=True),
    "2gX",
    None,
]
_PRICES = [
    "100",
    "100.5",
    "0",
    "-1",
    "0.0000000001",
    "abc",
    " 100 ",
    Decimal("0"),
    Decimal("99.25"),
    Decimal("NaN"),
    P(5),
    P(0),
    P(5, symbol="ETH-USDT"),
    100,
    0,
    -1,
    1.5,
    0.0,
    True,
]
_QTYS = [
    "1",
    "0.00000001",
    "0.000000001",
    "0",
    "-2",
    Decimal("0"),
    Decimal("2.5"),
    Q(10),
    Q(0),
    Q(10, scale=6),
    Q(10, quote=True, scale=8),
    Q(10, symbol_id=9),
    2,
    0,
    2.5,
    "x",
]


def _cases(
    bases: dict[str, dict[str, Any]], mutations: list[tuple[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any]]] = []
    for base_name, base in bases.items():
        cases.append((base_name, dict(base)))
        for index, (field, value) in enumerate(mutations):
            args = dict(base)
            if value is _UNSET:
                args.pop(field, None)
            else:
                args[field] = value
            cases.append((f"{base_name}-{field}-{index}", args))
    return cases


MODIFY_BASES: dict[str, dict[str, Any]] = {
    "price": dict(key=Key("2gX"), new_price="101.5"),
    "qty": dict(key=Key("bot-1", client=True), new_qty="0.75", behavior="amend_only"),
    "risk": dict(key=Key("2gX"), new_attached_risk={"take_profit": {"trigger_price": "120"}}),
    "clear": dict(key=Key(77), new_price="99", clear_attached_risk=True),
}
MODIFY_MUTATIONS: list[tuple[str, Any]] = [
    *[("key", value) for value in _KEYS],
    *[("new_price", value) for value in [*_PRICES, None]],
    *[("new_qty", value) for value in [*_QTYS, None]],
    *[("new_attached_risk", value) for value in [*_RISK_VARIANTS[:40], None]],
    *[("clear_attached_risk", value) for value in (True, False, 1, None)],
    *[("behavior", value) for value in ("amend_or_replace", "REPLACE_ONLY", "cancel", "", None)],
    *[("symbol", value) for value in (SYMBOL, "ETH-USDT", _UNSET)],
]

CANCEL_BASES: dict[str, dict[str, Any]] = {
    "order_id": dict(key=Key("2gX")),
    "client_id": dict(key=Key("bot-1", client=True)),
}
CANCEL_MUTATIONS: list[tuple[str, Any]] = [
    *[("key", value) for value in _KEYS],
    *[("symbol", value) for value in (SYMBOL, "ETH-USDT", "")],
    ("symbol_id", 7),
]

OCO_BASES: dict[str, dict[str, Any]] = {
    "sell": dict(
        side="sell",
        qty="0.5",
        take_profit={"trigger_price": "120"},
        stop_loss={"trigger_price": "90"},
    ),
    "buy_limit": dict(
        side="buy",
        qty=Q(25_000_000),
        take_profit={"trigger_price": "80", "order_type": "limit", "limit_price": "80.5"},
        stop_loss={"trigger_price_ticks": 110_000_000_000, "child": {"market_ioc": {}}},
        self_trade_prevention_mode="expire_both",
    ),
}
_LEGS: list[Any] = [
    {"trigger_price": "100"},
    {"trigger_price": "100", "trigger_price_source": "index"},
    {"trigger_price": "100", "trigger_price_source": "mark"},
    {"trigger_price": "100", "order_type": "limit"},
    {"trigger_price": "100", "order_type": "limit", "limit_price": "0"},
    {"trigger_price": "100", "order_type": "limit", "limit_price": "1.0000000001"},
    {"trigger_price": "100.0000000001"},
    {"trigger_price": "0"},
    {"trigger_price": 100},
    {"trigger_price_ticks": 0},
    {"trigger_price": P(5, symbol="ETH-USDT")},
    {"bogus": 1},
    {},
    "leg",
]
OCO_MUTATIONS: list[tuple[str, Any]] = [
    *[("side", value) for value in ("buy", "SELL", "hold", 1)],
    *[("qty", value) for value in _QTYS],
    *[("take_profit", value) for value in _LEGS],
    *[("stop_loss", value) for value in _LEGS],
    *[("self_trade_prevention_mode", value) for value in ("expire_maker", "DECREMENT", "x", None)],
    *[("symbol", value) for value in (SYMBOL, "ETH-USDT")],
]

TRIGGER_MODIFY_BASES: dict[str, dict[str, Any]] = {
    "price": dict(trigger_id="2gX", trigger_price="95"),
    "trailing": dict(trigger_id=99, trailing_distance_bps=40, max_slippage_ticks=0),
    "activation": dict(trigger_id="2gX", activation_price="0", max_slippage_bps=0),
}
TRIGGER_MODIFY_MUTATIONS: list[tuple[str, Any]] = [
    *[("trigger_id", value) for value in ("2gX", 1, 0, "1", "0OIl", "", -1, 2**64, True, 1.5)],
    *[("trigger_price", value) for value in [*_PRICES, None]],
    *[("activation_price", value) for value in [*_PRICES, None]],
    *[("trailing_distance_ticks", value) for value in (5, "6", 0, -1, True, None)],
    *[("trailing_distance_bps", value) for value in (1, 10000, 10001, 0, None)],
    *[("max_slippage_ticks", value) for value in (3, 0, "0", -1, None)],
    *[("max_slippage_bps", value) for value in (1, 10000, 10001, 0, -1, "x", None)],
]


@pytest.fixture(scope="module")
async def client() -> AsyncIterator[AsyncPolyester]:
    async with sdk_client() as sdk:
        yield sdk


def _ids(value: Any) -> str:
    return value if isinstance(value, str) else ""


@pytest.mark.parametrize(
    ("name", "args"),
    _cases({k: {"symbol": SYMBOL, **v} for k, v in MODIFY_BASES.items()}, MODIFY_MUTATIONS),
    ids=_ids,
)
async def test_orders_modify_matches_the_sdk(client: AsyncPolyester, name: str, args: dict) -> None:
    now = now_utc()
    sdk_args = materialize(args, sdk=True, now=now)
    sdk_args.setdefault("symbol", None)
    sdk = await sdk_outcome(lambda: client.orders.modify(**sdk_args))
    built = pure_outcome(
        lambda: pure.orders.modify(MARKET, **materialize(args, sdk=False, now=now))
    )
    if "symbol" not in args:
        # The SDK requires its symbol; the pure builder's market names it.
        assert sdk.error is not None
        sdk = await sdk_outcome(lambda: client.orders.modify(**{**sdk_args, "symbol": SYMBOL}))
    assert_same(sdk, built, generated=(("request_id", "mod-"),))


@pytest.mark.parametrize(("name", "args"), _cases(CANCEL_BASES, CANCEL_MUTATIONS), ids=_ids)
async def test_orders_cancel_matches_the_sdk(client: AsyncPolyester, name: str, args: dict) -> None:
    now = now_utc()
    # Without a market the request names none; with it, the market's.
    sdk = await sdk_outcome(lambda: client.orders.cancel(**materialize(args, sdk=True, now=now)))
    market = MARKET if "symbol" in args or "symbol_id" in args else None
    built = pure_outcome(
        lambda: pure.orders.cancel(market, **materialize(args, sdk=False, now=now))
    )
    assert_same(sdk, built)


@pytest.mark.parametrize(
    ("name", "args"),
    _cases({k: {"symbol": SYMBOL, **v} for k, v in OCO_BASES.items()}, OCO_MUTATIONS),
    ids=_ids,
)
async def test_triggers_create_oco_matches_the_sdk(
    client: AsyncPolyester, name: str, args: dict
) -> None:
    now = now_utc()
    sdk = await sdk_outcome(
        lambda: client.triggers.create_oco(**materialize(args, sdk=True, now=now))
    )
    built = pure_outcome(
        lambda: pure.triggers.create_oco(MARKET, **materialize(args, sdk=False, now=now))
    )
    assert_same(sdk, built, generated=(("oco.client_list_id", "oco-"),))


@pytest.mark.parametrize(
    "trigger_id", ["2gX", 1, 2**64 - 1, 0, "1", "0OIl", "", " 2gX", -1, 2**64, True, 1.5, None]
)
async def test_triggers_cancel_matches_the_sdk(client: AsyncPolyester, trigger_id: Any) -> None:
    sdk = await sdk_outcome(lambda: client.triggers.cancel(trigger_id=trigger_id))
    built = pure_outcome(lambda: pure.triggers.cancel(trigger_id=trigger_id))
    assert_same(sdk, built)


@pytest.mark.parametrize("with_market", [True, False])
@pytest.mark.parametrize(
    ("name", "args"), _cases(TRIGGER_MODIFY_BASES, TRIGGER_MODIFY_MUTATIONS), ids=_ids
)
async def test_triggers_modify_matches_the_sdk(
    client: AsyncPolyester, name: str, args: dict, with_market: bool
) -> None:
    now = now_utc()
    sdk_args = materialize(args, sdk=True, now=now)
    if with_market:
        sdk_args["symbol"] = SYMBOL
    sdk = await sdk_outcome(lambda: client.triggers.modify(**sdk_args))
    built = pure_outcome(
        lambda: pure.triggers.modify(
            MARKET if with_market else None, **materialize(args, sdk=False, now=now)
        )
    )
    assert_same(sdk, built)


_HOST_OWNED = [
    (
        pure.orders.create,
        {"side": "buy", "order_type": "limit", "qty": "1", "price": "1"},
        ("sub_account_id", "client_order_id"),
    ),
    (
        pure.orders.modify,
        {"key": pure.OrderId("2gX"), "new_price": "1"},
        ("sub_account_id", "request_id", "new_client_order_id"),
    ),
    (pure.orders.cancel, {"key": pure.OrderId("2gX")}, ("sub_account_id",)),
    (
        pure.triggers.create,
        {"trigger_type": "twap", "side": "buy", "qty": "1"},
        ("sub_account_id", "client_trigger_id"),
    ),
    (
        pure.triggers.create_oco,
        {
            "side": "sell",
            "qty": "1",
            "take_profit": {"trigger_price": "2"},
            "stop_loss": {"trigger_price": "1"},
        },
        ("sub_account_id", "client_list_id"),
    ),
    (pure.triggers.modify, {"trigger_id": "2gX", "trigger_price": "1"}, ("sub_account_id",)),
]


@pytest.mark.parametrize(
    ("builder", "args", "field"),
    [(builder, args, field) for builder, args, fields in _HOST_OWNED for field in fields],
)
def test_host_owned_fields_are_refused(builder: Any, args: dict, field: str) -> None:
    """The host fills who the caller is and which attempt this is."""
    with pytest.raises(ValueError) as refused:
        builder(MARKET, **args, **{field: "x"})
    assert str(refused.value) == f"{field} is assigned by the host; leave it out"


def test_trigger_cancel_refuses_a_sub_account() -> None:
    assert pure.triggers.cancel(trigger_id="2gX") == {"triggerId": "5656"}
    with pytest.raises(ValueError, match="sub_account_id is assigned by the host"):
        pure.triggers.cancel(trigger_id="2gX", sub_account_id="x")
