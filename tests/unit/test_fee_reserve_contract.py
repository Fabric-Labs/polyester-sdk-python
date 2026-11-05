from datetime import UTC, datetime

from google.protobuf.json_format import ParseDict

from polyester.codecs.decode.fees import spot_fee_rate_from_proto
from polyester.gen.fees.v1.fees_pb2 import SpotFeeRate


def test_fee_reserves_breakdown_and_proto_defaults():
    msg = ParseDict(
        {
            "reserveFeeRatePercent": "0.09",
            "postOnlyReserveFeeRatePercent": "0.08",
            "nextChangeAt": "2026-11-06T00:00:00Z",
            "breakdown": {
                "tierMakerFeeRatePercent": "-0.08",
                "tierTakerFeeRatePercent": "0.135",
                "marketMultiplier": {
                    "makerMultiplierPercent": "90",
                    "takerMultiplierPercent": "20",
                    "effectiveFrom": "2026-11-01T00:00:00Z",
                },
                "referralDiscount": {
                    "makerDiscountPercent": "5",
                    "takerDiscountPercent": "10",
                    "effectiveFrom": "2026-11-01T00:00:00Z",
                },
            },
        },
        SpotFeeRate(),
    )
    row = spot_fee_rate_from_proto(msg)
    assert row.reserve_fee_rate_percent == "0.09"
    assert row.post_only_reserve_fee_rate_percent == "0.08"
    assert row.next_change_at == datetime(2026, 11, 6, tzinfo=UTC)
    assert row.breakdown.tier_maker_fee_rate_percent == "-0.08"
    assert row.breakdown.account_discounts == []
    assert row.breakdown.market_multiplier.maker_multiplier_percent == "90"
    assert row.breakdown.market_multiplier.effective_to is None
    assert row.breakdown.referral_discount.taker_discount_percent == "10"
    assert row.breakdown.referral_discount.all_markets is False
    assert row.breakdown.referral_discount.effective_to is None
    empty = spot_fee_rate_from_proto(SpotFeeRate())
    assert empty.breakdown is None
    assert empty.next_change_at is None
