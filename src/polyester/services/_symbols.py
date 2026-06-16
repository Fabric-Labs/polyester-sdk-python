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
