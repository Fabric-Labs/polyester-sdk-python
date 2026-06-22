from polyester.codecs.wire_decode import decode_lifecycle_flow


def test_decode_lifecycle_flow_from_detail_summary() -> None:
    flow = decode_lifecycle_flow(
        {
            "summary": {
                "intentId": "intent-abc",
                "flowKind": "DEPOSIT",
                "latestStep": "CONFIRMED",
                "isOpen": False,
                "isTerminal": True,
            },
            "steps": [],
        }
    )
    assert flow.intent_id == "intent-abc"
    assert flow.flow_kind == "DEPOSIT"
    assert flow.latest_step == "CONFIRMED"
    assert flow.is_terminal is True


def test_decode_lifecycle_flow_from_list_item() -> None:
    flow = decode_lifecycle_flow(
        {
            "intentId": "intent-xyz",
            "latestStep": "PENDING",
            "isOpen": True,
        }
    )
    assert flow.intent_id == "intent-xyz"
    assert flow.latest_step == "PENDING"
    assert flow.is_open is True
