"""Load a startup catalog: bounded retries of an idempotent read, then validation.

The client loads the spot config and the funding (deposit/withdraw) config when
it is created, each on its own. A read that fails the way a dropped or stalled
connection does (``unavailable``, ``deadline_exceeded``) is read again, at most
``STARTUP_ATTEMPTS`` times in all, with backoff, and never past the startup
deadline; every retry goes through a connection of its own. Anything else, and
a response that does not validate, ends the load at once. Only these reads are
retried here: they change nothing on the server.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pyqwest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.message import Message

from polyester._redact import redact_text
from polyester.errors import PolyesterCatalogHydrationError
from polyester.services._retry import _is_real_unavailability
from polyester.transport import TransportFactory, capture_response_refs

STARTUP_ATTEMPTS = 3
INITIAL_BACKOFF = 0.25
MAX_BACKOFF = 1.0

# Indirections so tests can drive the clock.
_sleep = asyncio.sleep
_monotonic = time.monotonic

_FAILURE_WORDS = {
    "timeout": "timed out",
    "connection_closed": "connection closed",
    "connect_failed": "could not connect",
    "unavailable": "server unavailable",
    "error": "request failed",
}


@dataclass(frozen=True, slots=True)
class CatalogSource:
    """One startup catalog: what it is called and how to read it."""

    catalog: str
    name: str
    operation: str
    client_cls: type
    # Sends the read through a generated client, with a deadline in milliseconds.
    read: Callable[[Any, int], Awaitable[Message]]


async def load_catalog(
    transport: TransportFactory,
    source: CatalogSource,
    install: Callable[[Message], None],
    *,
    request_timeout: float,
    deadline: float,
) -> None:
    """Read ``source`` and ``install`` it, or raise ``PolyesterCatalogHydrationError``.

    ``deadline`` is a ``time.monotonic()`` instant; each attempt gets the
    client's request timeout or what is left before the deadline, if less.
    """
    started = _monotonic()
    delay = INITIAL_BACKOFF
    attempt = 0
    while True:
        attempt += 1
        timeout_ms = max(1, int(min(request_timeout, deadline - _monotonic()) * 1000))
        with capture_response_refs() as refs:
            try:
                response = await _read_once(transport, source, timeout_ms, fresh=attempt > 1)
            except ConnectError as exc:
                failure = exc
            else:
                break
        if (
            not _is_real_unavailability(failure)
            or attempt >= STARTUP_ATTEMPTS
            or _monotonic() + delay >= deadline
        ):
            raise _read_failure(
                source,
                failure,
                attempts=attempt,
                elapsed=_monotonic() - started,
                response_ref=refs[-1] if refs else None,
            )
        await _sleep(delay)
        delay = min(delay * 2, MAX_BACKOFF)
    try:
        install(response)
    except Exception as exc:
        raise PolyesterCatalogHydrationError(
            f"catalog hydration failed: {source.name} ({source.operation}) is invalid: "
            f"{redact_text(str(exc))}",
            catalog=source.catalog,
            operation=source.operation,
            failure="invalid",
            attempts=attempt,
        ) from exc


async def _read_once(
    transport: TransportFactory, source: CatalogSource, timeout_ms: int, *, fresh: bool
) -> Message:
    if not fresh:
        return await source.read(transport.create_public_client(source.client_cls), timeout_ms)
    async with transport.fresh_public_client(source.client_cls) as client:
        return await source.read(client, timeout_ms)


def _failure_kind(exc: ConnectError) -> str:
    cause = exc.__cause__
    if exc.code is Code.DEADLINE_EXCEEDED or isinstance(cause, TimeoutError):
        return "timeout"
    if isinstance(cause, ConnectionError):
        return "connect_failed"
    if isinstance(cause, (pyqwest.RemoteProtocolError, pyqwest.ReadError, pyqwest.WriteError)):
        return "connection_closed"
    if exc.code is Code.UNAVAILABLE:
        return "unavailable"
    return "error"


def _read_failure(
    source: CatalogSource,
    exc: ConnectError,
    *,
    attempts: int,
    elapsed: float,
    response_ref: str | None,
) -> PolyesterCatalogHydrationError:
    # Imported here: polyester._wire must load after the codecs, which import it.
    from polyester._wire import map_connect_error

    mapped = map_connect_error(exc)
    mapped.__cause__ = exc
    kind = _failure_kind(exc)
    noun = "attempt" if attempts == 1 else "attempts"
    message = (
        f"catalog hydration failed: {source.name} ({source.operation}) "
        f"{_FAILURE_WORDS[kind]} after {attempts} {noun} in {elapsed:.1f}s"
    )
    if response_ref:
        message += f"; response ref {response_ref}"
    error = PolyesterCatalogHydrationError(
        f"{message}: {redact_text(str(mapped))}",
        catalog=source.catalog,
        operation=source.operation,
        failure=kind,
        attempts=attempts,
        response_ref=response_ref,
    )
    error.__cause__ = mapped
    return error
