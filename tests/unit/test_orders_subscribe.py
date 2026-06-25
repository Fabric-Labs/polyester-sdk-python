from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.errors import PolyesterValidationError
from polyester.services.orders import AsyncOrdersService


@pytest.mark.asyncio
async def test_orders_subscribe_builds_private_channel() -> None:
    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(return_value="subscription")
    service = AsyncOrdersService(
        transport=MagicMock(),
        catalogs=MagicMock(),
        default_sub_account_id=None,
        default_account_id="acct_test",
        realtime=realtime,
    )

    result = await service.subscribe()

    assert result == "subscription"
    channel = realtime.subscribe_proto.await_args.args[0]
    assert channel == "private:spot:orders:acct_test:proto"


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
