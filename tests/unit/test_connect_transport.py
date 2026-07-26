import httpx

from polyester.connect_transport import (
    connect_headers,
    encode_connect_body,
    normalize_procedure,
    raise_for_status,
)
from polyester.errors import PolyesterRouteNotFoundError, PolyesterValidationError


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
