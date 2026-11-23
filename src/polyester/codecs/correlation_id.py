from __future__ import annotations

from polyester.codecs.pure_bridge import call, pure

CLIENT_ID_MAX_LEN: int = pure._CLIENT_ID_MAX_LEN
REQUEST_ID_MAX_LEN: int = pure._REQUEST_ID_MAX_LEN


def validate_correlation_id(value: str, field: str, max_len: int) -> str:
    return check_correlation_id(value.strip(), field, max_len)


def check_correlation_id(value: str, field: str, max_len: int) -> str:
    """Check ``value`` as given, untrimmed: 1 to ``max_len`` ASCII letters,
    digits, ``.``, ``_``, ``:``, ``/`` or ``-``, the client order ID rule."""
    return call(pure._check_correlation_id, value, field, max_len)


def optional_client_id(value: str | None, field: str = "client_order_id") -> str | None:
    return call(pure._optional_client_id, value, field)


def required_client_id(value: str, field: str) -> str:
    return call(pure._required_client_id, value, field)


def optional_request_id(value: str | None) -> str | None:
    return call(pure._optional_request_id, value)
