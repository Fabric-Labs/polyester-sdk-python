"""Changelog client against a fake Connect server (protobuf over HTTP)."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone

import pytest
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, Polyester
from polyester.errors import (
    PolyesterApiError,
    PolyesterError,
    PolyesterResponseContractError,
    PolyesterValidationError,
    is_not_found,
)
from polyester.gen.changelog.v1 import changelog_pb2 as pb

SERVICE = "/changelog.v1.ChangelogService/"
BASE = datetime(2026, 10, 31, 12, tzinfo=UTC)
CATEGORIES = [pb.BREAKING_CHANGE, pb.NEW_FEATURE, pb.IMPROVEMENT, pb.BUG_FIX]
AUTH_HEADERS = ("authorization", "x-api-key-id", "x-api-signature")


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


@dataclass
class FakeChangelog:
    """Posts newest first: post i is published i days before BASE and holds
    two changes; change n has id 1000+n, category CATEGORIES[n % 4] and needs
    action when n % 3 == 0. Page tokens are item offsets."""

    post_count: int
    repeat_token: bool = False
    # When set, replaces every ListPosts next_page_token in order: a server
    # whose tokens cycle back to an earlier page.
    cycle_tokens: list[str] | None = None
    posts: list[pb.Post] = field(default_factory=list)
    entries: list[pb.ChangeEntry] = field(default_factory=list)
    posts_calls: list[pb.ListPostsRequest] = field(default_factory=list)
    changes_calls: list[pb.ListChangesRequest] = field(default_factory=list)
    auth_header_seen: bool = False

    def __post_init__(self) -> None:
        n = 0
        for i in range(self.post_count):
            published = BASE - timedelta(days=i)
            slug = published.strftime("%Y-%m-%d")
            changes = []
            for _ in range(2):
                changes.append(
                    pb.Change(
                        id=1000 + n,
                        title=f"change {n}",
                        summary=f"summary {n}",
                        category=CATEGORIES[n % 4],
                        action_required=n % 3 == 0,
                        audiences=[pb.DEVELOPERS],
                        surfaces=[pb.API],
                    )
                )
                n += 1
            post = pb.Post(
                summary=pb.PostSummary(
                    slug=slug,
                    title=f"post {slug}",
                    published_at=_ts(published),
                    coverage_cutoff=_ts(published - timedelta(hours=1)),
                    change_count=2,
                ),
                sections=[pb.Section(heading="API", summary="API changes", changes=changes)],
            )
            self.posts.append(post)
            for change in changes:
                self.entries.append(
                    pb.ChangeEntry(
                        change=change,
                        post_slug=slug,
                        published_at=_ts(published),
                        section_heading="API",
                    )
                )

    def handle(self, request: Request) -> Response:
        if any(request.headers.get(name) for name in AUTH_HEADERS):
            self.auth_header_seen = True
        method = request.path.removeprefix(SERVICE)
        body = request.get_data()
        if method == "ListPosts":
            return self._list_posts(pb.ListPostsRequest.FromString(body))
        if method == "GetPost":
            return self._get_post(pb.GetPostRequest.FromString(body))
        if method == "ListChanges":
            return self._list_changes(pb.ListChangesRequest.FromString(body))
        return _error(404, "unimplemented", "not found")

    def _list_posts(self, req: pb.ListPostsRequest) -> Response:
        self.posts_calls.append(req)
        if self.cycle_tokens is not None:
            index = (len(self.posts_calls) - 1) % len(self.cycle_tokens)
            return _ok(
                pb.ListPostsResponse(
                    posts=[self.posts[0].summary], next_page_token=self.cycle_tokens[index]
                )
            )
        items, next_token = _page([p.summary for p in self.posts], req.page_token, req.limit, 20)
        if self.repeat_token and req.page_token:
            next_token = req.page_token
        return _ok(pb.ListPostsResponse(posts=items, next_page_token=next_token))

    def _get_post(self, req: pb.GetPostRequest) -> Response:
        for post in self.posts:
            if post.summary.slug == req.slug:
                return _ok(pb.GetPostResponse(post=post))
        return _error(404, "not_found", "post not found")

    def _list_changes(self, req: pb.ListChangesRequest) -> Response:
        self.changes_calls.append(req)
        start = req.start_time.ToDatetime(tzinfo=UTC) if req.HasField("start_time") else None
        end = req.end_time.ToDatetime(tzinfo=UTC) if req.HasField("end_time") else None
        if start is not None and end is not None and end <= start:
            return _error(400, "invalid_argument", "end_time must be after start_time")
        matched = []
        for entry in self.entries:
            if req.categories and entry.change.category not in req.categories:
                continue
            if req.HasField("action_required") and (
                entry.change.action_required != req.action_required
            ):
                continue
            if start is not None and entry.published_at.ToDatetime(tzinfo=UTC) < start:
                continue
            matched.append(entry)
        items, next_token = _page(matched, req.page_token, req.limit, 100)
        return _ok(pb.ListChangesResponse(changes=items, next_page_token=next_token))


def _page(items: list, token: str, limit: int, fallback: int) -> tuple[list, str]:
    start = int(token) if token else 0
    end = min(start + (limit or fallback), len(items))
    return items[start:end], str(end) if end < len(items) else ""


def _ok(message: Message) -> Response:
    return Response(message.SerializeToString(), status=200, content_type="application/proto")


def _error(status: int, code: str, message: str) -> Response:
    body = json.dumps({"code": code, "message": message})
    return Response(body, status=status, content_type="application/json")


def _serve(httpserver: HTTPServer, fake: FakeChangelog) -> str:
    httpserver.expect_request(
        "/changelog.v1.ChangelogService/ListPosts", method="POST"
    ).respond_with_handler(fake.handle)
    httpserver.expect_request(
        "/changelog.v1.ChangelogService/GetPost", method="POST"
    ).respond_with_handler(fake.handle)
    httpserver.expect_request(
        "/changelog.v1.ChangelogService/ListChanges", method="POST"
    ).respond_with_handler(fake.handle)
    return httpserver.url_for("").rstrip("/")


@pytest.fixture
def fake_api(httpserver: HTTPServer):
    def make(post_count: int, **kwargs) -> tuple[FakeChangelog, str]:
        fake = FakeChangelog(post_count, **kwargs)
        return fake, _serve(httpserver, fake)

    return make


@pytest.fixture
async def public_client(fake_api):
    clients: list[AsyncPolyester] = []

    def make(post_count: int, **kwargs) -> tuple[FakeChangelog, AsyncPolyester]:
        fake, url = fake_api(post_count, **kwargs)
        client = AsyncPolyester(api_url=url, hydrate_catalogs=False)
        clients.append(client)
        return fake, client

    yield make
    for client in clients:
        await client.aclose()


@pytest.fixture
def sync_client(fake_api) -> Iterator:
    clients: list[Polyester] = []

    def make(post_count: int, **kwargs) -> tuple[FakeChangelog, Polyester]:
        fake, url = fake_api(post_count, **kwargs)
        client = Polyester(api_url=url, hydrate_catalogs=False)
        clients.append(client)
        return fake, client

    yield make
    for client in clients:
        client.close()


async def test_iter_posts_follows_every_page_without_credentials(public_client) -> None:
    fake, client = public_client(5)

    slugs = [post.slug async for post in client.changelog.iter_posts(limit=2)]

    assert slugs == ["2026-10-31", "2026-10-30", "2026-10-29", "2026-10-28", "2026-10-27"]
    assert [(req.page_token, req.limit) for req in fake.posts_calls] == [
        ("", 2),
        ("2", 2),
        ("4", 2),
    ]
    assert not fake.auth_header_seen


async def test_iter_posts_stops_fetching_when_the_caller_breaks(public_client) -> None:
    fake, client = public_client(5)

    async for post in client.changelog.iter_posts(limit=2):
        assert post.slug == "2026-10-31"
        break

    assert len(fake.posts_calls) == 1


async def test_iter_posts_rejects_a_repeated_page_token(public_client) -> None:
    _, client = public_client(5, repeat_token=True)
    seen = []

    with pytest.raises(PolyesterResponseContractError, match="ListPosts"):
        async for post in client.changelog.iter_posts(limit=2):
            seen.append(post.slug)

    assert len(seen) == 4


@pytest.mark.parametrize(
    ("start", "cycle", "calls"),
    [
        # "" -> A -> B -> A: A recurs after two pages.
        (None, ["A", "B", "A"], ["", "A", "B"]),
        # "" -> A -> B -> C -> B.
        (None, ["A", "B", "C", "B"], ["", "A", "B", "C"]),
        # The caller's starting token counts: S -> A -> S.
        ("S", ["A", "S"], ["S", "A"]),
    ],
)
async def test_iter_posts_rejects_a_page_token_cycle(public_client, start, cycle, calls) -> None:
    fake, client = public_client(5, cycle_tokens=cycle)
    seen = 0

    with pytest.raises(PolyesterResponseContractError, match="ListPosts"):
        async for _ in client.changelog.iter_posts(page_token=start):
            seen += 1

    assert [req.page_token for req in fake.posts_calls] == calls
    assert seen == len(calls)


def test_sync_iter_posts_rejects_a_page_token_cycle(sync_client) -> None:
    fake, client = sync_client(5, cycle_tokens=["A", "B", "A"])

    with pytest.raises(PolyesterResponseContractError, match="ListPosts"):
        list(client.changelog.iter_posts())

    assert [req.page_token for req in fake.posts_calls] == ["", "A", "B"]


async def test_get_post_decodes_sections_and_base58_ids(public_client) -> None:
    _, client = public_client(2)

    post = await client.changelog.get_post("2026-10-30")

    assert post.summary.slug == "2026-10-30"
    assert post.summary.change_count == 2
    assert post.summary.published_at == BASE - timedelta(days=1)
    assert [(s.heading, s.summary) for s in post.sections] == [("API", "API changes")]
    change = post.sections[0].changes[0]
    # 1002 in base58 is "JH"; the decimal form must never leak.
    assert change.id == "JH"
    assert change.category == "improvement"
    assert change.audiences == ["developers"]
    assert change.surfaces == ["api"]
    assert change.details is None and change.migration_guidance is None


async def test_get_post_unknown_slug_is_not_found(public_client) -> None:
    _, client = public_client(1)

    with pytest.raises(PolyesterApiError) as caught:
        await client.changelog.get_post("2001-01-01")

    assert caught.value.code == "not_found"
    assert is_not_found(caught.value)


async def test_enum_values_newer_than_the_sdk_are_tolerated(public_client) -> None:
    fake, client = public_client(1)
    change = fake.posts[0].sections[0].changes[0]
    change.category = 99
    change.ClearField("audiences")
    change.audiences.extend([pb.TRADERS, 42])
    change.ClearField("surfaces")
    change.surfaces.extend([77, pb.TRADING])

    post = await client.changelog.get_post("2026-10-31")

    got = post.sections[0].changes[0]
    assert got.category == "99"
    assert got.audiences == ["traders", "42"]
    assert got.surfaces == ["77", "trading"]


async def test_breaking_changes_since_filters_and_pages(public_client) -> None:
    fake, client = public_client(600)
    since = BASE - timedelta(days=599)

    changes = await client.changelog.breaking_changes_since(since)

    # 1200 changes cycle through four categories, so 300 are breaking.
    assert len(changes) == 300
    assert {entry.change.category for entry in changes} == {"breaking_change"}
    req = fake.changes_calls[0]
    assert list(req.categories) == [pb.BREAKING_CHANGE]
    assert req.start_time.ToDatetime(tzinfo=UTC) == since
    assert not req.HasField("action_required")
    assert req.limit == 500
    assert len(fake.changes_calls) == 1


async def test_action_required_since_follows_page_tokens(public_client) -> None:
    fake, client = public_client(1000)
    since = BASE - timedelta(days=999)

    changes = await client.changelog.action_required_since(since)

    # Every third of 2000 changes needs action: 667 of them, over two pages.
    assert len(changes) == 667
    assert [req.page_token for req in fake.changes_calls] == ["", "500"]
    for req in fake.changes_calls:
        assert req.HasField("action_required") and req.action_required
        assert not req.categories
    ids = [entry.change.id for entry in changes]
    assert len(set(ids)) == len(ids)
    assert all(entry.change.action_required for entry in changes)


async def test_list_changes_sends_filters_and_maps_invalid_argument(public_client) -> None:
    fake, client = public_client(1)
    start = datetime(2026, 10, 1, tzinfo=UTC)

    with pytest.raises(PolyesterApiError) as caught:
        await client.changelog.list_changes(
            categories=["new_feature", "BUG_FIX"],
            surfaces=["trading"],
            audiences=["market_makers"],
            start_time=start,
            end_time=start,
            post_slug="2026-10-31",
            sort="asc",
            limit=10,
        )

    assert caught.value.code == "invalid_argument"
    req = fake.changes_calls[0]
    assert list(req.categories) == [pb.NEW_FEATURE, pb.BUG_FIX]
    assert list(req.surfaces) == [pb.TRADING]
    assert list(req.audiences) == [pb.MARKET_MAKERS]
    assert req.post_slug == "2026-10-31"
    assert req.sort == pb.SORT_ASC
    assert req.limit == 10


@pytest.mark.parametrize(
    "kwargs",
    [
        {"categories": ["99"]},
        {"surfaces": ["surface_unspecified"]},
        {"audiences": ["whales"]},
        {"categories": "breaking_change"},
        {"sort": "newest"},
        {"action_required": 1},
        {"start_time": datetime(2026, 10, 1)},
    ],
)
async def test_list_changes_rejects_values_it_cannot_send(public_client, kwargs) -> None:
    fake, client = public_client(1)

    with pytest.raises(PolyesterValidationError):
        await client.changelog.list_changes(**kwargs)

    assert fake.changes_calls == []


def test_sync_client_iterates_pages_and_runs_the_helpers(sync_client) -> None:
    fake, client = sync_client(5)

    slugs = [post.slug for post in client.changelog.iter_posts(limit=2)]
    assert slugs == ["2026-10-31", "2026-10-30", "2026-10-29", "2026-10-28", "2026-10-27"]

    for _ in client.changelog.iter_posts(limit=2):
        break
    assert len(fake.posts_calls) == 4

    breaking = client.changelog.breaking_changes_since(BASE - timedelta(days=4))
    assert [entry.change.id for entry in breaking] == ["JF", "JK", "JP"]
    assert client.changelog.get_post("2026-10-31").summary.slug == "2026-10-31"
    with pytest.raises(PolyesterApiError) as caught:
        client.changelog.get_post("2001-01-01")
    assert is_not_found(caught.value)
    assert not fake.auth_header_seen


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(
            datetime(1969, 12, 31, 23, 59, 59, 500_000, tzinfo=UTC),
            id="half a second before the epoch",
        ),
        pytest.param(datetime(1970, 1, 1, tzinfo=UTC), id="the epoch"),
        pytest.param(
            datetime(2026, 11, 7, 16, 30, 0, 123_456, tzinfo=timezone(timedelta(hours=2))),
            id="an ordinary date in another zone",
        ),
        pytest.param(datetime.max.replace(tzinfo=UTC), id="the last microsecond of year 9999"),
        pytest.param(datetime.min.replace(tzinfo=UTC), id="the first microsecond of year 1"),
    ],
)
async def test_list_changes_sends_exact_time_bounds(public_client, value: datetime) -> None:
    """Time bounds are sent as protobuf's own UTC conversion sends them."""
    fake, client = public_client(1)
    # The fake refuses an empty range; only the request matters here.
    with contextlib.suppress(PolyesterError):
        await client.changelog.list_changes(start_time=value, end_time=value)
    req = fake.changes_calls[0]
    want = _ts(value)
    assert (req.start_time.seconds, req.start_time.nanos) == (want.seconds, want.nanos)
    assert (req.end_time.seconds, req.end_time.nanos) == (want.seconds, want.nanos)
