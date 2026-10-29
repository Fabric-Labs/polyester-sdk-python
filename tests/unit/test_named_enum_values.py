"""Newly published enum values decode to their names, never a numeric fallback."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error, protobuf_to_public_dict
from polyester.codecs.decode.lifecycle import flow_summary_from_proto
from polyester.codecs.decode.orders import preview_order_from_proto
from polyester.codecs.decode.triggers import trigger_events_list_from_proto, trigger_from_proto
from polyester.errors import PolyesterApiError
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2


def test_deposit_source_not_confirmed_lifecycle_reason() -> None:
    flow = flow_summary_from_proto(
        lifecycle_read_pb2.FlowSummaryView(
            flow_id="flow-deposit",
            flow_kind=types_pb2.KIND_DEPOSIT,
            lifecycle_reason=types_pb2.DEPOSIT_SOURCE_NOT_CONFIRMED,
        )
    )
    assert flow.lifecycle_reason == "deposit_source_not_confirmed"


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (triggers_pb2.TRIGGER_CANCEL_REASON_ACCOUNT_REPAIR, "account_repair"),
        (triggers_pb2.TRIGGER_CANCEL_REASON_PAIR_DRAIN_TRIGGER, "pair_drain_trigger"),
        (triggers_pb2.TRIGGER_CANCEL_REASON_PAIR_DRAIN_TWAP, "pair_drain_twap"),
        (triggers_pb2.TRIGGER_CANCEL_REASON_PAIR_DRAIN_LADDER, "pair_drain_ladder"),
        (
            triggers_pb2.TRIGGER_CANCEL_REASON_PAIR_DRAIN_ATTACHED_LEG,
            "pair_drain_attached_leg",
        ),
    ],
)
def test_trigger_cancel_reasons(reason: int, expected: str) -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=1, status=triggers_pb2.STATUS_CANCELED, cancel_reason=reason
        )
    )
    assert trigger.cancel_reason == expected
    event = trigger_events_list_from_proto(
        triggers_pb2.ListTriggerEventsResponse(
            events=[
                triggers_pb2.TriggerEvent(
                    trigger_id=1, event_type=triggers_pb2.EVENT_CANCELED, cancel_reason=reason
                )
            ]
        )
    ).events[0]
    assert event.cancel_reason == expected


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            triggers_pb2.TRIGGER_FAILURE_REASON_INDEX_PRICE_UNAVAILABLE,
            "index_price_unavailable",
        ),
        (
            triggers_pb2.TRIGGER_FAILURE_REASON_TRIGGER_WOULD_TRIGGER_IMMEDIATELY,
            "trigger_would_trigger_immediately",
        ),
    ],
)
def test_trigger_failure_reasons(reason: int, expected: str) -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(trigger_id=1, status=triggers_pb2.STATUS_FAILED, failure_reason=reason)
    )
    assert trigger.failure_reason == expected
    event = trigger_events_list_from_proto(
        triggers_pb2.ListTriggerEventsResponse(
            events=[
                triggers_pb2.TriggerEvent(
                    trigger_id=1, event_type=triggers_pb2.EVENT_FAILED, failure_reason=reason
                )
            ]
        )
    ).events[0]
    assert event.failure_reason == expected


@pytest.mark.parametrize(
    "code",
    [
        "ERROR_CODE_TRIGGER_WOULD_TRIGGER_IMMEDIATELY",
        "ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN",
        "ERROR_CODE_TRIGGER_CREATE_OUTCOME_UNKNOWN",
    ],
)
def test_order_error_codes(code: str) -> None:
    value = orders_pb2.ErrorCode.Value(code)
    mapped = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION, "refused", details=[orders_pb2.ErrorDetail(code=value)]
        )
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == code
    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            admissible=False,
            rejection=orders_pb2.ErrorDetail(code=value),
            evaluated_at={"seconds": 1},
        )
    )
    assert preview.rejection is not None
    assert preview.rejection.code == code.removeprefix("ERROR_CODE_")


def test_auth_temporarily_unavailable_code() -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.UNAVAILABLE,
            "try again",
            details=[auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TEMPORARILY_UNAVAILABLE)],
        )
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == "AUTH_TEMPORARILY_UNAVAILABLE"


def test_halted_pair_status_in_spot_config() -> None:
    raw = protobuf_to_public_dict(
        marketdata_pb2.GetSpotConfigResponse(
            pairs=[marketdata_pb2.PairConfig(symbol_id=1, status=marketdata_pb2.PAIR_STATUS_HALTED)]
        )
    )
    assert raw["pairs"][0]["status"] == "PAIR_STATUS_HALTED"
