from pytest_httpserver import HTTPServer

from polyester.gen.orders.v1 import orders_read_pb2
from polyester.models import ClientOrderId
from polyester.services.orders import AsyncOrdersService, _get_order_execution_pages
from tests.unit.test_trigger_read_retry import _service


async def test_execution_pages_pin_the_returned_generation(httpserver: HTTPServer):
    path = "/orders.v1.OrdersReadService/GetOrder"
    for token, qty in [("older-executions", 40), ("", 60)]:
        body = orders_read_pb2.GetOrderResponse(
            order=orders_read_pb2.Order(
                order_id=9, cum_qty_scaled=100, inherited_cum_qty_scaled=40
            ),
            trades=[orders_read_pb2.UserTrade(order_id=9, qty_scaled=qty)],
            next_page_token=token,
        ).SerializeToString()
        httpserver.expect_oneshot_request(path, method="POST").respond_with_data(
            body,
            content_type="application/proto",
        )
    _, transport = _service(httpserver)
    try:
        result = await _get_order_execution_pages(
            AsyncOrdersService(transport, None, None),
            key=ClientOrderId("reused-client-id"),
        )
    finally:
        await transport.aclose()
    assert len(httpserver.log) == 2
    requests = [orders_read_pb2.GetOrderRequest.FromString(req.data) for req, _ in httpserver.log]
    assert requests[0].client_order_id == "reused-client-id"
    assert requests[1].order_id == 9
    assert requests[1].page_token == "older-executions"
    assert result.order.cum_qty.scaled == 100
    assert sum(trade.qty.scaled for trade in result.trades) == 100
