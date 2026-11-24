"""``polyester/pure_models.py`` runs in pydantic-monty, a restricted Python
interpreter with no C extensions, loaded after ``polyester/pure.py``, and
decodes there what it decodes in CPython.

Every case of the equivalence matrix (``pure_models_support.matrix``, as
canonical proto-JSON and with every field written) is decoded in the
interpreter and in CPython over the same files: the same models (compared by
``repr``) or the same refusal. The SDK equivalence tests hold the CPython
results to the SDK. Decoding is deterministic, and names defined after the
files load (theirs, pure.py's, ``polyester`` itself and every builtin) do not
change it.
"""

from __future__ import annotations

import ast
import builtins
import keyword
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest
from pydantic_monty import Monty

from tests.unit import pure_models_support as support

# The runner binds what it uses before the shadowing code runs, as the files do.
RUNNER = """
def _rt_factory():
  _models = polyester_models
  _repr = repr
  _str = str
  _ValueError = ValueError

  def run(cases, spec):
    results = []
    for kind, data, bound in cases:
      decode = _models.order if kind == "order" else _models.trigger
      try:
        results.append(["ok", _repr(decode(data, spec if bound else None))])
      except _ValueError as exc:
        results.append(["error", _str(exc)])
    return results

  return run


_rt_run = _rt_factory()
"""
CALL = "_rt_run(rt_cases, rt_spec)"
_LOCALS = re.compile(r"\b[A-Za-z_]+\.<locals>\.")


def matrix() -> list[list[Any]]:
    cases = []
    for message in support.matrix():
        kind = "order" if message.DESCRIPTOR.name == "Order" else "trigger"
        bound = support.binds(message)
        cases.append([kind, support.to_dict(message), bound])
        cases.append([kind, support.to_dict(message, all_fields=True), bound])
    return cases


CASES = matrix()


def _normalize(results: Any) -> list[list[str]]:
    # CPython names a class defined in a function by its qualified name.
    return [[kind, _LOCALS.sub("", text)] for kind, text in results]


def _cpython(cases: list[list[Any]], shadow: str = "") -> list[list[str]]:
    namespace = support.load(RUNNER + "\n" + shadow)
    namespace.update(rt_cases=cases, rt_spec=support.SPEC)
    return _normalize(eval(CALL, namespace))  # noqa: S307 - the runner under test


@pytest.fixture(scope="module")
def monty() -> Iterator[Monty]:
    with Monty() as pool:
        yield pool


def _in_monty(pool: Monty, cases: list[list[Any]], shadow: str = "", **policy: Any) -> Any:
    checkout = pool.checkout(os_policy=policy) if policy else pool.checkout()
    with checkout as session:
        session.feed_run(support.PURE_SOURCE)
        session.feed_run(support.SOURCE)
        session.feed_run(RUNNER)
        if shadow:
            session.feed_run(shadow)
        results = session.feed_run(CALL, inputs={"rt_cases": cases, "rt_spec": support.SPEC})
    return _normalize(results)


@pytest.fixture(scope="module")
def expected() -> list[list[str]]:
    return _cpython(CASES)


def test_the_matrix_decodes_the_same_in_the_restricted_runtime(
    monty: Monty, expected: list[list[str]]
) -> None:
    got = _in_monty(monty, CASES)
    assert len(got) == len(expected) == len(CASES)
    mismatched = [
        (case, want, have)
        for case, want, have in zip(CASES, expected, got, strict=True)
        if want != have
    ]
    assert mismatched == []
    assert {kind for kind, _ in got} == {"ok", "error"}


SAMPLE_BOT = """
from datetime import datetime, timezone
from decimal import Decimal

pair = {"symbol": "BTC-USDT", "symbolId": 7, "baseQuantityScale": 8, "quoteQuantityScale": 6}
fills = []


def on_order(data):
  order = polyester_models.order(data, pair)
  if order.status == "working" and order.cum_qty.as_decimal() > 0:
    fills.append([order.order_id, str(order.cum_qty.as_decimal()), order.price.format()])
  if order.attached_risk is not None and order.attached_risk.stop_loss is not None:
    stop = order.attached_risk.stop_loss.trigger_price
    return polyester.orders.modify(pair, key=polyester.OrderId(order.order_id), new_price=stop)
  return None


def on_trigger(data):
  trigger = polyester_models.trigger(data, pair)
  created = trigger.created_at.isoformat()
  return [trigger.trigger_type, trigger.status, trigger.qty.format(), created]


modify = on_order({
  "orderId": "9", "symbolId": 7, "side": "BUY", "status": "WORKING", "orderType": "LIMIT",
  "origQtyScaled": "25000000", "cumQtyScaled": "10000000", "priceTicks": "64000500000000",
  "attachedRisk": {"stopLoss": {"policy": {"triggerPriceTicks": "63000000000000"}}},
})
seen = on_trigger({
  "triggerId": "5", "symbolId": 7, "status": "STATUS_ARMED", "qtyScaled": "25000000",
  "trailingStop": {"side": "SELL", "trailingDistanceBps": 150},
  "createdAt": "2026-11-24T12:00:00.250Z",
})
[fills, modify, seen, isinstance(polyester_models.order({}).orig_qty, polyester.Quantity)]
"""


