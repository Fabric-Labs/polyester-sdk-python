"""The server time and window a ``TIMESTAMP_SKEW`` refusal names."""

from __future__ import annotations

from polyester.models.system import ServerTime


def timestamp_window_from_proto(msg) -> ServerTime | None:
    """An ``auth.v1.TimestampWindow``, ``None`` when it names no server time."""
    if int(msg.server_time_ms) <= 0:
        return None
    return ServerTime(
        server_time_ms=int(msg.server_time_ms),
        recv_window_ms=int(msg.recv_window_ms),
        max_future_ms=int(msg.max_future_ms),
    )


# The contract's types: ``server_time_ms`` is an int64, the windows uint32.
_INT64_MAX = 2**63 - 1
_UINT32_MAX = 2**32 - 1


def timestamp_window_from_json(value: object) -> ServerTime | None:
    """A REST problem's ``timestampWindow``: ``serverTimeMs`` as a decimal
    string or number (an int64), ``recvWindowMs`` and ``maxFutureMs`` as
    numbers (uint32). ``None`` when absent or unreadable, and a window value
    out of its type's range reads as ``None``: the refusal stands without
    it, with its own status and retry delay."""
    if not isinstance(value, dict):
        return None

    def integer(raw: object, maximum: int) -> int | None:
        # Bounded before any conversion: a digit string longer than the type
        # allows is unreadable, never a conversion error.
        if isinstance(raw, bool):
            return None
        if isinstance(raw, str):
            if not (raw.isascii() and raw.isdigit()) or len(raw) > len(str(maximum)):
                return None
            raw = int(raw)
        if isinstance(raw, int) and 0 <= raw <= maximum:
            return raw
        return None

    server = integer(value.get("serverTimeMs"), _INT64_MAX)
    if server is None or server <= 0:
        return None
    return ServerTime(
        server_time_ms=server,
        recv_window_ms=integer(value.get("recvWindowMs"), _UINT32_MAX),
        max_future_ms=integer(value.get("maxFutureMs"), _UINT32_MAX),
    )
