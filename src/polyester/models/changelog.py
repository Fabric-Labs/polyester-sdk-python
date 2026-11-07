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
# "documentation", "platform", "market_data", "quickswap", "rewards". Values
# newer than this SDK read as numbers.


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
