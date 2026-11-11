"""Remove credentials from URLs the SDK prints, sends or puts in errors."""

from __future__ import annotations

import contextlib
import dataclasses
import inspect
import os
import threading
from urllib.parse import unquote, urlsplit, urlunsplit

import msgspec

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
PROXY_PLACEHOLDER = "[proxy]"
SECRET_PLACEHOLDER = "[REDACTED]"
# A client-held secret shorter than this is too common to replace in text.
_MIN_SECRET_LENGTH = 4
_known_secrets: set[str] = set()
_known_secrets_lock = threading.Lock()


def register_secret(secret: str) -> None:
    """Remember a client-held secret so :func:`redact_text` removes it anywhere."""
    if len(secret) >= _MIN_SECRET_LENGTH:
        with _known_secrets_lock:
            _known_secrets.add(secret)


def register_url_secrets(url: str) -> None:
    """Remember the userinfo of a URL the client holds, and its password.

    Both, raw and decoded, are removed wherever they appear in error text,
    however the URL around them was quoted or mangled.
    """
    netloc = url.partition("://")[2].split("/", 1)[0]
    userinfo, at, _host = netloc.rpartition("@")
    if not at or not userinfo:
        return
    # The exact userinfo and the password: a user name alone is not secret
    # and too common to replace in text.
    password = userinfo.partition(":")[2]
    for part in (userinfo, password):
        register_secret(part)
        register_secret(unquote(part))


def _secrets_in_effect() -> list[str]:
    """The registered secrets and the userinfo of the proxies the environment sets."""
    with _known_secrets_lock:
        secrets = set(_known_secrets)
    for name in _PROXY_ENV:
        proxy = (os.environ.get(name) or "").strip()
        netloc = proxy.partition("://")[2].split("/", 1)[0]
        userinfo, at, _host = netloc.rpartition("@")
        if at and userinfo:
            password = userinfo.partition(":")[2]
            secrets.update(part for part in (userinfo, password) if len(part) >= _MIN_SECRET_LENGTH)
    return sorted(secrets, key=len, reverse=True)


# How deep redaction follows containers and models held by an exception.
_MAX_DEPTH = 6


def redact_text(text: str) -> str:
    """Return ``text`` with every URL in it reduced as :func:`url_for_error` does.

    For messages that quote an answer's or a transport's own words, where a
    URL's userinfo or query may hold any character, parentheses and quotes
    included: after each ``://``, up to the next whitespace, everything up to
    the last ``@`` (the userinfo, whatever it holds) and everything from the
    next ``?`` or ``#`` on (the query and fragment) is dropped. A proxy
    URL from the environment becomes ``[proxy]``, a URL the old parser would
    refuse becomes ``[REDACTED INVALID URL]``, and every client-held secret
    (see :func:`register_url_secrets` and :func:`register_secret`) and the
    userinfo of the environment's proxies become ``[REDACTED]``.
    """
    for name in _PROXY_ENV:
        proxy = (os.environ.get(name) or "").strip()
        if not proxy:
            continue
        forms = {proxy, proxy.rstrip("/"), url_without_userinfo(proxy)}
        for form in sorted(forms, key=len, reverse=True):
            if form and form != INVALID_URL:
                text = text.replace(form, PROXY_PLACEHOLDER)
    out: list[str] = []
    position = 0
    while (separator := text.find("://", position)) != -1:
        start = separator + 3
        end = start
        while end < len(text) and not text[end].isspace():
            end += 1
        token = text[start:end]
        scheme = separator
        while scheme > position and (text[scheme - 1].isalnum() or text[scheme - 1] in "+.-"):
            scheme -= 1
        if url_for_error(text[scheme:end]) == INVALID_URL:
            # At least what the URL parser refuses stays refused: a URL that
            # does not parse is dropped whole.
            out.append(text[position:scheme])
            out.append(INVALID_URL)
            position = end
            continue
        # Fail closed: the last "@" anywhere ends a userinfo, even one that
        # holds "?" or "#", or a URL that does not parse.
        at = token.rfind("@")
        if at != -1:
            token = token[at + 1 :]
        cut = min((i for i in (token.find("?"), token.find("#")) if i != -1), default=len(token))
        out.append(text[position:start])
        out.append(token[:cut])
        position = end
    out.append(text[position:])
    # URLs first, so a registered secret inside one can't make it unparsable.
    text = "".join(out)
    for secret in _secrets_in_effect():
        text = text.replace(secret, SECRET_PLACEHOLDER)
    return text


def _redacted(value: object, depth: int = 0) -> object:
    """``value`` with every string it holds passed through :func:`redact_text`.

    Strings, lists, tuples, dicts, dataclasses and msgspec structs are copied
    redacted; anything else, or anything deeper than ``_MAX_DEPTH``, is kept.
    """
    if isinstance(value, str):
        return redact_text(value)
    if depth >= _MAX_DEPTH:
        return value
    if isinstance(value, list):
        return [_redacted(item, depth + 1) for item in value]
    if isinstance(value, tuple) and not hasattr(value, "_fields"):
        return tuple(_redacted(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return {key: _redacted(item, depth + 1) for key, item in value.items()}
    if isinstance(value, msgspec.Struct):
        with contextlib.suppress(Exception):
            return msgspec.structs.replace(
                value,
                **{
                    name: _redacted(getattr(value, name), depth + 1)
                    for name in value.__struct_fields__
                },
            )
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        with contextlib.suppress(Exception):
            return dataclasses.replace(
                value,
                **{
                    field.name: _redacted(getattr(value, field.name), depth + 1)
                    for field in dataclasses.fields(value)
                    if field.init
                },
            )
        return value
    return value


def redact_exception_chain(error: BaseException) -> None:
    """Redact, in place, what every exception in ``error``'s chain prints.

    Each exception keeps its class, its ``__cause__`` and its ``__context__``.
    Its ``args``, its notes, the string fields the exception type defines in
    C (such as ``OSError.strerror`` and ``filename``) and every attribute it
    holds, structured diagnostics included, are redacted, so ``str``,
    ``repr``, ``traceback.format_exception`` and those attributes print no
    credential.
    """
    seen: set[int] = set()
    pending: list[BaseException | None] = [error]
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        for cls in type(current).__mro__:
            for name, member in vars(cls).items():
                if name.startswith("__") or not (
                    inspect.isgetsetdescriptor(member) or inspect.ismemberdescriptor(member)
                ):
                    continue
                with contextlib.suppress(Exception):
                    value = getattr(current, name)
                    if isinstance(value, str):
                        setattr(current, name, redact_text(value))
        with contextlib.suppress(AttributeError, TypeError):
            current.args = tuple(_redacted(arg) for arg in current.args)
        notes = getattr(current, "__notes__", None)
        if isinstance(notes, list):
            notes[:] = [_redacted(note) for note in notes]
        for name, value in list(getattr(current, "__dict__", {}).items()):
            if isinstance(value, BaseException):
                continue
            redacted = _redacted(value)
            if redacted is not value:
                with contextlib.suppress(AttributeError, TypeError):
                    setattr(current, name, redacted)
        pending.extend((current.__cause__, current.__context__))
