from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable

from polyester.transport import TransportFactory

# Waits for the client's construction-time catalog hydration and raises when it
# failed, as ``AsyncPolyester.wait_for_catalogs`` does. The client passes one
# that raises :class:`~polyester.errors.PolyesterCatalogHydrationError`.
CatalogWait = Callable[[], Awaitable[None]]


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
        result from the catalogs and works without them: it waits as long,
        but a failed hydration costs only the labels.
        """
        if self._wait_for_catalogs is None:
            return
        if required:
            await self._wait_for_catalogs()
            return
        with contextlib.suppress(Exception):
            await self._wait_for_catalogs()
