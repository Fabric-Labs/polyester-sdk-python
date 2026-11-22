#!/usr/bin/env python3
"""Fail if the protobuf dependency floor is below the generated code's version.

Every generated ``*_pb2.py`` calls ``ValidateProtobufRuntimeVersion`` with the
protoc version that wrote it, and refuses to import on an older protobuf
runtime. The ``protobuf`` requirement in ``pyproject.toml`` must therefore
allow no runtime older than the newest generated module, or ``import polyester``
fails with ``VersionError`` on an install that pip considers valid.

Usage:
  python3 scripts/check_protobuf_floor.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
GEN_ROOT = ROOT / "src" / "polyester" / "gen"
PYPROJECT = ROOT / "pyproject.toml"

_VALIDATE_RE = re.compile(
    r"ValidateProtobufRuntimeVersion\(\s*_runtime_version\.Domain\.PUBLIC,\s*"
    r"(\d+),\s*(\d+),\s*(\d+),\s*'([^']*)'"
)


def gencode_version(gen_root: Path = GEN_ROOT) -> tuple[Version | None, list[str]]:
    """Return the newest protobuf version any generated module requires."""
    errors: list[str] = []
    newest: Version | None = None
    modules = sorted(gen_root.rglob("*_pb2.py")) if gen_root.is_dir() else []
    if not modules:
        return None, [f"no generated *_pb2.py modules under {gen_root}"]
    for path in modules:
        match = _VALIDATE_RE.search(path.read_text(encoding="utf-8"))
        if match is None:
            errors.append(f"{path}: no ValidateProtobufRuntimeVersion call")
            continue
        major, minor, patch, suffix = match.groups()
        try:
            version = Version(f"{major}.{minor}.{patch}{suffix}")
        except InvalidVersion:
            errors.append(f"{path}: unparsable gencode version {major}.{minor}.{patch}{suffix}")
            continue
        if newest is None or version > newest:
            newest = version
    return newest, errors


def protobuf_floor(pyproject: Path = PYPROJECT) -> tuple[Version | None, list[str]]:
    """Return the lowest protobuf version the package dependencies allow.

    The requirement must apply on every install: an environment marker would let
    an excluded environment resolve any protobuf another dependency accepts.
    """
    with pyproject.open("rb") as handle:
        dependencies = tomllib.load(handle)["project"].get("dependencies", [])
    requirements = [Requirement(item) for item in dependencies]
    protobuf = [req for req in requirements if req.name.lower() == "protobuf"]
    if len(protobuf) != 1:
        return None, [f"{pyproject}: expected one protobuf dependency, found {len(protobuf)}"]
    if protobuf[0].marker is not None:
        return None, [
            f"{pyproject}: protobuf requirement {protobuf[0]} has an environment marker; "
            "the floor must apply on every install"
        ]
    floors = [
        Version(spec.version.removesuffix(".*"))
        for spec in protobuf[0].specifier
        if spec.operator in {">=", "==", "~="}
    ]
    if not floors:
        return None, [f"{pyproject}: protobuf requirement {protobuf[0]} has no lower bound"]
    return max(floors), []


def check(gen_root: Path = GEN_ROOT, pyproject: Path = PYPROJECT) -> list[str]:
    required, errors = gencode_version(gen_root)
    floor, floor_errors = protobuf_floor(pyproject)
    errors.extend(floor_errors)
    if required is not None and floor is not None and floor < required:
        errors.append(
            f"protobuf floor {floor} is below the generated code's version {required}: "
            f'require "protobuf>={required}" in pyproject.toml'
        )
    return errors


def main() -> int:
    errors = check()
    if errors:
        for item in errors:
            print(f"error: {item}", file=sys.stderr)
        return 1
    required, _ = gencode_version()
    floor, _ = protobuf_floor()
    print(f"ok: protobuf floor {floor} covers the generated code's version {required}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
