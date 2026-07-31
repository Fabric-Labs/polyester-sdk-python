"""Unit tests for Price/Quantity/AssetAmount dual-path scalars."""

from decimal import Decimal

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import (
    create_order_to_proto,
    normalize_create_order_request,
    preview_order_to_proto,
    resolve_quote_quantity_scale,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.types.money import (
    AssetAmount,
    Price,
    Quantity,
    QuantityDomain,
    resolve_asset_amount_scaled,
    resolve_asset_amount_scaled_with_input_scale,
    resolve_price_ticks,
    resolve_qty_scaled,
    resolve_quote_qty_scaled,
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

    quote = Quantity.from_quote_decimal_str("12.34", 2, symbol="BTC-USD")
    req2 = normalize_create_order_request(
        symbol="BTC-USD",
        side="buy",
        order_type="market",
        max_quote_debit=quote,
    )
    proto2 = create_order_to_proto(req2, quote_quantity_scale=2)
    assert proto2.order.max_quote_debit_scaled == 1234


def test_preview_order_wraps_order_intent() -> None:
    req = normalize_create_order_request(
        symbol="BTC-USD",
        side="buy",
        order_type="market",
        max_quote_debit=Decimal("12.34"),
        fee_asset="base",
        sub_account_id=format_id(99),
    )
    preview = preview_order_to_proto(req, quote_quantity_scale=2)
    assert preview.subaccount_id == 99
    assert preview.HasField("order")
    assert preview.order.symbol == "BTC-USD"
    assert preview.order.side == orders_pb2.BUY
    assert preview.order.WhichOneof("sizing") == "max_quote_debit_scaled"
    assert preview.order.max_quote_debit_scaled == 1234
    assert preview.order.WhichOneof("execution") == "market_ioc"
    assert preview.order.fee_asset == orders_pb2.BASE


def test_quote_budget_requires_matching_catalog_scale() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USD",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    quote = Quantity.from_quote_scaled(5_000_000, 6, symbol="BTC-USD")
    assert resolve_quote_quantity_scale(catalogs, "BTC-USD", quote) == 6
    assert resolve_quote_qty_scaled(quote, 6, symbol="BTC-USD") == 5_000_000

    wrong_scale = Quantity.from_quote_scaled(5_000_000, 8)
    with pytest.raises(PolyesterValidationError, match="scale mismatch"):
        resolve_quote_quantity_scale(catalogs, "BTC-USD", wrong_scale)

    missing_scale = Quantity.from_scaled(
        5_000_000, domain=QuantityDomain.ORDER_QUOTE
    )
    with pytest.raises(PolyesterValidationError, match="quote amount scale is required"):
        resolve_quote_quantity_scale(catalogs, "BTC-USD", missing_scale)
    with pytest.raises(PolyesterValidationError, match="quote amount scale is required"):
        resolve_quote_qty_scaled(missing_scale, 6)

    with pytest.raises(PolyesterValidationError, match="order_base or order_quote"):
        Quantity.from_scaled(1, domain=QuantityDomain.ASSET)


def test_asset_amount_without_value_or_parameter_scale_fails_closed() -> None:
    amount = AssetAmount.from_scaled(1, domain=QuantityDomain.LEDGER_E18, asset_id=7)
    with pytest.raises(PolyesterValidationError, match="declared input scale"):
        resolve_asset_amount_scaled_with_input_scale(
            amount, None, 18, asset_id=7
        )
    assert (
        resolve_asset_amount_scaled_with_input_scale(
            amount, 6, 18, asset_id=7
        )
        == 1_000_000_000_000
    )


def test_create_order_rejects_float_qty() -> None:
    with pytest.raises(PolyesterValidationError):
        normalize_create_order_request(symbol="BTC-USD", side="buy", order_type="limit", qty=0.1)
