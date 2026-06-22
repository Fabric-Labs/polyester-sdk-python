#!/usr/bin/env python3
"""Live smoke test against Polyester devnet (delegates to pytest integration suite)."""

from __future__ import annotations

import os
import sys


def main() -> int:
    import pytest

    args = ["tests/integration", "tests/e2e", "-m", "integration", "-v"]
    if os.getenv("POLYESTER_TEST_MUTATION", os.getenv("POLYESTER_SMOKE_MUTATION", "")).lower() in (
        "1",
        "true",
        "yes",
    ):
        args = ["tests", "-m", "integration", "-v"]
    return pytest.main(args)


if __name__ == "__main__":
    sys.exit(main())
