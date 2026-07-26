"""POLY-3746 A7: POLYESTER_TEST_STRICT_LIVE flips skip → fail."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_strict_live_forbids_skip(tmp_path: Path) -> None:
    """Under STRICT_LIVE, a skipped test is reported as failed via conftest hook."""
    probe = tmp_path / "test_strict_live_probe.py"
    probe.write_text(
        textwrap.dedent(
            """\
            import pytest

            def test_probe_skip():
                pytest.skip("capability discovery probe")
            """
        ),
        encoding="utf-8",
    )
    conftest = tmp_path / "conftest.py"
    # Minimal copy of the STRICT_LIVE hook from tests/conftest.py
    conftest.write_text(
        textwrap.dedent(
            """\
            import os
            import pytest

            def _env_truthy(name: str) -> bool:
                return os.getenv(name, "").lower() in ("1", "true", "yes")

            @pytest.hookimpl(hookwrapper=True)
            def pytest_runtest_makereport(item, call):
                outcome = yield
                report = outcome.get_result()
                if _env_truthy("POLYESTER_TEST_STRICT_LIVE") and report.skipped:
                    report.outcome = "failed"
                    report.longrepr = (
                        f"{item.nodeid}: strict live mode forbids skipped tests; "
                        "unset POLYESTER_TEST_STRICT_LIVE for capability discovery"
                    )
            """
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "POLYESTER_TEST_STRICT_LIVE": "1"}
    env.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(probe), "-q", "--tb=line"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "strict live mode forbids skipped" in combined or "failed" in combined.lower()


def test_without_strict_live_skip_remains_skip(tmp_path: Path) -> None:
    probe = tmp_path / "test_strict_live_probe.py"
    probe.write_text(
        "import pytest\n\ndef test_probe_skip():\n    pytest.skip('ok')\n",
        encoding="utf-8",
    )
    env = {**os.environ}
    env.pop("POLYESTER_TEST_STRICT_LIVE", None)
    env.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(probe), "-q"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "skipped" in (result.stdout + result.stderr).lower()
