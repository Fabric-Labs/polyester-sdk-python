"""Remove credentials from URLs the SDK prints, sends or puts in errors."""

from __future__ import annotations

import contextlib
import os
import re
from urllib.parse import urlsplit, urlunsplit

INVALID_URL = "[REDACTED INVALID URL]"


def url_without_userinfo(url: str) -> str:
    """Return ``url`` without its userinfo (user name and password).

    A URL that does not parse, or has an ``@`` but no authority (such as
    ``https:user:password@host``), becomes ``[REDACTED INVALID URL]``, since
    its userinfo cannot be told apart from the rest of it.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return INVALID_URL
    if "@" not in parts.netloc:
        return INVALID_URL if not parts.netloc and "@" in url else url
    host = parts.netloc.rpartition("@")[2]
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def url_for_error(url: str) -> str:
    """Return ``url`` as an error may name it: scheme, host, port and path.

    Its userinfo, query and fragment are dropped, as any of them can carry a
    credential. A URL that does not parse, or has an ``@`` but no authority,
    becomes ``[REDACTED INVALID URL]``.
    """
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError for a port that is not a number
    except ValueError:
        return INVALID_URL
    if not parts.netloc and "@" in url:
        return INVALID_URL
    host = parts.netloc.rpartition("@")[2]
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


# The proxy settings pyqwest (reqwest) and httpx read from the environment.
_PROXY_ENV = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
# A URL inside free text: up to whitespace, a quote, an angle bracket or a parenthesis.
_URL_IN_TEXT = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>()]+")
PROXY_PLACEHOLDER = "[proxy]"


def redact_text(text: str) -> str:
    """Return ``text`` with every URL in it as :func:`url_for_error` names it.

    For messages that quote an answer's or a transport's own words: a proxy
    URL from the environment becomes ``[proxy]``, and any other URL loses its
    userinfo, query and fragment.
    """
    for name in _PROXY_ENV:
        proxy = (os.environ.get(name) or "").strip()
        if not proxy:
            continue
        forms = {proxy, proxy.rstrip("/"), url_without_userinfo(proxy)}
        for form in sorted(forms, key=len, reverse=True):
            if form and form != INVALID_URL:
                text = text.replace(form, PROXY_PLACEHOLDER)
    return _URL_IN_TEXT.sub(lambda match: url_for_error(match.group(0)), text)


def redact_exception_chain(error: BaseException) -> None:
    """Redact, in place, what every exception in ``error``'s chain prints.

    Each exception keeps its class, its ``__cause__`` and its ``__context__``;
    its ``args`` and its string attributes (such as a ``ConnectError``'s
    message or a gateway problem's ``detail``) pass through
    :func:`redact_text`, so ``str``, ``repr`` and
    ``traceback.format_exception`` print no credential.
    """
    seen: set[int] = set()
    pending: list[BaseException | None] = [error]
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        with contextlib.suppress(AttributeError, TypeError):
            current.args = tuple(
                redact_text(arg) if isinstance(arg, str) else arg for arg in current.args
            )
        for name, value in list(getattr(current, "__dict__", {}).items()):
            if isinstance(value, str):
                with contextlib.suppress(AttributeError, TypeError):
                    setattr(current, name, redact_text(value))
        pending.extend((current.__cause__, current.__context__))
