from polyester.codecs.wire_decode import decode_lifecycle_flow
from polyester.gen.chain.lifecycle.v1 import types_pb2


def test_decode_lifecycle_flow_from_detail_summary() -> None:
    flow = decode_lifecycle_flow(
        {
            "summary": {
                "intentId": "intent-abc",
                "flowKind": "KIND_DEPOSIT",
                "latestStep": "FLOW_STEP_SETTLEMENT",
                "isOpen": False,
                "isTerminal": True,
            },
            "steps": [],
        }
    )
    assert flow.intent_id == "intent-abc"
    assert flow.flow_kind == "deposit"
    assert flow.latest_step == "settlement"
    assert flow.is_terminal is True
    assert flow.lifecycle_reason == "unspecified"
    assert flow.zipper_reason is None


def test_decode_lifecycle_flow_from_list_item() -> None:
    flow = decode_lifecycle_flow(
        {
            "intentId": "intent-xyz",
            "latestStep": "FLOW_STEP_REQUEST",
            "isOpen": True,
        }
    )
    assert flow.intent_id == "intent-xyz"
    assert flow.latest_step == "request"
    assert flow.is_open is True


def test_decode_lifecycle_flow_accepts_normalized_snake_labels() -> None:
    flow = decode_lifecycle_flow(
        {
            "flowId": "flow-snake",
            "flowKind": "withdraw",
            "currentStep": "validation",
        }
    )
    assert flow.intent_id == "flow-snake"
    assert flow.flow_kind == "withdraw"
    assert flow.latest_step == "validation"


def test_decode_lifecycle_flow_surfaces_reasons() -> None:
    flow = decode_lifecycle_flow(
        {
            "flowId": "flow-1",
            "lifecycleReason": int(types_pb2.ZIPPER_EXECUTION_REJECTED),
            "zipperReason": {
                "code": 1003,
                "reasonId": "deposit_amount_below_minimum",
                "message": "too small",
            },
        }
    )
    assert flow.lifecycle_reason == "zipper_execution_rejected"
    assert flow.zipper_reason is not None
    assert flow.zipper_reason.code == 1003
    assert flow.zipper_reason.reason_id == "deposit_amount_below_minimum"
    assert flow.zipper_reason.message == "too small"


def test_decode_lifecycle_flow_accepts_symbolic_zipper_reason_code() -> None:
    flow = decode_lifecycle_flow(
        {
            "flowId": "flow-symbolic",
            "zipperReason": {
                "code": "DEPOSIT_AMOUNT_BELOW_MINIMUM",
                "reasonId": "deposit_amount_below_minimum",
                "message": "too small",
            },
        }
    )
    assert flow.zipper_reason is not None
    assert flow.zipper_reason.code == 1003


def test_decode_lifecycle_flow_unknown_reason_code() -> None:
    flow = decode_lifecycle_flow({"intentId": "x", "lifecycleReason": 2001})
    assert flow.lifecycle_reason == "unknown_reason_2001"
