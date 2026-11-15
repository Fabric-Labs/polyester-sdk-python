"""api_url and ws_url refuse a query string or fragment, with the same error.

The SDK appends paths to both and sends them on every request, connect and
reconnect, outside any signature, so nothing put in one by mistake may stay.
"""

from __future__ import annotations

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterValidationError


@pytest.mark.parametrize(
    ("field", "url"),
    [
        ("api_url", "https://example.test/api?token=SECRET123"),
        ("api_url", "https://example.test?"),
        ("api_url", "https://example.test/api#frag"),
        ("api_url", "https://example.test#"),
        ("ws_url", "wss://example.test/connection/websocket?token=SECRET123"),
        ("ws_url", "wss://example.test?"),
        ("ws_url", "wss://example.test/connection/websocket#frag"),
        ("ws_url", "wss://example.test#"),
    ],
)
async def test_base_url_with_query_or_fragment_is_refused(field: str, url: str) -> None:
    with pytest.raises(PolyesterValidationError) as raised:
        AsyncPolyester(hydrate_catalogs=False, **{field: url})
    assert str(raised.value) == f"{field} must not contain a query string or fragment"


@pytest.mark.parametrize(
    "ws_url", ["wss://example.test", "wss://example.test/connection/websocket"]
)
async def test_plain_ws_url_is_accepted(ws_url: str) -> None:
    client = AsyncPolyester(hydrate_catalogs=False, ws_url=ws_url)
    await client.aclose()
