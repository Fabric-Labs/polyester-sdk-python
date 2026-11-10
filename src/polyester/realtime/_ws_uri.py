"""Check a WebSocket URL without letting websockets quote its userinfo."""

from __future__ import annotations

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus, InvalidURI
from websockets.uri import parse_uri

from polyester._redact import url_without_userinfo
from polyester._redirects import redirect_refusal


def checked_ws_uri(url: str) -> str:
    """Return ``url`` when websockets accepts it.

    Otherwise raise websockets' ``InvalidURI`` naming the URL without its
    userinfo: websockets' own error quotes the whole URL, password included.
    """
    try:
        parse_uri(url)
    except InvalidURI as exc:
        reason = exc.msg
    else:
        return url
    raise InvalidURI(url_without_userinfo(url), reason)


class connect_without_redirects(connect):  # noqa: N801 - used as websockets' connect
    """``websockets.connect`` that never follows a handshake redirect.

    A private connection sends its realtime token once the handshake succeeds,
    so following a redirect would hand the token to the redirect target. A
    redirect raises :class:`~polyester.errors.PolyesterRedirectError` instead.
    """

    def process_redirect(self, exc: Exception) -> Exception | str:
        if isinstance(exc, InvalidStatus):
            response = exc.response
            refusal = redirect_refusal(
                response.status_code, response.headers.get("Location"), self.uri
            )
            if refusal is not None:
                return refusal
        return exc