def test_a_sample_bot_runs_in_the_restricted_runtime(monty: Monty) -> None:
    with monty.checkout() as session:
        session.feed_run(support.PURE_SOURCE)
        session.feed_run(support.SOURCE)
        fills, modify, seen, typed = session.feed_run(SAMPLE_BOT)
    assert fills == [["A", "0.1", "64000.5"]]
    assert modify == {"symbolId": 7, "orderId": "9", "newPriceTicks": "63000000000000"}
    assert seen == ["trailing_stop", "armed", "0.25", "2026-11-24T12:00:00.250000+00:00"]
    assert typed is True


def test_decoding_is_deterministic(monty: Monty, expected: list[list[str]]) -> None:
    cases = CASES[::7]
    first = _in_monty(monty, cases, datetime=datetime(2001, 1, 1), random_start={"seed": 1})
    second = _in_monty(monty, cases, datetime=datetime(2049, 6, 6), random_start={"seed": 2})
    assert first == second == expected[::7]


def _factory_names(source: str) -> set[str]:
    """Every name a file defines inside its factory, at any depth."""
    factory = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef))
    names: set[str] = set()
    for node in ast.walk(factory):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _shadowing_code(names: set[str]) -> str:
    """Code a bot or a host prelude might run after loading the files: its own
    definitions of ``names``, and of the pair of top-level names."""
    lines = [f"{name} = None" for name in sorted(names)]
    lines += [
        "polyester = None",
        "polyester_models = None",
        "class Order:",
        "  pass",
        "def _price(*args, **kwargs):",
        "  raise RuntimeError('a bot helper')",
        "def _label(value):",
        "  return 'bot'",
    ]
    return "\n".join(lines) + "\n"


FILE_NAMES = _factory_names(support.SOURCE) | _factory_names(support.PURE_SOURCE)
BUILTIN_NAMES = {
    name
    for name in dir(builtins)
    if name.isidentifier() and not keyword.iskeyword(name) and not name.startswith("__")
}


def test_names_defined_after_loading_do_not_change_the_decoders(
    monty: Monty, expected: list[list[str]]
) -> None:
    """Both files' own names, ``polyester`` and ``polyester_models``."""
    assert len(FILE_NAMES) > 150
    shadow = _shadowing_code(FILE_NAMES)
    assert _in_monty(monty, CASES, shadow) == expected
    # One shared namespace in CPython too: the files, the runner, then the shadowing code.
    assert _cpython(CASES, shadow) == expected


def test_this_file_reads_no_builtin_late(expected: list[list[str]]) -> None:
    """With pure.py in a namespace of its own, so its functions keep their
    builtins, every builtin and name defined after this file loads, in the
    namespace it shares with the bot, leaves the decoders unchanged."""
    pure_namespace: dict[str, Any] = {}
    exec(compile(support.PURE_SOURCE, str(support.PURE_PATH), "exec"), pure_namespace)  # noqa: S102
    namespace: dict[str, Any] = {"polyester": pure_namespace["polyester"]}
    source = support.SOURCE + "\n" + RUNNER + "\n" + _shadowing_code(FILE_NAMES | BUILTIN_NAMES)
    exec(compile(source, str(support.MODELS_PATH), "exec"), namespace)  # noqa: S102
    namespace.update(rt_cases=CASES, rt_spec=support.SPEC)
    assert _normalize(eval(CALL, namespace)) == expected  # noqa: S307


def test_builtins_defined_after_loading_do_not_change_the_decoders(
    monty: Monty, expected: list[list[str]]
) -> None:
    """Every builtin a bot could define, ``type = "limit"`` say, as well.

    pure.py's functions, which this file calls, must bind the builtins they
    use as they load, as this file does."""
    shadow = _shadowing_code(FILE_NAMES | BUILTIN_NAMES)
    cases = CASES[::5]
    assert _in_monty(monty, cases, shadow) == expected[::5]
    assert _cpython(cases, shadow) == expected[::5]
