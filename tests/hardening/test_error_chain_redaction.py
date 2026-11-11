"""POLY-9228: no member of an error's chain prints a credential.

An answer, or a transport error, can quote a URL with userinfo, such as a
proxy's. The SDK's own message was redacted, but the exceptions it chains for
debugging (the ``ConnectError`` and what caused it) kept the raw text, so
``traceback.format_exception`` printed the credential. The chain is now
redacted where Connect errors are mapped, keeping each exception's class and
``__cause__``. The URL and credentials here are synthetic.
"""

from __future__ import annotations

import traceback

import pytest
from connectrpc.errors import ConnectError

from polyester import AsyncPolyester
from polyester.errors import (
    PolyesterCatalogHydrationError,
    PolyesterError,
    PolyesterServerError,
)
from polyester.gen.marketdata.v1 import marketdata_pb2
from tests.hardening_support import HttpScript, MockHttpServer, ParsedRequest

USER = "sdk-proxy-user"
SECRET = "proxy-secret-9228"
QUERY = "token=query-secret"
PROXY_URL = f"http://{USER}:{SECRET}@proxy.example.test:3128/tunnel?{QUERY}"

ANSWERS = [
    pytest.param(
        lambda: HttpScript.json(
            503, {"code": "unavailable", "message": f"upstream {PROXY_URL} refused"}
        ),
        id="connect-error",
    ),
    pytest.param(
        lambda: HttpScript.json(
            502, {"code": "EDGE_PROXY_FAILED", "detail": f"upstream {PROXY_URL} refused"}
        ),
        id="gateway-problem",
    ),
]


