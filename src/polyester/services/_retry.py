"""Retry side-effect-free reads on unavailable responses or expired deadlines."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.message import Message

from polyester._wire import map_connect_error
from polyester.errors import (
    AUTH_TEMPORARILY_UNAVAILABLE,
    PolyesterApiError,
    PolyesterRateLimitError,
    PolyesterServerError,
    PolyesterTransportError,
    mutation_outcome_unknown,
)
from polyester.transport import TransportFactory

TRequest = TypeVar("TRequest", bound=Message)
TResponse = TypeVar("TResponse", bound=Message)
R = TypeVar("R")

# Indirections so tests can drive the clock.
_sleep = asyncio.sleep
_monotonic = time.monotonic


@dataclass(frozen=True, slots=True)
class UnavailableRetry:
    """Backoff for a read that may answer ``unavailable`` (HTTP 503) while the
    server catches up: the first retry after ``initial_delay`` seconds, each
    next delay doubled up to ``max_delay``, and no retry that would sleep past
    ``budget`` seconds after the first attempt."""

    initial_delay: float = 0.025
    max_delay: float = 0.5
    budget: float = 2.0


# Trigger reads answer UNAVAILABLE until they can show the latest answered
# modify, pause or resume (read-your-write), and briefly after a market halt.
TRIGGER_READ_RETRY = UnavailableRetry()


def _is_real_unavailability(exc: ConnectError) -> bool:
    """Whether a read may retry, by what the error means and not only its code.

    The Connect table gives HTTP 429 and 503 the code ``unavailable``, so a
    typed REST refusal arrives with it too. That refusal is final for this read.
    """
    if exc.code not in (Code.UNAVAILABLE, Code.DEADLINE_EXCEEDED):
        return False
    mapped = map_connect_error(exc)
    if isinstance(mapped, PolyesterRateLimitError):
        return False
    if isinstance(mapped, PolyesterApiError) and mapped.code == AUTH_TEMPORARILY_UNAVAILABLE:
        # Authentication could not run; the read was not processed.
        return True
    return isinstance(
        mapped, (PolyesterServerError, PolyesterTransportError)
    ) or mutation_outcome_unknown(mapped)


async def unary_auth_decoded_retry_unavailable(
    transport: TransportFactory,
    client_cls: type,
    call: Callable[..., Any],
    request: TRequest,
    decoder: Callable[[TResponse], R],
    *,
    policy: UnavailableRetry,
) -> R:
    """Like ``unary_auth_decoded``, resending the same request on ``unavailable``.

    Use it only for reads: a retried request must have no side effects. When
    the budget runs out the last ``unavailable`` is raised as usual
    (``PolyesterServerError``).
    """
    client = transport.create_auth_client(client_cls)
    started = _monotonic()
    delay = policy.initial_delay
    while True:
        try:
            response: TResponse = await call(client, request)
        except ConnectError as exc:
            if not _is_real_unavailability(exc) or _monotonic() - started + delay > policy.budget:
                raise map_connect_error(exc) from exc
            await _sleep(delay)
            delay = min(delay * 2, policy.max_delay)
            continue
        return decoder(response)
