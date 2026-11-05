from __future__ import annotations

from datetime import UTC

from polyester.catalogs import CatalogManager
from polyester.codecs.proto_helpers import has_field
from polyester.gen.fees.v1 import fees_pb2
from polyester.models.fees import (
    SpotFeeDiscount,
    SpotFeeMultiplier,
    SpotFeeRate,
    SpotFeeRateBreakdown,
    SpotFeeRatesList,
)


def spot_fee_rate_from_proto(
    msg: fees_pb2.SpotFeeRate,
    catalogs: CatalogManager | None = None,
) -> SpotFeeRate:
    symbol_id = int(msg.symbol_id)
    symbol = catalogs.symbol_for_symbol_id(symbol_id) if catalogs is not None else None
    return SpotFeeRate(
        symbol_id=symbol_id,
        symbol=symbol or "",
        maker_fee_rate_percent=msg.maker_fee_rate_percent or "",
        taker_fee_rate_percent=msg.taker_fee_rate_percent or "",
        vip_tier=int(msg.vip_tier),
        reserve_fee_rate_percent=msg.reserve_fee_rate_percent,
        post_only_reserve_fee_rate_percent=msg.post_only_reserve_fee_rate_percent,
        next_change_at=msg.next_change_at.ToDatetime(tzinfo=UTC)
        if has_field(msg, "next_change_at")
        else None,
        breakdown=_breakdown(msg.breakdown) if has_field(msg, "breakdown") else None,
    )


def spot_fee_rates_list_from_proto(
    msg: fees_pb2.GetSpotFeeRatesResponse,
    catalogs: CatalogManager | None = None,
) -> SpotFeeRatesList:
    return SpotFeeRatesList(
        fee_rates=[spot_fee_rate_from_proto(item, catalogs) for item in msg.fee_rates]
    )


def _discount(msg: fees_pb2.SpotFeeDiscount) -> SpotFeeDiscount:
    return SpotFeeDiscount(
        maker_discount_percent=msg.maker_discount_percent,
        taker_discount_percent=msg.taker_discount_percent,
        all_markets=msg.all_markets,
        effective_from=msg.effective_from.ToDatetime(tzinfo=UTC)
        if has_field(msg, "effective_from")
        else None,
        effective_to=msg.effective_to.ToDatetime(tzinfo=UTC)
        if has_field(msg, "effective_to")
        else None,
    )


def _breakdown(msg: fees_pb2.SpotFeeRateBreakdown) -> SpotFeeRateBreakdown:
    multiplier = None
    if has_field(msg, "market_multiplier"):
        item = msg.market_multiplier
        multiplier = SpotFeeMultiplier(
            maker_multiplier_percent=item.maker_multiplier_percent,
            taker_multiplier_percent=item.taker_multiplier_percent,
            effective_from=item.effective_from.ToDatetime(tzinfo=UTC)
            if has_field(item, "effective_from")
            else None,
            effective_to=item.effective_to.ToDatetime(tzinfo=UTC)
            if has_field(item, "effective_to")
            else None,
        )
    return SpotFeeRateBreakdown(
        tier_maker_fee_rate_percent=msg.tier_maker_fee_rate_percent,
        tier_taker_fee_rate_percent=msg.tier_taker_fee_rate_percent,
        market_multiplier=multiplier,
        account_discounts=[_discount(item) for item in msg.account_discounts],
        referral_discount=_discount(msg.referral_discount)
        if has_field(msg, "referral_discount")
        else None,
    )
