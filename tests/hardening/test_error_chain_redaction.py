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
