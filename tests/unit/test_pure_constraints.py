"""``polyester/pure.py`` stays inside what a restricted runtime with no C extensions runs.

The file is read with ``ast``: standard-library imports from an allowed list,
aliased private; one public name; no construct the runtime lacks (inheritance,
method decorators, generators, ``del``, ``global``, annotations of non-builtin
types, dunder access, float literals, clocks or entropy); nothing but
definitions at module level; and a size budget. Each rule is shown to catch
the construct it bans.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import polyester
from polyester import pure

SOURCE = Path(pure.__file__).read_text(encoding="utf-8")
MAX_BYTES = 80 * 1024

ALLOWED_MODULES = {
    "bisect",
    "collections",
    "copy",
    "dataclasses",
    "datetime",
    "decimal",
    "functools",
    "itertools",
    "json",
    "math",
    "re",
}
# Builtins the runtime lacks, or that reach outside the call (I/O, introspection).
BANNED_NAMES = {
    "__import__",
    "abc",
    "breakpoint",
    "bytearray",
    "callable",
    "classmethod",
    "compile",
    "delattr",
    "dir",
    "enum",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "memoryview",
    "open",
    "os",
    "print",
    "property",
    "random",
    "staticmethod",
    "super",
    "sys",
    "time",
    "typing",
    "vars",
}
# Attributes the runtime lacks, and every clock and entropy source.
BANNED_ATTRIBUTES = {
    "bit_length",
    "fromtimestamp",
    "monotonic",
    "now",
    "perf_counter",
    "random",
    "today",
    "urandom",
    "utcfromtimestamp",
    "utcnow",
}
BANNED_NODES = (
    ast.Assert,
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.Delete,
    ast.Global,
    ast.Match,
    ast.Nonlocal,
    ast.TryStar,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
DUNDER_METHODS = {"__repr__"}
BUILTIN_TYPES = {"int", "str", "bool", "dict", "list", "tuple", "set", "None"}


def _at(node: ast.AST) -> str:
    return f"line {getattr(node, 'lineno', '?')}: {ast.unparse(node)[:80]}"


def _static(node: ast.AST) -> bool:
    """A value computed from literals alone, at no more cost than a literal."""
    if isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.Attribute):
        return _static(node.value)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_static(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(_static(item) for item in [*node.keys, *node.values] if item is not None)
    if isinstance(node, ast.BinOp):
        return _static(node.left) and _static(node.right)
    if isinstance(node, ast.UnaryOp):
        return _static(node.operand)
    if isinstance(node, ast.Call):
        func = node.func
        if ast.unparse(func) == "_re.compile":
            return all(isinstance(arg, ast.Constant) for arg in node.args)
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "split"
            and isinstance(func.value, ast.Constant)
            and not node.args
        )
    return False


def _annotation_ok(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in BUILTIN_TYPES
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _annotation_ok(node.left) and _annotation_ok(node.right)
    if isinstance(node, ast.Subscript):
        inner = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        return _annotation_ok(node.value) and all(_annotation_ok(item) for item in inner)
    return False


def _public_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.extend(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.extend(alias.asname or alias.name for alias in node.names)
    return [name for name in names if not name.startswith("_")]


def problems(source: str) -> list[str]:
    """Every construct in ``source`` the restricted runtime does not take."""
    tree = ast.parse(source)
    found: list[str] = []
    if _public_names(tree) != ["polyester"]:
        found.append(f"public names {_public_names(tree)}")
    top = {id(node) for node in tree.body}
    for node in ast.walk(tree):
        if isinstance(node, BANNED_NODES):
            found.append(f"{type(node).__name__} at {_at(node)}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if id(node) not in top:
                found.append(f"import inside a function: {_at(node)}")
            if isinstance(node, ast.ImportFrom) and (node.level or node.module == "__future__"):
                found.append(f"relative or __future__ import: {_at(node)}")
            for alias in node.names:
                module = node.module if isinstance(node, ast.ImportFrom) else alias.name
                if (module or "").split(".")[0] not in ALLOWED_MODULES:
                    found.append(f"import of {module}: {_at(node)}")
                if not (alias.asname or "").startswith("_"):
                    found.append(f"import not bound to a private name: {_at(node)}")
        elif isinstance(node, ast.ClassDef):
            if node.bases or node.keywords:
                found.append(f"inheritance or metaclass: class {node.name}")
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                keywords = decorator.keywords if isinstance(decorator, ast.Call) else []
                # The runtime's dataclass takes frozen=, and no other option.
                if ast.unparse(target) != "_dataclass" or [k.arg for k in keywords] not in (
                    [],
                    ["frozen"],
                ):
                    found.append(f"class decorator {_at(decorator)}")
        elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
            if isinstance(node, ast.FunctionDef):
                if node.decorator_list:
                    found.append(f"decorated function {node.name}")
                if node.name.startswith("__") and node.name not in DUNDER_METHODS:
                    found.append(f"dunder method {node.name}")
                if node.returns is not None:
                    found.append(f"return annotation on {node.name}")
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if arg.annotation is not None:
                    found.append(f"annotated argument {arg.arg} at line {node.lineno}")
        elif isinstance(node, ast.AnnAssign):
            if not _annotation_ok(node.annotation):
                found.append(f"annotation beyond builtin types: {_at(node)}")
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                found.append(f"banned name: {_at(node)}")
        elif isinstance(node, ast.Attribute):
            is_type_name = (
                node.attr == "__name__"
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == "type"
            )
            if node.attr.startswith("__") and node.attr.endswith("__") and not is_type_name:
                found.append(f"dunder access: {_at(node)}")
            if node.attr in BANNED_ATTRIBUTES:
                found.append(f"banned attribute: {_at(node)}")
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (float, complex)):
                found.append(f"float literal: {_at(node)}")
            if isinstance(node.value, str) and node.value.startswith("__"):
                found.append(f"dunder string, a getattr in disguise: {_at(node)}")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and (node.func.id == "float" or (node.func.id == "setattr" and not _tags(node)))
        ):
            found.append(f"{node.func.id}() at {_at(node)}")
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            continue
        if not (isinstance(node, ast.Assign) and _static(node.value)):
            found.append(f"module-level work: {_at(node)}")
    for cls in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
        for index, node in enumerate(cls.body):
            if index == 0 and isinstance(node, ast.Expr) or isinstance(node, ast.FunctionDef):
                continue
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else node
            if value is not None and not (
                isinstance(node, (ast.Assign, ast.AnnAssign)) and _static(value)
            ):
                found.append(f"class-level work in {cls.name}: {_at(node)}")
    return found


def _tags(node: ast.Call) -> bool:
    # setattr(exc, "code" | "violations" | "fractional", ...) is how a refusal
    # carries the server's code where the runtime allows it; nothing else.
    first = node.args[0] if node.args else None
    name = node.args[1] if len(node.args) > 1 else None
    return (
        isinstance(first, ast.Name)
        and first.id == "exc"
        and isinstance(name, ast.Constant)
        and name.value in ("code", "violations", "fractional")
    )


def test_pure_uses_only_what_the_restricted_runtime_runs() -> None:
    assert problems(SOURCE) == []


@pytest.mark.parametrize(
    "snippet",
    [
        "import typing as _typing",
        "import os as _os",
        "from decimal import Decimal",
        "from .scalars import x as _x",
        "from __future__ import annotations",
        "def _f():\n    import re as _r",
        "public = 1",
        "def helper(): pass",
        "class _E(ValueError): pass",
        "class _M(metaclass=type): pass",
        "class _A:\n    @property\n    def x(self): return 1",
        "class _A:\n    @staticmethod\n    def x(): return 1",
        "@_dataclass(frozen=True, slots=True)\nclass _A:\n    x: int",
        "class _A:\n    x: _Decimal = 0",
        "def _f(x: _Decimal): return x",
        "def _f(x) -> int: return x",
        "def _f():\n    del _VERSION",
        "def _f():\n    global _VERSION",
        "def _g():\n    yield 1",
        "async def _g(): pass",
        "def _f(x):\n    return x.__class__",
        "def _f(x):\n    return x.__dict__",
        "def _f(x):\n    return getattr(x, '__dict__')",
        "class _A:\n    def __getattr__(self, name): return 1",
        "def _f(x):\n    return x.bit_length()",
        "def _f():\n    return _datetime.now()",
        "def _f():\n    return float('1.5')",
        "_RATE = 0.1",
        "def _f(x):\n    return x * 1.5",
        "def _f(x):\n    setattr(x, 'y', 1)",
        "def _f(x):\n    eval(x)",
        "def _f(x):\n    print(x)",
        "def _f(x):\n    return bytearray(x)",
        "def _f(x):\n    with x: pass",
        "def _f(x):\n    assert x",
        "_TABLE = [n for n in range(10)]",
        "_PAIRS = dict(a=1)",
        "_PATTERN = _re.compile(_SOMETHING + 'x')",
        "class _A:\n    x = [n for n in range(3)]",
    ],
)
def test_each_rule_catches_what_it_bans(snippet: str) -> None:
    assert problems(SOURCE + "\n\n" + snippet + "\n") != []


def test_size_budget() -> None:
    assert len(SOURCE.encode("utf-8")) < MAX_BYTES


def test_version_is_the_sdk_version() -> None:
    assert polyester.__version__ == pure.polyester.VERSION
