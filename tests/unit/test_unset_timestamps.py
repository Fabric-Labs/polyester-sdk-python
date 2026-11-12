"""A protobuf ``Timestamp`` the server leaves unset reads as ``None``.

An unset ``Timestamp`` field reads from the generated message as a default
``Timestamp`` (zero seconds), so decoding its value gave 1970-01-01T00:00:00Z,
the Unix epoch, which a caller could take for a real time: an API key that
was never used had ``last_used_at`` in 1970. Field presence decides now: an
unset field is ``None``, and a sent time, even the epoch itself, is kept.

The reads go through the public services over both wire formats
(``api_keys.list``, ``api_keys.get``, ``sub_accounts.list``,
``sub_accounts.get`` with its API keys, invites and policy,
``sub_accounts.list_invites`` and ``sub_accounts.list_activity``), through
the realtime decoders of the API-key, sub-account and policy streams, through
the JSON-dict API-key decoders, and through the exported profile decoders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester
from polyester.codecs.decode.auth import profile_from_proto, username_history_from_proto
from polyester.codecs.decode.sub_accounts import subaccount_activity_event_from_proto
from polyester.codecs.realtime_decode import (
    decode_api_key_bytes,
    decode_api_policy_bytes,
    decode_subaccount_bytes,
    decode_subaccount_policy_bytes,
)
from polyester.codecs.wire_decode import decode_api_key, decode_api_keys_list
from polyester.gen.auth.v1 import api_keys_pb2, policies_pb2, profile_pb2, subaccounts_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

WIRES = pytest.mark.parametrize("json_wire", [False, True], ids=["binary", "json"])

_SUBACCOUNT = 42
_UNSET_KEY_ID = "ak_" + "1" * 32
_SET_KEY_ID = "ak_" + "2" * 32

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_CREATED = datetime(2026, 11, 1, 8, 0, 0, 123456, tzinfo=UTC)
_USED = datetime(2026, 11, 2, 9, 30, 0, tzinfo=UTC)
_UPDATED = datetime(2026, 11, 3, 10, 45, 0, 500000, tzinfo=UTC)


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


def _unset_key() -> api_keys_pb2.ApiKey:
    # A key that was never used and has no update time: all unset.
    return api_keys_pb2.ApiKey(key_id=_UNSET_KEY_ID, label="never-used")


def _set_key() -> api_keys_pb2.ApiKey:
    # Sent times are kept; an explicitly sent epoch is a sent time.
    return api_keys_pb2.ApiKey(
        key_id=_SET_KEY_ID,
        label="used",
        created_at=_ts(_CREATED),
        last_used_at=_ts(_USED),
        updated_at=_ts(_EPOCH),
    )


def _keys() -> list[api_keys_pb2.ApiKey]:
    return [_unset_key(), _set_key()]


def _assert_keys(keys: list[Any]) -> None:
    unset, sent = keys
    assert unset.key_id == _UNSET_KEY_ID
    assert (unset.created_at, unset.last_used_at, unset.updated_at, unset.expires_at) == (
        None,
        None,
        None,
        None,
    )
    assert sent.key_id == _SET_KEY_ID
    assert (sent.created_at, sent.last_used_at, sent.updated_at) == (_CREATED, _USED, _EPOCH)


def _unset_subaccount() -> subaccounts_pb2.Subaccount:
    return subaccounts_pb2.Subaccount(id=_SUBACCOUNT, label="desk")


def _invites() -> list[subaccounts_pb2.SubaccountInvite]:
    return [
        # Pending: never responded to.
        subaccounts_pb2.SubaccountInvite(
            id=11, subaccount_id=_SUBACCOUNT, role=subaccounts_pb2.VIEWER
        ),
        subaccounts_pb2.SubaccountInvite(
            id=12,
            subaccount_id=_SUBACCOUNT,
            role=subaccounts_pb2.TRADER,
            created_at=_ts(_CREATED),
            responded_at=_ts(_UPDATED),
        ),
    ]


def _assert_invites(invites: list[Any]) -> None:
    pending, answered = invites
    assert (pending.created_at, pending.responded_at) == (None, None)
    assert (answered.created_at, answered.responded_at) == (_CREATED, _UPDATED)


def _unset_policy() -> policies_pb2.SubaccountPolicyView:
    # No review, no expiry, and no creation or update time sent.
    return policies_pb2.SubaccountPolicyView(id=5, name="desk")


def _assert_unset_policy(policy: Any) -> None:
    assert policy is not None
    assert (policy.review_at, policy.expires_at, policy.created_at, policy.updated_at) == (
        None,
        None,
        None,
        None,
    )


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
async def test_unset_timestamps_read_none_through_services(json_wire: bool) -> None:
    responses: dict[str, Message] = {
        "ListApiKeys": api_keys_pb2.ListApiKeysResponse(api_keys=_keys()),
        "GetApiKey": api_keys_pb2.GetApiKeyResponse(api_key=_unset_key()),
        "ListSubaccounts": subaccounts_pb2.ListSubaccountsResponse(
            subaccounts=[_unset_subaccount()]
        ),
        "GetSubaccount": subaccounts_pb2.GetSubaccountResponse(
            subaccount=_unset_subaccount(),
            api_keys=_keys(),
            invites=_invites(),
            policy=_unset_policy(),
        ),
        "ListSubaccountInvites": subaccounts_pb2.ListSubaccountInvitesResponse(invites=_invites()),
        "ListSubaccountActivity": subaccounts_pb2.ListSubaccountEventsResponse(
            events=[
                subaccounts_pb2.ActivityEvent(actor_account_id=7),
                subaccounts_pb2.ActivityEvent(actor_account_id=7, created_at=_ts(_CREATED)),
            ]
        ),
    }
    client, http = await _client(responses, json_wire)
    try:
        listed = await client.api_keys.list()
        got = await client.api_keys.get(key_id=_UNSET_KEY_ID)
        subaccounts = await client.sub_accounts.list()
        view = await client.sub_accounts.get(
            sub_account_id=_SUBACCOUNT,
            include_api_keys=True,
            include_invites=True,
            include_policy=True,
        )
        invites = await client.sub_accounts.list_invites()
        activity = await client.sub_accounts.list_activity(sub_account_id=_SUBACCOUNT)
    finally:
        await client.aclose()
        await http.aclose()

    _assert_keys(listed.api_keys)
    assert got is not None
    _assert_keys([got, listed.api_keys[1]])
    _assert_keys(view.api_keys)

    assert subaccounts.subaccounts[0].updated_at is None
    assert view.subaccount is not None
    assert view.subaccount.updated_at is None

    _assert_invites(view.invites)
    _assert_invites(invites.invites)
    _assert_unset_policy(view.policy)

    assert [event.created_at for event in activity.events] == [None, _CREATED]


def test_unset_timestamps_read_none_through_streams() -> None:
    _assert_keys([decode_api_key_bytes(key.SerializeToString()) for key in _keys()])

    assert decode_subaccount_bytes(_unset_subaccount().SerializeToString()).updated_at is None
    sent = subaccounts_pb2.Subaccount(id=_SUBACCOUNT, updated_at=_ts(_EPOCH))
    assert decode_subaccount_bytes(sent.SerializeToString()).updated_at == _EPOCH

    _assert_unset_policy(decode_subaccount_policy_bytes(_unset_policy().SerializeToString()))
    sent_policy = policies_pb2.SubaccountPolicyView(
        id=5,
        review_at=_ts(_CREATED),
        expires_at=_ts(_USED),
        created_at=_ts(_EPOCH),
        updated_at=_ts(_UPDATED),
    )
    decoded = decode_subaccount_policy_bytes(sent_policy.SerializeToString())
    assert (decoded.review_at, decoded.expires_at, decoded.created_at, decoded.updated_at) == (
        _CREATED,
        _USED,
        _EPOCH,
        _UPDATED,
    )

    api_policy = decode_api_policy_bytes(policies_pb2.ApiPolicyView(id=6).SerializeToString())
    assert (api_policy.created_at, api_policy.updated_at) == (None, None)
    sent_api_policy = policies_pb2.ApiPolicyView(
        id=6, created_at=_ts(_CREATED), updated_at=_ts(_UPDATED)
    )
    decoded_api = decode_api_policy_bytes(sent_api_policy.SerializeToString())
    assert (decoded_api.created_at, decoded_api.updated_at) == (_CREATED, _UPDATED)


def test_unset_timestamps_read_none_through_json_dict_decoders() -> None:
    _assert_keys([decode_api_key(MessageToDict(key)) for key in _keys()])
    listed = decode_api_keys_list(MessageToDict(api_keys_pb2.ListApiKeysResponse(api_keys=_keys())))
    _assert_keys(listed.api_keys)


def test_unset_timestamps_read_none_through_profile_and_activity_decoders() -> None:
    profile = profile_from_proto(profile_pb2.UserProfile(username="alice"))
    assert (profile.created_at, profile.next_username_change_at) == (None, None)
    sent = profile_from_proto(
        profile_pb2.UserProfile(
            username="alice",
            created_at=_ts(_CREATED),
            next_username_change_at=_ts(_UPDATED),
        )
    )
    assert (sent.created_at, sent.next_username_change_at) == (_CREATED, _UPDATED)

    history = username_history_from_proto(
        profile_pb2.GetUsernameHistoryResponse(
            history=[
                profile_pb2.UsernameHistoryEntry(username="old"),
                profile_pb2.UsernameHistoryEntry(username="new", set_at=_ts(_USED)),
            ]
        )
    )
    assert [entry.set_at for entry in history.history] == [None, _USED]

    event = subaccount_activity_event_from_proto(subaccounts_pb2.ActivityEvent())
    assert event.created_at is None
