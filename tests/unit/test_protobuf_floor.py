"""The protobuf dependency floor must cover the generated code's version."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "check_protobuf_floor", ROOT / "scripts" / "check_protobuf_floor.py"
)
assert _SPEC is not None and _SPEC.loader is not None
floor_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(floor_check)


def _gen_module(root: Path, name: str, major: int, minor: int, patch: int) -> None:
    path = root / f"{name}_pb2.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "_runtime_version.ValidateProtobufRuntimeVersion(\n"
        "    _runtime_version.Domain.PUBLIC,\n"
        f"    {major},\n    {minor},\n    {patch},\n    '',\n"
        f"    '{name}.proto'\n)\n",
        encoding="utf-8",
    )


def _pyproject(tmp_path: Path, *dependencies: str) -> Path:
    path = tmp_path / "pyproject.toml"
    items = ", ".join(f'"{item}"' for item in dependencies)
    path.write_text(f'[project]\nname = "x"\ndependencies = [{items}]\n', encoding="utf-8")
    return path


def test_repository_floor_covers_generated_code() -> None:
    assert floor_check.check() == []


def test_floor_below_newest_gencode_fails(tmp_path: Path) -> None:
    gen = tmp_path / "gen"
    _gen_module(gen, "a/v1/a", 7, 35, 0)
    _gen_module(gen, "b/v1/b", 7, 35, 1)
    errors = floor_check.check(gen, _pyproject(tmp_path, "protobuf>=7.35.0"))
    assert len(errors) == 1
    assert "protobuf floor 7.35.0 is below the generated code's version 7.35.1" in errors[0]


@pytest.mark.parametrize("requirement", ["protobuf>=7.35.1", "protobuf>=7.36", "protobuf~=7.35.1"])
def test_floor_at_or_above_gencode_passes(tmp_path: Path, requirement: str) -> None:
    gen = tmp_path / "gen"
    _gen_module(gen, "a/v1/a", 7, 35, 1)
    assert floor_check.check(gen, _pyproject(tmp_path, requirement)) == []


@pytest.mark.parametrize("requirement", ["protobuf", "protobuf<8", "protobuf>7.35.1"])
def test_requirement_without_lower_bound_fails(tmp_path: Path, requirement: str) -> None:
    gen = tmp_path / "gen"
    _gen_module(gen, "a/v1/a", 7, 35, 1)
    errors = floor_check.check(gen, _pyproject(tmp_path, requirement))
    assert errors == [
        f"{tmp_path / 'pyproject.toml'}: protobuf requirement {requirement} has no lower bound"
    ]


@pytest.mark.parametrize(
    "requirement",
    [
        "protobuf>=7.35.1; python_version >= '3.12'",
        "protobuf>=7.35.1; sys_platform == 'linux'",
    ],
)
def test_requirement_with_environment_marker_fails(tmp_path: Path, requirement: str) -> None:
    gen = tmp_path / "gen"
    _gen_module(gen, "a/v1/a", 7, 35, 1)
    pyproject = _pyproject(tmp_path, requirement)
    errors = floor_check.check(gen, pyproject)
    assert len(errors) == 1
    assert errors[0].startswith(f"{pyproject}: protobuf requirement protobuf>=7.35.1; ")
    assert errors[0].endswith("has an environment marker; the floor must apply on every install")


def test_missing_protobuf_dependency_fails(tmp_path: Path) -> None:
    gen = tmp_path / "gen"
    _gen_module(gen, "a/v1/a", 7, 35, 1)
    errors = floor_check.check(gen, _pyproject(tmp_path, "httpx>=0.27"))
    assert errors == [f"{tmp_path / 'pyproject.toml'}: expected one protobuf dependency, found 0"]


def test_generated_module_without_version_call_fails(tmp_path: Path) -> None:
    gen = tmp_path / "gen"
    _gen_module(gen, "a/v1/a", 7, 35, 1)
    (gen / "b_pb2.py").write_text("# no runtime check\n", encoding="utf-8")
    errors = floor_check.check(gen, _pyproject(tmp_path, "protobuf>=7.35.1"))
    assert errors == [f"{gen / 'b_pb2.py'}: no ValidateProtobufRuntimeVersion call"]


def test_no_generated_modules_fails(tmp_path: Path) -> None:
    errors = floor_check.check(tmp_path / "gen", _pyproject(tmp_path, "protobuf>=7.35.1"))
    assert errors == [f"no generated *_pb2.py modules under {tmp_path / 'gen'}"]
