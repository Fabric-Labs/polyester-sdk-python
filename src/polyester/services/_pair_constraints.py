from __future__ import annotations

from decimal import Decimal

from polyester.catalogs import CatalogManager, PairConstraints
from polyester.codecs.scalars import parse_price_ticks, parse_qty_scaled
from polyester.errors import PolyesterValidationError
from polyester.types.money import resolve_price_ticks, resolve_qty_scaled


def preflight_pair_constraints(
    catalogs: CatalogManager,
    *,
    symbol: str | None,
    qty: object | None = None,
    prices: dict[str, object | None] | None = None,
    notional_price: object | None = None,
) -> None:
    """Check deterministic catalog rules before encoding an order or trigger."""
    if not symbol:
        return
    constraints = catalogs.pair_constraints_for_symbol(symbol)
    if constraints is None:
        raise PolyesterValidationError(
            f"pair constraints for {symbol!r} are unavailable; "
            "await client.wait_for_catalogs() first"
        )
    for field_name, value in (prices or {}).items():
        if value is not None:
            _validate_tick_size(constraints, value, field_name=field_name)
    qty_decimal = _validate_quantity(constraints, qty) if qty is not None else None
    if qty_decimal is not None and notional_price is not None:
        _validate_min_notional(constraints, qty_decimal, notional_price)


def _validate_tick_size(
    constraints: PairConstraints,
    value: object,
    *,
    field_name: str,
) -> None:
    if constraints.tick_size is None:
        return
    ticks = resolve_price_ticks(value, field_name, symbol=constraints.symbol)  # type: ignore[arg-type]
    tick_size = parse_price_ticks(constraints.tick_size, "catalog tick_size")
    if tick_size <= 0 or ticks % tick_size:
        raise PolyesterValidationError(
            f"{field_name} must align to {constraints.symbol} tick_size {constraints.tick_size}"
        )


def _validate_quantity(constraints: PairConstraints, value: object) -> Decimal:
    scaled = resolve_qty_scaled(
        value,  # type: ignore[arg-type]
        constraints.base_quantity_scale,
        "qty",
        symbol=constraints.symbol,
        symbol_id=constraints.symbol_id,
    )
    quantity = Decimal(scaled) / (Decimal(10) ** constraints.base_quantity_scale)
    if constraints.step_size is not None:
        step_scaled = parse_qty_scaled(
            constraints.step_size,
            constraints.base_quantity_scale,
            "catalog step_size",
        )
        if scaled % step_scaled:
            raise PolyesterValidationError(
                f"qty must align to {constraints.symbol} step_size {constraints.step_size}"
            )
    if constraints.min_qty_base is not None:
        min_scaled = parse_qty_scaled(
            constraints.min_qty_base,
            constraints.base_quantity_scale,
            "catalog min_qty_base",
        )
        if scaled < min_scaled:
            raise PolyesterValidationError(
                f"qty must be at least {constraints.min_qty_base} for {constraints.symbol}"
            )
    return quantity


def _validate_min_notional(
    constraints: PairConstraints,
    quantity: Decimal,
    price: object,
) -> None:
    if constraints.min_notional_quote is None:
        return
    price_ticks = resolve_price_ticks(
        price,  # type: ignore[arg-type]
        "price",
        symbol=constraints.symbol,
    )
    notional = quantity * (Decimal(price_ticks) / Decimal(1_000_000))
    minimum = Decimal(constraints.min_notional_quote)
    if notional < minimum:
        raise PolyesterValidationError(
            f"computable notional must be at least {constraints.min_notional_quote} "
            f"for {constraints.symbol}"
        )
