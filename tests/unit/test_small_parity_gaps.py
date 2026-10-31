"""Smaller TS-parity rows: typed timeouts, trailing threshold, mark source, uint64 cursor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester import (
    PolyesterTimeoutError,
    PolyesterTransportError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester._wire import map_connect_error
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.orders import risk_policy_from_dict
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.trades import AsyncTradesService


def test_deadline_exceeded_is_a_typed_retryable_timeout_with_unknown_outcome() -> None:
    mapped = map_connect_error(ConnectError(Code.DEADLINE_EXCEEDED, "Request timed out"))

    assert isinstance(mapped, PolyesterTimeoutError)
    assert isinstance(mapped, PolyesterTransportError)
    assert is_retryable_error(mapped)
    assert mutation_outcome_unknown(mapped)


def test_trailing_runtime_details_expose_the_current_threshold() -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=9,
            symbol_id=1,
            status=triggers_pb2.STATUS_ARMED,
            trailing_stop=triggers_pb2.TrailingStopTrigger(
                side=orders_pb2.SELL, trailing_distance_bps=100
            ),
            trailing=triggers_pb2.TrailingDetails(
                trailing_distance_bps=100,
                peak_price_ticks=101_000_000_000,
                trigger_price_ticks=99_990_000_000,
            ),
        )
    )

    assert trigger.details is not None and trigger.details.trailing is not None
    threshold = trigger.details.trailing.trigger_price
    assert threshold is not None and threshold.ticks == 99_990_000_000


@pytest.mark.parametrize("source", ["mark", "MARK_PRICE"])
def test_spot_triggers_reject_the_mark_price_source(source: str) -> None:
    with pytest.raises(PolyesterValidationError, match="mark is not supported on spot"):
        create_trigger_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            trigger_type="stop_loss",
            side="sell",
            qty="0.1",
            trigger_price="100",
            trigger_price_source=source,
            quantity_scale=8,
        )
    with pytest.raises(PolyesterValidationError, match="mark is not supported on spot"):
        risk_policy_from_dict(
            {"stop_loss": {"trigger_price": "100", "trigger_price_source": source}}
        )


@pytest.mark.asyncio
async def test_trades_list_rejects_an_after_match_id_beyond_uint64_before_sending() -> None:
    service = AsyncTradesService(MagicMock(), MagicMock(), None)

    with pytest.raises(PolyesterValidationError, match="positive uint64 match id"):
        await service.list(symbol_id=1, after_match_id=2**64)
