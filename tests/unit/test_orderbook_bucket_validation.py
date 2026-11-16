"""An order book bucket is empty (no bucketing) or a positive price; anything else is refused."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.orderbook.local_book import parse_bucket_ticks
from polyester.services.orderbook import AsyncOrderbookService
from polyester.sync_subscribe import SyncSubscription

# A whitespace-only bucket is not empty: like a whitespace-only price, it is
# refused. Whitespace around a valid price is ignored, as for every price.
INVALID_BUCKETS = ["abc", "-1", "0", "0.000", " ", "\t \n", "0.0000000001", "nan", "inf"]


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return catalogs


@pytest.mark.parametrize(
    ("bucket", "ticks"),
    [
        (None, None),
        ("", None),
        ("0.01", 10_000_000),
        (" 0.01\t", 10_000_000),
        ("1", 1_000_000_000),
        ("0.000000001", 1),
    ],
)
def test_parse_bucket_ticks_accepts_empty_and_positive_prices(bucket, ticks) -> None:
    assert parse_bucket_ticks(bucket) == ticks


@pytest.mark.parametrize("bucket", INVALID_BUCKETS)
def test_parse_bucket_ticks_refuses_invalid_bucket(bucket) -> None:
    with pytest.raises(PolyesterValidationError, match="positive price") as raised:
        parse_bucket_ticks(bucket)
    assert "empty for no bucketing" in str(raised.value)


@pytest.mark.parametrize("bucket", ["abc", "-1", "0"])
async def test_create_subscription_refuses_invalid_bucket_before_io(monkeypatch, bucket) -> None:
    fetch = AsyncMock()
    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fetch)
    stream = MagicMock(side_effect=AssertionError("connected with an invalid bucket"))
    monkeypatch.setattr("polyester.services.orderbook.AsyncSnapshotThenStreamSubscription", stream)
    service = AsyncOrderbookService(MagicMock(), catalogs=_catalogs(), realtime=MagicMock())
    with pytest.raises(PolyesterValidationError, match="bucket"):
        await service.create_subscription(symbol="BTC-USDT", bucket=bucket)
    fetch.assert_not_called()
    stream.assert_not_called()


async def test_set_bucket_refuses_invalid_bucket_and_keeps_current(monkeypatch) -> None:
    snapshot = orderbook_pb2.GetOrderBookResponse(book_seq=1, available=True)
    snapshot.bids.add(price_ticks=71_600_000, qty_scaled=3)
    monkeypatch.setattr(
        "polyester.services.orderbook.unary_public_decoded", AsyncMock(return_value=snapshot)
    )

    class _Stream:
        async def start(self) -> None:
            return None

        def is_ready(self) -> bool:
            return True

        def is_disposed(self) -> bool:
            return False

        async def aclose(self) -> None:
            return None

    def stream(**kwargs):
        kwargs["apply_snapshot"](snapshot, [])
        return _Stream()

    monkeypatch.setattr("polyester.services.orderbook.AsyncSnapshotThenStreamSubscription", stream)
    service = AsyncOrderbookService(MagicMock(), catalogs=_catalogs(), realtime=MagicMock())
    sub = await service.create_subscription(symbol="BTC-USDT", bucket="0.01")
    try:
        first = await asyncio.wait_for(anext(sub), 3)
        assert first.bids[0].price.ticks == 70_000_000
        for invalid in INVALID_BUCKETS:
            with pytest.raises(PolyesterValidationError, match="positive price"):
                sub.set_bucket(invalid)
        # A refused bucket adds no view; None turns bucketing off and renders the book.
        sub.set_bucket(None)
        view = await asyncio.wait_for(anext(sub), 3)
        assert view.bids[0].price.ticks == 71_600_000
    finally:
        await sub.aclose()


def test_sync_set_bucket_refuses_invalid_bucket_in_the_caller() -> None:
    loop = MagicMock()
    target = MagicMock()
    sync = SyncSubscription(loop, close_coro=AsyncMock(), holder={"sub": target})
    with pytest.raises(PolyesterValidationError, match="positive price"):
        sync.set_bucket("abc")
    loop.call_soon_threadsafe.assert_not_called()
    sync.set_bucket("0.01")
    loop.call_soon_threadsafe.assert_called_once_with(target.set_bucket, "0.01")
