from __future__ import annotations

from datetime import datetime

import msgspec


class ServerVersion(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The build an environment serves (``system.v1.SystemService/GetVersion``).

    ``version`` is ``MAJOR.MINOR.PATCH`` for a release, such as ``0.10.0``. A
    build made after a release, which devnet may run, appends the number of
    source revisions since that release and ``g`` with the first 12 hexadecimal
    digits of its own revision: ``0.10.0-12-g4e21a2f09670``. It is not a
    semantic version: compare :attr:`release` to tell which release a build
    follows. ``commit`` is the full source revision of the build.
    ``environment`` names the environment that answered, such as ``devnet``,
    ``testnet``, ``mainnet`` or ``local``; it is a plain string, so a name this
    SDK does not know yet still reads.
    """

    version: str = ""
    commit: str = ""
    environment: str = ""

    @property
    def release(self) -> str:
        """The release a build follows: ``version`` up to its first ``-``."""
        return self.version.split("-", 1)[0]


# Status event kind labels.
STATUS_EVENT_KIND_MAINTENANCE = "maintenance"
STATUS_EVENT_KIND_INCIDENT = "incident"

# Status event state labels, as the window stands at the time of the response.
STATUS_EVENT_STATE_SCHEDULED = "scheduled"
STATUS_EVENT_STATE_IN_PROGRESS = "in_progress"
STATUS_EVENT_STATE_COMPLETED = "completed"
STATUS_EVENT_STATE_CANCELLED = "cancelled"

# Incident impact labels; "" for a maintenance and an incident not yet assessed.
STATUS_EVENT_IMPACT_DEGRADED = "degraded"
STATUS_EVENT_IMPACT_PARTIAL_OUTAGE = "partial_outage"
STATUS_EVENT_IMPACT_MAJOR_OUTAGE = "major_outage"

# Affected service labels: "trading", "market_data", "deposits",
# "withdrawals", "transfers", "accounts", "api", "quickswap", "app". A kind,
# state, impact or service newer than this SDK reads as its number, such as
# "10".


class StatusEventUpdate(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One progress note on a status event. Notes are never edited or removed;
    ``id`` is the note's position on its event, from 1."""

    id: int = 0
    message: str = ""
    created_at: datetime | None = None


class StatusEvent(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One scheduled maintenance or incident
    (``system.v1.SystemService/ListStatusEvents``).

    ``id`` is the event's stable public ID in base58. ``kind``, ``state``,
    ``impact`` and ``services`` are lowercase labels (``"maintenance"``,
    ``"in_progress"``, ``"degraded"``, ``"deposits"``); ``impact`` is "" for a
    maintenance and an incident not yet assessed. ``start_time`` and
    ``end_time`` bound the window: a maintenance always has an end, an
    incident without an expected end has ``end_time`` ``None``.
    ``cancelled_at`` is set only for a cancelled event, and ``details_url`` is
    ``None`` when the event links no announcement. ``markets`` (pair symbols)
    and ``assets`` (asset codes) are empty when the event is not limited to
    particular ones. ``updated_at`` moves with every change, a new note
    included, but not when the state moves only with the clock: compare it per
    ``id`` to refresh a banner.
    """

    id: str = ""
    kind: str = ""
    state: str = ""
    title: str = ""
    message: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    services: list[str] = msgspec.field(default_factory=list)
    markets: list[str] = msgspec.field(default_factory=list)
    updated_at: datetime | None = None
    impact: str = ""
    assets: list[str] = msgspec.field(default_factory=list)
    cancelled_at: datetime | None = None
    updates: list[StatusEventUpdate] = msgspec.field(default_factory=list)
    details_url: str | None = None


class StatusEventsPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of status events, the latest start first. ``next_page_token``
    is "" on the last page."""

    events: list[StatusEvent] = msgspec.field(default_factory=list)
    next_page_token: str = ""
