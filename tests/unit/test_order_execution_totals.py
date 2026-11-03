"""Orders carry their exact execution totals: ``avg_price_e18``, ``cum_notional``
and ``fee_total`` (contract notes 1921Z and 0308Z)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polyester.codecs.decode.orders import get_order_from_proto, order_from_proto
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.transport import TransportConfig, codec_for_config


def _u128(value: int) -> dict[str, int]:
    return {"hi": value >> 64, "lo": value & ((1 << 64) - 1)}


def _spent_buy(*, fee_asset: int = orders_pb2.QUOTE, is_rebate: bool = False,
               fee_qty: int = 4_148_504) -> orders_read_pb2.Order:
    # The 0308Z example: a market buy of 6000 USDT stopped by its price limit.
    order = orders_read_pb2.Order(
        order_id=7,
        symbol_id=1,
        side=orders_pb2.BUY,
        status=orders_read_pb2.CANCELED,
        cum_qty_scaled=4_148_504,
        avg_price_ticks=77_511_000_000_000,
        submitted_max_quote_debit_scaled=6_000_000_000,
        fee_asset=fee_asset,  # type: ignore[arg-type]
    )
    order.cum_notional.CopyFrom(order.cum_notional.__class__(**_u128(321558095317280000000)))
    order.avg_price_e18.CopyFrom(order.avg_price_e18.__class__(**_u128(77_511_000_000_000_000_000_000)))
    order.fee_total.qty_scaled = fee_qty
    order.fee_total.is_rebate = is_rebate
    order.fee_total.amount_e18.lo = 964674285951840000
    return order


def test_exact_totals_decode_without_floats() -> None:
    order = order_from_proto(_spent_buy())

    assert order.cum_notional_scaled == "321558095317280000000"
    assert order.cum_quote(8) == Decimal("3215.5809531728")
    assert order.fee_total is not None
    assert order.fee_total.amount_e18 == "964674285951840000"
    assert order.fee_total.amount == Decimal("0.96467428595184")
    assert not order.fee_total.is_rebate
    assert order.fee_total.qty is not None and order.fee_total.qty.scaled == 4_148_504


def test_avg_price_is_exact_at_18_decimals() -> None:
    msg = orders_read_pb2.Order(order_id=7, symbol_id=1, cum_qty_scaled=7_000_000,
                                avg_price_ticks=2908)
    msg.avg_price_e18.lo = 2908714285714
    order = order_from_proto(msg)

    assert order.avg_price == Decimal("0.000002908714285714")
    # avg_px keeps the 9-decimal average, rounded down.
    assert order.avg_px is not None and order.avg_px.ticks == 2908


def test_unset_totals_read_as_no_fills() -> None:
    order = order_from_proto(orders_read_pb2.Order(order_id=7, symbol_id=1))

    assert order.avg_price is None
    assert order.cum_notional_scaled == "0"
    assert order.cum_quote(8) == Decimal(0)
    assert order.fee_total is None
    assert order.quote_used(8) == Decimal(0)


def test_quote_used_and_unspent_follow_the_fee_asset() -> None:
    quote_fee = order_from_proto(_spent_buy())
    assert quote_fee.quote_used(8) == Decimal("3216.54562745875184")
    assert quote_fee.quote_unspent(quote_quantity_scale=6, base_quantity_scale=8) == Decimal(
        "2783.45437254124816"
    )

    rebate = order_from_proto(_spent_buy(is_rebate=True))
    assert rebate.quote_used(8) == Decimal("3214.61627888684816")

    base_fee = order_from_proto(_spent_buy(fee_asset=orders_pb2.BASE))
    assert base_fee.quote_used(8) == Decimal("3215.5809531728")


def test_quote_used_waits_for_the_fee_of_every_fill() -> None:
    trailing = order_from_proto(_spent_buy(fee_qty=4_000_000))
    assert trailing.quote_used(8) is None
    assert trailing.quote_unspent(quote_quantity_scale=6, base_quantity_scale=8) is None

    # Open-order reads and stream updates carry no fee total.
    open_read = _spent_buy()
    open_read.ClearField("fee_total")
    assert order_from_proto(open_read).quote_used(8) is None


def test_scale_is_required_when_the_order_has_none() -> None:
    with pytest.raises(PolyesterValidationError, match="base_quantity_scale"):
        order_from_proto(_spent_buy()).quote_used()
    scaled = order_from_proto(_spent_buy(), quantity_scale=8)
    assert scaled.cum_quote() == Decimal("3215.5809531728")


def test_order_reads_json_and_stream_carry_the_totals() -> None:
    codec = codec_for_config(TransportConfig(api_url="https://example.test", wire_format="json"))
    decoded = codec.decode(
        b'{"order": {"orderId": "7", "symbolId": 1, "cumQtyScaled": "4148504",'
        b' "submittedMaxQuoteDebitScaled": "6000000000", "feeAsset": "QUOTE",'
        b' "cumNotional": {"hi": "17", "lo": "7963446064217622528"},'
        b' "feeTotal": {"amountE18": {"lo": "964674285951840000"}, "qtyScaled": "4148504"}}}',
        orders_read_pb2.GetOrderResponse(),
    )
    read = get_order_from_proto(decoded)
    assert read.order is not None
    assert read.order.cum_quote(8) == Decimal("3215.5809531728")
    assert read.order.quote_used(8) == Decimal("3216.54562745875184")

    unit = private_orders_unit_from_proto(pb.Unit(orders=[_spent_buy()]))
    assert unit.orders[0].cum_notional_scaled == "321558095317280000000"
