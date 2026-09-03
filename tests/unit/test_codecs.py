import pytest

from polyester.codecs import (
    align_price_ticks,
    format_id,
    format_price_ticks,
    id_to_int,
    parse_price_ticks,
    parse_qty_scaled,
)
from polyester.codecs.ledger import resolve_balance_range, resolve_equity_group_by
from polyester.codecs.orders import (
    cancel_all_orders_to_proto,
    create_order_to_proto,
    create_order_to_wire,
    modify_order_to_proto,
    normalize_create_order_request,
)
from polyester.codecs.triggers import modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.models import ClientOrderId


def test_decimal_codecs_are_exact_integer_scaled() -> None:
    assert parse_price_ticks("50000.123456") == 50_000_123_456
    assert parse_qty_scaled("0.10000000", 8) == 10_000_000


def test_qty_string_accepts_trailing_zeros_beyond_scale() -> None:
    """POLY-4685: extra zeros past scale are padding, not extra precision."""
    assert parse_qty_scaled("1.500000000", 8) == 150_000_000
    assert parse_qty_scaled("1.500000000", 8) == parse_qty_scaled("1.5", 8)
    with pytest.raises(PolyesterValidationError, match="at most 8 decimal places"):
        parse_qty_scaled("1.500000001", 8)


def test_price_rejects_trailing_dot_and_accepts_trimmed_whitespace() -> None:
    with pytest.raises(PolyesterValidationError):
        parse_price_ticks("65000.")
    with pytest.raises(PolyesterValidationError):
        parse_price_ticks("65.")
    # Leading/trailing whitespace is trimmed (TS value.trim() parity).
    assert parse_price_ticks(" 65000") == 65_000_000_000
    assert parse_price_ticks("65000 ") == 65_000_000_000
    assert parse_price_ticks("65000.0") == 65_000_000_000


def test_create_order_rejects_stray_price_on_market() -> None:
    req = normalize_create_order_request(
        symbol="BTC-USDT",
        symbol_id=1,
        side="buy",
        order_type="market",
        qty="0.01",
        price="65000",
    )
    with pytest.raises(PolyesterValidationError, match="price is not valid for market"):
        create_order_to_proto(req, quantity_scale=8)


def test_price_ticks_round_trip() -> None:
    ticks = align_price_ticks(600_123_456, "0.01")
    assert ticks == 600_120_000
    assert parse_price_ticks(format_price_ticks(ticks)) == ticks


def test_ids_round_trip_as_base58() -> None:
    encoded = format_id(123456)
    assert id_to_int(encoded) == 123456


def test_create_order_rejects_float_qty() -> None:
    with pytest.raises(PolyesterValidationError):
        normalize_create_order_request(symbol="BTC-USD", side="buy", order_type="limit", qty=0.1)


def test_modify_order_to_proto_requires_order_key() -> None:
    with pytest.raises(TypeError):
        modify_order_to_proto(symbol="BTC-USD", new_price="100")
    proto = modify_order_to_proto(
        symbol="BTC-USD",
        symbol_id=1,
        key=ClientOrderId("cid-1"),
        new_price="100",
    )
    assert proto.client_order_id == "cid-1"
    assert proto.new_price_ticks == 100_000_000


def test_ledger_range_codecs() -> None:
    assert resolve_balance_range("7d") == ledger_read_pb2.DAY_7
    assert resolve_equity_group_by("account") == ledger_read_pb2.GROUP_BY_ACCOUNT


def test_modify_trigger_to_proto() -> None:
    proto = modify_trigger_to_proto(trigger_id="1", symbol_id=1, trigger_price="100")
    assert proto.trigger_price_ticks == 100_000_000


def test_cancel_all_orders_to_proto() -> None:
    proto = cancel_all_orders_to_proto(symbol_id=3, dry_run=True)
    assert proto.dry_run is True
    assert proto.symbol_id == 3


def test_create_order_to_wire_maps_public_strings() -> None:
    request = normalize_create_order_request(
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        tif="gtc",
        qty="0.1",
        price="50000",
    )
    assert create_order_to_wire(request, quantity_scale=8) == {
        "symbol": "BTC-USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "timeInForce": "GTC",
        "qty_scaled": 10_000_000,
        "limit_price_ticks": 50_000_000_000,
    }
