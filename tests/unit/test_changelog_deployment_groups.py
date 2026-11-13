"""Changelog deployment groups and release-post fields against a fake Connect
server (protobuf over HTTP)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, Polyester
from polyester.errors import PolyesterApiError, PolyesterResponseContractError, is_not_found
from polyester.gen.changelog.v1 import changelog_pb2 as pb
from polyester.models.changelog import (
    CHANGELOG_AVAILABILITY_AHEAD,
    CHANGELOG_ENVIRONMENT_DEVNET,
    CHANGELOG_ENVIRONMENT_MAINNET,
    CHANGELOG_ENVIRONMENT_TESTNET,
    ChangelogChangeException,
    ChangelogEnvironmentStatus,
)

SERVICE = "/changelog.v1.ChangelogService/"
BASE = datetime(2026, 11, 12, 9, 30, 15, 123456, tzinfo=UTC)
AUTH_HEADERS = ("authorization", "x-api-key-id", "x-api-signature")


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


def _summary(i: int) -> pb.DeploymentGroupSummary:
    """Group i is deployed i days before BASE; release 0.92.(20-i)."""
    version = f"0.92.{20 - i}"
    summary = pb.DeploymentGroupSummary(
        slug=f"testnet-v{version}",
        environment=pb.TESTNET,
        occurred_at=_ts(BASE - timedelta(days=i)),
        release_version=version,
        versions=[f"0.92.{19 - i}", version],
        posts=[
            pb.DeploymentGroupPost(
                slug=f"v{version}",
                release_version=version,
                title=f"Release {version}",
                published_at=_ts(BASE - timedelta(days=i, hours=2)),
                revision=2,
                updated_at=_ts(BASE - timedelta(days=i, hours=1)),
            )
        ],
    )
    if i % 2 == 0:
        summary.release_tag = f"v{version}"
        summary.previous_release_version = f"0.92.{18 - i}"
    return summary


@dataclass
class FakeChangelog:
    group_count: int
    group_response: pb.GetDeploymentGroupResponse | None = None
    list_calls: list[pb.ListDeploymentGroupsRequest] = field(default_factory=list)
    get_calls: list[pb.GetDeploymentGroupRequest] = field(default_factory=list)
    post: pb.Post | None = None
    auth_header_seen: bool = False

    def handle(self, request: Request) -> Response:
        if any(request.headers.get(name) for name in AUTH_HEADERS):
            self.auth_header_seen = True
        method = request.path.removeprefix(SERVICE)
        body = request.get_data()
        if method == "ListDeploymentGroups":
            req = pb.ListDeploymentGroupsRequest.FromString(body)
            self.list_calls.append(req)
            groups = [_summary(i) for i in range(self.group_count)]
            start = int(req.page_token) if req.page_token else 0
            end = min(start + (req.limit or 20), len(groups))
            return _ok(
                pb.ListDeploymentGroupsResponse(
                    groups=groups[start:end],
                    next_page_token=str(end) if end < len(groups) else "",
                )
            )
        if method == "GetDeploymentGroup":
            req = pb.GetDeploymentGroupRequest.FromString(body)
            self.get_calls.append(req)
            if self.group_response is not None:
                return _ok(self.group_response)
            for i in range(self.group_count):
                summary = _summary(i)
                if summary.slug == req.slug:
                    return _ok(_group(summary))
            return _error(404, "not_found", "deployment group not found")
        if method == "GetPost" and self.post is not None:
            return _ok(pb.GetPostResponse(post=self.post))
        return _error(404, "unimplemented", "not found")


def _group(summary: pb.DeploymentGroupSummary) -> pb.GetDeploymentGroupResponse:
    return pb.GetDeploymentGroupResponse(
        group=pb.DeploymentGroup(
            summary=summary,
            attention=[
                pb.DeploymentGroupAttention(
                    post_slug=f"v{summary.release_version}",
                    release_version=summary.release_version,
                    change=pb.Change(
                        id=1002,
                        title="Breaking",
                        summary="Needs action",
                        category=pb.BREAKING_CHANGE,
                        action_required=True,
                        environment_exceptions=[
                            pb.ChangeException(
                                environment=pb.TESTNET,
                                availability=pb.AHEAD,
                                live_at=_ts(BASE - timedelta(days=3)),
                            ),
                            pb.ChangeException(environment=pb.MAINNET, availability=pb.UNAVAILABLE),
                        ],
                    ),
                )
            ],
            highlights=[
                pb.DeploymentGroupHighlight(
                    post_slug=f"v{summary.release_version}",
                    release_version=summary.release_version,
                    text="Faster **fills**",
                )
            ],
        )
    )


def _ok(message: Message) -> Response:
    return Response(message.SerializeToString(), status=200, content_type="application/proto")


def _error(status: int, code: str, message: str) -> Response:
    return Response(
        json.dumps({"code": code, "message": message}),
        status=status,
        content_type="application/json",
    )


@pytest.fixture
def fake_api(httpserver: HTTPServer):
    def make(group_count: int, **kwargs) -> tuple[FakeChangelog, str]:
        fake = FakeChangelog(group_count, **kwargs)
        for method in ("ListDeploymentGroups", "GetDeploymentGroup", "GetPost"):
            httpserver.expect_request(SERVICE + method, method="POST").respond_with_handler(
                fake.handle
            )
        return fake, httpserver.url_for("").rstrip("/")

    return make


@pytest.fixture
async def public_client(fake_api):
    clients: list[AsyncPolyester] = []

    def make(group_count: int, **kwargs) -> tuple[FakeChangelog, AsyncPolyester]:
        fake, url = fake_api(group_count, **kwargs)
        client = AsyncPolyester(api_url=url, hydrate_catalogs=False)
        clients.append(client)
        return fake, client

    yield make
    for client in clients:
        await client.aclose()


async def test_list_deployment_groups_decodes_one_page_without_credentials(public_client) -> None:
    fake, client = public_client(3)

    page = await client.changelog.list_deployment_groups(limit=2)

    assert [(req.limit, req.page_token) for req in fake.list_calls] == [(2, "")]
    assert page.next_page_token == "2"
    first, second = page.groups
    assert first.slug == "testnet-v0.92.20"
    assert first.environment == CHANGELOG_ENVIRONMENT_TESTNET
    assert first.occurred_at == BASE
    assert first.release_version == "0.92.20"
    assert first.release_tag == "v0.92.20"
    assert first.previous_release_version == "0.92.18"
    assert first.versions == ["0.92.19", "0.92.20"]
    (post,) = first.posts
    assert (post.slug, post.release_version, post.title, post.revision) == (
        "v0.92.20",
        "0.92.20",
        "Release 0.92.20",
        2,
    )
    assert post.published_at == BASE - timedelta(hours=2)
    assert post.updated_at == BASE - timedelta(hours=1)
    # Omitted optional strings stay None, never "".
    assert second.release_tag is None and second.previous_release_version is None
    assert not fake.auth_header_seen


async def test_iter_deployment_groups_follows_every_page(public_client) -> None:
    fake, client = public_client(5)

    slugs = [group.slug async for group in client.changelog.iter_deployment_groups(limit=2)]

    assert slugs == [f"testnet-v0.92.{v}" for v in (20, 19, 18, 17, 16)]
    assert [req.page_token for req in fake.list_calls] == ["", "2", "4"]


async def test_get_deployment_group_decodes_attention_and_highlights(public_client) -> None:
    fake, client = public_client(2)

    group = await client.changelog.get_deployment_group("testnet-v0.92.19")

    assert [req.slug for req in fake.get_calls] == ["testnet-v0.92.19"]
    assert group.summary.slug == "testnet-v0.92.19"
    assert group.summary.release_tag is None
    (attention,) = group.attention
    assert (attention.post_slug, attention.release_version) == ("v0.92.19", "0.92.19")
    assert attention.change.id == "JH"
    assert attention.change.category == "breaking_change"
    assert attention.change.action_required is True
    assert attention.change.environment_exceptions == [
        ChangelogChangeException(
            environment="testnet",
            availability=CHANGELOG_AVAILABILITY_AHEAD,
            live_at=BASE - timedelta(days=3),
        ),
        ChangelogChangeException(environment="mainnet", availability="unavailable", live_at=None),
    ]
    (highlight,) = group.highlights
    assert (highlight.post_slug, highlight.release_version, highlight.text) == (
        "v0.92.19",
        "0.92.19",
        "Faster **fills**",
    )
    assert not fake.auth_header_seen


async def test_get_deployment_group_unknown_slug_is_not_found(public_client) -> None:
    _, client = public_client(1)

    with pytest.raises(PolyesterApiError) as caught:
        await client.changelog.get_deployment_group("devnet-v9.9.9")

    assert is_not_found(caught.value)


@pytest.mark.parametrize(
    "response",
    [
        pb.GetDeploymentGroupResponse(),
        pb.GetDeploymentGroupResponse(group=pb.DeploymentGroup()),
    ],
    ids=["no group", "no summary"],
)
async def test_get_deployment_group_without_group_is_a_contract_error(
    public_client, response
) -> None:
    _, client = public_client(1, group_response=response)

    with pytest.raises(PolyesterResponseContractError):
        await client.changelog.get_deployment_group("testnet-v0.92.20")


async def test_unknown_environment_and_availability_read_as_numbers(public_client) -> None:
    summary = _summary(0)
    summary.environment = 9
    response = _group(summary)
    response.group.attention[0].change.environment_exceptions[0].availability = 7
    _, client = public_client(1, group_response=response)

    group = await client.changelog.get_deployment_group("testnet-v0.92.20")

    assert group.summary.environment == "9"
    assert group.attention[0].change.environment_exceptions[0].availability == "7"


async def test_release_post_summary_keeps_release_fields_and_presence(public_client) -> None:
    summary = pb.PostSummary(
        slug="v0.92.9",
        title="Release 0.92.9",
        release_version="0.92.9",
        deployment_group_slug="testnet-v0.92.9",
        environments=[
            pb.EnvironmentStatus(environment=pb.DEVNET, live_at=_ts(BASE)),
            pb.EnvironmentStatus(environment=pb.TESTNET, live_at=_ts(BASE + timedelta(days=1))),
            pb.EnvironmentStatus(environment=pb.MAINNET),
        ],
    )
    _, client = public_client(0, post=pb.Post(summary=summary))

    post = await client.changelog.get_post("v0.92.9")

    assert post.summary.release_version == "0.92.9"
    assert post.summary.deployment_group_slug == "testnet-v0.92.9"
    assert post.summary.environments == [
        ChangelogEnvironmentStatus(environment=CHANGELOG_ENVIRONMENT_DEVNET, live_at=BASE),
        ChangelogEnvironmentStatus(environment="testnet", live_at=BASE + timedelta(days=1)),
        # Pending on mainnet: no time, not the epoch.
        ChangelogEnvironmentStatus(environment=CHANGELOG_ENVIRONMENT_MAINNET, live_at=None),
    ]


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        (pb.PostSummary(slug="2026-11-01", title="Weekly"), None),
        (pb.PostSummary(slug="v0.0.0", release_version="", deployment_group_slug=""), ""),
    ],
    ids=["absent", "explicit empty"],
)
async def test_post_summary_tells_absent_release_fields_from_empty_ones(
    public_client, summary, expected
) -> None:
    _, client = public_client(0, post=pb.Post(summary=summary))

    post = await client.changelog.get_post(summary.slug)

    assert post.summary.release_version == expected
    assert post.summary.deployment_group_slug == expected
    assert post.summary.environments == []


def test_sync_client_lists_iterates_and_gets_deployment_groups(fake_api) -> None:
    fake, url = fake_api(3)
    client = Polyester(api_url=url, hydrate_catalogs=False)
    try:
        page = client.changelog.list_deployment_groups(limit=1)
        assert [g.slug for g in page.groups] == ["testnet-v0.92.20"]
        slugs = [g.slug for g in client.changelog.iter_deployment_groups(limit=2)]
        assert slugs == ["testnet-v0.92.20", "testnet-v0.92.19", "testnet-v0.92.18"]
        group = client.changelog.get_deployment_group("testnet-v0.92.18")
        assert group.summary.release_tag == "v0.92.18"
    finally:
        client.close()
