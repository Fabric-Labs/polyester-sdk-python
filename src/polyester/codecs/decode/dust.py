from __future__ import annotations

from decimal import Decimal

from polyester.codecs.decode.balances import ledger_amount
from polyester.codecs.decode.common import require_id
from polyester.codecs.decode.internal_transfers import transfer_error_label
from polyester.codecs.proto_helpers import optional_timestamp
from polyester.codecs.scalars import format_scaled
from polyester.errors import PolyesterResponseContractError
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.transfer.v1 import dust_conversion_pb2 as dust_pb2
from polyester.models.dust import (
    DustAssetPrice,
    DustBalance,
    DustBalances,
    DustConversion,
    DustConversionsPage,
    DustQuote,
    DustSource,
)
from polyester.types.money import AssetAmount


def _scaled(msg: u128_pb2.U128) -> int:
    return (int(msg.hi) << 64) | int(msg.lo)


def _e18_decimal(msg: u128_pb2.U128) -> Decimal:
    """An 18-decimal fixed-point U128 as the exact Decimal it encodes."""
    # Built from its decimal string: exact whatever the decimal context.
    return Decimal(format_scaled(_scaled(msg), 18))


def _exact_decimal(value: int, scale: int) -> Decimal:
    """``value / 10**scale`` without rounding, whatever the decimal context.

    Built from its digits and exponent, so a large ``scale`` from the wire
    costs nothing to represent."""
    digits = tuple(int(d) for d in str(abs(value)))
    return Decimal((1 if value < 0 else 0, digits, -scale))


def _amount(msg: u128_pb2.U128, asset_id: int) -> AssetAmount:
    return ledger_amount(_scaled(msg), asset_id or None)


def _label(enum, value: int, prefix: str) -> str:
    if value == 0:
        return ""
    try:
        name: str = enum.Name(value)
    except ValueError:
        return f"UNKNOWN({value})"
    return name.removeprefix(prefix).lower()


def dust_balance_from_proto(msg: dust_pb2.DustBalance) -> DustBalance:
    asset_id = int(msg.asset_id)
    return DustBalance(
        asset_id=asset_id,
        quantity=_amount(msg.amount_e18, asset_id),
        eligibility=_label(
            dust_pb2.DustAssetEligibility, int(msg.eligibility), "DUST_ASSET_ELIGIBILITY_"
        ),
        usd_value=_e18_decimal(msg.usd_value_e18) if msg.HasField("usd_value_e18") else None,
    )


def dust_balances_from_proto(msg: dust_pb2.ListDustBalancesResponse) -> DustBalances:
    target = int(msg.target_asset_id)
    return DustBalances(
        target_asset_id=target,
        targets=[int(item) for item in msg.targets],
        fee_bps=int(msg.fee_bps),
        balances=[dust_balance_from_proto(item) for item in msg.balances],
        gross_usd=_e18_decimal(msg.gross_usd_e18),
        payout=_amount(msg.payout_e18, target),
        target_available=bool(msg.target_available),
    )


def _price_from_proto(msg: dust_pb2.DustAssetPrice) -> DustAssetPrice:
    return DustAssetPrice(
        asset_id=int(msg.asset_id),
        price=_exact_decimal(int(msg.price_ticks), int(msg.price_scale)),
        price_ticks=int(msg.price_ticks),
        price_scale=int(msg.price_scale),
        as_of=optional_timestamp(msg, "as_of"),
    )


def dust_quote_from_proto(msg: dust_pb2.QuoteDustConversionResponse) -> DustQuote:
    target = int(msg.target_asset_id)
    return DustQuote(
        quote_id=msg.quote_id,
        expires_at=optional_timestamp(msg, "expires_at"),
        target_asset_id=target,
        fee_bps=int(msg.fee_bps),
        gross_usd=_e18_decimal(msg.gross_usd_e18),
        payout=_amount(msg.payout_e18, target),
        balances=[dust_balance_from_proto(item) for item in msg.balances],
        prices=[_price_from_proto(item) for item in msg.prices],
    )


def dust_conversion_from_proto(msg: dust_pb2.DustConversion, operation: str) -> DustConversion:
    require_id(operation, "conversion_id", msg.conversion_id)
    target = int(msg.target_asset_id)
    return DustConversion(
        conversion_id=msg.conversion_id,
        quote_id=msg.quote_id,
        state=_label(dust_pb2.DustConversionState, int(msg.state), "DUST_CONVERSION_STATE_"),
        refusal_code=transfer_error_label(int(msg.refusal_code)),
        target_asset_id=target,
        sources=[
            DustSource(
                asset_id=int(item.asset_id), quantity=_amount(item.amount_e18, item.asset_id)
            )
            for item in msg.sources
        ],
        payout=_amount(msg.payout_e18, target),
        quoted_payout=_amount(msg.quoted_payout_e18, target),
        fee=_amount(msg.fee_e18, target),
        fee_bps=int(msg.fee_bps),
        created_at=optional_timestamp(msg, "created_at"),
        completed_at=optional_timestamp(msg, "completed_at"),
    )


def _required_conversion(msg, operation: str) -> DustConversion:
    if not msg.HasField("conversion"):
        raise PolyesterResponseContractError(operation, "missing conversion")
    return dust_conversion_from_proto(msg.conversion, operation)


def created_dust_conversion_from_proto(
    msg: dust_pb2.CreateDustConversionResponse,
) -> DustConversion:
    return _required_conversion(msg, "CreateDustConversion")


def dust_conversion_from_get_response(msg: dust_pb2.GetDustConversionResponse) -> DustConversion:
    return _required_conversion(msg, "GetDustConversion")


def dust_conversions_page_from_proto(
    msg: dust_pb2.ListDustConversionsResponse,
) -> DustConversionsPage:
    return DustConversionsPage(
        conversions=[
            dust_conversion_from_proto(item, "ListDustConversions") for item in msg.conversions
        ],
        next_page_token=msg.next_page_token,
    )
