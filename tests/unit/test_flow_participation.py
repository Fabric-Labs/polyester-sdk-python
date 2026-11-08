"""An account's flow list carries received transfers, each row says how the
account takes part, and the participation filter narrows it (contract c8d9827)."""

from __future__ import annotations

import pytest
from pytest_httpserver import HTTPServer

from polyester import PolyesterValidationError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2
from polyester.services.lifecycle import AsyncLifecycleService
from polyester.transport import TransportConfig, TransportFactory

_PATH = "/chain.lifecycle.v1.LifecycleReadService/ListFlows"
_SELF = "0x00000000000000000000000000000000000000a1"


def _response() -> bytes:
    lr = lifecycle_read_pb2
    return lr.ListFlowsResponse(
        flows=[
            lr.FlowSummaryView(
                flow_id="sent",
                flow_kind=types_pb2.KIND_TRANSFER,
                owner_account_id=7,
                participation=lr.PARTICIPATION_OWNER,
                source_address=_SELF,
                destination_address="0x00000000000000000000000000000000000000b2",
            ),
            lr.FlowSummaryView(
                flow_id="received",
                flow_kind=types_pb2.KIND_TRANSFER,
                owner_account_id=9,
                participation=lr.PARTICIPATION_RECIPIENT,
                source_address="0x00000000000000000000000000000000000000c3",
                destination_address=_SELF,
            ),
            lr.FlowSummaryView(flow_id="future", participation=9),
        ]
    ).SerializeToString()


async def _list(httpserver: HTTPServer, **kwargs):
    httpserver.expect_request(_PATH, method="POST").respond_with_data(
        _response(), content_type="application/proto", headers={"Connect-Protocol-Version": "1"}
    )
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        page = await AsyncLifecycleService(transport).list_flows(**kwargs)
    finally:
        await transport.aclose()
    captured, _ = httpserver.log[-1]
    sent = lifecycle_read_pb2.ListFlowsRequest.FromString(captured.data)
    return page, sent


async def test_rows_carry_participation_and_counterparty_addresses(httpserver: HTTPServer) -> None:
    page, sent = await _list(httpserver, owner_account_id="8", limit=10)
    assert sent.participation == lifecycle_read_pb2.PARTICIPATION_UNSPECIFIED
    sent_row, received, future = page.flows
    assert sent_row.participation == "owner"
    assert sent_row.destination_address == "0x00000000000000000000000000000000000000b2"
    assert received.participation == "recipient"
    assert received.source_address == "0x00000000000000000000000000000000000000c3"
    assert future.participation == "unknown_participation_9"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("owner", lifecycle_read_pb2.PARTICIPATION_OWNER),
        ("RECIPIENT", lifecycle_read_pb2.PARTICIPATION_RECIPIENT),
        ("PARTICIPATION_RECIPIENT", lifecycle_read_pb2.PARTICIPATION_RECIPIENT),
        ("", lifecycle_read_pb2.PARTICIPATION_UNSPECIFIED),
        (None, lifecycle_read_pb2.PARTICIPATION_UNSPECIFIED),
    ],
)
async def test_participation_filter_is_sent(
    httpserver: HTTPServer, label: str | None, expected: int
) -> None:
    _, sent = await _list(httpserver, owner_account_id="8", participation=label)
    assert sent.participation == expected
    assert sent.owner_account_id != 0


async def test_unknown_participation_is_refused_before_sending(httpserver: HTTPServer) -> None:
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        with pytest.raises(PolyesterValidationError):
            await AsyncLifecycleService(transport).list_flows(
                owner_account_id="8", participation="sender"
            )
    finally:
        await transport.aclose()
    assert len(httpserver.log) == 0
