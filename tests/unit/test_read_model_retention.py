"""Typed reads keep contract fields the server sends.

* Each address-book view entry keeps its own ``revision`` (POLY-9893).
* An API key keeps its policy, IP allowlist, expiry and public key (POLY-9894).
* An order keeps the ``batch_request_id`` of the batch replace that admitted
  it (POLY-9896).

The reads go through the public services over both wire formats, and through
the realtime decoders for the streams.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.realtime_decode import decode_api_key_bytes
from polyester.gen.auth.v1 import address_book_pb2, api_keys_pb2
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2
from polyester.models import ApiKeySummary
from polyester.models.order_key import OrderId
from polyester.models.trading import Order
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

WIRES = pytest.mark.parametrize("json_wire", [False, True], ids=["binary", "json"])


async def _client(responses: dict[str, Message], json_wire: bool) -> tuple[AsyncPolyester, Any]:
    async def handler(req: ParsedRequest) -> HttpScript:
        response = responses[req.path.rsplit("/", 1)[-1]]
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    return client, http


# --- POLY-9893: address-book view entry revisions -------------------------


def _external(entry_id: int, revision: int) -> address_book_pb2.ExternalAddressBookEntry:
    return address_book_pb2.ExternalAddressBookEntry(
        address_book_entry_id=entry_id,
        label=f"ext-{entry_id}",
        polychain_chain_id=1,
        address="0x00000000000000000000000000000000000000aa",
        revision=revision,
    )


def _internal(entry_id: int, revision: int) -> address_book_pb2.InternalAddressBookEntry:
    return address_book_pb2.InternalAddressBookEntry(
        address_book_entry_id=entry_id,
        label=f"int-{entry_id}",
        target_account_id=500,
        revision=revision,
    )


def _generic(entry_id: int, revision: int) -> address_book_pb2.AddressBookEntry:
    return address_book_pb2.AddressBookEntry(
        address_book_entry_id=entry_id,
        kind=address_book_pb2.EXTERNAL_CHAIN,
        label=f"entry-{entry_id}",
        revision=revision,
    )


# Mixed revisions, including the default 0; the view's own revision differs.
_EXTERNAL = [(11, 7), (12, 0), (13, 4)]
_INTERNAL = [(21, 19), (22, 2), (23, 0)]
_VIEW_REVISION = 99

_ADDRESS_BOOK = {
    "GetAddressBookView": address_book_pb2.GetAddressBookViewResponse(
        entries=address_book_pb2.AddressBookEntriesView(
            external=[_external(i, r) for i, r in _EXTERNAL],
            internal=[_internal(i, r) for i, r in _INTERNAL],
        ),
        view_revision=_VIEW_REVISION,
    ),
    "ListAddressBookEntries": address_book_pb2.ListAddressBookEntriesResponse(
        entries=[_generic(i, r) for i, r in _EXTERNAL + _INTERNAL]
    ),
}


@pytest.mark.asyncio
@WIRES
async def test_address_book_view_entries_keep_their_own_revision(json_wire: bool) -> None:
    from polyester.codecs.scalars import format_id

    client, http = await _client(_ADDRESS_BOOK, json_wire)
    try:
        view = await client.address_book.get_view()
        listed = await client.address_book.list_entries()
    finally:
        await client.aclose()
        await http.aclose()

    assert view.view_revision == _VIEW_REVISION
    assert view.entries is not None
    external = view.entries.external or []
    internal = view.entries.internal or []
    assert [(e.address_book_entry_id, e.revision) for e in external] == [
        (format_id(i), r) for i, r in _EXTERNAL
    ]
    assert [(e.address_book_entry_id, e.revision) for e in internal] == [
        (format_id(i), r) for i, r in _INTERNAL
    ]
    # Same revision as the generic entry read of the same entry.
    generic = {e.address_book_entry_id: e.revision for e in listed.entries}
    for entry in [*external, *internal]:
        assert entry.revision == generic[entry.address_book_entry_id]


# --- POLY-9894: API-key policy, IP allowlist, expiry, public key -----------

_PUBLIC_KEY = bytes(range(32))


def _expiry(seconds: int, nanos: int = 0) -> Timestamp:
    return Timestamp(seconds=seconds, nanos=nanos)


def _populated_key(policy_id: int, expires: Timestamp) -> api_keys_pb2.ApiKey:
    return api_keys_pb2.ApiKey(
        key_id="ak_" + "1" * 32,
        label="bot",
        status=api_keys_pb2.ACTIVE,
        subaccount_id=42,
        policy_id=policy_id,
        ip_whitelist=["192.0.2.1", "198.51.100.0/24"],
        public_key_ed25519=_PUBLIC_KEY,
        expires_at=expires,
        revision=3,
    )


def _absent_key() -> api_keys_pb2.ApiKey:
    return api_keys_pb2.ApiKey(key_id="ak_" + "2" * 32, label="plain", revision=1)


_KEY_CASES = [
    # policy id, its public id, expiry seconds/nanos, exact expected expiry
    (7, "8", 4_102_444_800, 0, datetime(2100, 1, 1, tzinfo=UTC)),
    (
        19,
        "L",
        4_133_980_799,
        123_456_000,
        datetime(2100, 12, 31, 23, 59, 59, 123_456, tzinfo=UTC),
    ),
]


def _assert_populated(key: ApiKeySummary | None, policy: str, expires: datetime) -> None:
    assert key is not None
    assert key.key_id == "ak_" + "1" * 32
    assert key.label == "bot"
    assert key.revision == 3
    assert key.policy_id == policy
    assert key.ip_whitelist == ["192.0.2.1", "198.51.100.0/24"]
    assert key.expires_at == expires
    assert key.public_key_ed25519 == _PUBLIC_KEY.hex()


def _assert_absent(key: ApiKeySummary | None) -> None:
    assert key is not None
    assert key.key_id == "ak_" + "2" * 32
    assert key.policy_id == ""
    assert key.ip_whitelist == []
    assert key.expires_at is None
    assert key.public_key_ed25519 == ""


@pytest.mark.asyncio
@WIRES
@pytest.mark.parametrize(("policy_id", "policy", "seconds", "nanos", "expires"), _KEY_CASES)
async def test_api_key_reads_keep_policy_allowlist_and_expiry(
    json_wire: bool, policy_id: int, policy: str, seconds: int, nanos: int, expires: datetime
) -> None:
    populated = _populated_key(policy_id, _expiry(seconds, nanos))
    responses: dict[str, Message] = {
        "GetApiKey": api_keys_pb2.GetApiKeyResponse(api_key=populated),
        "ListApiKeys": api_keys_pb2.ListApiKeysResponse(api_keys=[populated, _absent_key()]),
    }
    client, http = await _client(responses, json_wire)
    try:
        got = await client.api_keys.get(key_id=populated.key_id)
        listed = await client.api_keys.list()
    finally:
        await client.aclose()
        await http.aclose()

    _assert_populated(got, policy, expires)
    assert len(listed.api_keys) == 2
    _assert_populated(listed.api_keys[0], policy, expires)
    _assert_absent(listed.api_keys[1])


@pytest.mark.parametrize(("policy_id", "policy", "seconds", "nanos", "expires"), _KEY_CASES)
def test_api_key_stream_keeps_policy_allowlist_and_expiry(
    policy_id: int, policy: str, seconds: int, nanos: int, expires: datetime
) -> None:
    populated = _populated_key(policy_id, _expiry(seconds, nanos))
    _assert_populated(decode_api_key_bytes(populated.SerializeToString()), policy, expires)
    _assert_absent(decode_api_key_bytes(_absent_key().SerializeToString()))


# --- POLY-9896: order batch_request_id -------------------------------------

_BATCH_CASES = [(7, "8"), (18_446_744_073_709_551_614, "jpXCZedGfVP"), (0, "")]


def _order(batch_request_id: int) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(
        order_id=901,
        symbol_id=1,
        client_order_id="c-901",
        status=orders_read_pb2.WORKING,
        version=4,
        batch_request_id=batch_request_id,
    )


def _assert_batch(order: Order | None, expected: str) -> None:
    assert order is not None
    assert order.client_order_id == "c-901"
    assert order.version == 4
    assert order.batch_request_id == expected


@pytest.mark.asyncio
@WIRES
@pytest.mark.parametrize(("batch_id", "expected"), _BATCH_CASES)
async def test_order_reads_keep_batch_request_id(
    json_wire: bool, batch_id: int, expected: str
) -> None:
    responses: dict[str, Message] = {
        "GetOrder": orders_read_pb2.GetOrderResponse(order=_order(batch_id)),
        "GetOpenOrders": orders_read_pb2.GetOpenOrdersResponse(orders=[_order(batch_id)]),
        "GetOrderHistory": orders_read_pb2.GetOrderHistoryResponse(orders=[_order(batch_id)]),
    }
    client, http = await _client(responses, json_wire)
    try:
        got = (await client.orders.get(key=OrderId(901))).order
        open_orders = (await client.orders.list_open()).orders
        history = (await client.orders.list_history()).orders
    finally:
        await client.aclose()
        await http.aclose()

    _assert_batch(got, expected)
    _assert_batch(open_orders[0], expected)
    _assert_batch(history[0], expected)


@pytest.mark.parametrize(("batch_id", "expected"), _BATCH_CASES)
def test_order_stream_keeps_batch_request_id(
    batch_id: int, expected: str
) -> None:
    unit = private_orders_unit_from_proto(
        private_ws_pb2.Unit(orders=[_order(batch_id)]), scales=None
    )
    _assert_batch(unit.orders[0], expected)
