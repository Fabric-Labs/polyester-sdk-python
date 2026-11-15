"""Dust conversion (``transfer.v1.DustConversionService``) models.

Every amount is exact: asset amounts are :class:`~polyester.types.money.AssetAmount`
values in 18-decimal ledger units (``scale`` 18, domain ``ledger_e18``), and
USD values and prices are :class:`~decimal.Decimal` values built from the
wire integers without rounding. None of them passes through a float.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import msgspec

from polyester.types.money import AssetAmount


class DustBalance(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One available Trading balance judged for dust conversion.

    ``quantity`` is the whole available balance, what no open order or other
    reservation holds. ``eligibility`` is ``"eligible"`` (the balance is dust
    and converts), ``"target_asset"`` (the conversion's target, never a
    source), ``"tradable"`` (an open market accepts an order for it: sell or
    spend it instead), ``"above_value_limit"`` (worth more than 10 USD),
    ``"no_price"`` (no current index price; never valued at zero),
    ``"unsupported_asset"`` or ``"source_limit"`` (one conversion takes at
    most 20 balances, the highest-valued first; this one waits for the next).
    "" when the server names none; ``"UNKNOWN(n)"`` for a value this SDK does
    not know. ``usd_value`` is the balance's USD value, rounded down, or
    ``None`` when the asset has no current price.
    """

    asset_id: int = 0
    quantity: AssetAmount | None = None
    eligibility: str = ""
    usd_value: Decimal | None = None


class DustBalances(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The account's Trading balances judged for conversion into one target
    (``ListDustBalances``). It reserves nothing: quote to price a conversion.

    ``targets`` lists every asset the account can convert dust into, in
    preference order; ``target_asset_id`` is the one ``balances`` were judged
    for. ``gross_usd`` is the eligible balances' total USD value, rounded
    down, and ``payout`` what they would bring now in the target asset, after
    the ``fee_bps`` fee. ``target_available`` is false when the target cannot
    be paid now; a quote is then refused with ``ERROR_CODE_DUST_TARGET_UNAVAILABLE``.
    """

    target_asset_id: int = 0
    targets: list[int] = []
    fee_bps: int = 0
    balances: list[DustBalance] = []
    gross_usd: Decimal = Decimal(0)
    payout: AssetAmount | None = None
    target_available: bool = False


class DustAssetPrice(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The USD index price a quote used for one asset: ``price`` USD per whole
    unit, exactly ``price_ticks / 10**price_scale``. ``as_of`` is the time of
    the oldest index observation the price used."""

    asset_id: int = 0
    price: Decimal = Decimal(0)
    price_ticks: int = 0
    price_scale: int = 0
    as_of: datetime | None = None


class DustQuote(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A dust conversion quote (``QuoteDustConversion``), valid until
    ``expires_at`` (30 seconds). It reserves nothing.

    ``quote_id`` is what ``dust_conversions.convert`` takes; it is "" when no
    balance is eligible or their payout rounds to zero, and ``balances`` still
    says why. ``payout`` is in the target asset, after the ``fee_bps`` fee and
    rounded down to the target's quantity precision. ``prices`` holds the
    prices of the sources and the target.
    """

    quote_id: str = ""
    expires_at: datetime | None = None
    target_asset_id: int = 0
    fee_bps: int = 0
    gross_usd: Decimal = Decimal(0)
    payout: AssetAmount | None = None
    balances: list[DustBalance] = []
    prices: list[DustAssetPrice] = []


class DustSource(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One balance a conversion moves: the whole quoted balance."""

    asset_id: int = 0
    quantity: AssetAmount | None = None


class DustConversion(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One conversion of the account's dust into a target asset.

    ``state`` is ``"processing"`` (accepted; it completes or is refused
    without another request: read it again with ``dust_conversions.get``),
    ``"completed"`` (every source moved and the payout was credited,
    atomically) or ``"refused"`` (nothing moved). ``refusal_code`` says why a
    conversion was refused, as a lowercase label without the ``ERROR_CODE_``
    prefix, such as ``"dust_price_moved"``; "" otherwise. ``payout`` is in the
    target asset after the ``fee``; ``quoted_payout`` is what the quote
    showed. ``completed_at`` is ``None`` until the conversion completes.
    """

    conversion_id: str
    quote_id: str = ""
    state: str = ""
    refusal_code: str = ""
    target_asset_id: int = 0
    sources: list[DustSource] = []
    payout: AssetAmount | None = None
    quoted_payout: AssetAmount | None = None
    fee: AssetAmount | None = None
    fee_bps: int = 0
    created_at: datetime | None = None
    completed_at: datetime | None = None


class DustConversionsPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of conversions, newest first; ``next_page_token`` is "" on the
    last page."""

    conversions: list[DustConversion] = []
    next_page_token: str = ""
