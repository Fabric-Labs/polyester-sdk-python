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


def timestamp_window_from_json(value: object) -> ServerTime | None:
    """A REST problem's ``timestampWindow``: ``serverTimeMs`` as a decimal
    string or number, ``recvWindowMs`` and ``maxFutureMs`` as numbers.
    ``None`` when absent or unreadable: the refusal stands without it."""
    if not isinstance(value, dict):
        return None

    def integer(raw: object) -> int | None:
        if isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isascii() and raw.isdigit():
            return int(raw)
        return None

    server = integer(value.get("serverTimeMs"))
    if server is None or server <= 0:
        return None
    return ServerTime(
        server_time_ms=server,
        recv_window_ms=integer(value.get("recvWindowMs")),
        max_future_ms=integer(value.get("maxFutureMs")),
    )
