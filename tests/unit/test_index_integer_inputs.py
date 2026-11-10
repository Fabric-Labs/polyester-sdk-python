"""Integer depths and limits accept any exact integer type, such as NumPy's.

An exact integer is anything with ``__index__`` (``operator.index``), which is how NumPy
integers declare that they are lossless integers. ``bool`` has ``__index__`` too but is
refused, and ``float`` has none. The SDK sends and reports a plain ``int`` either way.
"""

from __future__ import annotations

import pytest

from polyester.codecs.orderbook import (
    orderbook_snapshot_depth,
    orderbook_stream_tier,
    require_published_stream_depth,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import heatmap_pb2 as heatmap
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.services._validation import validate_limit
from tests.unit.test_heatmap_requests import _with_client
from tests.unit.test_orderbook_depth_delta_binding import _snapshot_service
from tests.unit.test_orderbook_published_depths import (
    channel_for,
    harness,
    next_view,
    subscribed_channel,
)


class Index:
    """An exact integer that is not an ``int``: the protocol NumPy integers implement."""

    def __init__(self, value: int) -> None:
        self._value = value

    def __index__(self) -> int:
        return self._value

    def __repr__(self) -> str:
        return f"Index({self._value})"


def test_helpers_accept_index_integers_and_return_plain_ints() -> None:
    for value, helper, want in [
        (Index(11), orderbook_snapshot_depth, 20),
        (Index(0), orderbook_snapshot_depth, 50),
        (Index(10), orderbook_stream_tier, 20),
        (Index(20), require_published_stream_depth, 20),
        (Index(7), validate_limit, 7),
    ]:
        got = helper(value)
        assert (got, type(got)) == (want, int), (helper.__name__, value)


@pytest.mark.parametrize(
    "helper",
    [
        orderbook_snapshot_depth,
        orderbook_stream_tier,
        require_published_stream_depth,
        validate_limit,
    ],
)
@pytest.mark.parametrize("value", [True, False, 20.0, 1.5, "20", None])
def test_helpers_still_refuse_bool_float_and_non_integers(helper, value) -> None:
    with pytest.raises(PolyesterValidationError):
        helper(value)


@pytest.mark.parametrize(
    "helper", [orderbook_snapshot_depth, orderbook_stream_tier, require_published_stream_depth]
)
@pytest.mark.parametrize("value", [Index(-1), Index(5000)])
def test_depth_helpers_judge_the_index_value(helper, value) -> None:
    with pytest.raises(PolyesterValidationError, match="depth"):
        helper(value)


async def test_snapshot_accepts_an_index_integer_depth(monkeypatch) -> None:
    service, requests = _snapshot_service(monkeypatch)
    book = await service.get(symbol="BTC-USDT", depth=Index(11))
    assert [orderbook_pb2.Depth.Name(r.depth) for r in requests] == ["DEPTH_20"]
    assert (book.depth, type(book.depth)) == (20, int)


async def test_managed_book_accepts_an_index_integer_depth() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=Index(10))
        assert await subscribed_channel(h.server) == channel_for(20)
        view = await next_view(sub, what="first view")
        assert (view.depth, type(view.depth)) == (10, int)
        assert (len(view.bids), len(view.asks)) == (10, 10)
        await sub.aclose()


async def test_raw_deltas_accept_an_index_integer_depth() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.subscribe_deltas(symbol_id=1, depth=Index(20))
        assert await subscribed_channel(h.server) == channel_for(20)
        await sub.aclose()


async def test_heatmap_accepts_index_integer_depth_and_limit() -> None:
    async def run(client):
        await client.heatmap.get(symbol_id=1, interval="1m", depth=Index(11), limit=Index(3))

    requests = await _with_client(run)
    assert [(heatmap.HeatmapDepth.Name(r.depth), r.limit) for r in requests] == [("DEPTH_20", 3)]
