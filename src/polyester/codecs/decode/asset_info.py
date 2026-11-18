from __future__ import annotations

from datetime import datetime

from polyester.codecs.proto_helpers import has_field, optional_timestamp, proto_enum_name
from polyester.errors import PolyesterResponseContractError
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


def _provenance(item, name: str, asset_id: int) -> tuple[str, datetime]:
    """A present datapoint's source and time, which the contract always sets:
    a datapoint without them breaks it (an absent datapoint is unknown)."""
    as_of = optional_timestamp(item, "as_of")
    if int(item.source) == asset_info_pb2.SOURCE_UNSPECIFIED or as_of is None:
        raise PolyesterResponseContractError(
            "ListAssetInfo", f"asset {asset_id} {name} is missing its source or as_of"
        )
    return _source(item.source), as_of


def _market_value(
    msg: asset_info_pb2.AssetMarketStats, name: str, asset_id: int
) -> AssetMarketValue | None:
    if not has_field(msg, name):
        return None
    item = getattr(msg, name)
    if not item.value:
        raise PolyesterResponseContractError(
            "ListAssetInfo", f"asset {asset_id} {name} is missing its value"
        )
    source, as_of = _provenance(item, name, asset_id)
    return AssetMarketValue(value=item.value, source=source, as_of=as_of)


def _market_stats_from_proto(
    msg: asset_info_pb2.AssetMarketStats, asset_id: int
) -> AssetMarketStats:
    flag: AssetMarketFlag | None = None
    if has_field(msg, "max_supply_unlimited"):
        source, as_of = _provenance(msg.max_supply_unlimited, "max_supply_unlimited", asset_id)
        flag = AssetMarketFlag(source=source, as_of=as_of)
    return AssetMarketStats(
        circulating_supply=_market_value(msg, "circulating_supply", asset_id),
        total_supply=_market_value(msg, "total_supply", asset_id),
        max_supply=_market_value(msg, "max_supply", asset_id),
        max_supply_unlimited=flag,
        market_cap_usd=_market_value(msg, "market_cap_usd", asset_id),
        fully_diluted_market_cap_usd=_market_value(msg, "fully_diluted_market_cap_usd", asset_id),
        rank=_market_value(msg, "rank", asset_id),
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
            _market_stats_from_proto(msg.market_stats, int(msg.asset_id))
            if has_field(msg, "market_stats")
            else None
        ),
    )


def asset_info_list_from_proto(msg: asset_info_pb2.ListAssetInfoResponse) -> list[AssetInfo]:
    return [asset_info_from_proto(item) for item in msg.asset_info]
