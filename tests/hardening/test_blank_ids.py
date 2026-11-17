"""A supplied ID is an ID: empty or blank is refused, never read as absent.

Only ``None`` (or a field left out) means no ID. An empty string, whitespace,
or an ID with whitespace around it is refused with ``PolyesterValidationError``
before anything is sent: it never falls back to the main account, the client's
default, the public channel or no filter.
"""

from __future__ import annotations

from typing import Any

import pytest

import polyester.services.lifecycle as lifecycle_module
from polyester import AsyncPolyester, Polyester
from polyester.codecs.orders import (
    create_order_to_proto,
    create_order_to_wire,
    parse_optional_subaccount_id,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterRouteNotFoundError, PolyesterValidationError
from polyester.models import CreateOrderRequest
from polyester.services._scope import resolve_account_id
from tests.hardening.test_zero_ids import (
    SCOPED_CALLS,
    SUBSCRIBES,
    _refused,
    _scopes,
    zero_id_client,
)
from tests.hardening_support import make_test_credentials

BLANKS = ["", " ", "\t", " ", " 23", "23 "]
FLOW_BLANKS = ["", " ", "\t", " ", " flow_23", "flow_23 "]


# --- sub-account scopes --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize("name", sorted(SCOPED_CALLS))
async def test_blank_sub_account_scope_is_refused_before_sending(name: str, blank: str) -> None:
    call = SCOPED_CALLS[name]
    async with zero_id_client(default_sub_account_id=format_id(9)) as (client, http):
        for form, scope in _scopes(blank).items():
            try:
                await _refused(call(client, scope), http, "sub_account_id")
            except BaseException as exc:
                raise AssertionError(f"{name} {form} {blank!r}: {exc!r}") from exc


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [{}, {"sub_account_id": None}, {"account": "main"}])
async def test_an_absent_sub_account_still_sends(scope: dict[str, Any]) -> None:
    async with zero_id_client() as (client, http):
        with pytest.raises(PolyesterRouteNotFoundError):  # the server refuses every call
            await client.balances.list(**scope)
        assert http.request_count == 1


@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize("client_cls", [AsyncPolyester, Polyester])
def test_blank_default_sub_account_id_is_refused_when_the_client_is_made(
    client_cls: type, blank: str
) -> None:
    creds = make_test_credentials()
    with pytest.raises(PolyesterValidationError, match="default_sub_account_id must be a base58"):
        client_cls(
            api_url="http://127.0.0.1:9",
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
            default_sub_account_id=blank,
        )


@pytest.mark.parametrize("blank", BLANKS)
def test_blank_sub_account_codecs_are_refused(blank: str) -> None:
    order = dict(symbol="BTC-USDT", symbol_id=1, side="buy", order_type="limit", qty="0.1")
    with pytest.raises(PolyesterValidationError, match="sub_account_id"):
        parse_optional_subaccount_id(blank)
    with pytest.raises(PolyesterValidationError, match="sub_account_id"):
        create_order_to_proto(
            CreateOrderRequest(**order, price="1", sub_account_id=blank), quantity_scale=8
        )
    with pytest.raises(PolyesterValidationError, match="sub_account_id"):
        create_order_to_wire(
            CreateOrderRequest(**order, price="1", sub_account_id=blank), quantity_scale=8
        )


def test_absent_sub_account_codecs_name_no_sub_account() -> None:
    order = dict(symbol="BTC-USDT", symbol_id=1, side="buy", order_type="limit", qty="0.1")
    assert parse_optional_subaccount_id(None) is None
    proto = create_order_to_proto(CreateOrderRequest(**order, price="1"), quantity_scale=8)
    assert not proto.HasField("subaccount_id")
    assert "sub_account_id" not in create_order_to_wire(
        CreateOrderRequest(**order, price="1"), quantity_scale=8
    )


# --- account IDs of private subscriptions --------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize("name", sorted(SUBSCRIBES))
async def test_blank_account_id_is_refused_before_subscribing(name: str, blank: str) -> None:
    # The client has a default account, so a fallback would subscribe to it.
    async with zero_id_client() as (client, http):
        await _refused(SUBSCRIBES[name](client, blank), http, "account_id")
    if name == "lifecycle.subscribe_open_flows":
        return  # it takes no default account
    async with zero_id_client(default_account_id=blank) as (client, http):
        await _refused(SUBSCRIBES[name](client, None), http, "account_id")


@pytest.mark.parametrize("blank", BLANKS)
def test_resolve_account_id_never_falls_back_from_a_blank_id(blank: str) -> None:
    with pytest.raises(PolyesterValidationError, match="account_id must be a base58"):
        resolve_account_id(blank, format_id(7))
    with pytest.raises(PolyesterValidationError, match="account_id must be a base58"):
        resolve_account_id(None, blank)


def test_resolve_account_id_takes_the_default_only_when_none_is_given() -> None:
    assert resolve_account_id(None, format_id(7)) == format_id(7)
    assert resolve_account_id(format_id(8), format_id(7)) == format_id(8)
    assert resolve_account_id(8, None) == format_id(8)


