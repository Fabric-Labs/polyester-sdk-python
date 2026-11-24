"""``polyester/pure.py`` runs in pydantic-monty, a restricted Python interpreter
with no C extensions, and builds there what it builds in CPython.

The whole file is fed to the interpreter, then a runner calls each builder for
every case of the equivalence matrices. The same runner runs in CPython over
the same file: each case builds the same request, or raises the same error type
with the same message (the interpreter's exceptions carry no server code).
Builders are deterministic: frozen clocks and entropy seeds change nothing.
"""

from __future__ import annotations

import ast
import json
import operator
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic_monty import Monty

from polyester import pure
from tests.unit import test_pure_create_equivalence as create_cases
from tests.unit import test_pure_mutation_equivalence as mutation_cases
from tests.unit.pure_equivalence import MARKET, Expires, Key, P, Q

SOURCE = Path(pure.__file__).read_text(encoding="utf-8")
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)

RUNNER = """
from datetime import datetime as _rt_datetime
from decimal import Decimal as _rt_Decimal
import json as _rt_json


def _rt_decode(value):
  if isinstance(value, list) and value and value[0] == "$D":
    return _rt_Decimal(value[1])
  if isinstance(value, list) and value and value[0] == "$PR":
    return polyester.Price(value[1], value[2])
  if isinstance(value, list) and value and value[0] == "$QR":
    return polyester.Quantity(value[1], value[2], value[3], value[4], value[5])
  if isinstance(value, list) and value and value[0] == "$P":
    return polyester.Price.from_ticks(value[1], symbol=value[2])
  if isinstance(value, list) and value and value[0] == "$Q":
    return polyester.Quantity.from_scaled(
      value[1], scale=value[2], domain=value[3], symbol=value[4], symbol_id=value[5])
  if isinstance(value, list) and value and value[0] == "$K":
    return polyester.OrderId(value[1])
  if isinstance(value, list) and value and value[0] == "$C":
    return polyester.ClientOrderId(value[1])
  if isinstance(value, dict):
    return {key: _rt_decode(item) for key, item in value.items()}
  return value


def _rt_build(builder, args, now, market):
  if builder == "orders.create":
    return polyester.orders.create(market, now=now, **args)
  if builder == "orders.modify":
    return polyester.orders.modify(market, **args)
  if builder == "orders.cancel":
    return polyester.orders.cancel(market, **args)
  if builder == "triggers.create":
    return polyester.triggers.create(market, **args)
  if builder == "triggers.create_oco":
    return polyester.triggers.create_oco(market, **args)
  if builder == "triggers.modify":
    return polyester.triggers.modify(market, **args)
  return polyester.triggers.cancel(market, **args)


def _rt_run(cases, now_text):
  now = _rt_datetime.fromisoformat(now_text)
  results = []
  for builder, args, with_market in cases:
    try:
      built = _rt_build(builder, _rt_decode(args), now, rt_market if with_market else None)
      results.append(["ok", _rt_json.dumps(built, sort_keys=True)])
    except Exception as exc:
      message = str(exc) if isinstance(exc, ValueError) else ""
      results.append(["error", type(exc).__name__, message])
  return results


_rt_run(rt_cases, rt_now)
"""


def _encode(value: Any) -> Any:
    """A case argument as plain data either interpreter takes as input."""
    if isinstance(value, int) and type(value) not in (int, bool):
        # The runtime has no int subclasses: its value, as the SDK reads it.
        return operator.index(value)
    if isinstance(value, Key):
        return ["$C" if value.client else "$K", _encode(value.value)]
    if isinstance(value, Decimal):
        return ["$D", str(value)]
    if isinstance(value, P):
        return ["$PR" if value.raw else "$P", _encode(value.ticks), value.symbol]
    if isinstance(value, Q):
        domain = "order_quote" if value.quote else "order_base"
        tag = "$QR" if value.raw else "$Q"
        return [tag, _encode(value.scaled), value.scale, domain, value.symbol, value.symbol_id]
    if isinstance(value, Key):
        return ["$C" if value.client else "$K", value.value]
    if isinstance(value, Expires):
        return (NOW + timedelta(seconds=value.seconds)).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value


