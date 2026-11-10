"""A redirect whose Location does not parse is refused without repeating it.

Each test signs with a disposable Ed25519 key generated here and answers from
a loopback socket that writes the redirect byte for byte: test HTTP servers
refuse to send a Location that does not parse. Every URL marker is synthetic.
"""

from __future__ import annotations

import socket
import threading
import traceback
from collections.abc import Iterator

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.exceptions import InvalidURI

from polyester import AsyncPolyester, PolyesterError, PolyesterRedirectError
from polyester._redirects import redirect_refusal
from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError, is_retryable_error, mutation_outcome_unknown
from polyester.realtime._ws_uri import checked_ws_uri
from polyester.realtime.auth import fetch_subscription_token

SECRETS = (
    "synthetic-location-user",
    "synthetic-location-password",
    "synthetic-location-token",
    "synthetic-location-fragment",
)
_USERINFO = "synthetic-location-user:synthetic-location-password"
_TAIL = "/v1/me?token=synthetic-location-token#synthetic-location-fragment"
MALFORMED_LOCATIONS = {
    "invalid-port": f"http://{_USERINFO}@127.0.0.1:notaport{_TAIL}",
    "invalid-ipv6": f"http://{_USERINFO}@[::1{_TAIL}",
}


class _RawRedirect:
    """Answers every request with ``status`` and ``location``, counting them."""

    def __init__(self, status: int, location: str) -> None:
        self.status, self.location, self.requests = status, location, 0
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(16)
        self.url = f"http://127.0.0.1:{self._sock.getsockname()[1]}"
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                head, _, body = data.partition(b"\r\n\r\n")
                length = 0
                for line in head.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        length = int(line.split(b":", 1)[1])
                while len(body) < length:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    body += chunk
                self.requests += 1
                conn.sendall(
                    f"HTTP/1.1 {self.status} Redirect\r\nLocation: {self.location}\r\n"
                    "Content-Length: 0\r\nConnection: close\r\n\r\n".encode()
                )

    def close(self) -> None:
        self._sock.close()


@pytest.fixture
def raw_redirect() -> Iterator[list[_RawRedirect]]:
    servers: list[_RawRedirect] = []
    yield servers
    for server in servers:
        server.close()


def _rendered(err: BaseException) -> list[str]:
    """Every text ``err`` and the exceptions it chains expose."""
    out: list[str] = []
    seen: set[int] = set()
    pending: list[BaseException | None] = [err]
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        out += [str(current), repr(current), *map(repr, current.args)]
        out.append("".join(traceback.format_exception_only(type(current), current)))
        out += [repr(value) for value in vars(current).values()]
        pending += [current.__cause__, current.__context__]
    return out


def _assert_no_location_secrets(err: BaseException, location: str) -> None:
    for rendered in _rendered(err):
        for secret in (*SECRETS, location):
            assert secret not in rendered, f"error exposes {secret!r}: {rendered}"


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["json", "binary"])
@pytest.mark.parametrize("kind", sorted(MALFORMED_LOCATIONS))
@pytest.mark.parametrize("status", [301, 307, 308])
async def test_signed_malformed_redirect_is_refused_without_location_secrets(
    raw_redirect: list[_RawRedirect], status: int, kind: str, wire_format: str
) -> None:
    location = MALFORMED_LOCATIONS[kind]
    origin = _RawRedirect(status, location)
    raw_redirect.append(origin)
    client = AsyncPolyester(
        api_url=origin.url,
        api_key_id="ak_redirect_test",
        api_private_key=Ed25519PrivateKey.generate().private_bytes_raw().hex(),
        wire_format=wire_format,  # type: ignore[arg-type]
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(PolyesterError) as raised:
            await client.auth.me()
    finally:
        await client.aclose()

    _assert_no_location_secrets(raised.value, location)
    assert origin.requests == 1
    err = raised.value
    assert isinstance(err, PolyesterRedirectError), f"{type(err).__name__}: {err}"
    assert (err.status_code, err.origin, err.same_origin, err.malformed) == (
        status,
        "",
        False,
        True,
    )
    assert "malformed" in str(err)
    assert not is_retryable_error(err)
    assert mutation_outcome_unknown(err)


@pytest.mark.parametrize("kind", sorted(MALFORMED_LOCATIONS))
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_refusal_refuses_a_malformed_location(kind: str, status: int) -> None:
    """The refusal every redirect check shares, the WebSocket handshake's too."""
    location = MALFORMED_LOCATIONS[kind]
    refusal = redirect_refusal(status, location, "https://api.example.test/v1/rt/token")
    assert refusal is not None
    assert (refusal.status_code, refusal.origin, refusal.malformed) == (status, "", True)
    _assert_no_location_secrets(refusal, location)


@pytest.mark.parametrize(
    "url",
    [
        f"ws://{_USERINFO}@127.0.0.1:notaport/connection?token=synthetic-location-token"
        "#synthetic-location-fragment",
        f"ws://{_USERINFO}@[::1/connection?token=synthetic-location-token",
        f"ftp://{_USERINFO}@127.0.0.1/connection?token=synthetic-location-token",
    ],
)
def test_websocket_url_errors_have_no_userinfo_query_or_fragment(url: str) -> None:
    with pytest.raises(InvalidURI) as raised:
        checked_ws_uri(url)
    _assert_no_location_secrets(raised.value, url)


@pytest.mark.asyncio
async def test_token_error_endpoint_has_no_query() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "unauthenticated", "message": "refused"})

    credentials = ApiKeyCredentials(
        key_id="ak_redirect_test", private_key=Ed25519PrivateKey.generate().private_bytes_raw()
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as http:
        with pytest.raises(PolyesterAuthError) as raised:
            await fetch_subscription_token(
                http, credentials, api_url="https://api.example.test", channel="orders:1"
            )
    assert raised.value.endpoint == "https://api.example.test/v1/rt/subscribe"
    assert "?" not in str(raised.value)
    # The label still names the channel.
    assert "orders:1" in str(raised.value)
