"""``polyester/pure.py`` stays inside what a restricted runtime with no C extensions runs.

The file is read with ``ast``: standard-library imports from an allowed list,
aliased private; one public name; no construct the runtime lacks (inheritance,
method decorators, generators, ``del``, ``global``, annotations of non-builtin
types, dunder access, float literals, clocks or entropy); every builtin read
through a factory parameter bound to it at load, never through the namespace
it shares with other code; nothing but definitions at module level; and a size
budget. Each rule is shown to catch
the construct it bans.
"""

from __future__ import annotations

import ast
import builtins
import symtable
from pathlib import Path
from typing import Any

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
BUILTINS = frozenset(name for name in vars(builtins) if not name.startswith("_"))
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
    if isinstance(node, ast.Subscript):
        return _static(node.value) and isinstance(node.slice, ast.Constant)
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


def _factory(tree: ast.Module) -> ast.FunctionDef | None:
    """``def polyester(...): ...`` then ``polyester = polyester()``, and nothing else."""
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if (
        len(body) == 2
        and isinstance(body[0], ast.FunctionDef)
        and body[0].name == "polyester"
        and not body[0].decorator_list
        and ast.unparse(body[1]) == "polyester = polyester()"
    ):
        return body[0]
    return None


def _builds_scope(node: ast.stmt) -> bool:
    # ``_scope = locals()``: the factory hands its rules to the SDK.
    return ast.unparse(node) == "_scope = locals()"


def problems(source: str) -> list[str]:
    """Every construct in ``source`` the restricted runtime does not take, and
    every top-level name but ``polyester``."""
    tree = ast.parse(source)
    found: list[str] = []
    factory = _factory(tree)
    if factory is None:
        found.append("top level is not one polyester() factory and its call")
        return found
    found += _builtin_bindings(factory)
    found += _builtin_scopes(source)
    direct = {id(node) for node in factory.body}
    for node in ast.walk(factory):
        if isinstance(node, BANNED_NODES):
            found.append(f"{type(node).__name__} at {_at(node)}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if id(node) not in direct:
                found.append(f"import inside a nested function: {_at(node)}")
            if isinstance(node, ast.ImportFrom) and (node.level or node.module == "__future__"):
                found.append(f"relative or __future__ import: {_at(node)}")
            for alias in node.names:
                module = node.module if isinstance(node, ast.ImportFrom) else alias.name
                if (module or "").split(".")[0] not in ALLOWED_MODULES:
                    found.append(f"import of {module}: {_at(node)}")
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
                if node.name.startswith("__"):
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
    # The factory only defines, as a module would: no work when it runs.
    for node in factory.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            continue
        if _builds_scope(node):
            continue
        if not (isinstance(node, ast.Assign) and _static(node.value)):
            found.append(f"work at load: {_at(node)}")
    # ``locals=locals`` among the parameters binds it; the binding rule checks those.
    for node in (node for stmt in factory.body for node in ast.walk(stmt)):
        if isinstance(node, ast.Name) and node.id == "locals":
            parent_ok = any(
                _builds_scope(stmt) for stmt in factory.body if stmt.lineno == node.lineno
            )
            if not parent_ok:
                found.append(f"locals() beyond the factory's scope: {_at(node)}")
    for cls in [node for node in ast.walk(factory) if isinstance(node, ast.ClassDef)]:
        for index, node in enumerate(cls.body):
            if index == 0 and isinstance(node, ast.Expr) or isinstance(node, ast.FunctionDef):
                continue
            if isinstance(node, ast.Assign) and not all(
                isinstance(target, ast.Name) for target in node.targets
            ):
                # The runtime takes only ``name = <expr>`` in a class body.
                found.append(f"class-level unpacking in {cls.name}: {_at(node)}")
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else node
            if value is not None and not (
                isinstance(node, (ast.Assign, ast.AnnAssign)) and _static(value)
            ):
                found.append(f"class-level work in {cls.name}: {_at(node)}")
    return found


def _builtin_bindings(factory: ast.FunctionDef) -> list[str]:
    """Each builtin the factory reads is one of its parameters, bound to that
    builtin when the file loads (``def polyester(str=str, ...)``): code loaded
    later into the same namespace can rebind ``str``, not the builders' ``str``."""
    found: list[str] = []
    args = factory.args
    if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
        found.append("factory parameter that is not name=name")
    bound: set[str] = set()
    defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(args.args, defaults, strict=True):
        if hasattr(builtins, arg.arg) and isinstance(default, ast.Name) and default.id == arg.arg:
            bound.add(arg.arg)
        else:
            found.append(f"factory parameter {arg.arg} does not bind the builtin {arg.arg}")
    used = {
        node.id
        for stmt in factory.body
        for node in ast.walk(stmt)
        if isinstance(node, ast.Name) and hasattr(builtins, node.id)
    }
    found += [
        f"builtin {name} read from the shared namespace: bind it" for name in sorted(used - bound)
    ]
    found += [f"factory parameter {name} is never read" for name in sorted(bound - used)]
    return found


def _builtin_scopes(source: str) -> list[str]:
    """Each read of a builtin name inside the factory resolves to the factory's
    binding (or to a function's own local), never to the shared namespace. A
    class body that assigns a name reads it from the shared namespace, not the
    factory (``int = int`` there is whatever global ``int`` the bot bound); a
    method named ``format`` that the class body never reads is harmless."""
    top = symtable.symtable(source, "pure.py", "exec")
    factory = next(table for table in top.get_children() if table.get_name() == "polyester")
    found: list[str] = []
    for name in set(factory.get_identifiers()) & BUILTINS:
        symbol = factory.lookup(name)
        if not symbol.is_parameter() or symbol.is_assigned() or symbol.is_imported():
            found.append(f"builtin {name} rebound in the factory")
    tables = list(factory.get_children())
    while tables:
        table = tables.pop()
        tables += table.get_children()
        local_ok = table.get_type() != "class"
        for name in set(table.get_identifiers()) & BUILTINS:
            symbol = table.lookup(name)
            if not symbol.is_referenced() or symbol.is_free() or (local_ok and symbol.is_local()):
                continue
            where = f"{table.get_type()} {table.get_name()} at line {table.get_lineno()}"
            found.append(f"builtin {name} read from the shared namespace in {where}")
    return sorted(found)


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


def _inside(snippet: str) -> str:
    """``SOURCE`` with ``snippet`` among the factory's definitions."""
    marker = "  _types = ("
    assert SOURCE.count(marker) == 1
    indented = "".join(f"  {line}\n" for line in snippet.splitlines())
    return SOURCE.replace(marker, indented + marker)


def test_pure_uses_only_what_the_restricted_runtime_runs() -> None:
    assert problems(SOURCE) == []


def test_polyester_is_the_only_top_level_name() -> None:
    tree = ast.parse(SOURCE)
    names = [
        node.name if isinstance(node, ast.FunctionDef) else ast.unparse(node.targets[0])
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.Assign))
    ]
    assert names == ["polyester", "polyester"]
    assert len(tree.body) == 3  # docstring, factory, its call
    namespace: dict[str, Any] = {}
    exec(compile(SOURCE, "pure.py", "exec"), namespace)  # noqa: S102 - the file under test
    assert [name for name in namespace if not name.startswith("__")] == ["polyester"]


