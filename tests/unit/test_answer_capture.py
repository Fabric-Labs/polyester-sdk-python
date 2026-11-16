"""An answer's metadata is captured when its headers arrive.

Whatever then goes wrong with that answer, the error carries the answer's own
status and the delay it asked for: a body cut short, a body too large to read,
a body that never ends before the deadline, or a redirect the SDK refuses to
follow, with a valid or a malformed ``Location``. Each case is one request and
returns at once, since a 30 s delay is past every budget. A call that got no
answer at all carries neither.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
import pytest

from polyester import AsyncPolyester
from polyester.chain.rpc import JsonRpcClient, JsonRpcHttpError
from polyester.errors import PolyesterError, PolyesterRedirectError
from polyester.realtime.auth import fetch_rt_token
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

TIMEOUT = 0.4
REFUSED = "http://127.0.0.1:1"


def _truncated(status: int) -> HttpScript:
    # The headers promise 100 bytes; one arrives and the connection closes.
    return HttpScript.raw(
        status,
        headers=[
            ("Content-Type", "application/json"),
            ("Content-Length", "100"),
            ("Retry-After", "30"),
        ],
        body=b"{",
    )


def _oversized(status: int) -> HttpScript:
    body = b'{"code":"unavailable","message":"' + b"x" * (1024 * 1024) + b'"}'
    return HttpScript.raw(
        status,
        headers=[
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Retry-After", "30"),
        ],
        body=body,
    )


def _stalled(status: int) -> HttpScript:
    # The headers arrive; the body never does before the deadline.
    return HttpScript.headers_then_stall(
        status,
        headers=[
            ("Content-Type", "application/json"),
            ("Content-Length", "100"),
            ("Retry-After", "30"),
        ],
        stall=10.0,
    )


BODY_FAILURES: dict[str, Callable[[int], HttpScript]] = {
    "truncated": _truncated,
    "oversized": _oversized,
    "body deadline": _stalled,
}


def _redirect(location: str) -> HttpScript:
    return HttpScript.raw(
        307,
        headers=[("Location", location), ("Retry-After", "30"), ("Content-Length", "0")],
    )


class _Target:
    """A redirect target that counts what reaches it."""

    def __init__(self) -> None:
        self.calls = 0
        self.server: MockHttpServer | None = None

    async def __aenter__(self) -> _Target:
        async def handler(req: ParsedRequest) -> HttpScript:
            self.calls += 1
            return HttpScript.json(200, {})

        self.server = await MockHttpServer.spawn(handler)
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self.server is not None
        await self.server.aclose()

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"{self.server.base_url}/elsewhere"


MALFORMED_LOCATION = "http://[::1/broken"


async def _answer_with(script: HttpScript, call) -> tuple[BaseException | None, int, float]:
    """Answer every request with ``script``; return the call's error, the
    requests that reached the server and the time the call took."""
    calls = 0

    async def handler(req: ParsedRequest) -> HttpScript:
        nonlocal calls
        calls += 1
        return script

    server = await MockHttpServer.spawn(handler)
    started = time.monotonic()
    try:
        try:
            await call(server.base_url)
        except Exception as exc:
            return exc, calls, time.monotonic() - started
        return None, calls, time.monotonic() - started
    finally:
        await server.aclose()


def _assert_answer(error: BaseException | None, status: int, calls: int, elapsed: float) -> None:
    assert error is not None
    assert calls == 1, (calls, repr(error))
    assert elapsed < 3.0, (elapsed, repr(error))
    assert getattr(error, "status_code", None) == status, repr(error)
    assert getattr(error, "retry_after", None) == 30, repr(error)


# --- the API transport (ConnectRPC and REST) ----------------------------------------------------


def _api_call(op: str):
    async def call(base_url: str) -> None:
        creds = make_test_credentials()
        client = AsyncPolyester(
            api_url=base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
            timeout=TIMEOUT,
        )
        try:
            if op == "read":
                await client.triggers.get(trigger_id="9")
            else:
                await client.triggers.cancel(trigger_id="9")
        finally:
            await client.aclose()

    return call


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("failure", list(BODY_FAILURES))
async def test_api_body_failure_carries_the_answer(failure: str, op: str) -> None:
    error, calls, elapsed = await _answer_with(BODY_FAILURES[failure](503), _api_call(op))
    assert isinstance(error, PolyesterError), repr(error)
    _assert_answer(error, 503, calls, elapsed)


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("malformed", [False, True], ids=["valid", "malformed"])
async def test_api_refused_redirect_carries_the_answer(malformed: bool, op: str) -> None:
    async with _Target() as target:
        location = MALFORMED_LOCATION if malformed else target.url
        error, calls, elapsed = await _answer_with(_redirect(location), _api_call(op))
    assert isinstance(error, PolyesterRedirectError), repr(error)
    assert error.malformed is malformed
    _assert_answer(error, 307, calls, elapsed)
    assert target.calls == 0


# --- the realtime token, subscription and sub-account answers -----------------------------------


async def _token(base_url: str) -> None:
    creds = make_test_credentials()
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        await fetch_rt_token(
            http, creds, url=f"{base_url}/v1/rt/token", label="realtime connection token"
        )


@pytest.mark.parametrize("failure", list(BODY_FAILURES))
async def test_realtime_body_failure_carries_the_answer(failure: str) -> None:
    error, calls, elapsed = await _answer_with(BODY_FAILURES[failure](503), _token)
    assert isinstance(error, PolyesterError), repr(error)
    _assert_answer(error, 503, calls, elapsed)


@pytest.mark.parametrize("malformed", [False, True], ids=["valid", "malformed"])
async def test_realtime_refused_redirect_carries_the_answer(malformed: bool) -> None:
    async with _Target() as target:
        location = MALFORMED_LOCATION if malformed else target.url
        error, calls, elapsed = await _answer_with(_redirect(location), _token)
    assert isinstance(error, PolyesterRedirectError), repr(error)
    _assert_answer(error, 307, calls, elapsed)
    assert target.calls == 0


# --- a JSON-RPC endpoint's answer ----------------------------------------------------------------


async def _jsonrpc(base_url: str) -> None:
    await JsonRpcClient(base_url, timeout=TIMEOUT).arequest("eth_chainId")


@pytest.mark.parametrize("failure", list(BODY_FAILURES))
async def test_jsonrpc_body_failure_carries_the_answer(failure: str) -> None:
    error, calls, elapsed = await _answer_with(BODY_FAILURES[failure](503), _jsonrpc)
    assert isinstance(error, JsonRpcHttpError), repr(error)
    _assert_answer(error, 503, calls, elapsed)


@pytest.mark.parametrize("malformed", [False, True], ids=["valid", "malformed"])
async def test_jsonrpc_redirect_is_not_followed_and_carries_the_answer(malformed: bool) -> None:
    async with _Target() as target:
        location = MALFORMED_LOCATION if malformed else target.url
        error, calls, elapsed = await _answer_with(_redirect(location), _jsonrpc)
    assert isinstance(error, JsonRpcHttpError), repr(error)
    _assert_answer(error, 307, calls, elapsed)
    assert target.calls == 0


# --- no answer, no metadata ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [_api_call("read"), _api_call("write"), _token, _jsonrpc],
    ids=["read", "write", "token", "jsonrpc"],
)
async def test_no_answer_carries_no_metadata(call) -> None:
    with pytest.raises(Exception) as raised:
        await call(REFUSED)
    assert getattr(raised.value, "status_code", None) is None, repr(raised.value)
    assert getattr(raised.value, "retry_after", None) is None, repr(raised.value)
