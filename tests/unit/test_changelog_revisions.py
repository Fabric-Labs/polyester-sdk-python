"""Republished changelog posts: post revisions, and changes met again while
a walk pages through a republished post (contract 1bf038e)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, Polyester
from polyester.codecs.decode.changelog import (
    changelog_post_from_proto,
    changelog_post_summary_from_proto,
)
from polyester.gen.changelog.v1 import changelog_pb2 as pb
from tests.unit.test_changelog import _ok, _ts

PUBLISHED = datetime(2026, 11, 4, 10, tzinfo=UTC)
UPDATED = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
NEWER = datetime(2026, 11, 6, 9, tzinfo=UTC)
SINCE = datetime(2026, 11, 1, tzinfo=UTC)


def test_post_summary_reads_revision_and_updated_at() -> None:
    summary = changelog_post_summary_from_proto(
        pb.PostSummary(
            slug="2026-11-04", published_at=_ts(PUBLISHED), updated_at=_ts(UPDATED), revision=2
        )
    )
    assert summary.revision == 2
    assert summary.updated_at == UPDATED
    assert summary.published_at == PUBLISHED

    post = changelog_post_from_proto(
        pb.GetPostResponse(
            post=pb.Post(
                summary=pb.PostSummary(
                    slug="2026-11-04",
                    published_at=_ts(PUBLISHED),
                    updated_at=_ts(PUBLISHED),
                    revision=1,
                )
            )
        )
    )
    assert post.summary.revision == 1
    assert post.summary.updated_at == PUBLISHED

    # A server before revisions sends neither.
    older = changelog_post_summary_from_proto(
        pb.PostSummary(slug="2026-10-01", published_at=_ts(PUBLISHED))
    )
    assert older.revision == 0
    assert older.updated_at is None


def _entry(change_id: int, title: str, slug: str, published: datetime) -> pb.ChangeEntry:
    return pb.ChangeEntry(
        change=pb.Change(
            id=change_id, title=title, category=pb.BREAKING_CHANGE, action_required=True
        ),
        post_slug=slug,
        published_at=_ts(published),
    )


class RepublishingChangelog:
    """Two ListChanges pages. Between them the post the first page's token
    points into is republished, so the second page restarts at that post's
    first change and repeats change 1002 with its new wording."""

    def __init__(self) -> None:
        self.calls = 0

    def handle(self, request: Request) -> Response:
        self.calls += 1
        req = pb.ListChangesRequest.FromString(request.get_data())
        if not req.page_token:
            return _ok(
                pb.ListChangesResponse(
                    changes=[
                        _entry(1001, "newer post change", "2026-11-06", NEWER),
                        _entry(1002, "first wording", "2026-11-04", PUBLISHED),
                    ],
                    next_page_token="t1",
                )
            )
        return _ok(
            pb.ListChangesResponse(
                changes=[
                    _entry(1002, "corrected wording", "2026-11-04", PUBLISHED),
                    _entry(1003, "third", "2026-11-04", PUBLISHED),
                ]
            )
        )


def _serve(httpserver: HTTPServer) -> tuple[RepublishingChangelog, str]:
    fake = RepublishingChangelog()
    httpserver.expect_request(
        "/changelog.v1.ChangelogService/ListChanges", method="POST"
    ).respond_with_handler(fake.handle)
    return fake, httpserver.url_for("").rstrip("/")


async def test_iter_changes_yields_a_republished_change_once(httpserver: HTTPServer) -> None:
    fake, url = _serve(httpserver)
    async with AsyncPolyester(api_url=url, hydrate_catalogs=False) as client:
        ids = [entry.change.id async for entry in client.changelog.iter_changes()]
    assert fake.calls == 2
    assert len(ids) == 3 and len(set(ids)) == 3, ids


@pytest.mark.parametrize("helper", ["breaking_changes_since", "action_required_since"])
async def test_since_helpers_keep_one_current_copy(httpserver: HTTPServer, helper: str) -> None:
    _, url = _serve(httpserver)
    async with AsyncPolyester(api_url=url, hydrate_catalogs=False) as client:
        entries = await getattr(client.changelog, helper)(SINCE)
    ids = [entry.change.id for entry in entries]
    assert len(ids) == 3 and len(set(ids)) == 3, ids
    # The repeat keeps its place with the current revision's wording.
    assert [entry.change.title for entry in entries][1] == "corrected wording"


def test_sync_client_dedupes_too(httpserver: HTTPServer) -> None:
    _, url = _serve(httpserver)
    client = Polyester(api_url=url, hydrate_catalogs=False)
    try:
        ids = [entry.change.id for entry in client.changelog.iter_changes()]
        since = client.changelog.breaking_changes_since(SINCE)
    finally:
        client.close()
    assert len(ids) == 3 and len(set(ids)) == 3, ids
    assert [entry.change.title for entry in since] == [
        "newer post change",
        "corrected wording",
        "third",
    ]
