from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
import websockets

from polyester import AsyncPolyester
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import heatmap_pb2 as heatmap
from polyester.realtime.client import AsyncRealtimeClient
from polyester.services.heatmap import AsyncHeatmapService
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)

PUBLISHED = {
    "public:spot:market:heatmap:1s:1:proto": heatmap.INTERVAL_1S,
    "public:spot:market:heatmap:1m:1:proto": heatmap.INTERVAL_1M,
    "public:spot:market:heatmap:5m:1:proto": heatmap.INTERVAL_5M,
    "public:spot:market:heatmap:1h:1:proto": heatmap.INTERVAL_1H,
}


def _publication(data: bytes) -> bytes:
    assert len(data) < 120
    return bytes([len(data) + 6, 34, len(data) + 4, 34, len(data) + 2, 34, len(data)]) + data


@pytest.mark.parametrize(
    ("interval", "want"),
    [
        ("1s", heatmap.INTERVAL_1S),
        ("1m", heatmap.INTERVAL_1M),
        ("5m", heatmap.INTERVAL_5M),
        ("1h", heatmap.INTERVAL_1H),
        ("INTERVAL_1S", heatmap.INTERVAL_1S),
        ("interval_5m", heatmap.INTERVAL_5M),
    ],
)
async def test_subscribe_live_receives_buckets_published_for_every_interval(interval, want):
    # The server acknowledges a subscribe to any channel but publishes only on
    # public:spot:market:heatmap:<1s|1m|5m|1h>:<symbol_id>:proto.
    subscribed: list[str] = []

    async def handler(ws):
        await ws.recv()
        await ws.send(bytes.fromhex("020801"))
        command = await ws.recv()
        start = command.index(b"public:")
        channel = command[start : start + command[start - 1]].decode()
        subscribed.append(channel)
        await ws.send(bytes.fromhex("020802"))
        if channel in PUBLISHED:
            bucket = heatmap.HeatmapLiveBucket(
                symbol_id=1, interval=PUBLISHED[channel], ts_sec=1_700_000_000, updates_in_bucket=3
            )
            await ws.send(_publication(bucket.SerializeToString()))
        await ws.wait_closed()

    async with websockets.serve(
        handler, "127.0.0.1", 0, subprotocols=["centrifuge-protobuf"]
    ) as server:
        port = server.sockets[0].getsockname()[1]
        rt = AsyncRealtimeClient(f"ws://127.0.0.1:{port}")
        service = AsyncHeatmapService(None, realtime=rt)
        sub = await service.subscribe_live(symbol_id=1, interval=interval)
        try:
            bucket = await asyncio.wait_for(sub.__anext__(), timeout=3)
        except TimeoutError:
            pytest.fail(f"no live bucket within 3s; subscribed {subscribed}")
        finally:
            await sub.aclose()
            await rt.aclose()
    assert bucket.raw["interval"] == heatmap.HeatmapInterval.Name(want)


@pytest.mark.parametrize("interval", ["", "2m", "PEAK", "close", "INTERVAL_UNSPECIFIED"])
async def test_subscribe_live_refuses_intervals_the_server_does_not_publish(interval):
    service = AsyncHeatmapService(None, realtime=None)
    with pytest.raises(PolyesterValidationError, match="heatmap interval"):
        await service.subscribe_live(symbol_id=1, interval=interval)


class _Capture:
    def __init__(self) -> None:
        self.requests: list[heatmap.GetOrderbookHeatmapRequest] = []

    async def handler(self, req: ParsedRequest) -> HttpScript:
        message = heatmap.GetOrderbookHeatmapRequest.FromString(req.body)
        self.requests.append(message)
        response = heatmap.GetOrderbookHeatmapResponse(
            symbol_id=1,
            depth=message.depth,
            next_page_token="next" if len(self.requests) == 1 else "",
        )
        return connect_proto_response(response.SerializeToString())


async def _with_client(run):
    capture = _Capture()
    http = await MockHttpServer.spawn(capture.handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    try:
        await run(client)
    finally:
        await client.aclose()
        await http.aclose()
    return capture.requests


@pytest.mark.parametrize(
    ("interval", "quantity_mode"),
    [("PEAK", "peak"), ("1m", "INTERVAL_1M"), ("CLOSE", "close"), ("1m", "1m")],
)
async def test_get_refuses_a_value_of_the_other_enum(interval, quantity_mode):
    async def run(client):
        with pytest.raises(PolyesterValidationError):
            await client.heatmap.get(symbol_id=1, interval=interval, quantity_mode=quantity_mode)

    assert await _with_client(run) == []


async def test_get_keeps_an_explicit_end_with_from_ts_sec_across_pages():
    end = datetime.fromtimestamp(400, UTC)

    async def run(client):
        first = await client.heatmap.get(symbol_id=1, interval="1m", from_ts_sec=100, end_time=end)
        await client.heatmap.get(
            symbol_id=1,
            interval="1m",
            from_ts_sec=100,
            end_time=end,
            page_token=first.raw["nextPageToken"],
        )

    requests = await _with_client(run)
    assert [(r.time_range.start_time.seconds, r.time_range.end_time.seconds) for r in requests] == [
        (100, 400),
        (100, 400),
    ]


@pytest.mark.parametrize(
    ("depth", "want"),
    [
        (0, "DEPTH_50"),
        (1, "DEPTH_1"),
        (2, "DEPTH_5"),
        (5, "DEPTH_5"),
        (11, "DEPTH_20"),
        (20, "DEPTH_20"),
        (50, "DEPTH_50"),
        (101, "DEPTH_200"),
        (200, "DEPTH_200"),
        (300, "DEPTH_500"),
        (500, "DEPTH_500"),
        (501, "DEPTH_1000"),
        (1000, "DEPTH_1000"),
    ],
)
async def test_get_requests_the_smallest_supported_depth_covering_the_request(depth, want):
    async def run(client):
        result = await client.heatmap.get(symbol_id=1, interval="1m", depth=depth)
        assert result.raw["depth"] == want

    requests = await _with_client(run)
    assert [heatmap.HeatmapDepth.Name(r.depth) for r in requests] == [want]


@pytest.mark.parametrize("depth", [-1, 1001, 5000, True, 1.5])
async def test_get_refuses_depths_no_supported_depth_covers(depth):
    async def run(client):
        with pytest.raises(PolyesterValidationError, match="heatmap depth"):
            await client.heatmap.get(symbol_id=1, interval="1m", depth=depth)

    assert await _with_client(run) == []
