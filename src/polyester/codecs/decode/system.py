from __future__ import annotations

from polyester.codecs.proto_helpers import (
    format_uint64_id,
    has_field,
    optional_timestamp,
    proto_enum_name,
)
from polyester.gen.system.v1 import system_pb2
from polyester.models.system import StatusEvent, StatusEventsPage, StatusEventUpdate


def _labels(enum_type, values) -> list[str]:
    return [label for value in values if (label := proto_enum_name(enum_type, int(value)))]


def status_event_from_proto(msg: system_pb2.StatusEvent) -> StatusEvent:
    """Decode one status event. The id becomes base58; enum values newer than
    this SDK read as their number. Optional times and ``details_url`` stay
    ``None`` when the server omits them."""
    return StatusEvent(
        id=format_uint64_id(int(msg.id)),
        kind=proto_enum_name(system_pb2.StatusEventKind, int(msg.kind)),
        state=proto_enum_name(system_pb2.StatusEventState, int(msg.state)),
        title=msg.title,
        message=msg.message,
        start_time=optional_timestamp(msg, "start_time"),
        end_time=optional_timestamp(msg, "end_time"),
        services=_labels(system_pb2.AffectedService, msg.services),
        markets=list(msg.markets),
        updated_at=optional_timestamp(msg, "updated_at"),
        impact=proto_enum_name(system_pb2.StatusEventImpact, int(msg.impact)),
        assets=list(msg.assets),
        cancelled_at=optional_timestamp(msg, "cancelled_at"),
        updates=[
            StatusEventUpdate(
                id=int(update.id),
                message=update.message,
                created_at=optional_timestamp(update, "created_at"),
            )
            for update in msg.updates
        ],
        details_url=msg.details_url if has_field(msg, "details_url") else None,
    )


def status_events_page_from_proto(msg: system_pb2.ListStatusEventsResponse) -> StatusEventsPage:
    return StatusEventsPage(
        events=[status_event_from_proto(event) for event in msg.events],
        next_page_token=msg.next_page_token,
    )
