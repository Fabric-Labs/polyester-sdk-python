import json
from datetime import UTC, datetime

import pytest
from google.protobuf.json_format import MessageToDict, ParseDict

from polyester import AsyncPolyester
from polyester.gen.marketdata.v1 import heatmap_pb2 as heatmap
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)


@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("explicit_range", [False, True])
async def test_heatmap_continuation_retains_filters_without_inventing_window(
    json_wire, explicit_range
):
    seen = []
    token = "eyJoZWF0bWFwIjoxfQ=="

    async def handler(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/GetOrderbookHeatmap")
        message = (
            ParseDict(json.loads(req.body), heatmap.GetOrderbookHeatmapRequest())
            if json_wire
            else heatmap.GetOrderbookHeatmapRequest.FromString(req.body)
        )
        seen.append(message)
        response = heatmap.GetOrderbookHeatmapResponse(
            symbol_id=1,
            next_page_token=token if len(seen) == 1 else "",
            last_persisted_ts_sec=100,
        )
        return (
            HttpScript.json(200, MessageToDict(response))
            if json_wire
            else connect_proto_response(response.SerializeToString())
        )

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url, hydrate_catalogs=False, wire_format="json" if json_wire else "binary"
    )
    kwargs = {"symbol_id": 1, "interval": "1m", "depth": 50, "limit": 1, "quantity_mode": "peak"}
    if explicit_range:
        kwargs.update(
            start_time=datetime.fromtimestamp(100, UTC), end_time=datetime.fromtimestamp(400, UTC)
        )
    try:
        first = await client.heatmap.get(**kwargs)
        assert first.raw["nextPageToken"] == token
        second = await client.heatmap.get(**kwargs, page_token=first.raw["nextPageToken"])
        assert second.raw.get("nextPageToken", "") == ""
        assert len(seen) == 2
        assert seen[0].page_token == "" and seen[1].page_token == token
        assert seen[0].HasField("time_range")
        if explicit_range:
            assert seen[1].time_range == seen[0].time_range
        else:
            assert not seen[1].HasField("time_range")
        seen[0].ClearField("time_range")
        seen[1].ClearField("time_range")
        seen[1].page_token = ""
        assert seen[0] == seen[1]
        assert seen[0].symbol_id == 1 and seen[0].limit == 1
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("bound", ["from_ts_sec", "start_time", "end_time"])
async def test_heatmap_token_with_partial_range_does_not_add_current_time(bound):
    seen = []

    async def handler(req: ParsedRequest) -> HttpScript:
        seen.append(heatmap.GetOrderbookHeatmapRequest.FromString(req.body))
        return connect_proto_response(heatmap.GetOrderbookHeatmapResponse().SerializeToString())

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    value = 100 if bound == "from_ts_sec" else datetime.fromtimestamp(100, UTC)
    try:
        await client.heatmap.get(symbol_id=1, page_token="opaque", **{bound: value})
        assert len(seen) == 1
        tr = seen[0].time_range
        assert tr.HasField("start_time") == (bound != "end_time")
        assert tr.HasField("end_time") == (bound == "end_time")
        assert (tr.end_time if bound == "end_time" else tr.start_time).seconds == 100
    finally:
        await client.aclose()
        await http.aclose()
