"""The contract's time-window filters on order history and user trades.

Each bound reaches the request with its presence kept (``None`` stays unset,
an explicit 0 is sent), and a start after a non-zero end is refused with
:class:`PolyesterValidationError` before sending.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.scalars import UINT64_MAX
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.services.orders import AsyncOrdersService
from polyester.services.trades import AsyncTradesService
from tests.unit.support import CaptureUnary

START = 1_700_000_000_000_000_000
END = 1_700_000_003_600_000_000

SENT: list[tuple[int | None, int | None]] = [
    (None, None),
    (START, None),
    (None, END),
    (START, END),
    (START, START),
    (0, None),
    (None, 0),
    # An explicit end of 0 is the contract's empty page, whatever the start.
    (START, 0),
    (UINT64_MAX, 0),
]

REFUSED: list[tuple[int, int]] = [
    (END + 1, END),
    (2, 1),
    (UINT64_MAX, 1),
]


def _history() -> tuple[CaptureUnary, Callable[..., Awaitable[Any]], str, str]:
    capture = CaptureUnary(orders_read_pb2.GetOrderHistoryResponse())
    service = AsyncOrdersService(MagicMock(), MagicMock(), None)
    return capture, service.list_history, "polyester.services.orders", "orders.list_history"


def _trades() -> tuple[CaptureUnary, Callable[..., Awaitable[Any]], str, str]:
    capture = CaptureUnary(orders_read_pb2.GetUserTradesResponse())
    service = AsyncTradesService(MagicMock(), MagicMock(), None)
    return capture, service.list, "polyester.services.trades", "trades.list"


READS = [pytest.param(_history, id="history"), pytest.param(_trades, id="trades")]


def _bound(request: Any, field: str) -> int | None:
    return getattr(request, field) if request.HasField(field) else None


@pytest.mark.asyncio
@pytest.mark.parametrize("read", READS)
@pytest.mark.parametrize(("start", "end"), SENT)
async def test_time_window_is_sent_as_given(read, start: int | None, end: int | None) -> None:
    capture, call, module, _ = read()
    with patch(f"{module}.unary_auth_decoded", capture):
        await call(start_ts_ns=start, end_ts_ns=end)
    assert capture.calls == 1
    assert _bound(capture.request, "start_ts_ns") == start
    assert _bound(capture.request, "end_ts_ns") == end


@pytest.mark.asyncio
@pytest.mark.parametrize("read", READS)
async def test_time_window_defaults_to_unset(read) -> None:
    capture, call, module, _ = read()
    with patch(f"{module}.unary_auth_decoded", capture):
        await call()
    assert not capture.request.HasField("start_ts_ns")
    assert not capture.request.HasField("end_ts_ns")


@pytest.mark.asyncio
@pytest.mark.parametrize("read", READS)
@pytest.mark.parametrize(("start", "end"), REFUSED)
async def test_start_after_a_non_zero_end_is_refused_before_sending(
    read, start: int, end: int
) -> None:
    capture, call, module, label = read()
    with (
        patch(f"{module}.unary_auth_decoded", capture),
        pytest.raises(
            PolyesterValidationError,
            match=rf"^{label} start_ts_ns \({start}\) must be <= end_ts_ns \({end}\)",
        ),
    ):
        await call(start_ts_ns=start, end_ts_ns=end)
    assert capture.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("read", READS)
@pytest.mark.parametrize("field", ["start_ts_ns", "end_ts_ns"])
@pytest.mark.parametrize("value", [-1, UINT64_MAX + 1, True, 1.0, "1"])
async def test_a_bound_outside_the_uint64_field_is_refused_before_sending(
    read, field: str, value: object
) -> None:
    capture, call, module, label = read()
    with (
        patch(f"{module}.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match=rf"^{label} {field} "),
    ):
        await call(**{field: value})
    assert capture.calls == 0
