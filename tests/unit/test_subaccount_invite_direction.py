import pytest

from polyester.codecs.sub_accounts import invite_direction_from_label
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import subaccounts_pb2


def test_invite_direction_from_label() -> None:
    assert invite_direction_from_label("") == subaccounts_pb2.DIRECTION_UNSPECIFIED
    assert invite_direction_from_label("incoming") == subaccounts_pb2.INCOMING
    assert invite_direction_from_label("OUTGOING") == subaccounts_pb2.OUTGOING
    with pytest.raises(PolyesterValidationError, match="incoming"):
        invite_direction_from_label("sideways")
