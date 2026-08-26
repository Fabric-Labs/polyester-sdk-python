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
        if int(symbol_id) == 0:
            raise PolyesterValidationError(f"{label} symbol_id must be non-zero when explicitly supplied")
        return int(symbol_id)
    if symbol and catalogs is not None:
        resolved = catalogs.symbol_id_for_symbol(symbol)
        if resolved is not None:
            return resolved
    if symbol is None:
        raise PolyesterValidationError(f"{label} requires symbol or symbol_id")
    raise PolyesterValidationError(
        f"Unknown symbol {symbol!r}; call get_spot_config first or pass symbol_id"
    )


def resolve_optional_symbol_id(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None = None,
    label: str = "symbol filter",
) -> int | None:
    """Resolve an optional Connect symbol filter.

    Empty/omitted filters stay omitted (the server treats zero as all symbols).
    A supplied display symbol is resolved through the catalog and fails closed.
    """
    normalized = normalize_raw_symbol_filter(symbol, label=label)
    if symbol_id is None and normalized is None:
        return None
    return resolve_symbol_id(
        catalogs,
        symbol=normalized,
        symbol_id=symbol_id,
        label=label,
    )


def resolve_symbol_ids(
    catalogs: CatalogManager | None,
    symbols: list[str] | None,
    *,
    label: str = "symbol filters",
) -> list[int]:
    resolved: list[int] = []
    for symbol in normalize_raw_symbol_filters(symbols, label=label):
        resolved.append(
            resolve_symbol_id(catalogs, symbol=symbol, symbol_id=None, label=label)
        )
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
