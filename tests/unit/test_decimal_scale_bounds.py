"""Order quantity range, zero scale, Decimal size and execution-total scales."""

import json
import tracemalloc
from decimal import Decimal, localcontext

import pytest
from google.protobuf.json_format import MessageToDict, ParseDict

from polyester import AsyncPolyester, Quantity
from polyester.codecs.scalars import (
    INT64_MAX,
    INT64_MIN,
    format_price_ticks,
    format_qty_scaled,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.models.trading import Order, OrderFeeTotal
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

PAIRS = [
    {"symbol": "WIDE-USDT", "symbol_id": 7, "base_quantity_scale": 18, "quote_quantity_scale": 6},
    {"symbol": "BONK-USDT", "symbol_id": 5, "base_quantity_scale": 0, "quote_quantity_scale": 6},
    {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8, "quote_quantity_scale": 6},
]
_PREVIEW = orders.PreviewOrderResponse()
_PREVIEW.evaluated_at.seconds = 1
_RESPONSES = {
    "CreateOrder": (orders.CreateOrderRequest, orders.CreateOrderResponse(order_id=42)),
    "PreviewOrder": (orders.PreviewOrderRequest, _PREVIEW),
    "BatchCreateOrders": (orders.BatchCreateOrdersRequest, orders.BatchCreateOrdersResponse()),
}


async def _sent_quantities(json_wire: bool, method: str, symbol_id: int, qty) -> list[int]:
    """Send one order write for ``qty`` and return the base quantities received."""
    seen: list[int] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        name = req.path.rsplit("/", 1)[-1]
        request_type, response = _RESPONSES[name]
        request = (
            ParseDict(json.loads(req.body), request_type())
            if json_wire
            else request_type.FromString(req.body)
        )
        if name == "BatchCreateOrders":
            seen.extend(item.base_qty_scaled for item in request.items)
        else:
            seen.append(request.order.base_qty_scaled)
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    client.catalogs.hydrate_spot_config({"pairs": PAIRS})
    order = {"symbol_id": symbol_id, "side": "buy", "order_type": "limit", "qty": qty, "price": "1"}
    try:
        if method == "create":
            await client.orders.create(**order)
        elif method == "preview":
            await client.orders.preview_order(**order)
        else:
            await client.orders.batch_create(items=[order])
    finally:
        await client.aclose()
        await http.aclose()
    return seen


async def _refused_unsent(json_wire: bool, method: str, symbol_id: int, qty) -> str:
    with pytest.raises(PolyesterValidationError) as refused:
        seen = await _sent_quantities(json_wire, method, symbol_id, qty)
        pytest.fail(f"sent {seen}")
    return str(refused.value)


METHODS = ["create", "preview", "batch"]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("json_wire", [False, True])
async def test_order_write_refuses_quantity_beyond_int64_at_scale_18(json_wire, method):
    assert await _sent_quantities(json_wire, method, 7, "1") == [10**18]
    assert await _sent_quantities(json_wire, method, 7, "9.223372036854775807") == [INT64_MAX]
    for qty in ["10", "9.223372036854775808", Decimal("18.446744073709551615")]:
        message = await _refused_unsent(json_wire, method, 7, qty)
        assert message == "qty exceeds int64 range"


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("json_wire", [False, True])
async def test_order_write_decimal_quantity_at_known_zero_scale(json_wire, method):
    for qty in ["1000000", "1000000.000", Decimal("1E+6"), Quantity.from_scaled(1000000, scale=0)]:
        assert await _sent_quantities(json_wire, method, 5, qty) == [1000000]
    message = await _refused_unsent(json_wire, method, 5, "1000000.5")
    assert message.endswith("supports at most 0 decimal places: 1000000.5")
    assert await _sent_quantities(json_wire, method, 1, "0.00016") == [16000]
    with pytest.raises(PolyesterValidationError):
        await _sent_quantities(json_wire, method, 99, "1000000")


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "qty", [Decimal("1e-1000000"), Decimal("1e+1000000"), Decimal("1e-30"), Decimal("1e+30")]
)
async def test_order_write_bounds_decimal_exponents_before_expanding(method, qty):
    tracemalloc.start()
    try:
        message = await _refused_unsent(False, method, 1, qty)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(message) < 120, message
    # The refusal of 1e±1000000 used to build a million-digit string.
    assert peak < 512_000, peak


@pytest.mark.parametrize(
    ("value", "scale", "text"),
    [
        (INT64_MIN, 0, "-9223372036854775808"),
        (INT64_MIN, 9, "-9223372036.854775808"),
        (INT64_MIN, 18, "-9.223372036854775808"),
        (INT64_MIN, 36, "-0.000000000000000009223372036854775808"),
        (INT64_MIN + 1, 9, "-9223372036.854775807"),
        (INT64_MIN + 1, 18, "-9.223372036854775807"),
    ],
)
def test_formatters_min_int64(value, scale, text):
    assert format_qty_scaled(value, scale) == text
    if scale == 9:
        assert format_price_ticks(value) == text


def _high_scale_buy() -> Order:
    """1500 scaled base units at price 2, a 0.000001 quote fee, budget 1 at scale 6."""
    return Order(
        order_id="1",
        symbol_id=1,
        cum_qty=Quantity.from_scaled(1500),
        fee_asset="quote",
        cum_notional_scaled="3000000000000",
        fee_total=OrderFeeTotal(amount_e18="1000000000000", qty=Quantity.from_scaled(1500)),
        submitted_max_quote_debit_scaled="1000000",
    )


@pytest.mark.parametrize("scale", [8, 27, 28, 30, 36])
def test_execution_totals_at_every_catalog_base_scale(scale):
    order = _high_scale_buy()
    with localcontext(prec=100):  # exact expectations
        notional = Decimal(3).scaleb(3 - scale)
        used = notional + Decimal("0.000001")
        unspent = 1 - used
    assert order.cum_quote(scale) == notional
    assert order.quote_used(scale) == used
    assert order.quote_unspent(base_quantity_scale=scale, quote_quantity_scale=6) == unspent


@pytest.mark.parametrize("scale", [-1, 37])
def test_execution_totals_refuse_scales_outside_the_catalog_range(scale):
    order = _high_scale_buy()
    with pytest.raises(PolyesterValidationError):
        order.cum_quote(scale)
    with pytest.raises(PolyesterValidationError):
        order.quote_used(scale)
    with pytest.raises(PolyesterValidationError):
        order.quote_unspent(base_quantity_scale=scale, quote_quantity_scale=6)
    with pytest.raises(PolyesterValidationError):
        order.quote_unspent(base_quantity_scale=30, quote_quantity_scale=scale)


def test_decimal_size_bound_keeps_amounts_that_rescale_into_range():
    from polyester.types.money import resolve_asset_amount_scaled_with_input_scale

    # 1000 at scale 36 has 40 digits before it is rescaled to 1000 at scale 18.
    assert resolve_asset_amount_scaled_with_input_scale(Decimal("1000"), 36, 18) == 10**21
    assert resolve_asset_amount_scaled_with_input_scale(Decimal("1E+3"), 36, 18) == 10**21
    with pytest.raises(PolyesterValidationError, match="too large"):
        resolve_asset_amount_scaled_with_input_scale(Decimal("1E+1000000"), 36, 18)
