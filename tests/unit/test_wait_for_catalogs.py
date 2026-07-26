"""POLY-3746: wait_for_catalogs fails closed when hydration fails."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterTransportError, PolyesterValidationError


@pytest.mark.asyncio
async def test_wait_for_catalogs_raises_on_http_failure() -> None:
    client = AsyncPolyester(hydrate_catalogs=False)
    client.market_data.get_spot_config = AsyncMock(  # type: ignore[method-assign]
        side_effect=PolyesterTransportError("spot 500")
    )
    client._catalog_task = __import__("asyncio").create_task(client._hydrate_catalogs())
    with pytest.raises(PolyesterTransportError, match="spot 500"):
        await client.wait_for_catalogs()
    assert client.catalogs_last_error is not None
    assert "spot 500" in str(client.catalogs_last_error)
    await client.aclose()


@pytest.mark.asyncio
async def test_wait_for_catalogs_raises_on_empty_spot() -> None:
    class _Spot:
        raw = {"pairs": []}

    client = AsyncPolyester(hydrate_catalogs=False)
    client.market_data.get_spot_config = AsyncMock(return_value=_Spot())  # type: ignore[method-assign]
    client._catalog_task = __import__("asyncio").create_task(client._hydrate_catalogs())
    with pytest.raises(PolyesterValidationError, match="empty"):
        await client.wait_for_catalogs()
    assert client.catalogs.is_unusable
    await client.aclose()


@pytest.mark.asyncio
async def test_wait_for_catalogs_noop_when_disabled() -> None:
    client = AsyncPolyester(hydrate_catalogs=False)
    await client.wait_for_catalogs()
    assert client.catalogs_last_error is None
    await client.aclose()
