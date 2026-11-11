"""A canceled trigger reads ``canceled``, the contract's spelling (``STATUS_CANCELED``),
as its ``canceled`` event and the TypeScript and Rust SDKs do. The British
``cancelled`` is gone from outputs and filters alike: there is one spelling."""

from __future__ import annotations

import pytest

from polyester.codecs.decode.triggers import (
    trigger_event_type_from_label,
    trigger_from_proto,
    trigger_status_from_label,
)
from polyester.codecs.realtime_decode import decode_trigger_bytes
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary


def _canceled() -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(trigger_id=3, symbol_id=1, status=triggers_pb2.STATUS_CANCELED)


def test_canceled_trigger_reads_canceled() -> None:
    assert trigger_from_proto(_canceled()).status == "canceled"
    assert decode_trigger_bytes(_canceled().SerializeToString()).status == "canceled"


def test_status_and_event_filters_take_canceled() -> None:
    assert trigger_status_from_label("canceled") == triggers_pb2.STATUS_CANCELED
    assert trigger_status_from_label(" Canceled ") == triggers_pb2.STATUS_CANCELED
    assert trigger_event_type_from_label("canceled") == triggers_pb2.EVENT_CANCELED


def test_status_filter_refuses_cancelled() -> None:
    with pytest.raises(PolyesterValidationError, match="invalid trigger status 'cancelled'") as err:
        trigger_status_from_label("cancelled")
    assert "canceled" in str(err.value)
    assert "cancelled," not in str(err.value)


def test_event_type_filter_refuses_cancelled() -> None:
    with pytest.raises(PolyesterValidationError, match="invalid trigger event type 'cancelled'"):
        trigger_event_type_from_label("cancelled")


@pytest.mark.asyncio
async def test_list_refuses_cancelled_before_sending() -> None:
    from unittest.mock import MagicMock, patch

    capture = CaptureUnary(triggers_pb2.ListTriggersResponse())
    service = AsyncTriggersService(MagicMock(), MagicMock(), None)
    with (
        patch("polyester.services.triggers.unary_auth_decoded_retry_unavailable", capture),
        pytest.raises(PolyesterValidationError, match="invalid trigger status"),
    ):
        await service.list(status=["armed", "cancelled"])
    assert capture.calls == 0
