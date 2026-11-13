"""Protobuf ``Timestamp`` values decode exactly, never rounded into the next second.

A float of ``seconds + nanos / 1e9`` cannot hold nine fractional digits at
current epoch values, so a time in the last nanoseconds of a second rounded up
to the next second. Each decoder below reads a server message the way the SDK
does (serialized, then parsed) and must keep the second it was sent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polyester.codecs.decode.alerts import price_alert_from_proto
from polyester.codecs.decode.changelog import changelog_post_summary_from_proto
from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.decode.trading_rate_limits import rate_limit_config_from_proto
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.decode.vip import vip_tiers_list_from_proto
from polyester.codecs.proto_helpers import timestamp_to_rfc3339
from polyester.codecs.scalars import timestamp_dict_to_datetime
from polyester.gen.alerts.v1 import price_alerts_pb2
from polyester.gen.changelog.v1 import changelog_pb2
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.ratelimit.v1 import ratelimit_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.gen.vip.v1 import vip_pb2

# 2026-11-13T18:00:00Z
SECONDS = 1794592800
BASE = datetime(2026, 11, 13, 18, 0, 0, tzinfo=UTC)


def _roundtrip(msg):  # type: ignore[no-untyped-def]
    return type(msg).FromString(msg.SerializeToString())


@pytest.mark.parametrize(
    ("nanos", "expected"),
    [
        (999_999_999, "2026-11-13T18:00:00.999999999Z"),
        (999_999_404, "2026-11-13T18:00:00.999999404Z"),
        (999_999_403, "2026-11-13T18:00:00.999999403Z"),
        (123_456_789, "2026-11-13T18:00:00.123456789Z"),
        (0, "2026-11-13T18:00:00Z"),
    ],
)
def test_order_expire_at_keeps_its_second(nanos: int, expected: str) -> None:
    msg = orders_read_pb2.Order(symbol_id=1)
    msg.expire_at.seconds = SECONDS
    msg.expire_at.nanos = nanos
    decoded = order_from_proto(_roundtrip(msg), quantity_scale=8, quote_quantity_scale=6)
    assert decoded.expire_at == expected


def test_order_without_expire_at_reads_none() -> None:
    msg = orders_read_pb2.Order(symbol_id=1)
    decoded = order_from_proto(_roundtrip(msg), quantity_scale=8, quote_quantity_scale=6)
    assert decoded.expire_at is None


def test_rfc3339_before_the_epoch_is_exact() -> None:
    msg = orders_read_pb2.Order(symbol_id=1)
    msg.expire_at.seconds = -1
    msg.expire_at.nanos = 999_999_999
    assert timestamp_to_rfc3339(msg.expire_at) == "1969-12-31T23:59:59.999999999Z"


# datetime holds microseconds: the nanoseconds below one microsecond are
# dropped (truncated, as protobuf's ``ToDatetime`` does), never rounded up.
DATETIME_CASES = [
    (999_999_999, BASE.replace(microsecond=999_999)),
    (999_999_404, BASE.replace(microsecond=999_999)),
    (999_999_500, BASE.replace(microsecond=999_999)),
    (123_456_789, BASE.replace(microsecond=123_456)),
    (0, BASE),
]


@pytest.mark.parametrize(("nanos", "expected"), DATETIME_CASES)
def test_timestamp_dict_to_datetime_is_exact(nanos: int, expected: datetime) -> None:
    assert timestamp_dict_to_datetime({"seconds": SECONDS, "nanos": nanos}) == expected


@pytest.mark.parametrize(("nanos", "expected"), DATETIME_CASES)
def test_price_alert_times_are_exact(nanos: int, expected: datetime) -> None:
    msg = price_alerts_pb2.PriceAlert(alert_id=1, symbol_id=1)
    msg.created_at.seconds = SECONDS
    msg.created_at.nanos = nanos
    assert price_alert_from_proto(_roundtrip(msg), None).created_at == expected


@pytest.mark.parametrize(("nanos", "expected"), DATETIME_CASES)
def test_trigger_times_are_exact(nanos: int, expected: datetime) -> None:
    msg = triggers_pb2.Trigger()
    msg.created_at.seconds = SECONDS
    msg.created_at.nanos = nanos
    assert trigger_from_proto(_roundtrip(msg)).created_at == expected


@pytest.mark.parametrize(("nanos", "expected"), DATETIME_CASES)
def test_changelog_times_are_exact(nanos: int, expected: datetime) -> None:
    msg = changelog_pb2.PostSummary()
    msg.published_at.seconds = SECONDS
    msg.published_at.nanos = nanos
    assert changelog_post_summary_from_proto(_roundtrip(msg)).published_at == expected


@pytest.mark.parametrize(("nanos", "expected"), DATETIME_CASES)
def test_vip_times_are_exact(nanos: int, expected: datetime) -> None:
    msg = vip_pb2.ListVIPTiersResponse()
    msg.effective_from.seconds = SECONDS
    msg.effective_from.nanos = nanos
    assert vip_tiers_list_from_proto(_roundtrip(msg)).effective_from == expected


@pytest.mark.parametrize(("nanos", "expected"), DATETIME_CASES)
def test_rate_limit_times_are_exact(nanos: int, expected: datetime) -> None:
    msg = ratelimit_pb2.GetRateLimitConfigResponse()
    msg.effective_from.seconds = SECONDS
    msg.effective_from.nanos = nanos
    assert rate_limit_config_from_proto(_roundtrip(msg)).effective_from == expected
