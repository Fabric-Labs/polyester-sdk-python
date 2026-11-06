"""Whether a subscription the server ended may resume.

The server can end a subscription to a sub-account's channels after access was
granted again. The latest read of ``ListSubaccounts`` decides: listed with a
role means subscribe again with a fresh token. Requests are paced per client so
many subscriptions ending together cannot flood the list or token endpoints.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from polyester.codecs.scalars import UINT64_MAX, id_to_int
from polyester.errors import (
    PolyesterAuthError,
    PolyesterRealtimeError,
    PolyesterSubscriptionEndedError,
    PolyesterValidationError,
)
from polyester.gen.auth.v1 import subaccounts_pb2
from polyester.realtime.auth import signed_get

if TYPE_CHECKING:
    from polyester.realtime.client import AsyncRealtimeClient

SUBACCOUNTS_CHANNEL_PREFIX = "private:auth:subaccounts:"
_SUBACCOUNTS_LIST_PATH = "/v1/auth/subaccounts"
_SUBACCOUNTS_LIST_LABEL = "list sub-accounts"
_MAX_SUBACCOUNT_LIST_BYTES = 4 * 1024 * 1024
# A server unsubscribe code at or above this asks the client to subscribe again;
# a lower one ends the subscription.
_UNSUBSCRIBE_TEMPORARY_FROM = 2500
# The private channels a sub-account's access governs. The ID follows, then an
# optional ":proto".
_SUBACCOUNT_CHANNEL_PREFIXES = (
    "private:ledger:balances:",
    "private:ledger:transfers:",
    "private:spot:trades:",
    "private:spot:triggers:events:",
    "private:spot:triggers:",
    "private:chain:lifecycle:flows:",
)


@dataclass(frozen=True)
class ResubscribeTiming:
    """Bounds on resuming subscriptions the server ended."""

    # Hard limit on attempts without the subscription staying up for stable_after.
    max_attempts: int = 6
    # First per-subscription delay; it doubles per attempt.
    initial_backoff: float = 0.5
    # How long a resumed subscription must stay up to earn a fresh budget.
    stable_after: float = 60.0
    # Paces attempts across one client; each costs two token requests.
    attempt_spacing: float = 0.2
    # Paces ListSubaccounts across one client.
    read_interval: float = 1.0


class ServerUnsubscribedError(PolyesterRealtimeError):
    """Ends one connection whose subscription the server ended."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(f"server ended realtime subscription (code {code}: {reason})")
        self.unsubscribe_code = code
        self.server_reason = reason

    @property
    def temporary(self) -> bool:
        return self.unsubscribe_code >= _UNSUBSCRIBE_TEMPORARY_FROM

    def ended(
        self, channel: str, reason: str, cause: BaseException | None = None
    ) -> PolyesterSubscriptionEndedError:
        return PolyesterSubscriptionEndedError(
            channel=channel,
            unsubscribe_code=self.unsubscribe_code,
            server_reason=self.server_reason,
            reason=reason,
            cause=cause,
        )


def subaccount_channel_id(channel: str) -> int | None:
    """Return the sub-account ID of a channel its access governs."""
    for prefix in _SUBACCOUNT_CHANNEL_PREFIXES:
        if not channel.startswith(prefix):
            continue
        rest = channel[len(prefix) :].removesuffix(":proto")
        if not rest or ":" in rest:
            return None
        try:
            return id_to_int(rest, "account_id")
        except PolyesterValidationError:
            return None
    return None


@dataclass
class ResubscribeAttempt:
    """One subscription's bounded budget for resuming."""

    unsubscribed: ServerUnsubscribedError
    backoff_cap: float
    attempts: int = 0
    ready: bool = False
    ready_at: float = 0.0
    last_error: BaseException | None = field(default=None)

    def note_ready(self) -> None:
        self.ready = True
        self.ready_at = time.monotonic()
        self.last_error = None

    def next_delay(self) -> float:
        half = self.backoff_cap / 2
        delay = half + (secrets.randbelow(1_000_001) / 1_000_000) * half
        self.backoff_cap *= 2
        return delay


