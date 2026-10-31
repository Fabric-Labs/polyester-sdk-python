"""TIMESTAMP_SKEW is a retryable error; 501 / unimplemented is NotImplemented."""

from __future__ import annotations

import json

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from pytest_httpserver import HTTPServer

from polyester import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterNotImplementedError,
    PolyesterRouteNotFoundError,
    PolyesterTimestampSkewError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester._wire import map_connect_error
from polyester.realtime.auth import _auth_http_error
from polyester.services.market_data import AsyncMarketDataService
from polyester.transport import TransportConfig, TransportFactory

SPOT_CONFIG_PATH = "/marketdata.v1.MarketDataService/GetSpotConfig"


async def _spot_config_error(httpserver: HTTPServer) -> BaseException:
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        with pytest.raises(Exception) as caught:
            await AsyncMarketDataService(transport).get_spot_config()
    finally:
        await transport.aclose()
    return caught.value


def test_connect_timestamp_skew_is_retryable_and_not_outcome_unknown() -> None:
    mapped = map_connect_error(ConnectError(Code.UNAUTHENTICATED, "TIMESTAMP_SKEW"))

    assert isinstance(mapped, PolyesterTimestampSkewError)
    assert mapped.code == "TIMESTAMP_SKEW"
    assert mapped.status_code == 401
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


def test_other_unauthenticated_errors_stay_auth_errors() -> None:
    mapped = map_connect_error(ConnectError(Code.UNAUTHENTICATED, "SIGNATURE_INVALID"))

    assert isinstance(mapped, PolyesterAuthError)
    assert not is_retryable_error(mapped)


@pytest.mark.asyncio
@pytest.mark.parametrize("content_type", ["application/json", "application/problem+json"])
async def test_gateway_timestamp_skew_maps_through_the_connect_transport(
    httpserver: HTTPServer, content_type: str
) -> None:
    # The devnet gateway answers 401 application/json {"code": "TIMESTAMP_SKEW"}.
    httpserver.expect_request(SPOT_CONFIG_PATH, method="POST").respond_with_data(
        json.dumps({"code": "TIMESTAMP_SKEW"}), status=401, content_type=content_type
    )

    error = await _spot_config_error(httpserver)

    assert isinstance(error, PolyesterTimestampSkewError)
    assert error.status_code == 401
    assert is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"), [(401, "SIGNATURE_INVALID"), (401, "KEY_DISABLED"), (403, "IP_NOT_ALLOWED")]
)
async def test_other_gateway_rejections_are_auth_errors_not_retryable_server_errors(
    httpserver: HTTPServer, status: int, code: str
) -> None:
    httpserver.expect_request(SPOT_CONFIG_PATH, method="POST").respond_with_data(
        json.dumps({"code": code}), status=status, content_type="application/json"
    )

    error = await _spot_config_error(httpserver)

    assert isinstance(error, PolyesterAuthError)
    assert code in str(error)
    assert not is_retryable_error(error)


@pytest.mark.asyncio
async def test_connect_json_errors_still_map_by_their_connect_code(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request(SPOT_CONFIG_PATH, method="POST").respond_with_data(
        json.dumps({"code": "unavailable", "message": "try later"}),
        status=503,
        content_type="application/json",
    )

    error = await _spot_config_error(httpserver)

    assert type(error).__name__ == "PolyesterServerError"
    assert str(error) == "try later"


def test_realtime_token_timestamp_skew_is_retryable() -> None:
    error = _auth_http_error(
        status_code=401,
        label="realtime connection token",
        endpoint="https://api.example/v1/rt/token",
        body=json.dumps({"code": "TIMESTAMP_SKEW"}).encode(),
    )

    assert isinstance(error, PolyesterTimestampSkewError)
    assert is_retryable_error(error)


def test_connect_unimplemented_is_not_implemented() -> None:
    mapped = map_connect_error(ConnectError(Code.UNIMPLEMENTED, "method not supported"))

    assert isinstance(mapped, PolyesterNotImplementedError)
    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == "unimplemented"
    assert not is_retryable_error(mapped)


def test_missing_route_stays_route_not_found_and_is_not_implemented() -> None:
    mapped = map_connect_error(ConnectError(Code.UNIMPLEMENTED, "Not Found"))

    assert isinstance(mapped, PolyesterRouteNotFoundError)
    assert isinstance(mapped, PolyesterNotImplementedError)
    assert mapped.code == "route_not_found"


@pytest.mark.asyncio
async def test_bare_http_501_is_not_implemented(httpserver: HTTPServer) -> None:
    httpserver.expect_request(SPOT_CONFIG_PATH, method="POST").respond_with_data(
        "not implemented", status=501, content_type="text/plain"
    )

    error = await _spot_config_error(httpserver)

    assert isinstance(error, PolyesterNotImplementedError)
    assert not is_retryable_error(error)
