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


class AssetMarketValue(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One market datapoint. ``value`` is an exact nonnegative decimal string;
    never parse it as a float. ``source`` is ``"coinmarketcap"`` or
    ``"polyester"`` (the Polyester team), "" when not named, and a source this
    SDK does not know reads as its decimal string. ``as_of`` is when the source
    last observed or set the value: older values stay until a newer
    observation replaces them, so show it with the value."""

    value: str = ""
    source: str = ""
    as_of: datetime | None = None


class AssetMarketFlag(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A market fact that holds because it is present, with its ``source``
    and ``as_of`` as on :class:`AssetMarketValue`."""

    source: str = ""
    as_of: datetime | None = None


class AssetMarketStats(msgspec.Struct, kw_only=True, omit_defaults=True):
    """An asset's market datapoints. Each is ``None`` when unknown; hide it.

    Supplies are in asset units; ``market_cap_usd`` is price times circulating
    supply and ``fully_diluted_market_cap_usd`` price times maximum supply (or
    total supply when the maximum is unknown or unlimited), in US dollars.
    ``rank`` is the market capitalization rank as a positive integer string,
    1 the largest. ``max_supply_unlimited`` is present when the source reports
    no maximum supply; ``max_supply`` is then ``None``.
    """

    circulating_supply: AssetMarketValue | None = None
    total_supply: AssetMarketValue | None = None
    max_supply: AssetMarketValue | None = None
    max_supply_unlimited: AssetMarketFlag | None = None
    market_cap_usd: AssetMarketValue | None = None
    fully_diluted_market_cap_usd: AssetMarketValue | None = None
    rank: AssetMarketValue | None = None


class AssetInfo(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Asset information (``marketdata.v1.MarketDataService/ListAssetInfo``).

    ``asset_id`` is the numeric asset ID, the ``ledger_id`` of the spot and
    deposit/withdraw configs. ``editorial_updated_at`` is the time of the last
    effective editorial change, ``None`` when the server sends none.
    ``market_stats`` holds the asset's market datapoints, ``None`` when it has
    none. An asset with market datapoints and no team-written information is
    listed with an empty ``editorial``: treat that as unknown.
    """

    asset_id: int
    editorial: AssetEditorialInfo = msgspec.field(default_factory=AssetEditorialInfo)
    editorial_updated_at: datetime | None = None
    market_stats: AssetMarketStats | None = None