class SubaccountAccess:
    """What one client knows about sub-account access, and the pacing of asking."""

    def __init__(
        self, client: AsyncRealtimeClient, timing: ResubscribeTiming | None = None
    ) -> None:
        self._client = client
        self._timing = timing or ResubscribeTiming()
        self._removed: set[int] = set()
        self._next_read: asyncio.Future[set[int]] | None = None
        self._read_tasks: set[asyncio.Task[None]] = set()
        self._last_read = float("-inf")
        self._next_attempt_at = float("-inf")

    def close(self) -> None:
        """Stop reads still running for a closing client."""
        for task in self._read_tasks:
            task.cancel()

    def attempt_after(
        self, current: ResubscribeAttempt | None, unsubscribed: ServerUnsubscribedError
    ) -> ResubscribeAttempt:
        """Budget for a new unsubscribe: kept unless the subscription stayed up."""
        if current is None or (
            current.ready and time.monotonic() - current.ready_at >= self._timing.stable_after
        ):
            current = ResubscribeAttempt(
                unsubscribed=unsubscribed, backoff_cap=self._timing.initial_backoff
            )
        current.unsubscribed = unsubscribed
        current.ready = False
        return current

    def note_update(self, payload: bytes) -> None:
        """Apply one ``auth.v1.Subaccount`` update, in arrival order."""
        update = subaccounts_pb2.Subaccount()
        try:
            update.ParseFromString(payload)
        except Exception:
            return
        if not update.id:
            return
        if update.removed:
            self._removed.add(update.id)
        else:
            self._removed.discard(update.id)

    async def await_resume(self, channel: str, attempt: ResubscribeAttempt) -> None:
        """Return when ``channel`` may be subscribed again; raise why it may not."""
        client = self._client
        account = subaccount_channel_id(channel)
        if account is None or client._credentials is None or not client._api_url:
            raise attempt.unsubscribed.ended(channel, "not_resubscribable")
        while True:
            if account in self._removed:
                raise attempt.unsubscribed.ended(channel, "access_removed")
            if attempt.attempts >= self._timing.max_attempts:
                raise attempt.unsubscribed.ended(channel, "retries_exhausted", attempt.last_error)
            attempt.attempts += 1
            await asyncio.sleep(attempt.next_delay())
            if account in self._removed:
                raise attempt.unsubscribed.ended(channel, "access_removed")
            try:
                listed = await self._read()
            except PolyesterAuthError as exc:
                raise attempt.unsubscribed.ended(channel, "list_refused", exc) from exc
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt.last_error = exc
                continue
            if account not in listed:
                raise attempt.unsubscribed.ended(channel, "not_listed")
            await asyncio.sleep(self._reserve_attempt())
            return

    def _reserve_attempt(self) -> float:
        now = time.monotonic()
        slot = max(self._next_attempt_at, now)
        self._next_attempt_at = slot + self._timing.attempt_spacing
        return slot - now

    async def _read(self) -> set[int]:
        """Listed sub-accounts from a request started after this call, shared and paced."""
        call = self._next_read
        if call is None:
            call = asyncio.get_running_loop().create_future()
            # Waiters may all be cancelled; the outcome must not warn as unretrieved.
            call.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            self._next_read = call
            task = asyncio.create_task(self._run_read(call))
            self._read_tasks.add(task)
            task.add_done_callback(self._read_tasks.discard)
        return await asyncio.shield(call)

    async def _run_read(self, call: asyncio.Future[set[int]]) -> None:
        try:
            wait = self._last_read + self._timing.read_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            # Callers from here on need a read that starts after them.
            self._next_read = None
            self._last_read = time.monotonic()
            listed = await self._fetch_listed()
        except asyncio.CancelledError:
            if self._next_read is call:
                self._next_read = None
            call.cancel()
            raise
        except Exception as exc:
            if not call.done():
                call.set_exception(exc)
        else:
            if not call.done():
                call.set_result(listed)

    async def _fetch_listed(self) -> set[int]:
        client = self._client
        url = f"{client._require_api_url().rstrip('/')}{_SUBACCOUNTS_LIST_PATH}"
        raw = await signed_get(
            client._require_http(),
            client._require_credentials(),
            url=url,
            label=_SUBACCOUNTS_LIST_LABEL,
            max_bytes=_MAX_SUBACCOUNT_LIST_BYTES,
        )
        try:
            payload = json.loads(raw)
            entries = payload.get("subaccounts", [])
            return {
                _listed_id(entry["id"])
                for entry in entries
                if not entry.get("removed") and _has_role(entry.get("role"))
            }
        except (AttributeError, KeyError, TypeError, ValueError, PolyesterValidationError) as exc:
            raise PolyesterRealtimeError(f"{_SUBACCOUNTS_LIST_LABEL}: invalid response") from exc


def _listed_id(value: Any) -> int:
    # The list reports IDs in decimal; a decimal with no zero digit also reads as
    # base58, so decimal comes first.
    if isinstance(value, str) and value.isdecimal():
        parsed = int(value)
        if parsed > UINT64_MAX:
            raise ValueError("id exceeds uint64 range")
        return parsed
    return id_to_int(value, "id")


def _has_role(role: Any) -> bool:
    if isinstance(role, str):
        return role not in ("", "SUBACCOUNT_ROLE_UNSPECIFIED")
    return isinstance(role, int) and not isinstance(role, bool) and role != 0
