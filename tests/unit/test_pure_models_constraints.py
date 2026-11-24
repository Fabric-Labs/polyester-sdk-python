"""``polyester/pure_models.py`` stays inside what a restricted runtime with no C
extensions runs, and inside its size budget.

The rules are ``polyester/pure.py``'s (``test_pure_constraints.problems``),
with ``polyester_models`` as the one top-level name. The file reads nothing
from outside its factory but ``polyester`` (pure.py's namespace) and builtins,
and those only while it loads, so code defined after it cannot reach its own
code.
"""

from __future__ import annotations

import ast
import builtins
from typing import Any

import pytest

from tests.unit import pure_models_support as support
from tests.unit.test_pure_constraints import problems

SOURCE = support.SOURCE
NAME = "polyester_models"
# 24 KiB: each source KB costs about 2.3 KB in every warm bot session.
MAX_BYTES = 24 * 1024


def _factory() -> ast.FunctionDef:
    return next(node for node in ast.parse(SOURCE).body if isinstance(node, ast.FunctionDef))


def _bound(node: ast.AST) -> set[str]:
    """Every name ``node`` binds, at any depth."""
    names: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, (ast.FunctionDef, ast.ClassDef)):
            names.add(item.name)
        elif isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
            names.add(item.id)
        elif isinstance(item, ast.arg):
            names.add(item.arg)
        elif isinstance(item, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in item.names)
    return names


ANNOTATION_NAMES = frozenset(
    {node.name for node in _factory().body if isinstance(node, ast.ClassDef)}
    | {"_Price", "_Quantity", "_Decimal", "_datetime"}
)


def test_pure_models_uses_only_what_the_restricted_runtime_runs() -> None:
    assert problems(SOURCE, NAME, ANNOTATION_NAMES) == []


def test_polyester_models_is_the_only_top_level_name() -> None:
    tree = ast.parse(SOURCE)
    assert len(tree.body) == 3  # docstring, factory, its call
    assert ast.unparse(tree.body[2]) == f"{NAME} = {NAME}()"
    namespace = support.load()
    assert [name for name in namespace if not name.startswith("__")] == ["polyester", NAME]


@pytest.mark.parametrize("snippet", ["_helper = 1", "def _f(): pass", "polyester = 1"])
def test_a_second_top_level_name_is_refused(snippet: str) -> None:
    assert problems(SOURCE + "\n\n" + snippet + "\n", NAME, ANNOTATION_NAMES) != []


def test_a_foreign_annotation_is_refused() -> None:
    marker = "  @_dataclass\n  class OrderFeeTotal:\n"
    assert SOURCE.count(marker) == 1
    source = SOURCE.replace(marker, marker + "    other: _Market | None = None\n")
    assert problems(source, NAME, ANNOTATION_NAMES) != []


def _free_loads(node: ast.AST, bound: set[str]) -> list[ast.Name]:
    return [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id not in bound
    ]


def _late_reads(source: str) -> list[str]:
    factory = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef))
    bound = _bound(factory)
    late = []
    for statement in factory.body:
        if isinstance(statement, ast.FunctionDef):
            late += _free_loads(statement, bound)
        elif isinstance(statement, ast.ClassDef):
            for member in statement.body:
                if isinstance(member, ast.FunctionDef):
                    late += _free_loads(member, bound)
    return [ast.unparse(item) for item in late]


def test_outside_names_are_read_only_while_the_file_loads() -> None:
    """``polyester`` and the builtins are read by the factory's own statements
    (its imports and ``_name = name`` bindings) and class annotations, which
    run as the file loads, never by the decoders when a bot calls them."""
    factory = _factory()
    bound = _bound(factory)
    free = {item.id for item in _free_loads(factory, bound)}
    assert free - set(dir(builtins)) == {"polyester"}
    assert _late_reads(SOURCE) == []


@pytest.mark.parametrize(
    ("old", "new"),
    [("  len=len,\n", ""), ("_Price.from_ticks", "polyester.Price.from_ticks")],
)
def test_a_late_read_is_caught(old: str, new: str) -> None:
    assert old in SOURCE
    assert _late_reads(SOURCE.replace(old, new)) != []


def test_size_budget() -> None:
    size = len(SOURCE.encode("utf-8"))
    print(f"polyester/pure_models.py is {size} bytes of {MAX_BYTES}")
    assert size < MAX_BYTES, f"polyester/pure_models.py is {size} bytes, over {MAX_BYTES}"


def test_no_version_to_stamp() -> None:
    """The release stamps pure.py's ``_VERSION``; this file carries none."""
    assert "VERSION" not in SOURCE


def test_the_loaded_models_are_the_files() -> None:
    models: Any = support.load()[NAME]
    assert models.Order.__name__ == "Order"
    assert callable(models.order) and callable(models.trigger)
