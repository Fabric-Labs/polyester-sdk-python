"""Shared REST problem metadata for gateway and realtime errors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# The most digits an integer in an answer's body may have: an unsigned 128-bit
# value has 39. A longer one names nothing this SDK reads, and converting it
# could fail (Python refuses integer strings over 4300 digits).
MAX_INTEGER_DIGITS = 39


def _bounded_int(text: str) -> int | None:
    return int(text) if len(text.lstrip("-")) <= MAX_INTEGER_DIGITS else None


def loads_bounded(raw: bytes | str) -> Any:
    """Parse an answer's JSON body, reading an integer longer than
    ``MAX_INTEGER_DIGITS`` as ``None`` so the rest of the body still reads."""
    return json.loads(raw, parse_int=_bounded_int)


@dataclass(frozen=True)
class HTTPProblem:
    """Code is the stable discriminator; type is its canonical URI form."""

    code: str
    status: int
    detail: str
    type: str


def decode_http_problem(data: Any, status: int) -> HTTPProblem | None:
    if not isinstance(data, dict) or not isinstance(data.get("code"), str) or not data["code"]:
        return None
    code = data["code"]
    detail = data.get("detail", data.get("message", ""))
    return HTTPProblem(
        code=code,
        status=status,
        detail=detail if isinstance(detail, str) else "",
        type="https://polyester.dev/problems/" + code.lower().replace("_", "-"),
    )
