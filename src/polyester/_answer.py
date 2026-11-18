"""An HTTP answer's metadata on the errors made from it.

Every error that comes from an HTTP answer carries the answer's own status and
the delay it asked for (``status_code``, ``retry_after``); an error with no
answer behind it carries neither.
"""

from __future__ import annotations

from contextlib import suppress
from math import isfinite
from typing import Any

from polyester._problem import HTTPProblem, decode_http_problem, loads_bounded
from polyester.errors import PolyesterError, PolyesterRealtimeError


def retry_after_from_headers(headers: Any) -> float | None:
    """The delay in seconds an answer's headers ask for: ``Retry-After``, then
    ``Retry-After-Ms``, then ``Grpc-Retry-Pushback-Ms``; ``None`` without one."""
    for header, divisor in (
        ("retry-after", 1),
        ("retry-after-ms", 1000),
        ("grpc-retry-pushback-ms", 1000),
    ):
        with suppress(ValueError, TypeError):
            value = float(headers.get(header, "")) / divisor
            if isfinite(value) and value >= 0:
                return value
    return None


def attach_answer(error: BaseException, status: int, headers: Any) -> BaseException:
    """``error`` carrying the answer it came from: the answer's own status, and
    its delay unless the error already holds one."""
    if isinstance(error, PolyesterError):
        error.status_code = status
        if error.retry_after is None:
            error.retry_after = retry_after_from_headers(headers)
    return error


def refused_upgrade(exc: BaseException, message: str) -> PolyesterRealtimeError | None:
    """A refused WebSocket upgrade as a realtime error carrying its answer, or
    ``None`` when ``exc`` is no refused upgrade (no answer at all, say)."""
    from websockets.exceptions import InvalidStatus

    if not isinstance(exc, InvalidStatus):
        return None
    response = exc.response
    # The API answers a refused upgrade with a problem body naming its code
    # (``TOO_MANY_SESSIONS_API_KEY``, ``METHOD_NOT_ALLOWED``, ...), as for a
    # REST refusal; an answer without one keeps only its status.
    problem = _problem_of(response.body, response.status_code)
    error = PolyesterRealtimeError(message, code=problem.code if problem else None)
    error.problem = problem
    error.__cause__ = exc
    attach_answer(error, response.status_code, response.headers)
    return error


def _problem_of(body: object, status: int) -> HTTPProblem | None:
    if not isinstance(body, bytes | bytearray) or not body:
        return None
    try:
        # Bounded, so an integer too long to convert costs the body nothing.
        payload = loads_bounded(bytes(body))
    except ValueError:
        return None
    return decode_http_problem(payload, status)
