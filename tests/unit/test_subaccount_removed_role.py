"""A sub-account update says when the caller lost access (POLY-9397).

``auth.v1.Subaccount.removed`` tells the caller to drop a sub-account it can no
longer access; the role is then ``SUBACCOUNT_ROLE_UNSPECIFIED``. A role or
access change does not move ``revision`` or ``updated_at``, so the typed update
must carry ``removed`` and the role as sent: an empty role, never ``viewer``.
"""

from __future__ import annotations

import pytest
from google.protobuf.json_format import MessageToJson, Parse

from polyester.codecs.decode.sub_accounts import subaccount_from_proto
from polyester.codecs.realtime_decode import decode_subaccount_bytes
from polyester.gen.auth.v1 import subaccounts_pb2

REVISIONS = [0, 3, 9_007_199_254_740_993]


def _subaccount(*, removed: bool, role: int, revision: int) -> subaccounts_pb2.Subaccount:
    msg = subaccounts_pb2.Subaccount(
        id=42,
        role=role,  # type: ignore[arg-type]
        status=subaccounts_pb2.SUBACCOUNT_STATUS_ACTIVE,
        revision=revision,
        removed=removed,
    )
    msg.updated_at.seconds = 1_762_819_200
    return msg


@pytest.mark.parametrize("revision", REVISIONS)
def test_removal_is_distinct_from_an_active_viewer(revision: int) -> None:
    removal = _subaccount(
        removed=True, role=subaccounts_pb2.SUBACCOUNT_ROLE_UNSPECIFIED, revision=revision
    )
    active = _subaccount(removed=False, role=subaccounts_pb2.VIEWER, revision=revision)
    # The generated round trip keeps the flag and the exact revision.
    wire = subaccounts_pb2.Subaccount.FromString(removal.SerializeToString())
    assert wire.removed is True and wire.revision == revision

    removed = decode_subaccount_bytes(removal.SerializeToString())
    kept = decode_subaccount_bytes(active.SerializeToString())
    assert removed.removed is True
    assert removed.role == ""
    assert removed.revision == revision
    assert kept.removed is False
    assert kept.role == "viewer"
    assert kept.revision == revision
    assert removed != kept


@pytest.mark.parametrize(
    ("role", "label"),
    [
        (subaccounts_pb2.VIEWER, "viewer"),
        (subaccounts_pb2.TRADER, "trader"),
        (subaccounts_pb2.ADMIN, "admin"),
        (subaccounts_pb2.OWNER, "owner"),
    ],
)
def test_role_changes_read_as_sent(role: int, label: str) -> None:
    update = decode_subaccount_bytes(
        _subaccount(removed=False, role=role, revision=3).SerializeToString()
    )
    assert update.role == label
    assert update.removed is False


def test_json_wire_keeps_removed_and_the_unspecified_role() -> None:
    removal = _subaccount(
        removed=True, role=subaccounts_pb2.SUBACCOUNT_ROLE_UNSPECIFIED, revision=3
    )
    parsed = Parse(MessageToJson(removal), subaccounts_pb2.Subaccount())
    decoded = subaccount_from_proto(parsed)
    assert decoded.removed is True
    assert decoded.role == ""


def test_removed_is_omitted_when_false() -> None:
    import msgspec

    active = decode_subaccount_bytes(
        _subaccount(removed=False, role=subaccounts_pb2.VIEWER, revision=3).SerializeToString()
    )
    assert "removed" not in msgspec.to_builtins(active)
