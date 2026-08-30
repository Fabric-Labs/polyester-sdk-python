from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import PolyesterAuthError, PolyesterTransportError
from polyester.transport import TransportConfig, TransportFactory
from polyester.user_agent import USER_AGENT, is_cloudflare_browser_ban


def test_user_agent_is_polyester_sdk_identity() -> None:
    assert USER_AGENT.startswith("polyester-sdk-python/")
    assert "python-requests" not in USER_AGENT
    assert "python-httpx" not in USER_AGENT


def test_transport_http_client_sets_user_agent() -> None:
    factory = TransportFactory(TransportConfig(api_url="https://example.test"))
    assert factory.public_http.headers["user-agent"] == USER_AGENT


def test_cloudflare_1010_is_transport_not_auth() -> None:
    body = (
        "<!DOCTYPE html><html><title>Attention Required! | Cloudflare</title>"
        "<body>error code: 1010</body></html>"
    )
    assert is_cloudflare_browser_ban(body)
    mapped = map_connect_error(ConnectError(Code.PERMISSION_DENIED, body))
    assert isinstance(mapped, PolyesterTransportError)
    assert "1010" in str(mapped)
    assert "authentication" in str(mapped).lower()


def test_real_auth_403_still_auth_error() -> None:
    mapped = map_connect_error(ConnectError(Code.PERMISSION_DENIED, "nope"))
    assert isinstance(mapped, PolyesterAuthError)
