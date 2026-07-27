import httpx
import pytest

from polyester.connect_transport import connect_headers, raise_for_status
from polyester.errors import PolyesterAuthError, PolyesterTransportError
from polyester.transport import TransportConfig, TransportFactory
from polyester.user_agent import USER_AGENT, is_cloudflare_browser_ban


def test_user_agent_is_polyester_sdk_identity() -> None:
    assert USER_AGENT.startswith("polyester-sdk-python/")
    assert "python-requests" not in USER_AGENT
    assert "python-httpx" not in USER_AGENT


def test_connect_headers_include_user_agent() -> None:
    headers = connect_headers(wire_format="json")
    assert headers["User-Agent"] == USER_AGENT


def test_transport_http_client_sets_user_agent() -> None:
    factory = TransportFactory(TransportConfig(api_url="https://example.test"))
    assert factory.public_http.headers["user-agent"] == USER_AGENT


def test_cloudflare_1010_is_transport_not_auth() -> None:
    body = (
        "<!DOCTYPE html><html><title>Attention Required! | Cloudflare</title>"
        "<body>error code: 1010</body></html>"
    )
    assert is_cloudflare_browser_ban(body)
    response = httpx.Response(403, text=body)
    with pytest.raises(PolyesterTransportError) as caught:
        raise_for_status(response)
    assert "1010" in str(caught.value)
    assert "authentication" in str(caught.value).lower()


def test_real_auth_403_still_auth_error() -> None:
    response = httpx.Response(403, text='{"code":"permission_denied","message":"nope"}')
    with pytest.raises(PolyesterAuthError):
        raise_for_status(response)