@pytest.mark.asyncio
async def test_open_flows_without_an_account_id_is_the_public_feed(monkeypatch) -> None:
    routed: list[str] = []

    async def public(_realtime: Any, *, channel: str, decode: Any) -> str:
        routed.append(channel)
        return "public"

    async def private(
        _realtime: Any, *, channel_template: str, account_id: Any, default_account_id: Any, **_: Any
    ) -> str:
        # As the real one resolves it before subscribing.
        resolved = resolve_account_id(account_id, default_account_id)
        routed.append(channel_template.format(account_id=resolved))
        return "private"

    monkeypatch.setattr(lifecycle_module, "subscribe_public_proto", public)
    monkeypatch.setattr(lifecycle_module, "subscribe_account_proto", private)
    async with zero_id_client() as (client, _http):
        assert await client.lifecycle.subscribe_open_flows() == "public"
        assert await client.lifecycle.subscribe_open_flows(account_id=None) == "public"
        assert await client.lifecycle.subscribe_open_flows(account_id=format_id(7)) == "private"
        for blank in BLANKS:
            with pytest.raises(PolyesterValidationError, match="account_id"):
                await client.lifecycle.subscribe_open_flows(account_id=blank)
    assert routed == [
        "public:chain:lifecycle:flows:proto",
        "public:chain:lifecycle:flows:proto",
        f"private:chain:lifecycle:flows:{format_id(7)}:proto",
    ]


def test_blank_account_id_environment_variable_is_unset(monkeypatch) -> None:
    # Configuration, not a caller's ID: trimmed, and blank means unset.
    monkeypatch.setenv("POLYESTER_ACCOUNT_ID", "   ")
    assert AsyncPolyester.from_env(hydrate_catalogs=False).default_account_id is None
    monkeypatch.setenv("POLYESTER_ACCOUNT_ID", f"  {format_id(7)}\n")
    assert AsyncPolyester.from_env(hydrate_catalogs=False).default_account_id == format_id(7)


# --- order and trigger filters -------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize("method", ["list_open", "list_history"])
async def test_blank_trigger_id_filter_is_refused_not_dropped(method: str, blank: str) -> None:
    async with zero_id_client() as (client, http):
        await _refused(getattr(client.orders, method)(trigger_id=blank), http, "trigger_id")


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["list_open", "list_history"])
async def test_an_absent_trigger_id_filter_still_sends(method: str) -> None:
    async with zero_id_client() as (client, http):
        with pytest.raises(PolyesterRouteNotFoundError):
            await getattr(client.orders, method)(trigger_id=None)
        assert http.request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize(
    ("label", "call"),
    [
        ("trigger_id", lambda c, v: c.triggers.get(trigger_id=v)),
        ("trigger_id", lambda c, v: c.triggers.list_events(trigger_id=v)),
        ("parent_order_id", lambda c, v: c.triggers.list(parent_order_id=v)),
        ("order_list_id", lambda c, v: c.triggers.list(order_list_id=v)),
        ("order_id", lambda c, v: c.trades.list(order_id=v)),
        ("lineage_id", lambda c, v: c.trades.list(lineage_id=v)),
        ("alert_id", lambda c, v: c.alerts.cancel(alert_id=v)),
        (
            "address_book_entry_id",
            lambda c, v: c.address_book.delete_entry(address_book_entry_id=v),
        ),
        ("tag_id", lambda c, v: c.address_book.delete_tag(tag_id=v)),
    ],
)
async def test_blank_order_trigger_alert_and_address_book_ids_are_refused(
    label: str, call: Any, blank: str
) -> None:
    async with zero_id_client() as (client, http):
        await _refused(call(client, blank), http, label)


# --- lifecycle flow IDs --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", FLOW_BLANKS)
@pytest.mark.parametrize(
    "call",
    [
        lambda c, v: c.lifecycle.get_flow(flow_id=v),
        lambda c, v: c.lifecycle.get_flow(intent_id=v),
        # A supplied flow_id is used, never replaced by intent_id.
        lambda c, v: c.lifecycle.get_flow(flow_id=v, intent_id="flow_23"),
        lambda c, v: c.lifecycle.get_account_flow(flow_id=v),
        lambda c, v: c.lifecycle.subscribe_flow_detail(flow_id=v),
    ],
)
async def test_blank_flow_id_is_refused_before_sending(call: Any, blank: str) -> None:
    async with zero_id_client() as (client, http):
        before = http.request_count
        with pytest.raises(PolyesterValidationError, match="flow_id|intent_id"):
            await call(client, blank)
        assert http.request_count == before, "a request was sent"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.lifecycle.get_flow(flow_id="flow_23"),
        lambda c: c.lifecycle.get_flow(intent_id="flow_23"),
        lambda c: c.lifecycle.get_account_flow(flow_id="flow_23"),
    ],
)
async def test_a_flow_id_is_still_sent(call: Any) -> None:
    async with zero_id_client() as (client, http):
        with pytest.raises(PolyesterRouteNotFoundError):
            await call(client)
        assert http.request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", [*BLANKS, " 0x" + "ab" * 20, "0x" + "ab" * 20 + " "])
async def test_blank_smart_account_address_filter_is_refused_not_dropped(blank: str) -> None:
    async with zero_id_client() as (client, http):
        before = http.request_count
        with pytest.raises(PolyesterValidationError, match="smart_account_address"):
            await client.lifecycle.list_flows(smart_account_address=blank)
        assert http.request_count == before, "a request was sent"


@pytest.mark.asyncio
@pytest.mark.parametrize("address", [None, "0x" + "ab" * 20])
async def test_an_absent_or_valid_smart_account_address_filter_still_sends(
    address: str | None,
) -> None:
    async with zero_id_client() as (client, http):
        with pytest.raises(PolyesterRouteNotFoundError):
            await client.lifecycle.list_flows(smart_account_address=address)
        assert http.request_count == 1
