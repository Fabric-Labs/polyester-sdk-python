"""Account and sub-account IDs that decode to 0 are refused before sending.

On the wire 0 is unset: a sub-account ID of 0 is the main account, and an
account ID of 0 names no account. ``"1"`` is the public ID of 0
(``format_id(0)``), and ``"0"`` and ``"00"`` read as decimal 0. Each form an
ID arrives in is passed to a client against a local server that counts every
request, and nothing may reach it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.codecs.address_book import create_entry_to_proto
from polyester.codecs.orders import (
    batch_cancel_orders_to_proto,
    batch_create_orders_to_proto,
    batch_replace_orders_to_proto,
    cancel_all_after_to_proto,
    cancel_all_orders_to_proto,
    create_order_to_proto,
    modify_order_to_proto,
    parse_optional_subaccount_id,
    preview_order_to_proto,
)
from polyester.codecs.scalars import format_id
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterRouteNotFoundError, PolyesterValidationError
from polyester.models import CreateOrderRequest, OrderId
from polyester.services._scope import resolve_account_id
from tests.hardening_support import HttpScript, MockHttpServer, ParsedRequest, make_test_credentials

ZERO_STRINGS = ["0", "00", "1"]
REFUSED = "must be a non-zero"


def _refuse_all(_req: ParsedRequest) -> HttpScript:
    return HttpScript.not_found()


@asynccontextmanager
async def zero_id_client(**config: Any) -> AsyncIterator[tuple[AsyncPolyester, MockHttpServer]]:
    http = await MockHttpServer.spawn(_refuse_all)
    creds = make_test_credentials()
    config.setdefault("default_account_id", format_id(7))
    client = AsyncPolyester(
        api_url=http.base_url,
        ws_url=http.base_url.replace("http", "ws", 1) + "/connection/websocket",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        timeout=5.0,
        **config,
    )
    # A hydrated pair, so order and trigger writes get as far as the wire.
    client.catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    try:
        yield client, http
    finally:
        await client.aclose()
        await http.aclose()


def _order(**fields: Any) -> CreateOrderRequest:
    return CreateOrderRequest(
        symbol="BTC-USDT", side="buy", order_type="limit", qty="0.1", price="50000", **fields
    )


Call = Callable[[AsyncPolyester, dict[str, Any]], Awaitable[Any]]
TRIGGER = format_id(42)

# Every client method that takes a sub-account scope, called with ``scope``
# (``sub_account_id=`` or ``account=``) added to its arguments.
SCOPED_CALLS: dict[str, Call] = {
    "orders.create": lambda c, s: c.orders.create(
        _order(sub_account_id=s["sub_account_id"]) if "sub_account_id" in s else _order(),
        account=s.get("account"),
    ),
    "orders.preview_order": lambda c, s: c.orders.preview_order(
        _order(sub_account_id=s["sub_account_id"]) if "sub_account_id" in s else _order(),
        account=s.get("account"),
    ),
    "orders.list_open": lambda c, s: c.orders.list_open(**s),
    "orders.list_history": lambda c, s: c.orders.list_history(**s),
    "orders.get": lambda c, s: c.orders.get(key=OrderId(42), **s),
    "orders.cancel": lambda c, s: c.orders.cancel(key=OrderId(42), symbol_id=1, **s),
    "orders.modify": lambda c, s: c.orders.modify(
        key=OrderId(42), symbol="BTC-USDT", new_price="50001", **s
    ),
    "orders.cancel_all": lambda c, s: c.orders.cancel_all(dry_run=True, **s),
    "orders.cancel_all_after": lambda c, s: c.orders.cancel_all_after(timeout_sec=10, **s),
    "orders.batch_create": lambda c, s: c.orders.batch_create(items=[_order()], **s),
    "orders.batch_cancel": lambda c, s: c.orders.batch_cancel(
        items=[{"key": OrderId(42), "symbol_id": 1}], **s
    ),
    "orders.batch_replace": lambda c, s: c.orders.batch_replace(
        items=[{"key": OrderId(42), "new_price": "50001"}], symbol="BTC-USDT", **s
    ),
    "orders.get_batch_replace_status": lambda c, s: c.orders.get_batch_replace_status(
        batch_request_id=format_id(42), **s
    ),
    "balances.list": lambda c, s: c.balances.list(**s),
    "balances.get_balance_history": lambda c, s: c.balances.get_balance_history(**s),
    "balances.get_equity_history": lambda c, s: c.balances.get_equity_history(**s),
    "fees.get_spot_fee_rates": lambda c, s: c.fees.get_spot_fee_rates(**s),
    "rate_limits.get_trading_rate_limits": lambda c, s: c.rate_limits.get_trading_rate_limits(**s),
    "triggers.list": lambda c, s: c.triggers.list(**s),
    "triggers.get": lambda c, s: c.triggers.get(trigger_id=TRIGGER, **s),
    "triggers.create": lambda c, s: c.triggers.create(
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="0.1",
        trigger_price="49000",
        order_type="market",
        **s,
    ),
    "triggers.cancel": lambda c, s: c.triggers.cancel(trigger_id=TRIGGER, **s),
    "triggers.pause": lambda c, s: c.triggers.pause(trigger_id=TRIGGER, **s),
    "triggers.resume": lambda c, s: c.triggers.resume(trigger_id=TRIGGER, **s),
    "triggers.modify": lambda c, s: c.triggers.modify(
        trigger_id=TRIGGER, trigger_price="49000", **s
    ),
    "triggers.list_events": lambda c, s: c.triggers.list_events(trigger_id=TRIGGER, **s),
    "trades.list": lambda c, s: c.trades.list(**s),
    "transfers.list": lambda c, s: c.transfers.list(**s),
    "api_keys.list": lambda c, s: c.api_keys.list(**s),
    "sub_accounts.get": lambda c, s: c.sub_accounts.get(**s),
    "sub_accounts.list_members": lambda c, s: c.sub_accounts.list_members(**s),
    "sub_accounts.list_activity": lambda c, s: c.sub_accounts.list_activity(**s),
    "address_book.list_entries": lambda c, s: c.address_book.list_entries(**s),
    "address_book.get_view": lambda c, s: c.address_book.get_view(**s),
    "address_book.create_tag": lambda c, s: c.address_book.create_tag(name="desk", **s),
    "deposit.list_addresses": lambda c, s: c.deposit.list_addresses(chain_id=1, **s),
    "guard_signer.get_status": lambda c, s: c.guard_signer.get_status(**s),
}


def _scopes(zero: str) -> dict[str, dict[str, Any]]:
    return {
        "sub_account_id": {"sub_account_id": zero},
        "account string": {"account": zero},
        "account subaccountId": {"account": {"subaccountId": zero}},
        "account sub_account_id": {"account": {"sub_account_id": zero}},
    }


async def _refused(call: Awaitable[Any], http: MockHttpServer, label: str) -> None:
    before = http.request_count
    with pytest.raises(PolyesterValidationError, match=f"{label} {REFUSED}"):
        await call
    assert http.request_count == before, "a request was sent"


@pytest.mark.asyncio
@pytest.mark.parametrize("zero", ZERO_STRINGS)
@pytest.mark.parametrize("name", sorted(SCOPED_CALLS))
async def test_zero_sub_account_id_is_refused_before_sending(name: str, zero: str) -> None:
    call = SCOPED_CALLS[name]
    async with zero_id_client() as (client, http):
        for form, scope in _scopes(zero).items():
            try:
                await _refused(call(client, scope), http, "sub_account_id")
            except BaseException as exc:
                raise AssertionError(f"{name} {form} {zero!r}: {exc!r}") from exc


@pytest.mark.asyncio
@pytest.mark.parametrize("zero", ZERO_STRINGS)
@pytest.mark.parametrize("name", sorted(SCOPED_CALLS))
async def test_zero_default_sub_account_id_is_refused_before_sending(name: str, zero: str) -> None:
    async with zero_id_client(default_sub_account_id=zero) as (client, http):
        await _refused(SCOPED_CALLS[name](client, {}), http, "sub_account_id")


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [{}, {"sub_account_id": ""}, {"sub_account_id": format_id(42)}])
async def test_omitted_and_non_zero_sub_accounts_still_send(scope: dict[str, Any]) -> None:
    async with zero_id_client() as (client, http):
        with pytest.raises(PolyesterRouteNotFoundError):  # the server refuses every call
            await client.balances.list(**scope)
        assert http.request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("zero", ZERO_STRINGS)
async def test_zero_batch_item_sub_account_id_is_refused(zero: str) -> None:
    async with zero_id_client() as (client, http):
        before = http.request_count
        with pytest.raises(PolyesterValidationError):
            await client.orders.batch_create(items=[_order(sub_account_id=zero)])
        assert http.request_count == before


ZERO_FORMS: list[str | int] = [*ZERO_STRINGS, 0]

# The exported codecs that encode a sub-account ID, called with ``sub``.
CODECS: dict[str, Callable[[Any], Any]] = {
    "parse_optional_subaccount_id": parse_optional_subaccount_id,
    "create_order_to_proto": lambda sub: create_order_to_proto(
        _order(symbol_id=1, sub_account_id=sub), quantity_scale=8, quote_quantity_scale=6
    ),
    "preview_order_to_proto": lambda sub: preview_order_to_proto(
        _order(symbol_id=1, sub_account_id=sub), quantity_scale=8, quote_quantity_scale=6
    ),
    "batch_create_orders_to_proto": lambda sub: batch_create_orders_to_proto(
        items=[_order(symbol_id=1)], sub_account_id=sub, quantity_scale=8
    ),
    "batch_cancel_orders_to_proto": lambda sub: batch_cancel_orders_to_proto(
        items=[{"key": OrderId(42), "symbol_id": 1}], sub_account_id=sub
    ),
    "batch_replace_orders_to_proto": lambda sub: batch_replace_orders_to_proto(
        items=[{"key": OrderId(42), "new_price": "50001"}],
        symbol_id=1,
        symbol="BTC-USDT",
        sub_account_id=sub,
        quantity_scale=8,
    ),
    "modify_order_to_proto": lambda sub: modify_order_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        key=OrderId(42),
        sub_account_id=sub,
        new_price="50001",
        quantity_scale=8,
    ),
    "cancel_all_orders_to_proto": lambda sub: cancel_all_orders_to_proto(sub_account_id=sub),
    "cancel_all_after_to_proto": lambda sub: cancel_all_after_to_proto(
        sub_account_id=sub, timeout_sec=10
    ),
    "create_trigger_to_proto": lambda sub: create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="stop_loss",
        side="sell",
        qty="0.1",
        trigger_price="49000",
        order_type="market",
        sub_account_id=sub,
        quantity_scale=8,
    ),
    "modify_trigger_to_proto": lambda sub: modify_trigger_to_proto(
        trigger_id=TRIGGER, symbol_id=1, sub_account_id=sub, trigger_price="49000"
    ),
}


@pytest.mark.parametrize("zero", ZERO_FORMS)
@pytest.mark.parametrize("name", sorted(CODECS))
def test_zero_sub_account_id_public_codecs_are_refused(name: str, zero: str | int) -> None:
    with pytest.raises(PolyesterValidationError, match=f"sub_account_id {REFUSED}"):
        CODECS[name](zero)


def test_zero_address_book_entry_codec_is_refused() -> None:
    # create_entry_to_proto takes the decoded wire ID.
    with pytest.raises(PolyesterValidationError, match=f"subaccount_id {REFUSED}"):
        create_entry_to_proto(
            subaccount_id=0,
            label="desk",
            note="",
            address="0xabc",
            polychain_chain_id=1,
            smart_account_address=None,
            tag_ids=None,
            new_tags=None,
        )


def test_non_zero_codec_ids_are_kept() -> None:
    assert parse_optional_subaccount_id(format_id(42)) == 42
    assert parse_optional_subaccount_id(None) is None
    assert parse_optional_subaccount_id("") is None
    assert cancel_all_orders_to_proto(sub_account_id=format_id(42)).subaccount_id == 42


SUBSCRIBES: dict[str, Callable[[AsyncPolyester, Any], Awaitable[Any]]] = {
    "api_keys.subscribe": lambda c, a: c.api_keys.subscribe(account_id=a),
    "balances.subscribe": lambda c, a: c.balances.subscribe(account_id=a),
    "lifecycle.subscribe_open_flows": lambda c, a: c.lifecycle.subscribe_open_flows(account_id=a),
    "orders.subscribe": lambda c, a: c.orders.subscribe(account_id=a),
    "policies.subscribe_subaccount_policies": lambda c, a: c.policies.subscribe_subaccount_policies(
        account_id=a
    ),
    "policies.subscribe_api_policies": lambda c, a: c.policies.subscribe_api_policies(account_id=a),
    "sub_accounts.subscribe": lambda c, a: c.sub_accounts.subscribe(account_id=a),
    "sub_accounts.subscribe_api_keys": lambda c, a: c.sub_accounts.subscribe_api_keys(account_id=a),
    "trades.subscribe": lambda c, a: c.trades.subscribe(account_id=a),
    "transfers.subscribe": lambda c, a: c.transfers.subscribe(account_id=a),
    "triggers.subscribe": lambda c, a: c.triggers.subscribe(account_id=a),
    "triggers.subscribe_events": lambda c, a: c.triggers.subscribe_events(account_id=a),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("zero", ZERO_STRINGS)
@pytest.mark.parametrize("name", sorted(SUBSCRIBES))
async def test_zero_account_id_is_refused_before_subscribing(name: str, zero: str) -> None:
    async with zero_id_client() as (client, http):
        await _refused(SUBSCRIBES[name](client, zero), http, "account_id")
    if name == "lifecycle.subscribe_open_flows":
        return  # an unset account is the public open-flows channel
    async with zero_id_client(default_account_id=zero) as (client, http):
        await _refused(SUBSCRIBES[name](client, None), http, "account_id")


@pytest.mark.parametrize("zero", ZERO_STRINGS)
def test_resolve_account_id_refuses_zero(zero: str) -> None:
    with pytest.raises(PolyesterValidationError, match=f"account_id {REFUSED}"):
        resolve_account_id(zero, None)
    with pytest.raises(PolyesterValidationError, match=f"account_id {REFUSED}"):
        resolve_account_id(None, zero)


@pytest.mark.asyncio
@pytest.mark.parametrize("zero", ZERO_FORMS)
async def test_zero_account_id_arguments_are_refused(zero: str | int) -> None:
    async with zero_id_client() as (client, http):
        await _refused(
            client.internal_transfers.create(
                asset_id=1,
                quantity="1",
                idempotency_key="idem-1",
                destination_account_id=zero,
                quantity_scale=18,
            ),
            http,
            "destination_account_id",
        )
        await _refused(
            client.internal_transfers.create(
                asset_id=1,
                quantity="1",
                idempotency_key="idem-1",
                destination_subaccount_id=zero,
                quantity_scale=18,
            ),
            http,
            "destination_subaccount_id",
        )
        await _refused(client.lifecycle.list_flows(owner_account_id=zero), http, "owner_account_id")
