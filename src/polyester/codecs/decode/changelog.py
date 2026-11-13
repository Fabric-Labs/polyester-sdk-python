from __future__ import annotations

from datetime import UTC, datetime

from polyester.codecs.proto_helpers import format_uint64_id, has_field, proto_enum_name
from polyester.errors import PolyesterResponseContractError
from polyester.gen.changelog.v1 import changelog_pb2
from polyester.models.changelog import (
    ChangelogChange,
    ChangelogChangeEntry,
    ChangelogChangeException,
    ChangelogChangesPage,
    ChangelogDeploymentGroup,
    ChangelogDeploymentGroupAttention,
    ChangelogDeploymentGroupHighlight,
    ChangelogDeploymentGroupPost,
    ChangelogDeploymentGroupsPage,
    ChangelogDeploymentGroupSummary,
    ChangelogEnvironmentStatus,
    ChangelogPost,
    ChangelogPostsPage,
    ChangelogPostSummary,
    ChangelogSection,
)


def _timestamp(ts) -> datetime | None:
    seconds = int(getattr(ts, "seconds", 0) or 0)
    nanos = int(getattr(ts, "nanos", 0) or 0)
    if seconds == 0 and nanos == 0:
        return None
    return datetime.fromtimestamp(seconds + nanos / 1_000_000_000, tz=UTC)


def _optional_timestamp(msg, field: str) -> datetime | None:
    return _timestamp(getattr(msg, field)) if has_field(msg, field) else None


def _optional_string(msg, field: str) -> str | None:
    return getattr(msg, field) if has_field(msg, field) else None


def _environment(value) -> str:
    return proto_enum_name(changelog_pb2.Environment, int(value))


def _labels(enum_type, values) -> list[str]:
    return [label for value in values if (label := proto_enum_name(enum_type, int(value)))]


def changelog_change_from_proto(msg: changelog_pb2.Change) -> ChangelogChange:
    """Decode one change. The id becomes base58; enum values newer than this
    SDK read as their number."""
    return ChangelogChange(
        id=format_uint64_id(int(msg.id)),
        title=msg.title,
        summary=msg.summary,
        details=msg.details if has_field(msg, "details") else None,
        category=proto_enum_name(changelog_pb2.ChangeCategory, int(msg.category)),
        action_required=bool(msg.action_required),
        migration_guidance=msg.migration_guidance if has_field(msg, "migration_guidance") else None,
        audiences=_labels(changelog_pb2.Audience, msg.audiences),
        surfaces=_labels(changelog_pb2.Surface, msg.surfaces),
        environment_exceptions=[
            ChangelogChangeException(
                environment=_environment(item.environment),
                availability=proto_enum_name(
                    changelog_pb2.ChangeAvailability, int(item.availability)
                ),
                live_at=_optional_timestamp(item, "live_at"),
            )
            for item in msg.environment_exceptions
        ],
    )


def changelog_post_summary_from_proto(msg: changelog_pb2.PostSummary) -> ChangelogPostSummary:
    return ChangelogPostSummary(
        slug=msg.slug,
        title=msg.title,
        introduction=msg.introduction,
        published_at=_timestamp(msg.published_at) if has_field(msg, "published_at") else None,
        updated_at=_timestamp(msg.updated_at) if has_field(msg, "updated_at") else None,
        revision=int(msg.revision),
        coverage_cutoff=_timestamp(msg.coverage_cutoff)
        if has_field(msg, "coverage_cutoff")
        else None,
        change_count=int(msg.change_count),
        breaking_change_count=int(msg.breaking_change_count),
        action_required_count=int(msg.action_required_count),
        new_feature_count=int(msg.new_feature_count),
        improvement_count=int(msg.improvement_count),
        bug_fix_count=int(msg.bug_fix_count),
        release_version=_optional_string(msg, "release_version"),
        environments=[
            ChangelogEnvironmentStatus(
                environment=_environment(item.environment),
                live_at=_optional_timestamp(item, "live_at"),
            )
            for item in msg.environments
        ],
        deployment_group_slug=_optional_string(msg, "deployment_group_slug"),
    )


