#!/usr/bin/env python3
"""Fail if generated Connect clients import proto paths instead of polyester.gen.

connect-python emits ``import fees.v1.fees_pb2``. This SDK nests gen under
``src/polyester/gen``, so those imports must be rewritten to
``import polyester.gen.fees.v1.fees_pb2``. Publication has repeatedly dropped
the rewrite for fees, VIP, and rate-limit.

Usage:
  python3 scripts/check_connect_imports.py
  python3 scripts/rewrite_connect_imports.py   # then re-run this check
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN_ROOT = ROOT / "src" / "polyester" / "gen"

# Third-party / stdlib imports that appear in generated *_connect.py.
_ALLOWED_PREFIXES = (
    "polyester.gen.",
    "connectrpc.",
    "collections",
    "typing",
    "google.",
)

_IMPORT_RE = re.compile(r"^(?:import|from)\s+(\S+)")


def _allowed(module: str) -> bool:
    return module.startswith(_ALLOWED_PREFIXES) or module in {"collections", "typing"}


def find_bad_imports(gen_root: Path = GEN_ROOT) -> list[str]:
    errors: list[str] = []
    if not gen_root.is_dir():
        return [f"missing gen root: {gen_root}"]
    for path in sorted(gen_root.rglob("*_connect.py")):
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            match = _IMPORT_RE.match(line)
            if not match:
                continue
            module = match.group(1)
            if _allowed(module):
                continue
            rel = path.relative_to(ROOT)
            errors.append(f"{rel}:{lineno}: {line}")
    return errors


def main() -> int:
    errors = find_bad_imports()
    if not errors:
        print("ok: Connect clients import polyester.gen.*")
        return 0
    print(
        "error: generated Connect clients still use proto-relative imports.\n"
        "  run: python3 scripts/rewrite_connect_imports.py",
        file=sys.stderr,
    )
    for item in errors:
        print(f"  {item}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
