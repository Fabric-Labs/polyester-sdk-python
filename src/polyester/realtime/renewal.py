"""Token renewal for one private Centrifugo connection."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Literal

from websockets.asyncio.client import ClientConnection

from polyester.errors import PolyesterRealtimeError
from polyester.realtime.protocol import ProtocolError, Reply, refresh_command, sub_refresh_command

RenewalKind = Literal["connection", "subscription"]


class TokenRenewer:
    """Renews a private connection's connection and subscription tokens.

    It takes fresh tokens from the same endpoints, and handles a failed
    renewal, as the private order stream does: the failure is reported, and
    the server ending the subscription or the connection then drives the usual
    resubscribe. Its work stops with the connection, so a renewal is only ever
    sent on the connection that scheduled it.
    """

    def __init__(
        self,
        ws: ClientConnection,
        channel: str,
        *,
        unit: float,
        first_id: int,
        fetch: Callable[[RenewalKind], Awaitable[str]],
        report: Callable[[BaseException], None],
    ) -> None:
        self._ws = ws
        self._channel = channel
        # Seconds per TTL unit: one, shortened in tests.
        self._unit = unit
        self._next_id = first_id
        self._fetch = fetch
        self._report = report
        # Serialises writes: the reader answers pings while a renewal sends.
        self._send_lock = asyncio.Lock()
        self._pending: dict[int, RenewalKind] = {}
        self._timers: dict[RenewalKind, asyncio.Task[None]] = {}
        self._stopped = False

    async def send(self, frame: bytes) -> None:
        async with self._send_lock:
            await self._ws.send(frame)

    def schedule(self, kind: RenewalKind, expires: bool, ttl: int) -> None:
        """Renew ``kind``'s token ``ttl`` units from now when the server said it expires."""
        if not expires or self._stopped:
            return
        previous = self._timers.pop(kind, None)
        if previous is not None:
            previous.cancel()
        self._timers[kind] = asyncio.create_task(self._renew_after(kind, ttl * self._unit))

    async def _renew_after(self, kind: RenewalKind, delay: float) -> None:
        await asyncio.sleep(delay)
        try:
            token = await self._fetch(kind)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._stopped:
                self._report(exc)
            return
        if self._stopped:
            return
        request_id = self._next_id
        self._next_id += 1
        self._pending[request_id] = kind
        if kind == "subscription":
            frame = sub_refresh_command(request_id, self._channel, token)
        else:
            frame = refresh_command(request_id, token)
        # A failed write leaves the reader to see the connection end.
        with contextlib.suppress(Exception):
            await self.send(frame)

    def handle_reply(self, reply: Reply) -> bool:
        """Take the answer to a renewal and schedule the next; False for any other reply."""
        kind = self._pending.pop(reply.id, None)
        if kind is None:
            return False
        if reply.error is not None:
            # The server ends what it no longer accepts; that drives recovery.
            self._report(_renewal_refused(kind, reply.error))
            return True
        self.schedule(kind, reply.expires, reply.ttl)
        return True

    async def stop(self) -> None:
        """Cancel pending renewals and wait for one in flight to finish."""
        self._stopped = True
        timers = list(self._timers.values())
        self._timers.clear()
        for timer in timers:
            timer.cancel()
        if timers:
            await asyncio.gather(*timers, return_exceptions=True)


def _renewal_refused(kind: RenewalKind, error: ProtocolError) -> PolyesterRealtimeError:
    temporary = " (temporary)" if error.temporary else ""
    return PolyesterRealtimeError(
        f"realtime {kind} token renewal refused: "
        f"centrifugo error {error.code}: {error.message}{temporary}"
    )
