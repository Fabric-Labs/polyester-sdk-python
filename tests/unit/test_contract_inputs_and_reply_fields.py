"""Inputs the published contract refuses are refused before sending, and
reply fields it defines are kept.

Each refusal cites the contract rule it applies: asset IDs outside the
range ``ListAssetInfoRequest.asset_ids`` allows, a deposit address created
for chain 0, and a ladder without both price bounds. Each kept field is a
field of the reply the SDK used to drop or return in another form: the
order IDs of an ``ORDER_UNAVAILABLE`` stale report, and an address book's
``caller_role`` as a role name.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.codecs.decode.address_book import address_book_summary_from_proto
from polyester.codecs.scalars import format_id
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterError, PolyesterValidationError
from polyester.gen.auth.v1 import address_book_pb2, subaccounts_pb2
from polyester.gen.chain.deposit.v1 import deposit_pb2
from polyester.gen.marketdata.v1 import asset_info_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models import PrivateOrdersConnected, PrivateOrdersSnapshot, PrivateOrdersStale
from polyester.realtime.private_orders import PrivateOrderStream, private_ws_url
from tests.hardening_support import HttpScript, MockHttpServer, ParsedRequest, make_test_credentials
from tests.unit.test_private_orders_stream import (
    ACCOUNT_B58,
    FakePrivateWsServer,
    Tokens,
    next_event,
    open_stream,
)

_CREDS = make_test_credentials()


@asynccontextmanager
async def _client() -> AsyncIterator[tuple[AsyncPolyester, list[ParsedRequest]]]:
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return HttpScript.json(500, {"code": "internal", "message": "stop"})

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


# --- asset info IDs ------------------------------------------------------------------------------
# asset_info.proto, ListAssetInfoRequest:
#   repeated uint32 asset_ids = 1 [(buf.validate.field).repeated = {
#     max_items: 1000, items: { uint32: { gt: 0, lte: 2147483647 } } }];


def test_asset_id_range_is_read_from_the_contract() -> None:
    from polyester.services.market_data import ASSET_ID_MAX, ASSET_ID_MIN

    assert (ASSET_ID_MIN, ASSET_ID_MAX) == (1, 2147483647)


@pytest.mark.parametrize("ids", [[0], [2147483648], [0, 2147483648], [1, 0], [2**32 - 1]])
async def test_asset_ids_outside_the_contract_range_are_refused_before_sending(
    ids: list[int],
) -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="asset_ids"):
            await client.market_data.list_asset_info(ids)
    assert requests == []


@pytest.mark.parametrize("ids", [[1, 2147483647], []])
async def test_asset_ids_within_the_contract_range_are_sent(ids: list[int]) -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterError):  # the mock answers 500
            await client.market_data.list_asset_info(ids)
    assert len(requests) == 1
    sent = asset_info_pb2.ListAssetInfoRequest.FromString(requests[0].body)
    assert list(sent.asset_ids) == ids


async def test_more_asset_ids_than_the_contract_allows_are_refused_before_sending() -> None:
    from polyester.services.market_data import ASSET_IDS_MAX

    assert ASSET_IDS_MAX == 1000  # max_items: 1000
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="asset_ids"):
            await client.market_data.list_asset_info(list(range(1, 1002)))
    assert requests == []


async def test_as_many_asset_ids_as_the_contract_allows_are_sent() -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterError):  # the mock answers 500
            await client.market_data.list_asset_info(list(range(1, 1001)))
    assert len(requests) == 1
    sent = asset_info_pb2.ListAssetInfoRequest.FromString(requests[0].body)
    assert len(sent.asset_ids) == 1000


# --- deposit address chain -----------------------------------------------------------------------
# deposit.proto, CreateDepositAddressRequest:
#   uint32 chain_id = 2 [(buf.validate.field).uint32.gt = 0];   (no ignore-if-zero)
# ListDepositAddressesRequest.chain_id has IGNORE_IF_ZERO_VALUE: 0 lists every chain.


async def test_create_deposit_address_refuses_chain_zero_before_sending() -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="chain_id"):
            await client.deposit.create_address(chain_id=0)
    assert requests == []


async def test_create_deposit_address_sends_a_positive_chain() -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterError):  # the mock answers 500
            await client.deposit.create_address(chain_id=2)
    assert len(requests) == 1
    assert deposit_pb2.CreateDepositAddressRequest.FromString(requests[0].body).chain_id == 2


async def test_list_deposit_addresses_with_chain_zero_still_lists_every_chain() -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterError):  # the mock answers 500
            await client.deposit.list_addresses(chain_id=0)
    assert len(requests) == 1
    assert deposit_pb2.ListDepositAddressesRequest.FromString(requests[0].body).chain_id == 0


# --- ladder price bounds -------------------------------------------------------------------------
# triggers.proto, LadderTrigger: both bounds are required (no presence, no ignore-if-zero):
#   int64 price_min_ticks = 2 [(buf.validate.field).int64.gt = 0];
#   int64 price_max_ticks = 3 [(buf.validate.field).int64.gt = 0];
# so a bound left out is 0 on the wire, which the rule refuses.

_LADDER = dict(
    trigger_type="ladder",
    symbol="BTC-USDT",
    symbol_id=1,
    side="buy",
    qty="1",
    quantity_scale=8,
    ladder_levels=3,
)


@pytest.mark.parametrize(
    ("bounds", "missing"),
    [
        ({}, "ladder_price_min"),
        ({"ladder_price_max": "60000"}, "ladder_price_min"),
        ({"ladder_price_min": "50000"}, "ladder_price_max"),
    ],
)
def test_a_ladder_without_both_price_bounds_is_refused(
    bounds: dict[str, Any], missing: str
) -> None:
    with pytest.raises(PolyesterValidationError, match=missing) as refused:
        create_trigger_to_proto(**_LADDER, **bounds)
    assert refused.value.code == "ERROR_CODE_TRIGGER_PRICE_INVALID"


async def test_a_ladder_without_price_bounds_is_not_sent() -> None:
    async with _client() as (client, requests):
        client.catalogs.hydrate_spot_config(
            {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
        )
        with pytest.raises(PolyesterValidationError, match="ladder_price_min"):
            await client.triggers.create(
                symbol="BTC-USDT",
                trigger_type="ladder",
                side="buy",
                qty="0.003",
                order_type="limit",
                ladder_levels=3,
            )
    assert requests == []


def test_a_ladder_with_both_bounds_still_encodes() -> None:
    proto = create_trigger_to_proto(**_LADDER, ladder_price_min="50000", ladder_price_max="60000")
    assert proto.trigger.ladder.price_min_ticks == 50_000 * 10**9
    assert proto.trigger.ladder.price_max_ticks == 60_000 * 10**9


# --- stale order IDs -----------------------------------------------------------------------------
# private_ws.proto, Unavailable.order_ids: "For ORDER_UNAVAILABLE: the public IDs of the orders
# whose current state is unknown, ascending. Empty for every other reason, which covers the
# whole view."


async def test_order_unavailable_keeps_its_order_ids() -> None:
    server = FakePrivateWsServer()
    await server.start()
    tokens = Tokens()
    stream = PrivateOrderStream(
        url=private_ws_url(server.api_url),
        fetch_connect_token=tokens.connect,
        fetch_subscribe_token=tokens.subscribe,
    )
    try:
        sub, conn = await open_stream(server, stream)
        await conn.snapshot("s1", "c1", [])
        assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
        await conn.send("s1", 4, unavailable=pb.Unavailable(reason=pb.FAILOVER))
        await conn.send(
            "s1", 5, unavailable=pb.Unavailable(reason=pb.ORDER_UNAVAILABLE, order_ids=[123, 456])
        )
        await conn.send("s1", 6, unavailable=pb.Unavailable(reason=pb.NOT_READY))
        await conn.send(
            "s1", 7, unavailable=pb.Unavailable(reason=pb.ORDER_UNAVAILABLE, order_ids=[789])
        )

        assert await next_event(sub) == PrivateOrdersStale(stale=True, order_ids=[])
        assert await next_event(sub) == PrivateOrdersStale(
            stale=True, order_ids=[format_id(123), format_id(456)]
        )
        assert await next_event(sub) == PrivateOrdersStale(stale=True, order_ids=[])
        assert await next_event(sub) == PrivateOrdersStale(stale=True, order_ids=[format_id(789)])

        # A consumer that joins later gets the current stale report with its IDs.
        late = await stream.subscribe(ACCOUNT_B58)
        assert isinstance(await next_event(late), PrivateOrdersConnected)
        assert isinstance(await next_event(late), PrivateOrdersSnapshot)
        assert await next_event(late) == PrivateOrdersStale(stale=True, order_ids=[format_id(789)])

        await conn.send("s1", 8, available=pb.Available())
        assert await next_event(sub) == PrivateOrdersStale(stale=False, order_ids=[])
    finally:
        await stream.aclose()
        await server.aclose()


# --- address book caller role --------------------------------------------------------------------
# address_book.proto, AddressBook: SubaccountRole caller_role = 2; read as the role name, the form
# every other role of the SDK has (SubAccount.role, members, invites).


@pytest.mark.parametrize(
    ("role", "name"),
    [
        (subaccounts_pb2.OWNER, "owner"),
        (subaccounts_pb2.TRADER, "trader"),
        (subaccounts_pb2.SUBACCOUNT_ROLE_UNSPECIFIED, ""),
    ],
)
def test_address_book_caller_role_is_the_role_name(role: int, name: str) -> None:
    book = address_book_summary_from_proto(address_book_pb2.AddressBook(caller_role=role))
    assert book.caller_role == name