def _chain(error: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in seen:
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


def _assert_clean(error: BaseException) -> None:
    printed = "".join(traceback.format_exception(error))
    for member in _chain(error):
        printed += str(member) + repr(member)
    for secret in (USER, SECRET, QUERY):
        assert secret not in printed, printed


def _spot_body() -> bytes:
    spot = marketdata_pb2.GetSpotConfigResponse()
    for code, scale in (("BTC", 8), ("USDT", 6)):
        asset = spot.assets.add()
        asset.asset = code
        asset.quantity_scale = scale
        asset.market_data_volume_scale = scale
    pair = spot.pairs.add()
    pair.symbol = "BTC-USDT"
    pair.symbol_id = 1
    pair.base_asset = "BTC"
    pair.quote_asset = "USDT"
    pair.base_quantity_scale = 8
    pair.quote_quantity_scale = 6
    pair.reference_price_scale = 9
    return spot.SerializeToString()


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ANSWERS)
async def test_a_unary_call_chains_no_credential(answer) -> None:
    http = await MockHttpServer.spawn(lambda _req: answer())
    client = AsyncPolyester(
        api_url=http.base_url, ws_url="ws://127.0.0.1:9/unused", hydrate_catalogs=False
    )
    try:
        with pytest.raises(PolyesterServerError) as info:
            await client.market_data.get_spot_config()
        error = info.value
        # The classes and the cause stay as they were.
        assert isinstance(error.__cause__, ConnectError)
        assert "upstream" in str(error)
        assert "proxy.example.test" in str(error)
        _assert_clean(error)
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ANSWERS)
async def test_catalog_startup_chains_no_credential(answer) -> None:
    def handler(req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/GetSpotConfig"):
            return HttpScript.raw(
                200, headers=[("Content-Type", "application/proto")], body=_spot_body()
            )
        return answer()

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(api_url=http.base_url, ws_url="ws://127.0.0.1:9/unused", timeout=2.0)
    try:
        await client.wait_for_catalogs()
        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await client.wait_for_funding_catalog()
        error = info.value
        assert isinstance(error.__cause__, PolyesterError)
        assert isinstance(error.__cause__.__cause__, ConnectError)
        _assert_clean(error)
    finally:
        await client.aclose()
        await http.aclose()


# Round 2: URLs whose userinfo or query holds a parenthesis or an apostrophe,
# OSError fields that are not args, and structured diagnostics.

TRICKY_URLS = [
    pytest.param(f"http://{USER}:one(two-{SECRET})@proxy.example.test/x", id="paren-userinfo"),
    pytest.param(f"http://{USER}:one'two-{SECRET}@proxy.example.test/x", id="quote-userinfo"),
    pytest.param(f"http://proxy.example.test/x?{QUERY}one(two-{SECRET})", id="paren-query"),
    pytest.param(f"http://proxy.example.test/x?{QUERY}one'two-{SECRET}", id="quote-query"),
    pytest.param(f"http://{USER}:{SECRET}?bad@proxy.example.test/x", id="question-in-userinfo"),
    pytest.param(f"http://{USER}:{SECRET}#bad@proxy.example.test/x", id="hash-in-userinfo"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", TRICKY_URLS)
async def test_a_url_with_parentheses_or_quotes_is_redacted(url: str) -> None:
    answer = HttpScript.json(503, {"code": "unavailable", "message": f"upstream {url} refused"})
    http = await MockHttpServer.spawn(lambda _req: answer)
    client = AsyncPolyester(
        api_url=http.base_url, ws_url="ws://127.0.0.1:9/unused", hydrate_catalogs=False
    )
    try:
        with pytest.raises(PolyesterServerError) as info:
            await client.market_data.get_spot_config()
        if "bad@" in url:
            # A URL the parser refuses is dropped whole, as before.
            assert "[REDACTED INVALID URL]" in str(info.value)
        else:
            assert "proxy.example.test" in str(info.value)
        _assert_clean(info.value)
    finally:
        await client.aclose()
        await http.aclose()


class _FailingHTTP:
    """An HTTP client whose every request fails with ``error``."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def post(self, *_args, **_kwargs):
        raise self.error

    async def get(self, *_args, **_kwargs):
        raise self.error


def _os_errors() -> list:
    import errno

    return [
        pytest.param(
            lambda: ConnectionResetError(errno.ECONNRESET, f"upstream {PROXY_URL}"),
            id="connection-reset-strerror",
        ),
        pytest.param(lambda: OSError(errno.EIO, "failure", PROXY_URL), id="os-error-filename"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("make_error", _os_errors())
async def test_a_transport_os_error_is_redacted_in_every_field(make_error) -> None:
    client = AsyncPolyester(
        api_url="http://127.0.0.1:9", ws_url="ws://127.0.0.1:9/unused", hydrate_catalogs=False
    )
    client._transport._connect_http = _FailingHTTP(make_error())  # type: ignore[assignment]
    try:
        with pytest.raises(PolyesterServerError) as info:
            await client.market_data.get_spot_config()
        cause = info.value.__cause__
        assert isinstance(cause, ConnectError)
        assert isinstance(cause.__cause__, OSError)
        _assert_clean(info.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("make_error", _os_errors())
async def test_a_catalog_load_os_error_is_redacted_in_every_field(make_error) -> None:
    client = AsyncPolyester(
        api_url="http://127.0.0.1:9",
        ws_url="ws://127.0.0.1:9/unused",
        timeout=0.5,
        catalog_timeout=1.0,
    )
    failing = _FailingHTTP(make_error())
    client._transport._connect_http = failing  # type: ignore[assignment]

    class _Transport:
        async def aclose(self) -> None:
            return None

    def fresh():  # every retry fails the same way
        return _Transport()

    client._transport._new_http_transport = fresh  # type: ignore[assignment]
    import polyester.transport as transport_module

    original = transport_module._ConnectHTTPClient

    class _Failing(original):  # type: ignore[misc, valid-type]
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def post(self, *_args, **_kwargs):
            raise make_error()

    transport_module._ConnectHTTPClient = _Failing  # type: ignore[misc]
    try:
        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await client.wait_for_funding_catalog()
        _assert_clean(info.value)
    finally:
        transport_module._ConnectHTTPClient = original  # type: ignore[misc]
        await client.aclose()


STRUCTURED = [
    pytest.param(
        401,
        {"code": "TIMESTAMP_SKEW", "detail": f"upstream {PROXY_URL} refused"},
        "problem",
        id="timestamp-skew-problem",
    ),
    pytest.param(
        429,
        {
            "code": "RATE_LIMIT_EXCEEDED",
            "detail": f"upstream {PROXY_URL}",
            "rate_limit": {"reason": "ip", "operation_id": PROXY_URL},
        },
        "detail",
        id="rate-limit-detail",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "body", "attribute"), STRUCTURED)
async def test_structured_diagnostics_are_redacted(status: int, body: dict, attribute: str) -> None:
    http = await MockHttpServer.spawn(lambda _req: HttpScript.json(status, body))
    client = AsyncPolyester(
        api_url=http.base_url, ws_url="ws://127.0.0.1:9/unused", hydrate_catalogs=False
    )
    try:
        with pytest.raises(PolyesterError) as info:
            await client.market_data.get_spot_config()
        diagnostic = getattr(info.value, attribute)
        assert diagnostic is not None, info.value
        printed = repr(diagnostic) + str(diagnostic)
        for secret in (USER, SECRET, QUERY):
            assert secret not in printed, printed
        _assert_clean(info.value)
    finally:
        await client.aclose()
        await http.aclose()


# Client-held secrets: the userinfo of the client's own API and WebSocket URLs,
# of the environment's proxies, and the API private key never reach an error's
# text, however the answer quotes them.

API_USER, API_SECRET = "sdk-api-user", "api-secret-9228"
WS_USER, WS_SECRET = "sdk-ws-user", "ws-secret-9228"
ENV_USER, ENV_SECRET = "sdk-env-proxy-user", "env-proxy-secret-9228"


@pytest.mark.asyncio
async def test_client_held_secrets_never_reach_an_error(monkeypatch) -> None:
    from tests.hardening_support import make_test_credentials

    monkeypatch.setenv("HTTPS_PROXY", f"http://{ENV_USER}:{ENV_SECRET}@127.0.0.1:9")
    creds = make_test_credentials()
    seed = creds.private_key[:32].hex()
    message = (
        f"auth {API_USER}:{API_SECRET} via http//{API_USER}:{API_SECRET}@api "
        f"ws {WS_USER}:{WS_SECRET} and {WS_SECRET} proxy {ENV_USER}:{ENV_SECRET} and {ENV_SECRET} "
        f"key {seed} "
        f"{creds.private_key.hex()} {API_SECRET}"
    )
    http = await MockHttpServer.spawn(
        lambda _req: HttpScript.json(503, {"code": "unavailable", "message": message})
    )
    host = http.base_url.removeprefix("http://")
    client = AsyncPolyester(
        api_url=f"http://{API_USER}:{API_SECRET}@{host}",
        ws_url=f"ws://{WS_USER}:{WS_SECRET}@127.0.0.1:9/unused",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(PolyesterServerError) as info:
            await client.market_data.get_spot_config()
        printed = "".join(traceback.format_exception(info.value))
        for member in _chain(info.value):
            printed += str(member) + repr(member)
        for secret in (
            f"{API_USER}:{API_SECRET}",
            API_SECRET,
            f"{WS_USER}:{WS_SECRET}",
            WS_SECRET,
            f"{ENV_USER}:{ENV_SECRET}",
            ENV_SECRET,
            seed,
        ):
            assert secret not in printed, (secret, printed)
        assert "[REDACTED]" in str(info.value)
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
async def test_percent_encoded_environment_proxy_userinfo_is_redacted_decoded(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "HTTPS_PROXY", "http://decoded%2Denv%2Duser:decoded%2Denv%2Dsecret%2DA73x@127.0.0.1:9"
    )
    message = "proxy decoded-env-user:decoded-env-secret-A73x and decoded-env-secret-A73x refused"
    http = await MockHttpServer.spawn(
        lambda _req: HttpScript.json(503, {"code": "unavailable", "message": message})
    )
    client = AsyncPolyester(
        api_url=http.base_url, ws_url="ws://127.0.0.1:9/unused", hydrate_catalogs=False
    )
    try:
        with pytest.raises(PolyesterServerError) as info:
            await client.market_data.get_spot_config()
        printed = "".join(traceback.format_exception(info.value))
        for member in _chain(info.value):
            printed += str(member) + repr(member)
        assert "decoded-env-secret-A73x" not in printed, printed
        assert "decoded-env-user:decoded-env-secret-A73x" not in printed, printed
    finally:
        await client.aclose()
        await http.aclose()
