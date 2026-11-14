from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from polyester.codecs.decode.system import status_events_page_from_proto
from polyester.gen.system.v1 import system_pb2
from polyester.gen.system.v1.system_connect import SystemServiceClient
from polyester.models.system import ServerVersion, StatusEvent, StatusEventsPage
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded
from polyester.services._validation import validate_limit
from polyester.services.changelog import _enum_values, _paginate


def server_version_from_proto(msg: system_pb2.GetVersionResponse) -> ServerVersion:
    return ServerVersion(
        version=msg.version,
        commit=msg.commit,
        environment=msg.environment,
    )


class AsyncSystemService(BaseService):
    """The environment's build and its scheduled maintenance and incidents.
    Needs no API key; calls count against the public per-IP read budget."""

    async def get_version(self) -> ServerVersion:
        return await unary_public_decoded(
            self._transport,
            SystemServiceClient,
            lambda client, req: client.get_version(req),
            system_pb2.GetVersionRequest(),
            server_version_from_proto,
        )

    async def list_status_events(
        self,
        *,
        states: Sequence[str] | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> StatusEventsPage:
        """One page of status events, the latest start first.

        ``states`` (``"scheduled"``, ``"in_progress"``, ``"completed"``,
        ``"cancelled"``) and ``kinds`` (``"maintenance"``, ``"incident"``)
        filter; no ``states`` lists current and upcoming events, as the server
        decides. A label this SDK does not know raises
        ``PolyesterValidationError`` before anything is sent. ``limit``
        defaults to 50 on the server (maximum 200). Reuse ``page_token`` only
        with the same ``states`` and ``kinds``: the server refuses it with
        other filters. Answers can be up to 10 seconds old.
        """
        request = system_pb2.ListStatusEventsRequest(
            states=_enum_values(system_pb2.StatusEventState, states, "states"),
            kinds=_enum_values(system_pb2.StatusEventKind, kinds, "kinds"),
            limit=validate_limit(limit, allow_none=True) or 0,
            page_token=page_token or "",
        )
        return await unary_public_decoded(
            self._transport,
            SystemServiceClient,
            lambda client, req: client.list_status_events(req),
            request,
            status_events_page_from_proto,
        )

    async def iter_status_events(
        self,
        *,
        states: Sequence[str] | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[StatusEvent]:
        """Every status event matching ``states`` and ``kinds`` from
        ``page_token`` (or the latest start) on, fetching pages as needed with
        the same filters. States follow the clock, so an event that changes
        state between two pages can be missing from both or come twice: match
        events by ``id``."""

        async def fetch(token: str | None) -> tuple[list[StatusEvent], str]:
            page = await self.list_status_events(
                states=states, kinds=kinds, limit=limit, page_token=token
            )
            return page.events, page.next_page_token

        async for event in _paginate("ListStatusEvents", page_token, fetch):
            yield event
