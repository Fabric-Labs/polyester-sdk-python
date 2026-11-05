"""Shared REST problem metadata for gateway and realtime errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
