from __future__ import annotations

from datetime import datetime

import msgspec

# Change category labels. A category newer than this SDK reads as its number,
# for example "9".
CHANGELOG_CATEGORY_BREAKING_CHANGE = "breaking_change"
CHANGELOG_CATEGORY_NEW_FEATURE = "new_feature"
CHANGELOG_CATEGORY_IMPROVEMENT = "improvement"
CHANGELOG_CATEGORY_BUG_FIX = "bug_fix"

# Audience labels: "all_users", "traders", "market_makers", "developers".
# Surface labels: "trading", "funding", "accounts", "api", "explorer",
# "documentation", "platform", "market_data", "quickswap", "rewards",
# "assistant". Values newer than this SDK read as numbers.

# Environment labels. An environment newer than this SDK reads as its number.
CHANGELOG_ENVIRONMENT_DEVNET = "devnet"
CHANGELOG_ENVIRONMENT_TESTNET = "testnet"
CHANGELOG_ENVIRONMENT_MAINNET = "mainnet"

# Change availability labels: how one change of a release differs from its
# release in one environment. A value newer than this SDK reads as its number.
# "ahead": available there while its release is still pending there.
CHANGELOG_AVAILABILITY_AHEAD = "ahead"
# "pending": not yet available there although its release is live there.
CHANGELOG_AVAILABILITY_PENDING = "pending"
# "unavailable": not available there for now, whatever its release's status.
CHANGELOG_AVAILABILITY_UNAVAILABLE = "unavailable"


