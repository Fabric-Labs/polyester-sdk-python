"""Check a WebSocket URL without letting websockets quote its userinfo."""

from __future__ import annotations

from websockets.exceptions import InvalidURI
from websockets.uri import parse_uri

from polyester._redact import url_without_userinfo


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
