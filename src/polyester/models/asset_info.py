from __future__ import annotations

from datetime import datetime

import msgspec


class AssetIssuePrice(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A known launch price. ``amount`` is an exact nonnegative decimal string
    (``"0"`` for a known zero price); ``currency`` is always ``"USD"``."""

    amount: str = ""
    currency: str = ""


class AssetEditorialInfo(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Team-maintained asset information.

    Empty strings and lists mean unknown; hide those rows. ``description`` is
    plain text: render it as text. The links are absolute HTTPS URLs;
    ``explorer_urls`` keeps the editorial order. ``issue_date`` is the launch
    calendar date as ``YYYY-MM-DD``, kept as text. ``issue_price`` is ``None``
    when the launch price is unknown.
    """

    description: str = ""
    website_url: str = ""
    whitepaper_url: str = ""
    explorer_urls: list[str] = msgspec.field(default_factory=list)
    x_url: str = ""
    telegram_url: str = ""
    discord_url: str = ""
    github_url: str = ""
    issue_date: str = ""
    issue_price: AssetIssuePrice | None = None


class AssetInfo(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Asset information (``marketdata.v1.MarketDataService/ListAssetInfo``).

    ``asset_id`` is the numeric asset ID, the ``ledger_id`` of the spot and
    deposit/withdraw configs. ``editorial_updated_at`` is the time of the last
    effective editorial change, ``None`` when the server sends none.
    """

    asset_id: int
    editorial: AssetEditorialInfo = msgspec.field(default_factory=AssetEditorialInfo)
    editorial_updated_at: datetime | None = None
