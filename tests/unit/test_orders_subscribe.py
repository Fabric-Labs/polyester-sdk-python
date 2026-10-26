from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.errors import PolyesterValidationError
from polyester.services.orders import AsyncOrdersService


@pytest.mark.asyncio
async def test_orders_subscribe_uses_the_private_order_socket() -> None:
    realtime = MagicMock()
    realtime.subscribe_private_orders = AsyncMock(return_value="subscription")
    service = AsyncOrdersService(
        transport=MagicMock(),
        catalogs=MagicMock(),
        default_sub_account_id=None,
        default_account_id="acct_test",
        realtime=realtime,
    )

    result = await service.subscribe()

    assert result == "subscription"
    realtime.subscribe_private_orders.assert_awaited_once_with("acct_test")
    realtime.subscribe_proto.assert_not_called()


@pytest.mark.asyncio
async def test_orders_subscribe_requires_account_id() -> None:
    service = AsyncOrdersService(
        transport=MagicMock(),
        catalogs=MagicMock(),
        default_sub_account_id=None,
        realtime=MagicMock(),
    )
    with pytest.raises(PolyesterValidationError, match="account_id is required"):
        await service.subscribe()
