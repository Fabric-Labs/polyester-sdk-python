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


def resolve_symbol_filter(
    catalogs: CatalogManager | None,
    symbol: str | None,
    *,
    label: str = "symbol filter",
) -> str | None:
    """Validate a raw string symbol filter against the hydrated catalog."""
    if symbol is None or symbol == "":
        return None
    if not isinstance(symbol, str) or not symbol.strip():
        raise PolyesterValidationError(f"{label} must be a non-empty symbol string")
    normalized = symbol.strip()
    if catalogs is None or catalogs.symbol_id_for_symbol(normalized) is None:
        raise PolyesterValidationError(
            f"Unknown symbol filter {normalized!r}; await client.wait_for_catalogs() first"
        )
    return normalized


def resolve_symbol_filters(
    catalogs: CatalogManager | None,
    symbols: list[str] | None,
    *,
    label: str = "symbol filters",
) -> list[str]:
    if not symbols:
        return []
    resolved: list[str] = []
    for symbol in symbols:
        item = resolve_symbol_filter(catalogs, symbol, label=label)
        if item is not None:
            resolved.append(item)
    return resolved
