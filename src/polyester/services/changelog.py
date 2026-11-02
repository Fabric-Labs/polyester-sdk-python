from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any, Literal, TypeVar

from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.changelog import (
    changelog_changes_page_from_proto,
    changelog_post_from_proto,
    changelog_posts_page_from_proto,
)
from polyester.codecs.scalars import datetime_to_timestamp_dict
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.changelog.v1 import changelog_pb2
from polyester.gen.changelog.v1.changelog_connect import ChangelogServiceClient
from polyester.models.changelog import (
    CHANGELOG_CATEGORY_BREAKING_CHANGE,
    ChangelogChangeEntry,
    ChangelogChangesPage,
    ChangelogPost,
    ChangelogPostsPage,
    ChangelogPostSummary,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded
from polyester.services._validation import validate_limit

T = TypeVar("T")

# Page size of the *_since helpers: the server maximum, so a long history
# costs as few rate-limited requests as possible.
_SINCE_PAGE_SIZE = 500

_SORT = {
    "asc": changelog_pb2.SORT_ASC,
    "desc": changelog_pb2.SORT_DESC,
}


class AsyncChangelogService(BaseService):
    """Public product changelog of the environment the client points at.

    Needs no API key. Filter labels are lowercase enum names such as
    ``"breaking_change"``, ``"market_makers"`` or ``"api"``.
    """

    async def list_posts(
        self,
        *,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> ChangelogPostsPage:
        """One page of post summaries, newest first. ``limit`` defaults to 20
        on the server (maximum 100)."""
        request = changelog_pb2.ListPostsRequest(
            limit=validate_limit(limit, allow_none=True) or 0,
            page_token=page_token or "",
        )
        return await unary_public_decoded(
            self._transport,
            ChangelogServiceClient,
            lambda client, req: client.list_posts(req),
            request,
            changelog_posts_page_from_proto,
        )

    async def get_post(self, slug: str) -> ChangelogPost:
        """One full post by slug. An unknown slug raises ``PolyesterApiError``
        with code ``not_found`` (see ``is_not_found``)."""
        return await unary_public_decoded(
            self._transport,
            ChangelogServiceClient,
            lambda client, req: client.get_post(req),
            changelog_pb2.GetPostRequest(slug=slug),
            changelog_post_from_proto,
        )

    async def list_changes(
        self,
        *,
        categories: Sequence[str] | None = None,
        action_required: bool | None = None,
        surfaces: Sequence[str] | None = None,
        audiences: Sequence[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        post_slug: str | None = None,
        sort: Literal["asc", "desc"] | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> ChangelogChangesPage:
        """One page of changes across posts.

        Filters on different fields combine with AND; values within one field
        combine with OR. Changes addressed to all users match any audience.
        ``start_time`` is inclusive and ``end_time`` exclusive, both on post
        publication time. ``sort`` orders posts (default ``"desc"``, newest
        first); changes keep publication order inside each post. ``limit``
        defaults to 100 on the server (maximum 500). Reuse ``page_token`` only
        with the same filters, time bounds and sort.
        """
        request = changelog_pb2.ListChangesRequest(
            categories=_enum_values(changelog_pb2.ChangeCategory, categories, "categories"),
            surfaces=_enum_values(changelog_pb2.Surface, surfaces, "surfaces"),
            audiences=_enum_values(changelog_pb2.Audience, audiences, "audiences"),
            post_slug=post_slug or "",
            sort=_sort(sort),
            limit=validate_limit(limit, allow_none=True) or 0,
            page_token=page_token or "",
        )
        if action_required is not None:
            if not isinstance(action_required, bool):
                raise PolyesterValidationError("action_required must be a bool")
            request.action_required = action_required
        if start_time is not None:
            request.start_time.CopyFrom(_timestamp(start_time))
        if end_time is not None:
            request.end_time.CopyFrom(_timestamp(end_time))
        return await unary_public_decoded(
            self._transport,
            ChangelogServiceClient,
            lambda client, req: client.list_changes(req),
            request,
            changelog_changes_page_from_proto,
        )

    async def iter_posts(
        self,
        *,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[ChangelogPostSummary]:
        """Every post summary from ``page_token`` (or the newest post) to the
        oldest, fetching pages as needed."""

        async def fetch(token: str | None) -> tuple[list[ChangelogPostSummary], str]:
            page = await self.list_posts(limit=limit, page_token=token)
            return page.posts, page.next_page_token

        async for post in _paginate("ListPosts", page_token, fetch):
            yield post

    async def iter_changes(
        self,
        *,
        categories: Sequence[str] | None = None,
        action_required: bool | None = None,
        surfaces: Sequence[str] | None = None,
        audiences: Sequence[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        post_slug: str | None = None,
        sort: Literal["asc", "desc"] | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[ChangelogChangeEntry]:
        """Every change matching the filters of ``list_changes``, fetching
        pages as needed."""

        async def fetch(token: str | None) -> tuple[list[ChangelogChangeEntry], str]:
            page = await self.list_changes(
                categories=categories,
                action_required=action_required,
                surfaces=surfaces,
                audiences=audiences,
                start_time=start_time,
                end_time=end_time,
                post_slug=post_slug,
                sort=sort,
                limit=limit,
                page_token=token,
            )
            return page.changes, page.next_page_token

        async for change in _paginate("ListChanges", page_token, fetch):
            yield change

    async def breaking_changes_since(self, since: datetime) -> list[ChangelogChangeEntry]:
        """Every breaking change published at or after ``since``, newest post
        first."""
        return [
            change
            async for change in self.iter_changes(
                categories=[CHANGELOG_CATEGORY_BREAKING_CHANGE],
                start_time=since,
                limit=_SINCE_PAGE_SIZE,
            )
        ]

    async def action_required_since(self, since: datetime) -> list[ChangelogChangeEntry]:
        """Every change that requires integrator action published at or after
        ``since``, newest post first."""
        return [
            change
            async for change in self.iter_changes(
                action_required=True,
                start_time=since,
                limit=_SINCE_PAGE_SIZE,
            )
        ]


async def _paginate(
    operation: str,
    token: str | None,
    fetch: Callable[[str | None], Awaitable[tuple[list[T], str]]],
) -> AsyncIterator[T]:
    """Yield every item of ``fetch``'s pages until a page has no next token.
    A next token equal to the one just sent would loop forever."""
    while True:
        items, next_token = await fetch(token)
        for item in items:
            yield item
        if not next_token:
            return
        if next_token == (token or ""):
            raise PolyesterResponseContractError(
                operation, "next_page_token repeats the request's page_token"
            )
        token = next_token


def _enum_values(enum_type: EnumTypeWrapper, labels: Sequence[str] | None, field: str) -> list[Any]:
    """Map filter labels such as ``"breaking_change"`` to enum numbers. A label
    this SDK does not know cannot be sent."""
    if labels is None:
        return []
    if isinstance(labels, str):
        raise PolyesterValidationError(f"{field} must be a sequence of labels, not a string")
    values: list[Any] = []
    for label in labels:
        try:
            value = int(enum_type.Value(str(label).strip().upper()))
        except ValueError:
            value = 0
        if value == 0:
            raise PolyesterValidationError(f"{field}: unknown value {label!r}")
        values.append(value)
    return values


def _sort(sort: str | None) -> Any:
    if sort is None:
        return changelog_pb2.SORT_DIRECTION_UNSPECIFIED
    value = _SORT.get(str(sort).strip().lower())
    if value is None:
        raise PolyesterValidationError(f'sort must be "asc" or "desc", got {sort!r}')
    return value


def _timestamp(value: datetime) -> Timestamp:
    parts = datetime_to_timestamp_dict(value)
    return Timestamp(seconds=parts["seconds"], nanos=parts["nanos"])
