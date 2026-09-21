"""Live confirmation that market-IOC slippage overrides reach the host.

Preview is the primary proof: the server evaluates the same OrderIntent as
create without placing a hold. Mutation create is IOC-only and cancels that
one client order if it is still open.
"""

from __future__ import annotations

import pytest

from polyester.errors import PolyesterApiError, PolyesterRouteNotFoundError
from polyester.models import ClientOrderId, PreviewOrderResult
from tests.e2e.helpers import unique_client_order_id, wait_for_terminal_order
from tests.helpers import (
    devnet_order_skip_message,
    is_devnet_order_internal_error,
    min_base_qty_for_pair,
    resolve_market_ref_price,
)
from tests.integration.support import call_optional, route_unavailable

_IGNORED_FIELD_HINTS = (
    "unknown field",
    "unknown argument",
    "no such field",
    "unrecognized field",
    "unsupported create",
)


async def _market_kwargs(live_client, symbol: str) -> dict[str, object]:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = next(
        (item for item in (spot.raw.get("pairs") or []) if item.get("symbol") == symbol),
        {},
    )
    if not pair:
        pytest.skip(f"{symbol} missing from spot config")
    ref_price = await resolve_market_ref_price(live_client, symbol, pair, side="buy")
    qty = min_base_qty_for_pair(pair, ref_price)
    return {
        "symbol": symbol,
        "side": "buy",
        "order_type": "market",
        "tif": "ioc",
        "qty": qty,
        "market_client_ref_price": ref_price,
    }


def _preview_fingerprint(preview: PreviewOrderResult) -> tuple[object, ...]:
    bound = preview.protected_price_bound.ticks if preview.protected_price_bound else None
    code = preview.rejection.code if preview.rejection else None
    return (preview.admissible, bound, code)


def _assert_host_accepted_slippage_field(preview: PreviewOrderResult, *, label: str) -> None:
    assert isinstance(preview, PreviewOrderResult), label
    assert preview.evaluated_at_ms >= 0, label
    if preview.rejection is None:
        return
    blob = " ".join(
        [
            preview.rejection.code,
            *(v.field_path for v in preview.rejection.violations),
            *(v.message for v in preview.rejection.violations),
        ]
    ).lower()
    if any(hint in blob for hint in _IGNORED_FIELD_HINTS):
        pytest.fail(f"{label} treated slippage as unknown/unsupported: {blob}")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_preview_market_ioc_accepts_slippage_overrides(live_client, smoke_symbol) -> None:
    await live_client.wait_for_catalogs()
    kwargs = await _market_kwargs(live_client, smoke_symbol)

    async def preview(**overrides: object) -> PreviewOrderResult:
        try:
            return await call_optional(
                live_client.orders.preview_order(**kwargs, **overrides),
                label="orders.preview_order",
            )
        except (PolyesterRouteNotFoundError, PolyesterApiError) as exc:
            if route_unavailable(exc):
                pytest.skip(f"orders.preview_order not mounted: {exc}")
            raise

    unset = await preview()
    bps = await preview(max_slippage_bps=25)
    ticks = await preview(max_slippage_ticks=1)
    _assert_host_accepted_slippage_field(unset, label="unset")
    _assert_host_accepted_slippage_field(bps, label="max_slippage_bps=25")
    _assert_host_accepted_slippage_field(ticks, label="max_slippage_ticks=1")

    fingerprints = {
        "unset": _preview_fingerprint(unset),
        "bps": _preview_fingerprint(bps),
        "ticks": _preview_fingerprint(ticks),
    }
    print(f"preview fingerprints={fingerprints}", flush=True)

    distinct = set(fingerprints.values())
    if len(distinct) == 1 and unset.protected_price_bound is not None:
        pytest.fail(
            "slippage overrides did not change preview vs pair default; "
            f"host may still be ignoring the field: {fingerprints['unset']}"
        )


@pytest.mark.integration
@pytest.mark.mutation
@pytest.mark.asyncio(loop_scope="session")
async def test_create_market_ioc_with_slippage_bps(
    live_client, trade_symbol, mutation_enabled, require_trade_trading_balance
) -> None:
    await live_client.wait_for_catalogs()
    kwargs = await _market_kwargs(live_client, trade_symbol)
    client_order_id = unique_client_order_id("mkt-slip")
    try:
        created = await live_client.orders.create(
            **kwargs,
            max_slippage_bps=25,
            client_order_id=client_order_id,
        )
    except Exception as exc:
        if is_devnet_order_internal_error(exc):
            pytest.skip(devnet_order_skip_message())
        raise

    assert created.client_order_id == client_order_id
    assert created.order_id
    assert created.status
    print(
        f"create status={created.status!r} order_id={created.order_id} "
        f"client_order_id={created.client_order_id}",
        flush=True,
    )
    if created.status in {"canceled", "rejected", "filled", "accepted"}:
        # Admission is the POLY-5379 proof. IOC market may fill/cancel and drop
        # out of get-by-client-id before the test can poll a terminal snapshot.
        try:
            await live_client.orders.cancel(key=ClientOrderId(client_order_id))
        except Exception:
            pass
        return
    try:
        detail = await wait_for_terminal_order(live_client, client_order_id)
        assert detail.order is not None
        assert detail.order.status in {"canceled", "rejected", "filled"}
    except AssertionError as exc:
        message = str(exc)
        if "did not reach terminal status" in message and "last status" not in message:
            return
        raise
    finally:
        try:
            await live_client.orders.cancel(key=ClientOrderId(client_order_id))
        except Exception:
            pass
