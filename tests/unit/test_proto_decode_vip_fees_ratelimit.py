from datetime import UTC, datetime

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.fees import spot_fee_rates_list_from_proto
from polyester.codecs.decode.trading_rate_limits import (
    rate_limit_config_from_proto,
    trading_rate_limits_from_proto,
)
from polyester.codecs.decode.vip import vip_status_from_proto, vip_tiers_list_from_proto
from polyester.gen.fees.v1 import fees_pb2
from polyester.gen.fees.v1.fees_connect import FeeServiceClient
from polyester.gen.ratelimit.v1 import ratelimit_pb2
from polyester.gen.ratelimit.v1.ratelimit_connect import RateLimitServiceClient
from polyester.gen.vip.v1 import vip_pb2
from polyester.gen.vip.v1.vip_connect import VIPServiceClient


def test_generated_connect_clients_import_from_package() -> None:
    assert FeeServiceClient.__name__ == "FeeServiceClient"
    assert VIPServiceClient.__name__ == "VIPServiceClient"
    assert RateLimitServiceClient.__name__ == "RateLimitServiceClient"


def _ts(seconds: int, nanos: int = 0) -> Timestamp:
    return Timestamp(seconds=seconds, nanos=nanos)


def test_vip_tiers_preserve_optional_aop_and_timestamps() -> None:
    msg = vip_pb2.ListVIPTiersResponse(
        policy_version=7,
        effective_from=_ts(1_700_000_000, 250_000_000),
        retention_threshold_bp=9500,
        tiers=[
            vip_pb2.VIPTier(
                tier=0,
                volume_threshold_usd="0",
                maker_fee_rate_percent="0.02",
                taker_fee_rate_percent="0.05",
            ),
            vip_pb2.VIPTier(
                tier=1,
                volume_threshold_usd="100000",
                aop_threshold_usd="50000.5",
                maker_fee_rate_percent="0.01",
                taker_fee_rate_percent="0.04",
            ),
        ],
    )
    result = vip_tiers_list_from_proto(msg)
    assert result.policy_version == 7
    assert result.retention_threshold_bp == 9500
    assert result.effective_from == datetime.fromtimestamp(
        1_700_000_000.25, tz=UTC
    )
    assert result.tiers[0].aop_threshold_usd is None
    assert result.tiers[1].aop_threshold_usd == "50000.5"
    assert result.tiers[1].volume_threshold_usd == "100000"


def test_vip_status_omits_unset_qualification_fields() -> None:
    msg = vip_pb2.GetVIPStatusResponse(
        tier=0,
        volume_tier=0,
        aop_tier=0,
        policy_version=1,
        policy_effective_from=_ts(1_700_000_100),
    )
    status = vip_status_from_proto(msg)
    assert status.tier == 0
    assert status.settled_volume_30d_usd is None
    assert status.average_aop_30d_usd is None
    assert status.effective_from is None
    assert status.evaluated_at is None
    assert status.metrics_as_of is None
    assert status.next_tier_thresholds is None
    assert status.policy_effective_from == datetime.fromtimestamp(
        1_700_000_100, tz=UTC
    )


def test_vip_status_surfaces_next_tier_and_metrics() -> None:
    msg = vip_pb2.GetVIPStatusResponse(
        tier=2,
        volume_tier=2,
        aop_tier=1,
        settled_volume_30d_usd="250000.12",
        average_aop_30d_usd="80000",
        policy_version=3,
        policy_effective_from=_ts(10),
        effective_from=_ts(20),
        evaluated_at=_ts(30),
        metrics_as_of=_ts(40),
        next_tier_thresholds=vip_pb2.NextVIPTierThresholds(
            tier=3,
            volume_threshold_usd="500000",
            aop_threshold_usd="150000",
        ),
    )
    status = vip_status_from_proto(msg)
    assert status.settled_volume_30d_usd == "250000.12"
    assert status.next_tier_thresholds is not None
    assert status.next_tier_thresholds.tier == 3
    assert status.metrics_as_of == datetime.fromtimestamp(40, tz=UTC)


def test_spot_fee_rates_decode_rows() -> None:
    msg = fees_pb2.GetSpotFeeRatesResponse(
        fee_rates=[
            fees_pb2.SpotFeeRate(
                symbol_id=7,
                maker_fee_rate_percent="0.01",
                taker_fee_rate_percent="0.04",
                vip_tier=2,
            )
        ]
    )
    result = spot_fee_rates_list_from_proto(msg)
    assert len(result.fee_rates) == 1
    row = result.fee_rates[0]
    assert row.symbol_id == 7
    assert row.symbol == ""
    assert row.vip_tier == 2


def test_rate_limit_config_uses_full_policy_class_names() -> None:
    msg = ratelimit_pb2.GetRateLimitConfigResponse(
        policy_version=9,
        effective_from=_ts(50),
        rules=[
            ratelimit_pb2.TradingRateLimitRule(
                policy_class=ratelimit_pb2.TRADING_RATE_LIMIT_CLASS_PLACE,
                vip_tier=0,
                quota_weight=100,
                period_ms=1000,
                burst_weight=20,
            ),
            ratelimit_pb2.TradingRateLimitRule(
                policy_class=99,
                vip_tier=1,
                quota_weight=50,
                period_ms=1000,
                burst_weight=10,
            ),
        ],
    )
    result = rate_limit_config_from_proto(msg)
    assert result.policy_version == 9
    assert result.rules[0].policy_class == "TRADING_RATE_LIMIT_CLASS_PLACE"
    assert result.rules[1].policy_class == "UNKNOWN_TRADING_RATE_LIMIT_CLASS(99)"


def test_trading_rate_limits_decode_account_and_api_key_rules() -> None:
    rule = ratelimit_pb2.TradingRateLimitRule(
        policy_class=ratelimit_pb2.TRADING_RATE_LIMIT_CLASS_CANCEL,
        vip_tier=3,
        quota_weight=200,
        period_ms=500,
        burst_weight=40,
    )
    msg = ratelimit_pb2.GetTradingRateLimitsResponse(
        policy_version=4,
        rules=[rule],
        api_key_rules=[rule],
    )
    result = trading_rate_limits_from_proto(msg)
    assert result.effective_from is None
    assert result.rules[0].policy_class == "TRADING_RATE_LIMIT_CLASS_CANCEL"
    assert result.api_key_rules[0].vip_tier == 3