@pytest.mark.parametrize(
    "snippet",
    [
        "import typing as _typing",
        "import os as _os",
        "from .scalars import x as _x",
        "from __future__ import annotations",
        "def _f():\n    import re as _r",
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
        "class _A:\n    def __repr__(self): return ''",
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
        "def _f():\n    return locals()",
        "_TABLE = [n for n in range(10)]",
        "_PAIRS = dict(a=1)",
        "_PATTERN = _re.compile(_SOMETHING + 'x')",
        "_run_now()",
        "class _A:\n    x = [n for n in range(3)]",
        "class _A:\n    x, y = _types",
        "def _f(x):\n    return min(x)",
        "def _f(x):\n    return x if hash(x) else None",
        "class _A:\n    def f(self):\n        return object()",
        "_f = lambda x: max(x)",
    ],
)
def test_each_rule_catches_what_it_bans(snippet: str) -> None:
    assert problems(_inside(snippet)) != []


def test_every_builtin_is_bound_at_load() -> None:
    assert _builtin_bindings(_factory(ast.parse(SOURCE))) == []
    assert _builtin_scopes(SOURCE) == []
    params = [arg.arg for arg in _factory(ast.parse(SOURCE)).args.args]
    assert {"type", "int", "str", "isinstance", "len", "range", "divmod", "abs"} <= set(params)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("  type=type,\n", ""),  # type() read from the shared namespace
        ("  type=type,\n", "  type=str,\n"),
        ("  type=type,\n", "  type=type,\n  min=min,\n"),  # bound, never read
        ("  type=type,\n", "  type=type,\n  _x=1,\n"),
        ("  type=type,\n", "  type=type,\n  *rest,\n"),
        ("def polyester(\n", "def polyester(\n  min,\n"),
        ("  _types = (", "  str = 1\n  _types = ("),  # the factory's binding replaced
    ],
)
def test_the_builtin_binding_rule_catches_what_it_bans(old: str, new: str) -> None:
    assert SOURCE.count(old) == 1
    assert problems(SOURCE.replace(old, new)) != []


