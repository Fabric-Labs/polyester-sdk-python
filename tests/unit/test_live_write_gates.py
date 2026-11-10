"""Live tests that write run only when POLYESTER_TEST_MUTATION opts in.

Each write test is run here with credentials but without the opt-in, against a closed
loopback port, so nothing leaves the machine. Every one must be skipped, not attempted.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

WRITE_TESTS = [
    "tests/integration/test_address_book.py::test_address_book_create_update_new_tags_round_trip",
    "tests/integration/test_address_book.py::test_social_verification_start_accepts_at_handle",
    "tests/integration/test_poly4996.py::test_social_verification_discord_without_handle",
]

# The read-only live tier of scripts/test_all.sh.
READ_ONLY_TIER = "integration and not mutation and not funded and not jwt_session and not realtime"


def _pytest(*args: str, mutation: str = "") -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "POLYESTER_API_KEY_ID": "sdk-write-gate-probe",
        "POLYESTER_API_PRIVATE_KEY": "11" * 32,
        "POLYESTER_ACCOUNT_ID": "",
        # Port 9 (discard) is closed on loopback: any request fails at once.
        "POLYESTER_API_URL": "http://127.0.0.1:9",
        "POLYESTER_WS_URL": "ws://127.0.0.1:9",
        "POLYESTER_TEST_MUTATION": mutation,
        "POLYESTER_TEST_STRICT_LIVE": "",
    }
    env.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _summary(result: subprocess.CompletedProcess[str]) -> str:
    """Pytest's closing line, such as ``1 skipped in 0.02s``."""
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


@pytest.mark.parametrize("node", WRITE_TESTS)
def test_write_test_is_skipped_without_the_mutation_opt_in(node: str) -> None:
    result = _pytest(node, "-rs", "-q")
    out = result.stdout + result.stderr
    assert _summary(result).startswith("1 skipped in "), out
    assert "POLYESTER_TEST_MUTATION" in out, out


def test_read_only_tier_selects_no_write_test() -> None:
    result = _pytest("tests/integration", "--collect-only", "-q", "-m", READ_ONLY_TIER)
    selected = set(result.stdout.split())
    assert result.returncode == 0, result.stdout + result.stderr
    assert selected.isdisjoint(WRITE_TESTS), sorted(selected & set(WRITE_TESTS))


def test_mutation_marker_alone_gates_a_test() -> None:
    # A write test that carries the marker but forgets the fixture is still skipped.
    probe_dir = REPO_ROOT / "tests" / "_write_gate_probes"
    probe_dir.mkdir(exist_ok=True)
    (probe_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    probe = probe_dir / "test_write_gate_probe.py"
    probe.write_text(
        "import pytest\n\n\n"
        "@pytest.mark.integration\n"
        "@pytest.mark.mutation\n"
        "def test_probe_write():\n"
        "    raise AssertionError('a mutation test ran without POLYESTER_TEST_MUTATION')\n",
        encoding="utf-8",
    )
    try:
        out = _pytest(str(probe.relative_to(REPO_ROOT)), "-rs", "-q")
        enabled = _pytest(str(probe.relative_to(REPO_ROOT)), "-q", mutation="1")
    finally:
        probe.unlink()
    assert _summary(out).startswith("1 skipped in "), out.stdout + out.stderr
    # Control: with the opt-in the probe runs (and fails on purpose).
    assert _summary(enabled).startswith("1 failed in "), enabled.stdout + enabled.stderr