def changelog_posts_page_from_proto(msg: changelog_pb2.ListPostsResponse) -> ChangelogPostsPage:
    return ChangelogPostsPage(
        posts=[changelog_post_summary_from_proto(post) for post in msg.posts],
        next_page_token=msg.next_page_token,
    )


def changelog_post_from_proto(msg: changelog_pb2.GetPostResponse) -> ChangelogPost:
    """Decode ``GetPostResponse``. A success without a post is a contract
    violation."""
    if not has_field(msg, "post") or not has_field(msg.post, "summary"):
        raise PolyesterResponseContractError("GetPost", "response is missing the post")
    return ChangelogPost(
        summary=changelog_post_summary_from_proto(msg.post.summary),
        sections=[
            ChangelogSection(
                heading=section.heading,
                summary=section.summary if has_field(section, "summary") else None,
                surface=proto_enum_name(changelog_pb2.Surface, int(section.surface)),
                changes=[changelog_change_from_proto(change) for change in section.changes],
            )
            for section in msg.post.sections
        ],
    )


def changelog_changes_page_from_proto(
    msg: changelog_pb2.ListChangesResponse,
) -> ChangelogChangesPage:
    return ChangelogChangesPage(
        changes=[
            ChangelogChangeEntry(
                change=changelog_change_from_proto(entry.change),
                post_slug=entry.post_slug,
                published_at=_timestamp(entry.published_at)
                if has_field(entry, "published_at")
                else None,
                section_heading=entry.section_heading,
            )
            for entry in msg.changes
        ],
        next_page_token=msg.next_page_token,
    )


def changelog_deployment_group_summary_from_proto(
    msg: changelog_pb2.DeploymentGroupSummary,
) -> ChangelogDeploymentGroupSummary:
    return ChangelogDeploymentGroupSummary(
        slug=msg.slug,
        environment=_environment(msg.environment),
        occurred_at=_optional_timestamp(msg, "occurred_at"),
        release_version=msg.release_version,
        release_tag=_optional_string(msg, "release_tag"),
        previous_release_version=_optional_string(msg, "previous_release_version"),
        versions=list(msg.versions),
        posts=[
            ChangelogDeploymentGroupPost(
                slug=post.slug,
                release_version=post.release_version,
                title=post.title,
                published_at=_optional_timestamp(post, "published_at"),
                revision=int(post.revision),
                updated_at=_optional_timestamp(post, "updated_at"),
            )
            for post in msg.posts
        ],
    )


def changelog_deployment_groups_page_from_proto(
    msg: changelog_pb2.ListDeploymentGroupsResponse,
) -> ChangelogDeploymentGroupsPage:
    return ChangelogDeploymentGroupsPage(
        groups=[changelog_deployment_group_summary_from_proto(group) for group in msg.groups],
        next_page_token=msg.next_page_token,
    )


def changelog_deployment_group_from_proto(
    msg: changelog_pb2.GetDeploymentGroupResponse,
) -> ChangelogDeploymentGroup:
    """Decode ``GetDeploymentGroupResponse``. A success without a group, or a
    group without its summary, is a contract violation."""
    if not has_field(msg, "group") or not has_field(msg.group, "summary"):
        raise PolyesterResponseContractError(
            "GetDeploymentGroup", "response is missing the deployment group"
        )
    group = msg.group
    return ChangelogDeploymentGroup(
        summary=changelog_deployment_group_summary_from_proto(group.summary),
        attention=[
            ChangelogDeploymentGroupAttention(
                post_slug=item.post_slug,
                release_version=item.release_version,
                change=changelog_change_from_proto(item.change),
            )
            for item in group.attention
        ],
        highlights=[
            ChangelogDeploymentGroupHighlight(
                post_slug=item.post_slug,
                release_version=item.release_version,
                text=item.text,
            )
            for item in group.highlights
        ],
    )
