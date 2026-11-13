from __future__ import annotations

from polyester.codecs.scalars import parse_price_ticks
from polyester.errors import PolyesterValidationError
from polyester.models import OrderbookData, OrderbookLevel
from polyester.models.realtime import OrderBookDeltaUpdate

BookSide = dict[int, int]


def levels_to_map(levels: list[tuple[str, str]] | None) -> BookSide:
    book: BookSide = {}
    for price_ticks, qty_scaled in levels or []:
        price = int(price_ticks)
        qty = int(qty_scaled)
        if price <= 0:
            raise PolyesterValidationError("orderbook level has invalid or missing price")
        if qty <= 0:
            raise PolyesterValidationError("orderbook level has invalid or missing quantity")
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
        price = int(getattr(level, price_attr))
        qty = int(getattr(level, qty_attr))
        if price <= 0:
            raise PolyesterValidationError("orderbook level has invalid or missing price")
        if qty <= 0:
            raise PolyesterValidationError("orderbook level has invalid or missing quantity")
        book[price] = qty
    return book


def apply_side_delta(book: BookSide, levels: list[tuple[str, str]] | None) -> None:
    for price_ticks, qty_scaled in levels or []:
        price = int(price_ticks)
        qty = int(qty_scaled)
        # Negative price/qty is wire corruption; never materialize it into the book.
        if price < 0 or qty < 0:
            continue
        if qty == 0:
            book.pop(price, None)
        else:
            book[price] = qty


def bucket_side(book: BookSide, bucket_ticks: int | None, *, asks: bool = False) -> BookSide:
    if not bucket_ticks or bucket_ticks <= 0:
        for price_ticks, qty_scaled in book.items():
            if price_ticks < 0:
                raise PolyesterValidationError("orderbook price ticks must be non-negative")
            if qty_scaled < 0:
                raise PolyesterValidationError("orderbook quantity must be non-negative")
            if price_ticks == 0 and qty_scaled > 0:
                raise PolyesterValidationError("orderbook level has invalid or missing price")
        return book
    aggregated: BookSide = {}
    for price_ticks, qty_scaled in book.items():
        if price_ticks < 0:
            raise PolyesterValidationError("orderbook price ticks must be non-negative")
        if qty_scaled <= 0:
            continue
        if price_ticks == 0:
            raise PolyesterValidationError("orderbook level has invalid or missing price")
        floor = (price_ticks // bucket_ticks) * bucket_ticks
        bucket_price = floor
        if asks and price_ticks % bucket_ticks != 0:
            bucket_price = floor + bucket_ticks
        aggregated[bucket_price] = aggregated.get(bucket_price, 0) + qty_scaled
    return aggregated


def format_orderbook_level(
    *,
    price_ticks: int,
    qty_scaled: int,
    quantity_scale: int,
    symbol: str | None = None,
    allow_zero_price: bool = False,
) -> OrderbookLevel:
    from polyester.types.money import Price, Quantity

    if price_ticks < 0 or (price_ticks == 0 and not allow_zero_price):
        raise PolyesterValidationError("orderbook level has invalid or missing price")
    if qty_scaled <= 0:
        raise PolyesterValidationError("orderbook level has invalid or missing quantity")
    return OrderbookLevel(
        price=Price.from_ticks(price_ticks, symbol=symbol),
        qty=Quantity.from_scaled(qty_scaled, scale=quantity_scale, symbol=symbol),
    )


def side_to_levels(
    book: BookSide,
    *,
    side: str,
    limit: int,
    quantity_scale: int,
    bucket_ticks: int | None = None,
    symbol: str | None = None,
) -> list[OrderbookLevel]:
    view = bucket_side(book, bucket_ticks, asks=side == "asks")
    entries = list(view.items())
    entries.sort(
        key=lambda item: item[0],
        reverse=side == "bids",
    )
    return [
        format_orderbook_level(
            price_ticks=price,
            qty_scaled=qty,
            # A floor-rounded display boundary may be zero even for positive raw bids.
            allow_zero_price=side == "bids" and bucket_ticks is not None and bucket_ticks > 0,
            quantity_scale=quantity_scale,
            symbol=symbol,
        )
        for price, qty in entries[:limit]
    ]


def build_orderbook_data(
    *,
    symbol: str,
    depth: int,
    book_seq: int,
    bids: BookSide,
    asks: BookSide,
    quantity_scale: int,
    bucket_ticks: int | None = None,
    available: bool = True,
) -> OrderbookData:
    """Render the book with up to ``depth`` levels per side; 0 renders none."""
    if depth < 0:
        raise PolyesterValidationError(f"orderbook depth must not be negative, got {depth}")
    return OrderbookData(
        symbol=symbol,
        depth=depth,
        book_seq=str(book_seq),
        available=available,
        bids=side_to_levels(
            bids,
            side="bids",
            limit=depth,
            bucket_ticks=bucket_ticks,
            quantity_scale=quantity_scale,
            symbol=symbol,
        ),
        asks=side_to_levels(
            asks,
            side="asks",
            limit=depth,
            bucket_ticks=bucket_ticks,
            quantity_scale=quantity_scale,
            symbol=symbol,
        ),
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
    """Apply one delta. Returns ``(new_book_seq, out_of_sync)``.

    Each update is the difference between two published views of the tier's
    top levels: ``book_seq_start`` is the sequence of the view it applies to
    (the previous update's ``book_seq_end``) and ``book_seq_end`` that of the
    view after it. An update whose ``book_seq_end`` is at most
    ``current_book_seq`` is already in the book and is dropped. Any other
    update applies only to a book at exactly ``book_seq_start``; one that
    starts anywhere else, before or after, cannot be applied and leaves the
    book out of sync (``out_of_sync`` true, the book unchanged) until a
    ``reset`` replaces it. A malformed update is out of sync too.
    """
    # Reject the whole update atomically. Skipping corrupt rows while advancing
    # the sequence permanently leaves stale quantity in the local book. A
    # positive quantity at price zero is a level bucket_side refuses to render,
    # so it is as malformed as a negative row.
    pairs = [(int(price), int(qty)) for price, qty in [*delta.bids, *delta.asks]]
    if any(price < 0 or qty < 0 or (price == 0 and qty > 0) for price, qty in pairs):
        return current_book_seq, True

    try:
        seq_start = int(delta.book_seq_start)
        seq_end = int(delta.book_seq_end)
    except (TypeError, ValueError):
        return current_book_seq, True
    if seq_start < 0 or seq_end < seq_start:
        return current_book_seq, True

    # An update that ends at or before the book's sequence is already in it. A
    # reset is a complete replacement through seq_end, so one that does not
    # advance the sequence must not clear or rewind a newer snapshot.
    if seq_end <= current_book_seq:
        return current_book_seq, False

    # A diff applies only to the exact view it was computed from: one that
    # starts after the book skipped a view, and one that starts before it
    # overlaps views the book already holds.
    if not delta.reset and seq_start != current_book_seq:
        return current_book_seq, True

    if delta.reset:
        bids.clear()
        asks.clear()
        current_book_seq = 0

    apply_side_delta(bids, list(delta.bids))
    apply_side_delta(asks, list(delta.asks))
    if seq_end > current_book_seq:
        current_book_seq = seq_end
    return current_book_seq, False
