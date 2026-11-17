from __future__ import annotations

from polyester.codecs.proto_helpers import has_field, optional_timestamp, proto_enum_name
from polyester.gen.marketdata.v1 import asset_info_pb2
from polyester.models.asset_info import (
    AssetEditorialInfo,
    AssetInfo,
    AssetIssuePrice,
    AssetMarketFlag,
    AssetMarketStats,
    AssetMarketValue,
)


def _editorial_from_proto(msg: asset_info_pb2.AssetEditorialInfo) -> AssetEditorialInfo:
    return AssetEditorialInfo(
        description=msg.description,
        website_url=msg.website_url,
        whitepaper_url=msg.whitepaper_url,
        explorer_urls=list(msg.explorer_urls),
        x_url=msg.x_url,
        telegram_url=msg.telegram_url,
        discord_url=msg.discord_url,
        github_url=msg.github_url,
        issue_date=msg.issue_date,
        issue_price=AssetIssuePrice(
            amount=msg.issue_price.amount, currency=msg.issue_price.currency
        )
        if has_field(msg, "issue_price")
        else None,
    )


def _source(value: int) -> str:
    return proto_enum_name(asset_info_pb2.AssetDataSource, int(value))


def _market_value(msg: asset_info_pb2.AssetMarketStats, name: str) -> AssetMarketValue | None:
    if not has_field(msg, name):
        return None
    item = getattr(msg, name)
    return AssetMarketValue(
        value=item.value, source=_source(item.source), as_of=optional_timestamp(item, "as_of")
    )


def _market_stats_from_proto(msg: asset_info_pb2.AssetMarketStats) -> AssetMarketStats:
    flag = msg.max_supply_unlimited
    return AssetMarketStats(
        circulating_supply=_market_value(msg, "circulating_supply"),
        total_supply=_market_value(msg, "total_supply"),
        max_supply=_market_value(msg, "max_supply"),
        max_supply_unlimited=(
            AssetMarketFlag(source=_source(flag.source), as_of=optional_timestamp(flag, "as_of"))
            if has_field(msg, "max_supply_unlimited")
            else None
        ),
        market_cap_usd=_market_value(msg, "market_cap_usd"),
        fully_diluted_market_cap_usd=_market_value(msg, "fully_diluted_market_cap_usd"),
        rank=_market_value(msg, "rank"),
    )


def asset_info_from_proto(msg: asset_info_pb2.AssetInfo) -> AssetInfo:
    """Decode one asset's information. A missing editorial object reads as an
    empty one; a missing launch price stays ``None``, apart from a known zero
    price."""
    return AssetInfo(
        asset_id=int(msg.asset_id),
        editorial=_editorial_from_proto(msg.editorial),
        editorial_updated_at=optional_timestamp(msg, "editorial_updated_at"),
        market_stats=(
            _market_stats_from_proto(msg.market_stats) if has_field(msg, "market_stats") else None
        ),
    )


def asset_info_list_from_proto(msg: asset_info_pb2.ListAssetInfoResponse) -> list[AssetInfo]:
    return [asset_info_from_proto(item) for item in msg.asset_info]
