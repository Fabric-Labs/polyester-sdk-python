"""The declared runtime dependencies exclude majors the SDK does not support.

``pip install --pre polyester-sdk`` accepts pre-releases of every dependency.
httpx 1.0 pre-releases drop ``httpx.AsyncClient``, which the SDK's transport
uses, so a pre-release install must not resolve them.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]


def _requirement(name: str) -> Requirement:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    matches = [Requirement(item) for item in project["dependencies"]]
    found = [req for req in matches if req.name == name]
    assert len(found) == 1, f"{name} is declared {len(found)} times"
    return found[0]


@pytest.mark.parametrize("version", ["1.0.dev6", "1.0.0a1", "1.0.0", "1.2.3"])
def test_httpx_requirement_excludes_1x_including_pre_releases(version: str) -> None:
    assert not _requirement("httpx").specifier.contains(version, prereleases=True)


@pytest.mark.parametrize("version", ["0.27.0", "0.28.1", "0.29.0"])
def test_httpx_requirement_admits_the_supported_0x_releases(version: str) -> None:
    assert _requirement("httpx").specifier.contains(version, prereleases=True)
