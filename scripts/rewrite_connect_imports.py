#!/usr/bin/env python3
"""Rewrite connect-python proto-path imports to polyester.gen.* after a gen drop.

Run this after copying generated Connect/protobuf output into src/polyester/gen/:

  python3 scripts/rewrite_connect_imports.py
  python3 scripts/check_connect_imports.py

Do not maintain a package allowlist. Any new ``foo.v1`` Connect file is remapped.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN_ROOT = ROOT / "src" / "polyester" / "gen"

_IMPORT_PB2 = re.compile(
    r"^(import )(?!polyester\.gen\.)([a-z][a-z0-9_.]*)(_pb2(?: as \S+)?)$",
    re.M,
)
_FROM_PB2 = re.compile(
    r"^(from )(?!polyester\.gen\.)([a-z][a-z0-9_.]*)( import \S+_pb2(?: as \S+)?)$",
    re.M,
)


def rewrite_text(text: str) -> str:
    text = _IMPORT_PB2.sub(r"\1polyester.gen.\2\3", text)
    return _FROM_PB2.sub(r"\1polyester.gen.\2\3", text)


def main() -> int:
    changed = 0
    for path in sorted(GEN_ROOT.rglob("*_connect.py")):
        original = path.read_text(encoding="utf-8")
        updated = rewrite_text(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
            print(f"rewrote {path.relative_to(ROOT)}")
    print(f"rewrote {changed} Connect file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
