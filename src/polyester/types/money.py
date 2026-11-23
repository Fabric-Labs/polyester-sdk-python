"""Immutable money scalar types for SDK write and read surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from polyester.codecs.pure_bridge import call, pure
from polyester.codecs.scalars import (
    PRICE_TICK_SCALE,
    decimal_to_scaled,
    format_price_ticks,
    format_qty_scaled,
    parse_qty_scaled,
    validate_protocol_scale,
)
from polyester.errors import PolyesterValidationError


class QuantityDomain(StrEnum):
    ORDER_BASE = "order_base"
    ORDER_QUOTE = "order_quote"
    ASSET = "asset"
    LEDGER_E18 = "ledger_e18"


def _require_scaled_int(value: int, field_name: str, *, allow_u128: bool = False) -> int:
    return call(pure._require_scaled_int, value, field_name, allow_u128)


@dataclass(frozen=True, slots=True)
class Price:
    """Resolved protocol price units (protobuf price_ticks, fixed 1e9)."""

    ticks: int
    symbol: str | None = None
    # How polyester.pure, which holds the rules, recognises a price.
    _polyester_kind: ClassVar[str] = "price"

    @classmethod
    def from_ticks(cls, ticks: int, *, symbol: str | None = None) -> Price:
        return cls(ticks=_require_scaled_int(ticks, "ticks"), symbol=symbol)

    def as_decimal(self) -> Decimal:
        return Decimal(format_price_ticks(self.ticks))

    def format(self) -> str:
        return format_price_ticks(self.ticks)

    def compatible_with(self, *, symbol: str | None = None) -> None:
        call(pure._price_compatible, self, symbol)


@dataclass(frozen=True, slots=True)
class Quantity:
    """Resolved order/trigger base or quote quantity (protobuf qty_scaled)."""

    scaled: int
    scale: int | None = None
    domain: QuantityDomain = QuantityDomain.ORDER_BASE
    symbol: str | None = None
    symbol_id: int | None = None
    _polyester_kind: ClassVar[str] = "quantity"

    @classmethod
    def from_scaled(
        cls,
        scaled: int,
        *,
        scale: int | None = None,
        domain: QuantityDomain = QuantityDomain.ORDER_BASE,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ) -> Quantity:
        checked = call(
            pure._quantity_from_scaled,
            scaled,
            scale=scale,
            domain=domain,
            symbol=symbol,
            symbol_id=symbol_id,
        )
        return cls(
            scaled=checked.scaled,
            scale=scale,
            domain=QuantityDomain(domain),
            symbol=symbol,
            symbol_id=symbol_id,
        )

    @classmethod
    def from_quote_scaled(
        cls,
        scaled: int,
        scale: int,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ) -> Quantity:
        """Construct a quote-debit budget from scaled integer units.

        ``scale`` is required so a bare integer can never silently inherit the
        catalog scale. Use
        ``CatalogManager.quote_quantity_scale_for_symbol``.
        """
        return cls.from_scaled(
            scaled,
            scale=scale,
            domain=QuantityDomain.ORDER_QUOTE,
            symbol=symbol,
            symbol_id=symbol_id,
        )

    @classmethod
    def from_quote_decimal_str(
        cls,
        raw: str,
        scale: int,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ) -> Quantity:
        scaled = parse_qty_scaled(raw, scale, "quote amount")
        return cls.from_quote_scaled(scaled, scale, symbol=symbol, symbol_id=symbol_id)

    @classmethod
    def from_quote_decimal(
        cls,
        raw: Decimal,
        scale: int,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ) -> Quantity:
        scaled = parse_qty_scaled(raw, scale, "quote amount")
        return cls.from_quote_scaled(scaled, scale, symbol=symbol, symbol_id=symbol_id)

    def as_decimal(self, scale: int | None = None) -> Decimal:
        return Decimal(call(pure._quantity_text, self, scale, "as_decimal"))

    def format(self, scale: int | None = None) -> str:
        return str(call(pure._quantity_text, self, scale, "format"))

    def compatible_with(
        self,
        *,
        domain: QuantityDomain = QuantityDomain.ORDER_BASE,
        scale: int | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ) -> None:
        call(pure._quantity_compatible, self, domain, scale, symbol, symbol_id)


@dataclass(frozen=True, slots=True)
class AssetAmount:
    """Resolved asset/ledger amount (transfer/withdraw amount_e18)."""

    scaled: int
    scale: int | None = None
    domain: QuantityDomain = QuantityDomain.ASSET
    asset_id: int | None = None
    _polyester_kind: ClassVar[str] = "asset_amount"

    @classmethod
    def from_scaled(
        cls,
        scaled: int,
        *,
        scale: int | None = None,
        domain: QuantityDomain = QuantityDomain.ASSET,
        asset_id: int | None = None,
    ) -> AssetAmount:
        value = _require_scaled_int(
            scaled,
            "scaled",
            allow_u128=domain == QuantityDomain.LEDGER_E18,
        )
        if scale is not None:
            validate_protocol_scale(scale)
        if domain not in (QuantityDomain.ASSET, QuantityDomain.LEDGER_E18):
            raise PolyesterValidationError("AssetAmount domain must be asset or ledger_e18")
        return cls(scaled=value, scale=scale, domain=domain, asset_id=asset_id)

    def as_decimal(self, scale: int | None = None) -> Decimal:
        resolved = scale if scale is not None else self.scale
        if resolved is None:
            raise PolyesterValidationError(
                "as_decimal requires a known scale; pass scale= or construct with scale="
            )
        validate_protocol_scale(resolved)
        return Decimal(format_qty_scaled(self.scaled, resolved))

    def format(self, scale: int | None = None) -> str:
        resolved = scale if scale is not None else self.scale
        if resolved is None:
            raise PolyesterValidationError(
                "format requires a known scale; pass scale= or construct with scale="
            )
        validate_protocol_scale(resolved)
        return format_qty_scaled(self.scaled, resolved)

    def compatible_with(
        self,
        *,
        domain: QuantityDomain = QuantityDomain.ASSET,
        scale: int | None = None,
        asset_id: int | None = None,
    ) -> None:
        if self.domain != domain:
            raise PolyesterValidationError(
                f"amount domain mismatch: value is {self.domain.value}, "
                f"destination is {domain.value}"
            )
        if self.scale is not None and scale is not None and self.scale != scale:
            raise PolyesterValidationError(
                f"amount scale mismatch: value scale is {self.scale}, destination is {scale}"
            )
        if self.asset_id is not None and asset_id is not None and self.asset_id != asset_id:
            raise PolyesterValidationError(
                f"amount asset_id mismatch: value is for {self.asset_id}, destination is {asset_id}"
            )


def resolve_price_ticks(
    value: str | Decimal | Price,
    field_name: str = "price",
    *,
    symbol: str | None = None,
) -> int:
    return call(pure._resolve_price_ticks, value, field_name, symbol)


def resolve_positive_price_ticks(
    value: str | Decimal | Price,
    field_name: str = "price",
    *,
    symbol: str | None = None,
) -> int:
    """Resolve a price the contract requires to be positive.

    A price of 0 in any form (``"0"``, ``"0.00"``, ``Decimal(0)``,
    ``Price.from_ticks(0)``) is refused: on the wire a 0 price reads as no
    price, so it would be sent as if it had been left out.
    """
    return call(pure._resolve_price_ticks, value, field_name, symbol, True)


def resolve_qty_scaled(
    value: str | Decimal | Quantity,
    scale: int,
    field_name: str = "qty",
    *,
    symbol: str | None = None,
    symbol_id: int | None = None,
) -> int:
    return call(pure._resolve_qty_scaled, value, scale, field_name, symbol, symbol_id)


def resolve_quote_qty_scaled(
    value: str | Decimal | Quantity,
    scale: int,
    field_name: str = "max_quote_debit",
    *,
    symbol: str | None = None,
    symbol_id: int | None = None,
) -> int:
    """Resolve a quote-debit budget. Typed values must carry the catalog quote scale."""
    return call(pure._resolve_quote_qty_scaled, value, scale, field_name, symbol, symbol_id)


def resolve_asset_amount_scaled(
    value: str | Decimal | AssetAmount,
    scale: int,
    field_name: str = "amount",
    *,
    domain: QuantityDomain = QuantityDomain.ASSET,
    asset_id: int | None = None,
) -> int:
    if isinstance(value, AssetAmount):
        value.compatible_with(domain=domain, scale=scale, asset_id=asset_id)
        if value.scaled <= 0:
            raise PolyesterValidationError(f"{field_name} must be positive")
        return value.scaled
    if isinstance(value, Quantity):
        raise PolyesterValidationError(f"{field_name} expects AssetAmount, not order Quantity")
    if isinstance(value, (int, float, bool)) and not isinstance(value, Decimal):
        raise PolyesterValidationError(
            f"{field_name} must be a decimal string, Decimal, or AssetAmount "
            "(use AssetAmount.from_scaled for scaled ints)"
        )
    return parse_qty_scaled(value, scale, field_name)


def resolve_asset_amount_scaled_with_input_scale(
    value: str | Decimal | AssetAmount,
    input_scale: int | None,
    target_scale: int,
    field_name: str = "amount",
    *,
    asset_id: int | None = None,
) -> int:
    """Rescale an asset amount exactly from its declared scale to ``target_scale``."""
    validate_protocol_scale(target_scale)
    if input_scale is not None:
        validate_protocol_scale(input_scale)
    if isinstance(value, AssetAmount):
        if value.asset_id is not None and asset_id is not None and value.asset_id != asset_id:
            raise PolyesterValidationError(
                f"amount asset_id mismatch: value is for {value.asset_id}, "
                f"destination is {asset_id}"
            )
        if value.scale is not None and input_scale is not None and value.scale != input_scale:
            raise PolyesterValidationError(
                f"{field_name} scale mismatch: value scale is {value.scale}, "
                f"input scale is {input_scale}"
            )
        source_scale = value.scale if value.scale is not None else input_scale
        if source_scale is None:
            raise PolyesterValidationError(
                f"{field_name} requires a declared input scale on AssetAmount or input_scale="
            )
        validate_protocol_scale(source_scale)
        scaled = value.scaled
    else:
        if input_scale is None:
            raise PolyesterValidationError(f"{field_name} requires input_scale")
        validate_protocol_scale(input_scale)
        source_scale = input_scale
        scaled = decimal_to_scaled(value, source_scale, field_name)

    if scaled <= 0:
        raise PolyesterValidationError(f"{field_name} must be positive")
    if source_scale < target_scale:
        scaled *= 10 ** (target_scale - source_scale)
    elif source_scale > target_scale:
        divisor = 10 ** (source_scale - target_scale)
        scaled, remainder = divmod(scaled, divisor)
        if remainder:
            raise PolyesterValidationError(
                f"{field_name} cannot be rescaled exactly from scale {source_scale} "
                f"to {target_scale}"
            )
    if scaled >= 1 << 128:
        raise PolyesterValidationError(f"{field_name} exceeds uint128 range")
    return scaled


__all__ = [
    "AssetAmount",
    "PRICE_TICK_SCALE",
    "Price",
    "Quantity",
    "QuantityDomain",
    "resolve_asset_amount_scaled",
    "resolve_asset_amount_scaled_with_input_scale",
    "resolve_price_ticks",
    "resolve_qty_scaled",
    "resolve_quote_qty_scaled",
]
