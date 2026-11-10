"""Remove credentials from URLs the SDK prints, sends or puts in errors."""

from __future__ import annotations

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
