import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.correlation_id import optional_client_id, optional_request_id
from polyester.codecs.orders import cancel_all_orders_to_proto, create_order_to_proto
from polyester.errors import PolyesterValidationError
from polyester.models import CreateOrderRequest
from polyester.services.orders import AsyncOrdersService


def test_correlation_id_boundaries_and_charset() -> None:
    assert optional_client_id(None) is None
    assert optional_client_id("   ") is None
    assert optional_client_id(" A.B_c:1/2-3 ") == "A.B_c:1/2-3"
    assert optional_client_id("a" * 36) == "a" * 36
    assert optional_request_id("r" * 64) == "r" * 64

    for value in ("bad id", "id!", "a" * 37):
        with pytest.raises(PolyesterValidationError):
            optional_client_id(value)
    with pytest.raises(PolyesterValidationError):
        optional_request_id("r" * 65)


def test_order_encoders_reject_invalid_correlation_ids() -> None:
    request = CreateOrderRequest(
        symbol="BTC-USDT",
        side="buy",
        order_type="market",
        qty="1",
        client_order_id="bad id",
    )
    with pytest.raises(PolyesterValidationError, match="invalid characters"):
        create_order_to_proto(request, quantity_scale=8)

    with pytest.raises(PolyesterValidationError, match="invalid characters"):
        cancel_all_orders_to_proto(request_id="bad request")


@pytest.mark.asyncio
async def test_singular_order_methods_reject_invalid_client_order_id_before_transport() -> None:
    service = AsyncOrdersService(None, CatalogManager(), None)
    with pytest.raises(PolyesterValidationError, match="invalid characters"):
        await service.cancel(client_order_id="bad id!")
    with pytest.raises(PolyesterValidationError, match="invalid characters"):
        await service.get(client_order_id="bad id!")
