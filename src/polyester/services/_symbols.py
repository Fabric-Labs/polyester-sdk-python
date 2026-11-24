from __future__ import annotations

from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.pure_bridge import call, exact_index, pure
from polyester.codecs.scalars import market_ids
from polyester.errors import PolyesterValidationError


def resolve_symbol_id(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None,
    label: str = "request",
) -> int:
    """Resolve a market from its name, its numeric ID, or both.

    Given both, they must name one market: a name that is not the catalog's
    name for the ID, or that the catalog maps to another ID, is refused.
    """
    return call(
        pure._resolve_symbol_id, symbol, exact_index(symbol_id), label, catalog_lookup(catalogs)
    )


def catalog_lookup(catalogs: CatalogManager | None) -> tuple[Any, Any] | None:
    """The catalogs as the shared resolver reads them: (ID of a name, name of an ID)."""
    if catalogs is None:
        return None
    # Read at use, as before: a lookup a call needs is the only one it makes.
    return (
        lambda symbol: catalogs.symbol_id_for_symbol(symbol),
        lambda symbol_id: catalogs.symbol_for_symbol_id(symbol_id),
    )


def resolve_order_identity(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None,
    label: str,
    require_catalog: bool = True,
) -> tuple[str | None, int]:
    """Resolve the wire pair and validate an explicitly supplied display symbol."""
    resolved_id = resolve_symbol_id(catalogs, symbol=symbol, symbol_id=symbol_id, label=label)
    canonical = catalogs.symbol_for_symbol_id(resolved_id) if catalogs is not None else None
    if canonical is None and require_catalog:
        raise PolyesterValidationError(
            f"{label} quantity scale is unavailable for symbol_id {resolved_id}; hydrate catalogs"
        )
    if canonical is not None and symbol is not None and symbol != canonical:
        raise PolyesterValidationError(
            f"{label} symbol mismatch: {symbol!r} does not match "
            f"symbol_id {resolved_id} ({canonical})"
        )
    return canonical or symbol, resolved_id


def resolve_optional_symbol_id(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None = None,
    label: str = "symbol filter",
) -> int | None:
    """Resolve an optional Connect symbol filter.

    An omitted (``None``) filter stays omitted (the server treats zero as all
    symbols). A supplied display symbol is resolved through the catalog and
    fails closed; a blank one is refused (see :func:`check_optional_symbol`),
    never read as every market.
    """
    normalized = check_optional_symbol(symbol, label=label)
    if symbol_id is None and normalized is None:
        return None
    return resolve_symbol_id(
        catalogs,
        symbol=normalized,
        symbol_id=symbol_id,
        label=label,
    )


def check_optional_symbol(symbol: object, *, label: str = "symbol filter") -> str | None:
    """An optional market filter's name, trimmed, or ``None`` when left out.

    A supplied name that is blank (empty or whitespace-only) or not a ``str``
    raises ``PolyesterValidationError``: it would resolve to no market and so
    match every market. It needs no catalogs, so a call checks it before
    awaiting them.
    """
    return call(pure._optional_symbol, symbol, label)


def resolve_symbol_ids(
    catalogs: CatalogManager | None,
    symbols: list[str] | None,
    *,
    label: str = "symbol filters",
) -> list[int]:
    resolved: list[int] = []
    for symbol in normalize_raw_symbol_filters(symbols, label=label):
        resolved.append(resolve_symbol_id(catalogs, symbol=symbol, symbol_id=None, label=label))
    return resolved


def display_symbol_for_id(catalogs: CatalogManager | None, symbol_id: int) -> str:
    if catalogs is None or not symbol_id:
        return ""
    return catalogs.symbol_for_symbol_id(int(symbol_id)) or ""


def normalize_raw_symbol_filter(
    symbol: str | None,
    *,
    label: str = "symbol filter",
) -> str | None:
    """Trim a display-symbol argument; empty/whitespace values are omitted."""
    if symbol is None:
        return None
    if not isinstance(symbol, str):
        raise PolyesterValidationError(f"{label} must be a symbol string")
    normalized = symbol.strip()
    return normalized or None


def normalize_raw_symbol_filters(
    symbols: list[str] | None,
    *,
    label: str = "symbol filters",
) -> list[str]:
    if not symbols:
        return []
    resolved: list[str] = []
    for symbol in symbols:
        item = normalize_raw_symbol_filter(symbol, label=label)
        if item is not None:
            resolved.append(item)
    return resolved


MAX_CANCEL_ALL_SYMBOL_IDS = 100


def resolve_cancel_all_symbol_ids(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None = None,
    symbols: list[str] | None = None,
    symbol_ids: list[int] | None = None,
    label: str = "orders.cancel_all",
) -> list[int]:
    """Resolve cancel-all Connect ``symbol_ids``.

    Empty means all symbols. Duplicates are ignored. At most 100 positive IDs
    are accepted. ``symbol``, ``symbols``, and ``symbol_ids`` are mutually
    exclusive once any of them selects at least one pair.
    """
    normalized_symbol = normalize_raw_symbol_filter(symbol, label=f"{label} symbol")
    normalized_symbols = normalize_raw_symbol_filters(symbols, label=f"{label} symbols")
    raw_ids = market_ids(symbol_ids, f"{label} symbol_ids") if symbol_ids is not None else []
    selected = sum(1 for group in (normalized_symbol, normalized_symbols, raw_ids) if group)
    if selected > 1:
        raise PolyesterValidationError(
            f"{label} accepts only one of symbol, symbols, or symbol_ids"
        )

    resolved: list[int] = []
    if raw_ids:
        for value in raw_ids:
            if value <= 0:
                raise PolyesterValidationError(f"{label} symbol_ids must be positive")
            resolved.append(value)
    elif normalized_symbol is not None:
        resolved.append(
            resolve_symbol_id(
                catalogs,
                symbol=normalized_symbol,
                symbol_id=None,
                label=f"{label} symbol",
            )
        )
    elif normalized_symbols:
        resolved.extend(resolve_symbol_ids(catalogs, normalized_symbols, label=f"{label} symbols"))

    unique: list[int] = []
    seen: set[int] = set()
    for value in resolved:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    if len(unique) > MAX_CANCEL_ALL_SYMBOL_IDS:
        raise PolyesterValidationError(
            f"{label} accepts at most {MAX_CANCEL_ALL_SYMBOL_IDS} symbol_ids"
        )
    return unique
