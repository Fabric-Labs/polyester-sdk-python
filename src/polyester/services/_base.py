from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

from polyester.transport import TransportFactory


class CatalogWait(Protocol):
    """Wait for the client's construction-time catalog hydration.

    With ``required`` a failed hydration raises
    :class:`~polyester.errors.PolyesterCatalogHydrationError`; without it the
    wait only ends once hydration has, whatever its outcome.
    """

    def __call__(self, *, required: bool = True) -> Awaitable[None]: ...


class BaseService:
    # Set by services that read the catalogs; ``None`` when hydration is off.
    _wait_for_catalogs: CatalogWait | None = None

    def __init__(self, transport: TransportFactory) -> None:
        self._transport = transport

    async def _ensure_catalogs(self, *, required: bool = True) -> None:
        """Wait for in-flight catalog hydration before reading the catalogs.

        Call it before resolving a display symbol or reading a pair's scales,
        so a call made right after the client is created doesn't refuse a
        valid symbol. ``required=False`` suits a read that only labels its
        result from the catalogs and works without them.
        """
        if self._wait_for_catalogs is not None:
            await self._wait_for_catalogs(required=required)
