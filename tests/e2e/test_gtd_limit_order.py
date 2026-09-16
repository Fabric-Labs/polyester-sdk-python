from datetime import UTC, datetime, timedelta

import pytest

from polyester.models import ClientOrderId
from tests.e2e.helpers import (
    unique_client_order_id,
    usdt_funded_buy_limit_params,
    wait_for_no_open_order,
    wait_for_open_order,
)
from tests.helpers import (
    DevnetOrderNotIndexedError,
    devnet_order_read_index_skip_message,
    devnet_order_skip_message,
    is_devnet_order_internal_error,
)

pytestmark = [
    pytest.mark.account_wide_cleanup,
    pytest.mark.usefixtures("account_wide_cleanup_enabled"),
]


def _gtd_unsupported(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "gtd",
            "expire_at",
            "expireat",
            "time_in_force",
            "timeinforce",
            "unimplemented",
            "not implemented",
        )
    )


@pytest.mark.integration
@pytest.mark.mutation
async def test_gtd_limit_order_round_trip(
    live_client, trade_symbol, mutation_enabled, require_trade_trading_balance
):
    price, qty = await usdt_funded_buy_limit_params(live_client, trade_symbol)
    client_order_id = unique_client_order_id("gtd")
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0)
    expires_at_text = expires_at.isoformat().replace("+00:00", "Z")

    try:
        created = await live_client.orders.create(
            symbol=trade_symbol,
            side="buy",
            order_type="limit",
            tif="gtd",
            qty=qty,
            price=price,
            post_only=True,
            expires_at=expires_at_text,
            client_order_id=client_order_id,
        )
    except Exception as exc:
        if is_devnet_order_internal_error(exc) or _gtd_unsupported(exc):
            pytest.skip(devnet_order_skip_message())
        raise
    assert created.status
    assert created.client_order_id == client_order_id
    assert created.order_id

    try:
        open_order = await wait_for_open_order(live_client, client_order_id)
    except DevnetOrderNotIndexedError:
        pytest.skip(devnet_order_read_index_skip_message())
    assert open_order.tif == "gtd"
    assert open_order.expire_at
    assert open_order.client_order_id == client_order_id

    detail = await live_client.orders.get(key=ClientOrderId(client_order_id))
    assert detail.order is not None
    assert detail.order.tif == "gtd"
    assert detail.order.expire_at
    assert detail.order.order_id == created.order_id

    try:
        cancelled = await live_client.orders.cancel(
            key=ClientOrderId(client_order_id),
            symbol=trade_symbol,
        )
        assert cancelled.status
        await wait_for_no_open_order(live_client, client_order_id)
    finally:
        await live_client.orders.cancel_all(symbol=trade_symbol, dry_run=False)