def matrix() -> list[list[Any]]:
    cases: list[list[Any]] = []
    for _, args in create_cases._order_cases():
        cases.append(["orders.create", _encode(args), True])
    for _, args in create_cases._trigger_cases():
        cases.append(["triggers.create", _encode(args), True])
    for builder, bases, mutations in (
        ("orders.modify", mutation_cases.MODIFY_BASES, mutation_cases.MODIFY_MUTATIONS),
        ("triggers.create_oco", mutation_cases.OCO_BASES, mutation_cases.OCO_MUTATIONS),
    ):
        for _, args in mutation_cases._cases(bases, mutations):
            cases.append([builder, _encode(args), True])
    for _, args in mutation_cases._cases(
        mutation_cases.CANCEL_BASES, mutation_cases.CANCEL_MUTATIONS
    ):
        cases.append(["orders.cancel", _encode(args), "symbol" in args or "symbol_id" in args])
    for _, args in mutation_cases._cases(
        mutation_cases.TRIGGER_MODIFY_BASES, mutation_cases.TRIGGER_MODIFY_MUTATIONS
    ):
        cases.append(["triggers.modify", _encode(args), True])
        cases.append(["triggers.modify", _encode(args), False])
        for market in (True, False):
            cases.append(["triggers.cancel", _encode({"trigger_id": args["trigger_id"]}), market])
    return cases


def _cpython(cases: list[list[Any]], now: datetime) -> list[list[Any]]:
    namespace: dict[str, Any] = {}
    exec(compile(SOURCE, "pure.py", "exec"), namespace)  # noqa: S102 - the file under test
    namespace.update(
        rt_cases=json.loads(json.dumps(cases)), rt_now=now.isoformat(), rt_market=MARKET
    )
    body, _, last = RUNNER.rstrip().rpartition("\n")
    exec(compile(body, "runner", "exec"), namespace)  # noqa: S102
    return eval(last, namespace)  # noqa: S307


@pytest.fixture(scope="module")
def monty() -> Iterator[Monty]:
    with Monty() as pool:
        yield pool


def _in_monty(pool: Monty, cases: list[list[Any]], now: datetime, **policy: Any) -> Any:
    checkout = pool.checkout(os_policy=policy) if policy else pool.checkout()
    with checkout as session:
        session.feed_run(SOURCE)
        return session.feed_run(
            RUNNER,
            inputs={"rt_cases": cases, "rt_now": now.isoformat(), "rt_market": MARKET},
        )


def test_the_matrix_builds_the_same_in_the_restricted_runtime(monty: Monty) -> None:
    cases = matrix()
    expected = _cpython(cases, NOW)
    got = [list(result) for result in _in_monty(monty, cases, NOW)]
    assert len(got) == len(expected) == len(cases)
    mismatched = [
        (case, want, have)
        for case, want, have in zip(cases, expected, got, strict=True)
        if want != have
    ]
    assert mismatched == []
    # The matrix builds requests, and refuses, in both.
    assert {result[0] for result in got} == {"ok", "error"}


SAMPLE_BOT = """
from datetime import datetime, timedelta, timezone
from decimal import Decimal

pair = {"symbol": "BTC-USDT", "symbolId": 7, "baseQuantityScale": 8, "quoteQuantityScale": 6}
m = polyester.market(pair)
now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
entry = polyester.orders.create(
  m, side="buy", order_type="limit", tif="gtd", qty=m.qty(Decimal("0.25")),
  price=m.price("64000.5"), expires_at=timedelta(minutes=30), now=now,
  attached_risk={"take_profit": {"trigger_price": "66000"},
                 "stop_loss": {"trigger_price": "63000"}})
stop = polyester.triggers.create(
  m, trigger_type="trailing_stop", side="sell", qty="0.25", trailing_distance_bps=150)
oco = polyester.triggers.create_oco(
  m, side="sell", qty="0.25", take_profit={"trigger_price": "66000"},
  stop_loss={"trigger_price": "63000", "order_type": "limit", "limit_price": "62900"})
move = polyester.orders.modify(m, key=polyester.OrderId("2gX"), new_price=m.price("64010"))
gone = polyester.orders.cancel(m, key=polyester.ClientOrderId("bot-1"))
try:
  polyester.orders.create(m, side="buy", order_type="limit", qty=0.25, price="1")
  refused = ""
except polyester.ValidationError as exc:
  refused = str(exc)
[entry, stop, oco, move, gone, refused, polyester.VERSION, repr(m.price("1.5"))]
"""


