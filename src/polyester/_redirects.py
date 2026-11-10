"""Signed requests never follow a redirect.

A redirect of a request signed with an API key would carry its key ID,
timestamp and signature to the redirect target, which could replay it within
its receive window. The signature covers the path, so a same-origin redirect to
another path could not verify either. Every redirect of a signed request is
refused with :class:`~polyester.errors.PolyesterRedirectError`, and so is one
whose ``Location`` does not parse, without repeating it.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from polyester.errors import PolyesterRedirectError

REDIRECT_STATUSES = frozenset({300, 301, 302, 303, 307, 308})
_API_KEY_HEADERS = frozenset({"x-api-key-id", "x-api-timestamp", "x-api-signature"})
_DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443}


def carries_api_key(headers: Any) -> bool:
    """Whether ``headers`` carry any API-key header.

    ``headers`` is anything with ``items()``, such as a ``dict`` or the
    ``pyqwest.Headers`` connectrpc sends, or an iterable of name-value pairs.
    """
    if headers is None:
        return False
    items = headers.items() if hasattr(headers, "items") else headers
    return any(str(name).lower() in _API_KEY_HEADERS and value for name, value in items)


def _origin(url: str) -> tuple[str, str]:
    """The origin of ``url`` to show, without userinfo, and to compare."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    shown = f"{scheme}://{host}" + (f":{parts.port}" if parts.port is not None else "")
    port = parts.port if parts.port is not None else _DEFAULT_PORTS.get(scheme)
    return shown, f"{scheme}://{host}:{port}"


def redirect_refusal(
    status: int, location: str | None, request_url: str
) -> PolyesterRedirectError | None:
    """The refusal of a redirect answering a signed request to ``request_url``.

    ``None`` when the answer is no redirect: not a redirect status, or no
    ``Location`` to follow.
    """
    if status not in REDIRECT_STATUSES or not location:
        return None
    try:
        shown, target = _origin(urljoin(request_url, location))
    except ValueError:
        # A Location that does not parse, such as one with a port that is not
        # a number, cannot be followed; the refusal never repeats it.
        return PolyesterRedirectError(
            status_code=status, origin="", same_origin=False, malformed=True
        )
    return PolyesterRedirectError(
        status_code=status, origin=shown, same_origin=target == _origin(request_url)[1]
    )
