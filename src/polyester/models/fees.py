from __future__ import annotations

from datetime import datetime

import msgspec


class SpotFeeMultiplier(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Market fee schedule in force over a UTC interval."""

    maker_multiplier_percent: str = ""
    taker_multiplier_percent: str = ""
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class SpotFeeDiscount(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Account or referral discount in force over a UTC interval."""

    maker_discount_percent: str = ""
    taker_discount_percent: str = ""
    all_markets: bool = False
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class SpotFeeRateBreakdown(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Components of the effective fee rates."""

    tier_maker_fee_rate_percent: str = ""
    tier_taker_fee_rate_percent: str = ""
    market_multiplier: SpotFeeMultiplier | None = None
    account_discounts: list[SpotFeeDiscount] = []
    referral_discount: SpotFeeDiscount | None = None


class SpotFeeRate(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Effective fill rates and rates used to reserve quote fees."""

    symbol_id: int = 0
    symbol: str = ""
    maker_fee_rate_percent: str = ""
    taker_fee_rate_percent: str = ""
    vip_tier: int = 0
    reserve_fee_rate_percent: str = ""
    post_only_reserve_fee_rate_percent: str = ""
    next_change_at: datetime | None = None
    breakdown: SpotFeeRateBreakdown | None = None


class SpotFeeRatesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Effective spot fee rows ordered by numeric market identifier."""

    fee_rates: list[SpotFeeRate]
