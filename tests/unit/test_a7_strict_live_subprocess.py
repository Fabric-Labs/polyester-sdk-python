"""POLY-3746 A7: STRICT_LIVE + missing/malformed credentials fail via subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_DIR = REPO_ROOT / "tests" / "_a7_probes"


def _run_pytest(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    cleaned = {**os.environ, **env}
    cleaned.pop("PYTEST_ADDOPTS", None)
    # Keep explicit empty strings so python-dotenv does not refill from .env.
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-q", "--tb=line"],
        cwd=str(REPO_ROOT),
        env=cleaned,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_probe(name: str, body: str) -> Path:
    PROBE_DIR.mkdir(exist_ok=True)
    gitignore = PROBE_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")
    path = PROBE_DIR / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_strict_live_missing_creds_fails_live_integration() -> None:
    """STRICT_LIVE + empty API-key env → live fixture skip becomes failure."""
    env = {
        "POLYESTER_TEST_STRICT_LIVE": "1",
        "POLYESTER_API_KEY_ID": "",
        "POLYESTER_API_PRIVATE_KEY": "",
        "POLYESTER_ACCOUNT_ID": "",
    }
    result = _run_pytest(
        ["tests/integration/test_trades.py", "-m", "integration", "--maxfail=1"],
        env=env,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert "strict live" in combined or "failed" in combined


def test_strict_live_malformed_private_key_fails_not_skip() -> None:
    """Malformed key must raise PolyesterAuthError (fail), not soft-skip as ok."""
    path = _write_probe(
        "test_malformed_key_probe.py",
        """\
        import pytest
        from polyester.auth import load_api_key_credentials
        from polyester.errors import PolyesterAuthError

        pytestmark = pytest.mark.integration

        def test_malformed_key_raises():
            with pytest.raises(PolyesterAuthError):
                load_api_key_credentials()
        """,
    )
    try:
        env = {
            "POLYESTER_TEST_STRICT_LIVE": "1",
            "POLYESTER_API_KEY_ID": "ak_test",
            "POLYESTER_API_PRIVATE_KEY": "not-valid-hex",
            "POLYESTER_ACCOUNT_ID": "",
        }
        result = _run_pytest([str(path.relative_to(REPO_ROOT))], env=env)
        assert result.returncode == 0, result.stdout + result.stderr
        combined = result.stdout + result.stderr
        assert "1 passed" in combined
        assert "skipped=0" in combined or " 0 skipped" in combined.lower()
    finally:
        path.unlink(missing_ok=True)


def test_strict_live_partial_creds_raise() -> None:
    path = _write_probe(
        "test_partial_creds_probe.py",
        """\
        import pytest
        from polyester.auth import load_api_key_credentials
        from polyester.errors import PolyesterAuthError

        pytestmark = pytest.mark.integration

        def test_partial_env_raises():
            with pytest.raises(PolyesterAuthError):
                load_api_key_credentials()
        """,
    )
    try:
        env = {
            "POLYESTER_TEST_STRICT_LIVE": "1",
            "POLYESTER_API_KEY_ID": "ak_only",
            # Empty private key with key id present must raise, not return None.
            "POLYESTER_API_PRIVATE_KEY": "",
            "POLYESTER_ACCOUNT_ID": "",
        }
        result = _run_pytest([str(path.relative_to(REPO_ROOT))], env=env)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        path.unlink(missing_ok=True)
