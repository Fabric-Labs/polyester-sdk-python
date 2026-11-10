"""Remove credentials from URLs the SDK prints, sends or puts in errors."""

from __future__ import annotations

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


# The proxy settings pyqwest (reqwest) and httpx read from the environment.
_PROXY_ENV = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
_URL_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^\s/@]+@")
PROXY_PLACEHOLDER = "[proxy]"


def redact_text(text: str) -> str:
    """Return ``text`` without URL userinfo and without the configured proxy URLs.

    For error messages that quote a transport's own words: a proxy URL from
    the environment, with or without credentials, becomes ``[proxy]``, and any
    other URL loses its user name and password.
    """
    for name in _PROXY_ENV:
        proxy = (os.environ.get(name) or "").strip()
        if not proxy:
            continue
        forms = {proxy, proxy.rstrip("/"), url_without_userinfo(proxy)}
        for form in sorted(forms, key=len, reverse=True):
            if form and form != INVALID_URL:
                text = text.replace(form, PROXY_PLACEHOLDER)
    return _URL_USERINFO.sub(r"\g<scheme>", text)
