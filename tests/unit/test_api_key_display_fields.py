"""API-key reads follow the contract's ``ApiKey`` on every decode path.

* A key of the main account reads ``subaccount_id == ""``, as Go and Rust
  read it, whether the server leaves ``subaccount_id`` unset or sends an
  explicit 0; it read ``"0"``.
* ``icon``, ``color`` and ``created_by_actor`` are kept as sent; ``""`` when
  the server sends none.

The reads go through the public services over both wire formats
(``api_keys.get``, ``api_keys.list`` and the API keys of
``sub_accounts.get``), through the realtime decoder of the API-key streams,
and through the JSON-dict decoder.
"""

from __future__ import annotations

from typing import Any

import pytest
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester._wire import protobuf_to_public_dict
from polyester.codecs.realtime_decode import decode_api_key_bytes
from polyester.codecs.scalars import format_id
from polyester.codecs.wire_decode import decode_api_key, decode_api_keys_list
from polyester.gen.auth.v1 import api_keys_pb2, subaccounts_pb2
from polyester.models import ApiKeySummary
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

WIRES = pytest.mark.parametrize("json_wire", [False, True], ids=["binary", "json"])

_MAIN_KEY_ID = "ak_" + "1" * 32
_EXPLICIT_ZERO_KEY_ID = "ak_" + "2" * 32
_SUB_KEY_ID = "ak_" + "3" * 32
_SUBACCOUNT = 42


def _main_key() -> api_keys_pb2.ApiKey:
    # A key of the main account: no subaccount_id, with the display fields.
    return api_keys_pb2.ApiKey(
        key_id=_MAIN_KEY_ID,
        label="bot",
        icon="🤖",
        color="violet-500",
        created_by_actor="alice",
        status=api_keys_pb2.ACTIVE,
        revision=3,
    )


def _explicit_zero_key() -> api_keys_pb2.ApiKey:
    # subaccount_id has presence: a server may send an explicit 0 for "none".
    return api_keys_pb2.ApiKey(key_id=_EXPLICIT_ZERO_KEY_ID, label="zero", subaccount_id=0)


def _sub_key() -> api_keys_pb2.ApiKey:
    return api_keys_pb2.ApiKey(
        key_id=_SUB_KEY_ID,
        label="desk",
        subaccount_id=_SUBACCOUNT,
        icon="#",
        color="",
        created_by_actor="desk-admin",
    )


def _keys() -> list[api_keys_pb2.ApiKey]:
    return [_main_key(), _explicit_zero_key(), _sub_key()]


def _assert_keys(keys: list[ApiKeySummary]) -> None:
    main, zero, sub = keys
    assert main.key_id == _MAIN_KEY_ID
    assert main.subaccount_id == ""
    assert (main.icon, main.color, main.created_by_actor) == ("🤖", "violet-500", "alice")

    assert zero.key_id == _EXPLICIT_ZERO_KEY_ID
    assert zero.subaccount_id == ""
    assert (zero.icon, zero.color, zero.created_by_actor) == ("", "", "")

    assert sub.key_id == _SUB_KEY_ID
    assert sub.subaccount_id == format_id(_SUBACCOUNT)
    assert (sub.icon, sub.color, sub.created_by_actor) == ("#", "", "desk-admin")


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


@pytest.mark.asyncio
@WIRES
async def test_api_key_reads_keep_main_account_and_display_fields(json_wire: bool) -> None:
    responses: dict[str, Message] = {
        "ListApiKeys": api_keys_pb2.ListApiKeysResponse(api_keys=_keys()),
        "GetApiKey": api_keys_pb2.GetApiKeyResponse(api_key=_main_key()),
        "GetSubaccount": subaccounts_pb2.GetSubaccountResponse(
            subaccount=subaccounts_pb2.Subaccount(id=_SUBACCOUNT), api_keys=_keys()
        ),
    }
    client, http = await _client(responses, json_wire)
    try:
        listed = await client.api_keys.list()
        got = await client.api_keys.get(key_id=_MAIN_KEY_ID)
        view = await client.sub_accounts.get(sub_account_id=_SUBACCOUNT, include_api_keys=True)
    finally:
        await client.aclose()
        await http.aclose()

    _assert_keys(listed.api_keys)
    assert got == listed.api_keys[0]
    _assert_keys(view.api_keys)


def test_api_key_stream_keeps_main_account_and_display_fields() -> None:
    _assert_keys([decode_api_key_bytes(key.SerializeToString()) for key in _keys()])


def test_api_key_json_dict_reads_like_the_proto_decoder() -> None:
    _assert_keys([decode_api_key(protobuf_to_public_dict(key)) for key in _keys()])
    listed = decode_api_keys_list(
        protobuf_to_public_dict(api_keys_pb2.ListApiKeysResponse(api_keys=_keys()))
    )
    _assert_keys(listed.api_keys)


def test_api_key_summary_serializes_display_fields_only_when_set() -> None:
    import msgspec

    sub, zero = (
        decode_api_key_bytes(_sub_key().SerializeToString()),
        decode_api_key_bytes(_explicit_zero_key().SerializeToString()),
    )
    absent = msgspec.to_builtins(zero)
    for name in ("subaccount_id", "icon", "color", "created_by_actor"):
        assert name not in absent
    encoded = msgspec.to_builtins(sub)
    assert encoded["subaccount_id"] == format_id(_SUBACCOUNT)
    assert encoded["icon"] == "#"
    assert encoded["created_by_actor"] == "desk-admin"
    assert "color" not in encoded
