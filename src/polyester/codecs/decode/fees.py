from __future__ import annotations

from polyester.gen.fees.v1 import fees_pb2
from polyester.models.fees import SpotFeeRate, SpotFeeRatesList


def spot_fee_rate_from_proto(msg: fees_pb2.SpotFeeRate) -> SpotFeeRate:
    return SpotFeeRate(
        symbol_id=int(msg.symbol_id),
        symbol=msg.symbol or "",
        maker_fee_rate_percent=msg.maker_fee_rate_percent or "",
        taker_fee_rate_percent=msg.taker_fee_rate_percent or "",
        vip_tier=int(msg.vip_tier),
    )


def spot_fee_rates_list_from_proto(msg: fees_pb2.GetSpotFeeRatesResponse) -> SpotFeeRatesList:
    return SpotFeeRatesList(
        fee_rates=[spot_fee_rate_from_proto(item) for item in msg.fee_rates]
    )
