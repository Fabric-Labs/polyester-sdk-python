from __future__ import annotations

from polyester.codecs.scalars import parse_price_ticks
from polyester.models import OrderbookData, OrderbookLevel
from polyester.models.realtime import OrderBookDeltaUpdate

BookSide = dict[int, int]


def levels_to_map(levels: list[tuple[str, str]] | None) -> BookSide:
    book: BookSide = {}
    for price_ticks, qty_scaled in levels or []:
        price = int(price_ticks)
        qty = int(qty_scaled)
        if qty == 0:
            continue
        book[price] = qty
    return book


def levels_from_proto_levels(
    levels: list[object] | None,
    *,
    price_attr: str = "price_ticks",
    qty_attr: str = "qty_scaled",
) -> BookSide:
    book: BookSide = {}
    for level in levels or []:
        qty = int(getattr(level, qty_attr))
        if qty == 0:
            continue
        book[int(getattr(level, price_attr))] = qty
    return book


def apply_side_delta(book: BookSide, levels: list[tuple[str, str]] | None) -> None:
    for price_ticks, qty_scaled in levels or []:
        price = int(price_ticks)
        qty = int(qty_scaled)
        if qty == 0:
            book.pop(price, None)
        else:
            book[price] = qty


def bucket_side(book: BookSide, bucket_ticks: int | None) -> BookSide:
    if not bucket_ticks or bucket_ticks <= 0:
        return book
    aggregated: BookSide = {}
    for price_ticks, qty_scaled in book.items():
        if qty_scaled <= 0:
            continue
        bucket_price = (price_ticks // bucket_ticks) * bucket_ticks
        aggregated[bucket_price] = aggregated.get(bucket_price, 0) + qty_scaled
    return aggregated


def side_to_levels(
    book: BookSide,
    *,
    side: str,
    limit: int,
    bucket_ticks: int | None = None,
) -> list[OrderbookLevel]:
    view = bucket_side(book, bucket_ticks)
    entries = list(view.items())
    entries.sort(
        key=lambda item: item[0],
        reverse=side == "bids",
    )
    return [
        OrderbookLevel(price_ticks=str(price), qty_scaled=str(qty))
        for price, qty in entries[:limit]
    ]


def build_orderbook_data(
    *,
    symbol: str,
    depth: int,
    book_seq: int,
    bids: BookSide,
    asks: BookSide,
    bucket_ticks: int | None = None,
) -> OrderbookData:
    return OrderbookData(
        symbol=symbol,
        depth=depth,
        book_seq=str(book_seq),
        bids=side_to_levels(bids, side="bids", limit=depth, bucket_ticks=bucket_ticks),
        asks=side_to_levels(asks, side="asks", limit=depth, bucket_ticks=bucket_ticks),
    )


def parse_bucket_ticks(bucket: str | None) -> int | None:
    if not bucket:
        return None
    try:
        return parse_price_ticks(bucket, "bucket")
    except Exception:
        return None


def apply_delta(
    *,
    bids: BookSide,
    asks: BookSide,
    current_book_seq: int,
    delta: OrderBookDeltaUpdate,
) -> tuple[int, bool]:
    """Apply one delta. Returns (new_book_seq, needs_snapshot_refresh)."""
    if delta.reset:
        bids.clear()
        asks.clear()
        current_book_seq = 0

    seq_start = int(delta.book_seq_start or 0)
    seq_end = int(delta.book_seq_end or 0)

    if current_book_seq != 0 and seq_start > current_book_seq + 1:
        return current_book_seq, True

    if seq_end <= current_book_seq:
        return current_book_seq, False

    apply_side_delta(bids, list(delta.bids))
    apply_side_delta(asks, list(delta.asks))
    if seq_end > current_book_seq:
        current_book_seq = seq_end
    return current_book_seq, False
