from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError


def resolve_symbol_id(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None,
    label: str = "request",
) -> int:
    if symbol_id is not None:
        return symbol_id
    if symbol and catalogs is not None:
        resolved = catalogs.symbol_id_for_symbol(symbol)
        if resolved is not None:
            return resolved
    if symbol is None:
        raise PolyesterValidationError(f"{label} requires symbol or symbol_id")
    raise PolyesterValidationError(
        f"Unknown symbol {symbol!r}; call get_spot_config first or pass symbol_id"
    )


def normalize_raw_symbol_filter(
    symbol: str | None,
    *,
    label: str = "symbol filter",
) -> str | None:
    """Trim a raw string symbol filter; empty/whitespace values are omitted.

    Endpoints that wire ``symbol`` / ``symbols`` as strings forward the value to
    the API. Catalog admission for unknown symbols is a backend concern.
    """
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
