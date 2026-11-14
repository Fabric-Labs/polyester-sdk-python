from __future__ import annotations

from polyester.codecs.proto_helpers import has_field, optional_timestamp
from polyester.gen.marketdata.v1 import asset_info_pb2
from polyester.models.asset_info import AssetEditorialInfo, AssetInfo, AssetIssuePrice


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


def asset_info_from_proto(msg: asset_info_pb2.AssetInfo) -> AssetInfo:
    """Decode one asset's information. A missing editorial object reads as an
    empty one; a missing launch price stays ``None``, apart from a known zero
    price."""
    return AssetInfo(
        asset_id=int(msg.asset_id),
        editorial=_editorial_from_proto(msg.editorial),
        editorial_updated_at=optional_timestamp(msg, "editorial_updated_at"),
    )


def asset_info_list_from_proto(msg: asset_info_pb2.ListAssetInfoResponse) -> list[AssetInfo]:
    return [asset_info_from_proto(item) for item in msg.asset_info]
