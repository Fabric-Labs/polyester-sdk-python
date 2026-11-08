"""The public signatures type-check as the runtime behaves, under ``mypy --strict``.

The snippets in ``tests/typing_snippets`` are type-checked, never run:
``accepted_calls.py`` must be clean, and each statement of
``rejected_calls.py`` marked ``# E: <text>`` must get an error containing
``<text>``, with no error anywhere else.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from mypy import api as mypy_api

import polyester.services

SNIPPETS = Path(__file__).resolve().parent.parent / "typing_snippets"
ERROR = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+): error: (?P<message>.*)$")
MARKER = re.compile(r"#\s*E:\s*(?P<text>.+?)\s*$")


@pytest.fixture(scope="module")
def mypy_errors(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[tuple[int, str]]]:
    work = tmp_path_factory.mktemp("mypy")
    config = work / "mypy.ini"
    # Not the repository config: it skips imports, which would make the SDK Any.
    config.write_text("[mypy]\n")
    files = sorted(str(path) for path in SNIPPETS.glob("*.py"))
    stdout, stderr, status = mypy_api.run(
        [
            "--config-file",
            str(config),
            "--strict",
            "--follow-imports=silent",
            "--cache-dir",
            str(work / "cache"),
            "--no-error-summary",
            "--hide-error-context",
            *files,
        ]
    )
    assert status in (0, 1), stderr or stdout
    errors: dict[str, list[tuple[int, str]]] = {}
    for line in stdout.splitlines():
        match = ERROR.match(line)
        if match is None:
            continue
        name = Path(match["path"]).name
        errors.setdefault(name, []).append((int(match["line"]), match["message"]))
    return errors


def test_accepted_calls_type_check(mypy_errors: dict[str, list[tuple[int, str]]]) -> None:
    assert mypy_errors.get("accepted_calls.py", []) == []


def _statements(tree: ast.AST) -> Iterator[ast.stmt]:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            yield from node.body


def test_rejected_calls_are_errors(mypy_errors: dict[str, list[tuple[int, str]]]) -> None:
    path = SNIPPETS / "rejected_calls.py"
    source = path.read_text()
    lines = source.splitlines()
    errors = mypy_errors.get(path.name, [])
    expected = 0
    claimed: set[int] = set()
    for statement in _statements(ast.parse(source)):
        end = statement.end_lineno or statement.lineno
        found = [(n, msg) for n, msg in errors if statement.lineno <= n <= end]
        claimed.update(n for n, _ in found)
        marker = MARKER.search(lines[statement.lineno - 1])
        if marker is None:
            assert found == [], f"line {statement.lineno}: unexpected {found}"
            continue
        expected += 1
        text = marker["text"]
        assert any(text in msg for _, msg in found), (
            f"line {statement.lineno}: mypy accepted a call it must reject "
            f"(want an error containing {text}; got {found})"
        )
    assert expected >= 10
    assert [(n, msg) for n, msg in errors if n not in claimed] == []


def _public_methods() -> Iterator[tuple[str, inspect.Signature]]:
    for module_info in pkgutil.iter_modules(polyester.services.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"polyester.services.{module_info.name}")
        for class_name, cls in vars(module).items():
            if not inspect.isclass(cls) or cls.__module__ != module.__name__:
                continue
            for name, member in vars(cls).items():
                if name.startswith("_") or not inspect.isfunction(member):
                    continue
                yield f"{class_name}.{name}", inspect.signature(member)


def _union(annotation: object) -> set[str]:
    assert isinstance(annotation, str), annotation
    return {part.strip() for part in annotation.split("|")}


def test_every_public_account_id_parameter_accepts_an_int() -> None:
    checked = 0
    wrong = []
    for name, signature in _public_methods():
        for parameter in signature.parameters.values():
            if parameter.name in ("sub_account_id", "account_id"):
                checked += 1
                if _union(parameter.annotation) != {"str", "int", "None"}:
                    wrong.append(f"{name}({parameter.name}: {parameter.annotation})")
            elif parameter.name == "account":
                checked += 1
                if _union(parameter.annotation) != {"AccountScope", "None"}:
                    wrong.append(f"{name}(account: {parameter.annotation})")
    assert checked > 100
    assert wrong == []
