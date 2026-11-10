"""A service's ``wait_for_catalogs`` callback is a zero-argument coroutine function.

``AsyncOrdersService``, ``AsyncTriggersService`` and ``AsyncMarketOverviewService``
accepted ``wait_for_catalogs=client.wait_for_catalogs`` or any ``async def`` taking
no arguments; the services that now wait for hydration keep that contract.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from polyester import AsyncPolyester
from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterError, PolyesterValidationError
from polyester.models import OrderId
from polyester.services import (
    AsyncMarketOverviewService,
    AsyncOrdersService,
    AsyncTriggersService,
)
from polyester.services._base import BaseService


def _services(wait: Any) -> list[tuple[str, Any]]:
    catalogs = CatalogManager()
    transport = MagicMock()
    orders = AsyncOrdersService(transport, catalogs, None, wait_for_catalogs=wait)
    triggers = AsyncTriggersService(transport, catalogs, None, wait_for_catalogs=wait)
    overview = AsyncMarketOverviewService(transport, catalogs=catalogs, wait_for_catalogs=wait)
    return [
        (
            "orders.modify",
            lambda: orders.modify(key=OrderId(1), symbol="NOPE-USDT", new_qty="1"),
        ),
        (
            "triggers.create",
            lambda: triggers.create(
                symbol="NOPE-USDT",
                trigger_type="stop_loss",
                side="sell",
                qty="1",
                trigger_price="0.1",
            ),
        ),
        ("market_overview.list", lambda: overview.list(symbols=["NOPE-USDT"])),
    ]


@pytest.mark.asyncio
async def test_zero_argument_callback_is_awaited_before_resolving() -> None:
    calls: list[str] = []

    async def ready() -> None:
        calls.append("ready")

    for name, call in _services(ready):
        calls.clear()
        with pytest.raises(PolyesterValidationError, match="Unknown symbol 'NOPE-USDT'"):
            await call()
        assert calls == ["ready"], name


@pytest.mark.asyncio
async def test_client_wait_for_catalogs_is_accepted_as_the_callback() -> None:
    client = AsyncPolyester(api_url="http://127.0.0.1:9", hydrate_catalogs=False)
    try:
        for _name, call in _services(client.wait_for_catalogs):
            with pytest.raises(PolyesterValidationError, match="Unknown symbol 'NOPE-USDT'"):
                await call()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_callback_failure_is_raised_where_catalogs_are_required() -> None:
    async def failed() -> None:
        raise PolyesterError("catalogs failed to load")

    for name, call in _services(failed):
        with pytest.raises(PolyesterError, match="catalogs failed to load"):
            await call()
        assert name


@pytest.mark.asyncio
async def test_label_only_wait_tolerates_a_failed_callback() -> None:
    calls: list[str] = []

    async def failed() -> None:
        calls.append("failed")
        raise PolyesterError("catalogs failed to load")

    service = BaseService(MagicMock())
    service._wait_for_catalogs = failed
    await service._ensure_catalogs(required=False)
    assert calls == ["failed"]
    with pytest.raises(PolyesterError, match="catalogs failed to load"):
        await service._ensure_catalogs()
