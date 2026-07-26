import httpx
import pytest

from polyester.connect_transport import (
    connect_headers,
    encode_connect_body,
    normalize_procedure,
    raise_for_status,
)
from polyester.errors import (
    PolyesterRateLimitError,
    PolyesterRouteNotFoundError,
    PolyesterValidationError,
)


def test_normalize_procedure_adds_leading_slash() -> None:
    assert normalize_procedure("marketdata.v1.MarketDataService/GetSpotConfig") == (
        "/marketdata.v1.MarketDataService/GetSpotConfig"
    )


def test_connect_json_headers() -> None:
    headers = connect_headers(wire_format="json")
    assert headers["Content-Type"] == "application/json"
    assert headers["Connect-Protocol-Version"] == "1"


def test_encode_connect_json_body_empty_object() -> None:
    assert encode_connect_body({}, wire_format="json") == b"{}"


def test_raise_for_status_404_is_route_not_found() -> None:
    response = httpx.Response(404, text="404 page not found")
    try:
        raise_for_status(response)
    except PolyesterRouteNotFoundError:
        pass
    else:
        raise AssertionError("expected PolyesterRouteNotFoundError")


def test_binary_wire_requires_generated_clients() -> None:
    try:
        encode_connect_body({}, wire_format="binary")
    except PolyesterValidationError:
        pass
    else:
        raise AssertionError("expected binary wire format to require generated clients")


def test_rate_limit_parses_retry_after_seconds() -> None:
    response = httpx.Response(429, text="slow down", headers={"Retry-After": "2.5"})
    with pytest.raises(PolyesterRateLimitError) as caught:
        raise_for_status(response)
    assert caught.value.retry_after == 2.5


def test_rate_limit_ignores_malformed_retry_after() -> None:
    response = httpx.Response(429, text="slow down", headers={"Retry-After": "tomorrow"})
    with pytest.raises(PolyesterRateLimitError) as caught:
        raise_for_status(response)
    assert caught.value.retry_after is None
