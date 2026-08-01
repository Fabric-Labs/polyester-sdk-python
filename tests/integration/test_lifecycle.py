import pytest

from polyester.errors import PolyesterServerError
from polyester.models import LifecycleFlowSummary, ZipperReasonDetails
from tests.integration.support import call_optional


@pytest.mark.integration
@pytest.mark.optional
async def test_lifecycle_list_flows(live_client):
    try:
        result = await call_optional(
            live_client.lifecycle.list_flows(limit=5),
            label="lifecycle.list_flows",
        )
    except PolyesterServerError:
        pytest.skip("lifecycle flows response incompatible with current proto on devnet")

    assert isinstance(result.flows, list)
    for flow in result.flows:
        assert isinstance(flow, LifecycleFlowSummary)
        assert flow.intent_id
        assert isinstance(flow.lifecycle_reason, str)
        assert flow.lifecycle_reason
        # Successful/settled flows commonly report unspecified; failed Zipper
        # flows may populate zipper_reason with reason_id/message/code.
        if flow.zipper_reason is not None:
            assert isinstance(flow.zipper_reason, ZipperReasonDetails)
            assert isinstance(flow.zipper_reason.code, int)
            assert isinstance(flow.zipper_reason.reason_id, str)
            assert isinstance(flow.zipper_reason.message, str)
        # Wire FlowReason / reason_code must not leak as public attributes.
        assert not hasattr(flow, "reason_code")
        assert not hasattr(flow, "flow_reason")
