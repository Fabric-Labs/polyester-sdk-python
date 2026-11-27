"""``market_overview.list`` sends the contract's sort key, direction and
sparkline intervals.

``order_by``, ``sort`` and ``sparkline_intervals`` are
``ListMarketOverviewRequest`` fields 4, 5 and 7. Unset, they stay unset and the
server keeps its defaults (descending 24h USD volume, the 24h sparkline). An
unknown value is refused before anything is sent. A page token is bound to the
sort it was issued for, so the next page is asked with the same sort.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from polyester import AsyncPolyester, Polyester
from polyester.errors import PolyesterValidationError
from polyester.gen.marketoverview.v1 import marketoverview_pb2 as mo
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)

ORDER_BY = {
    "change_24h_bps": mo.ORDER_BY_CHANGE_24H_BPS,
    "volume_24h_usd": mo.ORDER_BY_VOLUME_24H_USD,
    "last_price": mo.ORDER_BY_LAST_PRICE,
    "date_added": mo.ORDER_BY_DATE_ADDED,
}
SORT = {"asc": mo.SORT_ASC, "desc": mo.SORT_DESC}
INTERVALS = {
    "SPARKLINE_1H": mo.SPARKLINE_1H,
    "SPARKLINE_24H": mo.SPARKLINE_24H,
    "SPARKLINE_1W": mo.SPARKLINE_1W,
    "SPARKLINE_1M": mo.SPARKLINE_1M,
}


class _Capture:
    def __init__(self) -> None:
        self.requests: list[mo.ListMarketOverviewRequest] = []

    async def handler(self, req: ParsedRequest) -> HttpScript:
        self.requests.append(mo.ListMarketOverviewRequest.FromString(req.body))
        reply = mo.ListMarketOverviewResponse(next_page_token="page-2")
        return connect_proto_response(reply.SerializeToString())


async def _list(**kwargs: Any) -> tuple[_Capture, list[mo.ListMarketOverviewRequest]]:
    capture = _Capture()
    http = await MockHttpServer.spawn(capture.handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    try:
        await client.market_overview.list(**kwargs)
    finally:
        await client.aclose()
        await http.aclose()
    return capture, capture.requests


@pytest.mark.parametrize(("label", "value"), sorted(ORDER_BY.items()))
async def test_order_by_is_sent_as_field_4(label: str, value: int) -> None:
    _, [request] = await _list(order_by=label)
    assert request.order_by == value
    assert request.sort == mo.SORT_DIRECTION_UNSPECIFIED


@pytest.mark.parametrize(("label", "value"), sorted(SORT.items()))
async def test_sort_is_sent_as_field_5(label: str, value: int) -> None:
    _, [request] = await _list(order_by="last_price", sort=label)
    assert (request.order_by, request.sort) == (mo.ORDER_BY_LAST_PRICE, value)


async def test_sparkline_intervals_are_sent_as_field_7() -> None:
    _, [request] = await _list(include_sparklines=True, sparkline_intervals=list(INTERVALS))
    assert list(request.sparkline_intervals) == list(INTERVALS.values())
    _, [request] = await _list(include_sparklines=True, sparkline_intervals=[])
    assert list(request.sparkline_intervals) == []


async def test_unset_sort_keeps_the_server_default() -> None:
    _, [request] = await _list()
    assert request.order_by == 0
    assert request.sort == 0
    # Nothing is encoded for either field: the server applies its default order.
    assert mo.ListMarketOverviewRequest(limit=50).SerializeToString() == request.SerializeToString()


async def test_the_next_page_is_asked_with_the_same_sort() -> None:
    capture = _Capture()
    http = await MockHttpServer.spawn(capture.handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    try:
        first = await client.market_overview.list(order_by="date_added", sort="asc", limit=10)
        await client.market_overview.list(
            order_by="date_added", sort="asc", limit=10, page_token=first.next_page_token
        )
    finally:
        await client.aclose()
        await http.aclose()
    second = capture.requests[1]
    assert (second.page_token, second.order_by, second.sort) == (
        "page-2",
        mo.ORDER_BY_DATE_ADDED,
        mo.SORT_ASC,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"order_by": "volume"},
        {"order_by": "DATE_ADDED"},
        {"order_by": "unspecified"},
        {"order_by": 4},
        {"sort": "ascending"},
        {"sort": "DESC"},
        {"sort": 1},
        {"sparkline_intervals": ["1h"]},
        {"sparkline_intervals": ["SPARKLINE_INTERVAL_UNSPECIFIED"]},
        {"sparkline_intervals": [2]},
        {"sparkline_intervals": "SPARKLINE_1H"},
    ],
)
async def test_unknown_values_are_refused_before_sending(kwargs: dict[str, Any]) -> None:
    capture = _Capture()
    http = await MockHttpServer.spawn(capture.handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    try:
        with pytest.raises(PolyesterValidationError, match=next(iter(kwargs))):
            await client.market_overview.list(**kwargs)
    finally:
        await client.aclose()
        await http.aclose()
    assert capture.requests == []


async def test_the_sync_client_sends_the_same_fields() -> None:
    capture = _Capture()
    http = await MockHttpServer.spawn(capture.handler)

    def call() -> None:
        with Polyester(api_url=http.base_url, hydrate_catalogs=False) as client:
            client.market_overview.list(
                order_by="change_24h_bps",
                sort="desc",
                include_sparklines=True,
                sparkline_intervals=["SPARKLINE_1W"],
            )

    try:
        await asyncio.to_thread(call)
    finally:
        await http.aclose()
    [request] = capture.requests
    assert (request.order_by, request.sort) == (mo.ORDER_BY_CHANGE_24H_BPS, mo.SORT_DESC)
    assert list(request.sparkline_intervals) == [mo.SPARKLINE_1W]
