from polyester.codecs.scalars import format_id
from polyester.codecs.wire_decode import (
    decode_balances_list,
    decode_order,
    decode_order_mutation,
    decode_orders_list,
)


def test_decode_order_from_connect_json_shape() -> None:
    order = decode_order(
        {
            "orderId": "42",
            "symbolId": 7,
            "clientOrderId": "cid-1",
            "side": "BUY",
            "status": "WORKING",
            "orderType": "LIMIT",
            "timeInForce": "GTC",
            "origQtyScaled": "1000",
            "leavesQtyScaled": "1000",
            "priceTicks": "12345",
        }
    )
    assert order.symbol_id == 7
    assert order.side == "buy"
    assert order.status == "working"
    assert order.order_type == "limit"
    assert order.orig_qty is not None and order.orig_qty.scaled == 1000
    assert order.client_order_id == "cid-1"


def test_decode_orders_list() -> None:
    result = decode_orders_list(
        {
            "orders": [{"orderId": "1", "symbolId": 2, "side": "SELL"}],
            "nextPageToken": "abc",
        }
    )
    assert len(result.orders) == 1
    assert result.next_page_token == "abc"


def test_decode_order_mutation() -> None:
    result = decode_order_mutation({"orderId": "99", "clientOrderId": "cid"})
    assert result.status == "accepted"
    assert result.order_id == format_id(99)
    assert result.client_order_id == "cid"
    canceled = decode_order_mutation({"status": "ACCEPTED", "orderId": "99"})
    assert canceled.status == "accepted"
    assert canceled.order_id == format_id(99)


def test_decode_balances_list() -> None:
    result = decode_balances_list(
        {
            "balances": [
                {
                    "assetId": 3,
                    "trading": {"hi": 0, "lo": 5},
                    "funding": {"hi": 0, "lo": 0},
                    "reserved": {"hi": 0, "lo": 0},
                    "available": {"hi": 0, "lo": 5},
                }
            ]
        }
    )
    assert len(result.balances) == 1
    assert result.balances[0].asset_id == 3
