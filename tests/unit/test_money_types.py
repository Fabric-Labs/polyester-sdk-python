"""Unit tests for Price/Quantity/AssetAmount dual-path scalars."""

from decimal import Decimal

import pytest

from polyester.codecs.orders import create_order_to_proto, normalize_create_order_request
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.types.money import (
    AssetAmount,
    Price,
    Quantity,
    QuantityDomain,
    resolve_asset_amount_scaled,
    resolve_price_ticks,
    resolve_qty_scaled,
)


def test_strict_decimal_rejects_excess_precision() -> None:
    with pytest.raises(PolyesterValidationError, match="at most 6"):
        resolve_price_ticks("50000.1234567")
    with pytest.raises(PolyesterValidationError, match="at most 8"):
        resolve_qty_scaled("0.123456789", 8)


def test_scaled_path_pass_through() -> None:
    qty = Quantity.from_scaled(100_000, scale=8, symbol="BTC-USD")
    price = Price.from_ticks(50_000_000_000, symbol="BTC-USD")
    assert resolve_qty_scaled(qty, 8, symbol="BTC-USD") == 100_000
    assert resolve_price_ticks(price, symbol="BTC-USD") == 50_000_000_000


def test_rejects_float_and_bare_int_and_bool() -> None:
    with pytest.raises(PolyesterValidationError):
        resolve_qty_scaled(0.1, 8)  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError):
        resolve_qty_scaled(1, 8)  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError):
        Quantity.from_scaled(True)  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError):
        Price.from_ticks(False)  # type: ignore[arg-type]


def test_domain_mismatch_rejected() -> None:
    amount = AssetAmount.from_scaled(100, domain=QuantityDomain.ASSET, asset_id=1)
    with pytest.raises(PolyesterValidationError, match="AssetAmount"):
        resolve_qty_scaled(amount, 8)  # type: ignore[arg-type]
    qty = Quantity.from_scaled(100, scale=8)
    with pytest.raises(PolyesterValidationError, match="order Quantity"):
        resolve_asset_amount_scaled(qty, 18)  # type: ignore[arg-type]


def test_symbol_mismatch_on_reuse() -> None:
    qty = Quantity.from_scaled(100_000, scale=8, symbol="BTC-USD")
    with pytest.raises(PolyesterValidationError, match="symbol mismatch"):
        resolve_qty_scaled(qty, 8, symbol="ETH-USD")


def test_create_order_accepts_decimal_and_scaled() -> None:
    req = normalize_create_order_request(
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        qty=Decimal("0.1"),
        price=Decimal("50000"),
    )
    proto = create_order_to_proto(req, quantity_scale=8)
    assert proto.order.base_qty_scaled == 10_000_000
    assert proto.order.limit_gtc.price_ticks == 50_000_000_000

    req2 = normalize_create_order_request(
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        qty=Quantity.from_scaled(10_000_000, scale=8, symbol="BTC-USD"),
        price=Price.from_ticks(50_000_000_000, symbol="BTC-USD"),
    )
    proto2 = create_order_to_proto(req2, quantity_scale=8)
    assert proto2.order.base_qty_scaled == proto.order.base_qty_scaled
    assert proto2.order.limit_gtc.price_ticks == proto.order.limit_gtc.price_ticks


def test_create_order_supports_quote_budget_sizing() -> None:
    req = normalize_create_order_request(
        symbol="BTC-USD",
        side="buy",
        order_type="market",
        max_quote_debit=Decimal("12.34"),
        fee_asset="base",
    )
    proto = create_order_to_proto(
        req,
        quantity_scale=8,
        quote_quantity_scale=2,
    )
    assert proto.order.WhichOneof("sizing") == "max_quote_debit_scaled"
    assert proto.order.max_quote_debit_scaled == 1234
    assert proto.order.fee_asset == orders_pb2.BASE


def test_create_order_rejects_float_qty() -> None:
    with pytest.raises(PolyesterValidationError):
        normalize_create_order_request(symbol="BTC-USD", side="buy", order_type="limit", qty=0.1)
