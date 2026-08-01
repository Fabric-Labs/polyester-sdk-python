from __future__ import annotations

import pytest

from polyester.errors import PolyesterApiError, PolyesterRouteNotFoundError
from polyester.models import PreviewOrderResult
from tests.helpers import min_base_qty_for_pair, resolve_far_below_buy_limit_price
from tests.integration.support import call_optional, route_unavailable


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio(loop_scope="session")
async def test_preview_order_admission_shape(live_client, smoke_symbol) -> None:
    """Live PreviewOrder must return the admission-only public shape."""
    await live_client.wait_for_catalogs()
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = next(
        (
            item
            for item in (spot.raw.get("pairs") or [])
            if isinstance(item, dict) and item.get("symbol") == smoke_symbol
        ),
        None,
    )
    if pair is None:
        pytest.skip(f"smoke symbol {smoke_symbol!r} missing from spot config")

    price = await resolve_far_below_buy_limit_price(live_client, smoke_symbol, pair)
    qty = min_base_qty_for_pair(pair, price)

    try:
        preview = await call_optional(
            live_client.orders.preview_order(
                symbol=smoke_symbol,
                side="buy",
                order_type="limit",
                tif="gtc",
                qty=qty,
                price=price,
                post_only=True,
            ),
            label="orders.preview_order",
        )
    except (PolyesterRouteNotFoundError, PolyesterApiError) as exc:
        if route_unavailable(exc):
            pytest.skip(f"orders.preview_order not mounted: {exc}")
        raise

    assert isinstance(preview, PreviewOrderResult)
    assert preview.admissible is not None
    assert isinstance(preview.evaluated_at_ms, int)
    assert preview.evaluated_at_ms >= 0
    # Removed estimate fields must not exist on the public model.
    assert not hasattr(preview, "estimated_quote_debit")
    assert not hasattr(preview, "estimated_fee")
    assert not hasattr(preview, "price_bound")
    if preview.admissible:
        assert preview.rejection is None
        assert preview.resolved_base_qty_scaled != "" or preview.resolved_base_qty is not None
    else:
        assert preview.rejection is not None
        assert preview.rejection.code
        assert isinstance(preview.rejection.violations, list)
    if preview.protected_price_bound is not None:
        assert preview.protected_price_bound.ticks is not None