def test_a_sample_bot_runs_in_the_restricted_runtime(monty: Monty) -> None:
    with monty.checkout() as session:
        session.feed_run(SOURCE)
        entry, stop, oco, move, gone, refused, version, price = session.feed_run(SAMPLE_BOT)
    assert entry["order"]["limitGtd"] == {
        "priceTicks": "64000500000000",
        "expireAt": "2026-11-24T12:30:00Z",
    }
    assert entry["order"]["baseQtyScaled"] == "25000000"
    assert set(entry["order"]["attachedRisk"]) == {"takeProfit", "stopLoss"}
    assert stop == {
        "trigger": {
            "symbolId": 7,
            "qtyScaled": "25000000",
            "trailingStop": {"side": "SELL", "trailingDistanceBps": 150},
        }
    }
    assert oco["oco"]["stopLoss"]["child"] == {"limitGtc": {"priceTicks": "62900000000000"}}
    assert move == {"symbolId": 7, "orderId": "5656", "newPriceTicks": "64010000000000"}
    assert gone == {"clientOrderId": "bot-1", "symbolId": 7}
    assert refused == (
        "qty must be a decimal string, Decimal, or typed scaled value (floats are not allowed)"
    )
    assert version == pure.polyester.VERSION
    assert price == "Price(ticks=1500000000, symbol='BTC-USDT')"


def test_builders_are_deterministic(monty: Monty) -> None:
    cases = matrix()[::7]
    first = _in_monty(monty, cases, NOW, datetime=datetime(2001, 1, 1), random_start={"seed": 1})
    second = _in_monty(monty, cases, NOW, datetime=datetime(2049, 6, 6), random_start={"seed": 2})
    assert first == second
    assert _cpython(cases, NOW) == _cpython(cases, NOW)


def _factory_names() -> list[str]:
    """Every name ``polyester.pure`` defines inside its factory."""
    factory = next(node for node in ast.parse(SOURCE).body if isinstance(node, ast.FunctionDef))
    names: set[str] = set()
    for node in factory.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in node.names)
    return sorted(names)


def _shadowing_code() -> str:
    """Code a bot or a host prelude might run after loading the file: its own
    definitions of every name the file uses inside."""
    lines = [f"{name} = None" for name in _factory_names()]
    lines += [
        "class _Market:",
        "  pass",
        "class Market:",
        "  pass",
        "def _err(*args, **kwargs):",
        "  raise RuntimeError('a bot helper')",
        "def _int(value):",
        "  return 1",
        "def _market(spec):",
        "  return _Market()",
    ]
    return "\n".join(lines) + "\n"


def test_names_defined_after_loading_do_not_change_the_builders(monty: Monty) -> None:
    cases = matrix()
    assert len(_factory_names()) > 100
    expected = _cpython(cases, NOW)
    with monty.checkout() as session:
        session.feed_run(SOURCE)
        session.feed_run(_shadowing_code())
        got = session.feed_run(
            RUNNER,
            inputs={"rt_cases": cases, "rt_now": NOW.isoformat(), "rt_market": MARKET},
        )
    assert [list(result) for result in got] == expected
    # One shared namespace in CPython too: the file, then the shadowing code.
    namespace: dict[str, Any] = {}
    exec(compile(SOURCE + "\n" + _shadowing_code(), "shared", "exec"), namespace)  # noqa: S102
    namespace.update(
        rt_cases=json.loads(json.dumps(cases)), rt_now=NOW.isoformat(), rt_market=MARKET
    )
    body, _, last = RUNNER.rstrip().rpartition("\n")
    exec(compile(body, "runner", "exec"), namespace)  # noqa: S102
    assert eval(last, namespace) == expected  # noqa: S307