@pytest.mark.parametrize(
    "snippet",
    ["_helper = 1", "import re as _re", "def _f(): pass", "class _A: pass", "public = 1"],
)
def test_a_second_top_level_name_is_refused(snippet: str) -> None:
    assert problems(SOURCE + "\n\n" + snippet + "\n") != []
    assert problems(snippet + "\n\n" + SOURCE) != []


def test_size_budget() -> None:
    size = len(SOURCE.encode("utf-8"))
    print(f"polyester/pure.py is {size} bytes of {MAX_BYTES}")
    assert size < MAX_BYTES, f"polyester/pure.py is {size} bytes, over its {MAX_BYTES}-byte budget"


def test_contract_limits_are_the_contracts() -> None:
    """The file holds the limits the SDK reads from the contract's rules."""
    import msgspec

    from polyester.codecs import oco, triggers
    from polyester.codecs.pure_bridge import pure as impl
    from polyester.models import CreateOrderRequest

    assert impl._TWAP_DURATION_MS == (triggers.TWAP_DURATION_MS_MIN, triggers.TWAP_DURATION_MS_MAX)
    assert impl._TWAP_SLICE_INTERVAL_MS == (
        triggers.TWAP_SLICE_INTERVAL_MS_MIN,
        triggers.TWAP_SLICE_INTERVAL_MS_MAX,
    )
    assert impl._LADDER_LEVELS == (triggers.LADDER_LEVELS_MIN, triggers.LADDER_LEVELS_MAX)
    assert impl._CLIENT_TRIGGER_ID_MAX_BYTES == triggers.CLIENT_TRIGGER_ID_MAX_BYTES
    assert impl._CLIENT_LIST_ID_MAX_LEN == oco.CLIENT_LIST_ID_MAX_LEN
    fields = {field.name for field in msgspec.structs.fields(CreateOrderRequest)}
    assert set(impl._CREATE_ORDER_FIELDS) == fields


def test_version_is_the_sdk_version() -> None:
    namespace: Any = pure.polyester
    assert polyester.__version__ == namespace.VERSION


# A class body that assigns a name reads it from the module namespace, not the
# enclosing function: ``int = int`` there is whatever ``int`` the bot bound.
CLASS_SCOPE_PROBE = """
def polyester(int=int):
  def _probe():
    class _C:
      int = int
    return _C.int
  return _probe

polyester = polyester()
"""


def test_a_class_body_rebinding_a_builtin_reads_the_shared_namespace() -> None:
    namespace: dict[str, Any] = {}
    exec(compile(CLASS_SCOPE_PROBE, "probe", "exec"), namespace)  # noqa: S102 - the probe
    assert namespace["polyester"]() is int
    namespace["int"] = "junk"
    assert namespace["polyester"]() == "junk"
    assert _builtin_bindings(_factory(ast.parse(CLASS_SCOPE_PROBE))) == []
    assert problems(CLASS_SCOPE_PROBE) == [
        "builtin int read from the shared namespace in class _C at line 4"
    ]


@pytest.mark.parametrize(
    "snippet",
    [
        "class _A:\n    str = str",
        "class _A:\n    len = 1\n    x = len",
        "class _A:\n    def repr(self): return ''\n    x = repr",
        "def _f():\n    class _A:\n        isinstance = isinstance\n    return _A",
    ],
)
def test_a_class_body_cannot_rebind_a_builtin_it_reads(snippet: str) -> None:
    assert _builtin_scopes(_inside(snippet)) != []


@pytest.mark.parametrize(
    "snippet",
    [
        "class _A:\n    def format(self): return str(self)",  # the class body never reads it
        "def _f(type):\n    return type",  # the function's own value
        "def _f(x):\n    return [str for str in x]",
    ],
)
def test_a_name_that_is_not_a_builtin_read_is_allowed(snippet: str) -> None:
    assert _builtin_scopes(_inside(snippet)) == []