class ChangelogEnvironmentStatus(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Whether a release is live in one environment.

    ``environment`` is an environment label (``"devnet"``); ``live_at`` is
    when the release went live there, ``None`` while it is pending there.
    """

    environment: str = ""
    live_at: datetime | None = None


class ChangelogChangeException(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The status of one change in one environment where it differs from its
    release's status.

    ``environment`` is an environment label, ``availability`` an availability
    label (``"ahead"``, ``"pending"``, ``"unavailable"``). ``live_at`` is when
    the change became available there: set for ``"ahead"`` only, ``None``
    otherwise.
    """

    environment: str = ""
    availability: str = ""
    live_at: datetime | None = None


class ChangelogChange(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One product change in a changelog post.

    ``id`` is the change's public base58 identifier.
    """

    id: str = ""
    title: str = ""
    summary: str = ""
    details: str | None = None
    category: str = ""
    action_required: bool = False
    migration_guidance: str | None = None
    audiences: list[str] = msgspec.field(default_factory=list)
    surfaces: list[str] = msgspec.field(default_factory=list)
    environment_exceptions: list[ChangelogChangeException] = msgspec.field(default_factory=list)
    """Environments, any of them and not only the one the client points at,
    where this change differs from its release's status, for example a change
    already available on testnet before its release reaches testnet. Empty
    outside release posts and when the change follows its release
    everywhere."""


class ChangelogSection(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A post's changes under one heading.

    ``surface`` is the product area the section covers, as a surface label
    (``"market_data"``), or ``""`` for a section not tied to one area, such as
    the changes that need your attention. It does not change which changes a
    ``list_changes`` surface filter matches: each change keeps its own
    ``surfaces``.
    """

    heading: str = ""
    summary: str | None = None
    surface: str = ""
    changes: list[ChangelogChange] = msgspec.field(default_factory=list)


class ChangelogPostSummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A changelog post without its sections, with change counts by kind.

    ``slug`` is the post's coverage cutoff date, ``YYYY-MM-DD``, with a ``-2``
    or ``-3`` suffix for a later post on the same day.

    A published post can be republished, for example to correct its copy or
    withdraw a change. Its ``slug``, ``published_at`` (the time of first
    publication) and its changes' ``id`` values stay the same. ``revision``
    starts at 1 and increases with each republication, and ``updated_at`` is
    when the current revision was published, equal to ``published_at`` for
    revision 1. A server that predates revisions sends neither: ``revision``
    reads 0 and ``updated_at`` ``None``. To follow edits, read a post again
    when its ``revision`` differs from the one you hold.

    A release post announces one release: ``release_version`` (``"0.92.9"``)
    is set, its slug is ``v<release>`` and its content is the same in every
    environment, where it is listed even while its release is still pending.
    ``environments`` is the status of that release in each environment,
    devnet, testnet and mainnet in that order, and changes when the release
    goes live somewhere without a new ``revision``: compare the whole summary
    to notice it. ``deployment_group_slug`` names the deployment group that
    brought the release to this environment (see ``get_deployment_group``);
    it is ``None`` while the release is pending here. For any other post
    ``release_version`` and ``deployment_group_slug`` are ``None`` and
    ``environments`` is empty.
    """

    slug: str = ""
    title: str = ""
    introduction: str = ""
    published_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0
    coverage_cutoff: datetime | None = None
    change_count: int = 0
    breaking_change_count: int = 0
    action_required_count: int = 0
    new_feature_count: int = 0
    improvement_count: int = 0
    bug_fix_count: int = 0
    release_version: str | None = None
    environments: list[ChangelogEnvironmentStatus] = msgspec.field(default_factory=list)
    deployment_group_slug: str | None = None


class ChangelogPost(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One full changelog post at its current revision."""

    summary: ChangelogPostSummary
    sections: list[ChangelogSection] = msgspec.field(default_factory=list)


class ChangelogChangeEntry(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One change with the post it was published in."""

    change: ChangelogChange
    post_slug: str = ""
    published_at: datetime | None = None
    section_heading: str = ""


class ChangelogPostsPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One ``ListPosts`` page, newest post first."""

    posts: list[ChangelogPostSummary] = msgspec.field(default_factory=list)
    next_page_token: str = ""


class ChangelogChangesPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One ``ListChanges`` page."""

    changes: list[ChangelogChangeEntry] = msgspec.field(default_factory=list)
    next_page_token: str = ""


class ChangelogDeploymentGroupPost(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One published release post a deployment group brought.

    ``slug`` (``"v0.92.9"``) reads the post with ``get_post``;
    ``published_at`` is its first publication and ``updated_at`` that of its
    current ``revision`` (from 1).
    """

    slug: str = ""
    release_version: str = ""
    title: str = ""
    published_at: datetime | None = None
    revision: int = 0
    updated_at: datetime | None = None


class ChangelogDeploymentGroupSummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One deployment group without its details.

    A deployment group is one deployment to the environment that raised its
    release version, bringing every release above the previous group's
    version up to and including its own. ``slug`` (``"testnet-v0.92.9"``) is
    its stable, shareable identifier; ``environment`` an environment label;
    ``occurred_at`` when the deployment ran; ``release_version`` its own,
    highest release; ``release_tag`` (``"v0.92.9"``) ``None`` when unknown;
    ``previous_release_version`` ``None`` for the first group. ``versions``
    lists every release it brought, ascending, and ``posts`` the published
    release posts among them, ascending by release.
    """

    slug: str = ""
    environment: str = ""
    occurred_at: datetime | None = None
    release_version: str = ""
    release_tag: str | None = None
    previous_release_version: str | None = None
    versions: list[str] = msgspec.field(default_factory=list)
    posts: list[ChangelogDeploymentGroupPost] = msgspec.field(default_factory=list)


class ChangelogDeploymentGroupAttention(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One change of a deployment group that needs attention: breaking, or
    with ``action_required``, as in the release post ``post_slug``."""

    post_slug: str = ""
    release_version: str = ""
    change: ChangelogChange = msgspec.field(default_factory=ChangelogChange)


class ChangelogDeploymentGroupHighlight(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One highlight of a release post in a deployment group; ``text`` is
    inline Markdown."""

    post_slug: str = ""
    release_version: str = ""
    text: str = ""


class ChangelogDeploymentGroup(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One complete deployment group.

    ``attention`` lists the breaking changes and the changes that require
    action across the group's posts, in post order (ascending release), then
    section and change order; ``highlights`` the posts' highlights, in post
    order.
    """

    summary: ChangelogDeploymentGroupSummary
    attention: list[ChangelogDeploymentGroupAttention] = msgspec.field(default_factory=list)
    highlights: list[ChangelogDeploymentGroupHighlight] = msgspec.field(default_factory=list)


class ChangelogDeploymentGroupsPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One ``ListDeploymentGroups`` page, newest deployment first."""

    groups: list[ChangelogDeploymentGroupSummary] = msgspec.field(default_factory=list)
    next_page_token: str = ""
