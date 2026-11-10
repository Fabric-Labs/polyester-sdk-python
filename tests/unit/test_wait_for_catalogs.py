"""POLY-3746: wait_for_catalogs fails closed when hydration fails.

POLY-9228: it raises ``PolyesterCatalogHydrationError`` naming the spot config,
with the failure as ``__cause__`` (the error ``catalogs_last_error`` holds).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

import polyester.client as client_module
from polyester import AsyncPolyester
from polyester.errors import (
    PolyesterCatalogHydrationError,
    PolyesterServerError,
    PolyesterValidationError,
)
from polyester.gen.marketdata.v1 import marketdata_pb2


def _start_spot_load(client: AsyncPolyester) -> None:
    client._catalog_task = asyncio.create_task(client._hydrate_spot(time.monotonic() + 5))


@pytest.mark.asyncio
async def test_wait_for_catalogs_raises_on_http_failure(monkeypatch) -> None:
    async def read(_client, _timeout_ms):
        raise ConnectError(Code.INTERNAL, "spot 500")

    monkeypatch.setattr(client_module, "SPOT_CONFIG", replace(client_module.SPOT_CONFIG, read=read))
    client = AsyncPolyester(hydrate_catalogs=False)
    _start_spot_load(client)
    with pytest.raises(PolyesterCatalogHydrationError, match="spot 500") as info:
        await client.wait_for_catalogs()
    assert info.value.catalog == "spot"
    assert info.value.attempts == 1
    assert isinstance(info.value.__cause__, PolyesterServerError)
    assert client.catalogs_last_error is info.value.__cause__
    assert "spot 500" in str(client.catalogs_last_error)
    await client.aclose()


@pytest.mark.asyncio
async def test_wait_for_catalogs_raises_on_empty_spot(monkeypatch) -> None:
    async def read(_client, _timeout_ms):
        return marketdata_pb2.GetSpotConfigResponse()

    monkeypatch.setattr(client_module, "SPOT_CONFIG", replace(client_module.SPOT_CONFIG, read=read))
    client = AsyncPolyester(hydrate_catalogs=False)
    _start_spot_load(client)
    with pytest.raises(PolyesterCatalogHydrationError, match="empty") as info:
        await client.wait_for_catalogs()
    assert info.value.failure == "invalid"
    assert isinstance(info.value.__cause__, PolyesterValidationError)
    assert client.catalogs.is_unusable
    await client.aclose()


@pytest.mark.asyncio
async def test_wait_for_catalogs_noop_when_disabled() -> None:
    client = AsyncPolyester(hydrate_catalogs=False)
    await client.wait_for_catalogs()
    await client.wait_for_funding_catalog()
    assert client.catalogs_last_error is None
    await client.aclose()
