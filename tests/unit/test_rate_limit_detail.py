from __future__ import annotations

import httpx
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.timestamp_pb2 import Timestamp

from polyester._wire import map_connect_error
from polyester.codecs.decode.orders import preview_order_from_proto
from polyester.connect_transport import raise_for_status
from polyester.errors import PolyesterRateLimitError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2


def _rate_limit_detail(**overrides) -> ratelimit_pb2.RateLimitDetail:
    values = dict(
        reason=ratelimit_pb2.QUOTA_EXCEEDED,
        limit=100,
        remaining=0,
        retry_after_ms=2500,
        policy_version=3,
        operation_id="orders.create",
        policy_class=ratelimit_pb2.TRADING_PLACE,
        scope=ratelimit_pb2.API_KEY,
        refill_model=ratelimit_pb2.CONTINUOUS,
    )
    values.update(overrides)
    return ratelimit_pb2.RateLimitDetail(**values)


def test_map_connect_error_surfaces_nested_rate_limit_detail() -> None:
    detail = orders_pb2.ErrorDetail(
        code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED,
        rate_limit=_rate_limit_detail(),
    )
    mapped = map_connect_error(ConnectError(Code.RESOURCE_EXHAUSTED, "slow down", details=[detail]))
    assert isinstance(mapped, PolyesterRateLimitError)
    assert mapped.retry_after == 2.5
    assert mapped.detail is not None
    assert mapped.detail.reason == "QUOTA_EXCEEDED"
    assert mapped.detail.limit == 100
    assert mapped.detail.remaining == 0
    assert mapped.detail.retry_after_ms == 2500
    assert mapped.detail.policy_version == 3
    assert mapped.detail.operation_id == "orders.create"
    assert mapped.detail.policy_class == "TRADING_PLACE"
    assert mapped.detail.scope == "API_KEY"
    assert mapped.detail.refill_model == "CONTINUOUS"


def test_map_connect_error_surfaces_top_level_rate_limit_detail() -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.RESOURCE_EXHAUSTED,
            "quota",
            details=[_rate_limit_detail(retry_after_ms=1250)],
        )
    )
    assert isinstance(mapped, PolyesterRateLimitError)
    assert mapped.retry_after == 1.25
    assert mapped.detail is not None
    assert mapped.detail.retry_after_ms == 1250


def test_map_connect_error_preserves_absent_optional_fields() -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.RESOURCE_EXHAUSTED,
            "quota",
            details=[
                orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                    rate_limit=ratelimit_pb2.RateLimitDetail(
                        reason=ratelimit_pb2.AUTHORITY_UNAVAILABLE,
                        operation_id="orders.create",
                    ),
                )
            ],
        )
    )
    assert isinstance(mapped, PolyesterRateLimitError)
    assert mapped.retry_after is None
    assert mapped.detail is not None
    assert mapped.detail.limit is None
    assert mapped.detail.remaining is None
    assert mapped.detail.retry_after_ms is None
    assert mapped.detail.policy_version is None
    assert mapped.detail.reason == "AUTHORITY_UNAVAILABLE"


def test_http_429_prefers_retry_after_ms_header() -> None:
    response = httpx.Response(
        429,
        text="slow down",
        headers={"Retry-After-Ms": "1500"},
    )
    try:
        raise_for_status(response)
    except PolyesterRateLimitError as exc:
        assert exc.retry_after == 1.5
    else:
        raise AssertionError("expected PolyesterRateLimitError")


def test_preview_rejection_surfaces_rate_limit_detail() -> None:
    result = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            admissible=False,
            rejection=orders_pb2.ErrorDetail(
                code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                rate_limit=_rate_limit_detail(retry_after_ms=500),
            ),
            evaluated_at=Timestamp(seconds=1),
        ),
        quantity_scale=8,
        symbol="BTC-USDT",
        symbol_id=1,
    )
    assert result.rejection is not None
    assert result.rejection.code == "RATE_LIMIT_EXCEEDED"
    assert result.rejection.rate_limit is not None
    assert result.rejection.rate_limit.retry_after_ms == 500
    assert result.rejection.rate_limit.policy_class == "TRADING_PLACE"
