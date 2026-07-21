from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.decode.address_book import address_book_entry_from_proto
from polyester.codecs.decode.api_keys import api_key_from_proto
from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
from polyester.codecs.decode.sub_accounts import subaccount_from_proto
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import address_book_pb2, api_keys_pb2, policies_pb2, subaccounts_pb2
from polyester.services.address_book import AsyncAddressBookService
from polyester.services.api_keys import AsyncApiKeysService
from polyester.services.policies import AsyncPoliciesService
from polyester.services.sub_accounts import AsyncSubAccountsService
from tests.unit.support import CaptureUnary


@pytest.mark.asyncio
async def test_subaccount_one_field_update_mask() -> None:
    capture = CaptureUnary(
        subaccounts_pb2.UpdateSubaccountResponse(
            subaccount=subaccounts_pb2.Subaccount(id=7, label="new", revision=2)
        )
    )
    with patch("polyester.services.sub_accounts.unary_auth_decoded", capture):
        service = AsyncSubAccountsService(transport=MagicMock(), default_sub_account_id=None)
        await service.update(
            sub_account_id=format_id(70),
            expected_revision=1,
            label="new",
        )
    assert capture.request.subaccount_id == 70
    assert capture.request.expected_revision == 1
    assert capture.request.subaccount.label == "new"
    assert list(capture.request.update_mask.paths) == ["label"]
    assert capture.request.subaccount.icon == ""
    assert capture.request.subaccount.color == ""
    assert capture.request.subaccount.status == ""


@pytest.mark.asyncio
async def test_subaccount_empty_string_and_status_paths() -> None:
    capture = CaptureUnary(subaccounts_pb2.UpdateSubaccountResponse())
    with patch("polyester.services.sub_accounts.unary_auth_decoded", capture):
        service = AsyncSubAccountsService(transport=MagicMock(), default_sub_account_id=None)
        await service.update(
            sub_account_id=format_id(100),
            expected_revision=3,
            label="",
            icon="",
        )
    assert list(capture.request.update_mask.paths) == ["label", "icon"]
    assert capture.request.subaccount.label == ""
    assert capture.request.subaccount.icon == ""


@pytest.mark.asyncio
async def test_subaccount_update_requires_positive_revision() -> None:
    service = AsyncSubAccountsService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="expected_revision"):
        await service.update(sub_account_id=format_id(100), expected_revision=0, label="x")


@pytest.mark.asyncio
async def test_subaccount_update_requires_non_empty_mask() -> None:
    service = AsyncSubAccountsService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="update_mask"):
        await service.update(sub_account_id=format_id(100), expected_revision=1)


@pytest.mark.asyncio
async def test_api_key_update_presence_and_clear_expires_at() -> None:
    capture = CaptureUnary(api_keys_pb2.UpdateApiKeyResponse())
    with patch("polyester.services.api_keys.unary_auth_decoded", capture):
        service = AsyncApiKeysService(transport=MagicMock(), default_sub_account_id=None)
        await service.update(
            key_id="ak_0123456789abcdef0123456789abcdef",
            expected_revision=4,
            label="",
            ip_whitelist=[],
            expires_at=None,
        )
    assert list(capture.request.update_mask.paths) == ["label", "ip_whitelist", "expires_at"]
    assert capture.request.api_key.label == ""
    assert list(capture.request.api_key.ip_whitelist) == []
    assert not capture.request.api_key.HasField("expires_at")


@pytest.mark.asyncio
async def test_api_key_update_sets_expires_at_and_falsey_status() -> None:
    expires = datetime(2030, 1, 1, tzinfo=UTC)
    capture = CaptureUnary(api_keys_pb2.UpdateApiKeyResponse())
    with patch("polyester.services.api_keys.unary_auth_decoded", capture):
        service = AsyncApiKeysService(transport=MagicMock(), default_sub_account_id=None)
        await service.update(
            key_id="ak_0123456789abcdef0123456789abcdef",
            expected_revision=2,
            status="disabled",
            ip_whitelist=["10.0.0.0/8"],
            expires_at=expires,
        )
    assert "status" in capture.request.update_mask.paths
    assert "ip_whitelist" in capture.request.update_mask.paths
    assert "expires_at" in capture.request.update_mask.paths
    assert capture.request.api_key.status == api_keys_pb2.DISABLED
    assert list(capture.request.api_key.ip_whitelist) == ["10.0.0.0/8"]
    assert capture.request.api_key.HasField("expires_at")


@pytest.mark.asyncio
async def test_api_key_create_uses_repeated_ip_whitelist() -> None:
    capture = CaptureUnary(api_keys_pb2.CreateApiKeyResponse())
    with patch("polyester.services.api_keys.unary_auth_decoded", capture):
        service = AsyncApiKeysService(transport=MagicMock(), default_sub_account_id=None)
        await service.create(label="bot", ip_whitelist=["1.2.3.4/32"])
    assert list(capture.request.ip_whitelist) == ["1.2.3.4/32"]


@pytest.mark.asyncio
async def test_policy_create_uses_nested_policy() -> None:
    capture = CaptureUnary(policies_pb2.CreateSubaccountPolicyResponse())
    with patch("polyester.services.policies.unary_auth_decoded", capture):
        service = AsyncPoliciesService(transport=MagicMock(), default_sub_account_id=None)
        await service.create_subaccount_policy(
            name="desk",
            description="d",
            sub_account_id=format_id(90),
            actions=["READ_BALANCES", "READ_SPOT"],
            trading_halted=False,
            locked=True,
            global_notional_cap=0,
        )
    assert capture.request.HasField("policy")
    assert capture.request.policy.name == "desk"
    assert capture.request.policy.description == "d"
    assert capture.request.subaccount_id == 90
    assert list(capture.request.policy.actions) == [
        policies_pb2.READ_BALANCES,
        policies_pb2.READ_SPOT,
    ]
    assert capture.request.policy.trading_halted is False
    assert capture.request.policy.locked is True
    assert capture.request.policy.global_notional_cap == 0


@pytest.mark.asyncio
async def test_api_policy_create_nested_and_assign() -> None:
    capture = CaptureUnary(policies_pb2.CreateApiPolicyResponse())
    with patch("polyester.services.policies.unary_auth_decoded", capture):
        service = AsyncPoliciesService(transport=MagicMock(), default_sub_account_id=None)
        await service.create_api_policy(
            name="api",
            actions=["READ_BALANCES", "READ_SPOT"],
            is_template=False,
            assign_to_key_id="ak_0123456789abcdef0123456789abcdef",
        )
    assert capture.request.HasField("policy")
    assert capture.request.policy.name == "api"
    assert capture.request.policy.is_template is False
    assert list(capture.request.policy.actions) == [
        policies_pb2.READ_BALANCES,
        policies_pb2.READ_SPOT,
    ]
    assert capture.request.assign_to_key_id == "ak_0123456789abcdef0123456789abcdef"


@pytest.mark.asyncio
async def test_policy_update_false_zero_empty_and_clear_timestamps() -> None:
    capture = CaptureUnary(policies_pb2.UpdateSubaccountPolicyResponse())
    with patch("polyester.services.policies.unary_auth_decoded", capture):
        service = AsyncPoliciesService(transport=MagicMock(), default_sub_account_id=None)
        await service.update_subaccount_policy(
            policy_id=format_id(50),
            expected_revision=8,
            name="",
            actions=["READ_BALANCES", "READ_SPOT"],
            spot_markets=[],
            trading_halted=False,
            global_notional_cap=0,
            review_at=None,
            expires_at=None,
        )
    assert capture.request.policy_id == 50
    assert capture.request.expected_revision == 8
    paths = list(capture.request.update_mask.paths)
    assert paths == [
        "name",
        "spot_markets",
        "actions",
        "global_notional_cap",
        "trading_halted",
        "review_at",
        "expires_at",
    ]
    assert capture.request.policy.name == ""
    assert list(capture.request.policy.actions) == [
        policies_pb2.READ_BALANCES,
        policies_pb2.READ_SPOT,
    ]
    assert list(capture.request.policy.spot_markets) == []
    assert capture.request.policy.trading_halted is False
    assert capture.request.policy.global_notional_cap == 0
    assert not capture.request.policy.HasField("review_at")
    assert not capture.request.policy.HasField("expires_at")


@pytest.mark.asyncio
async def test_api_policy_update_one_field_omits_others() -> None:
    capture = CaptureUnary(policies_pb2.UpdateApiPolicyResponse())
    with patch("polyester.services.policies.unary_auth_decoded", capture):
        service = AsyncPoliciesService(transport=MagicMock(), default_sub_account_id=None)
        await service.update_api_policy(
            policy_id=format_id(30),
            expected_revision=2,
            description="only",
        )
    assert list(capture.request.update_mask.paths) == ["description"]
    assert capture.request.policy.description == "only"
    assert capture.request.policy.name == ""
    assert capture.request.policy.is_template is False


@pytest.mark.asyncio
async def test_address_book_entry_update_no_new_tags() -> None:
    capture = CaptureUnary(address_book_pb2.UpdateAddressBookEntryResponse())
    with patch("polyester.services.address_book.unary_auth_decoded", capture):
        service = AsyncAddressBookService(transport=MagicMock(), default_sub_account_id=None)
        await service.update_entry(
            address_book_entry_id=format_id(110),
            expected_revision=6,
            label="L",
            note="",
            tag_ids=[],
        )
    assert capture.request.address_book_entry_id == 110
    assert capture.request.expected_revision == 6
    assert list(capture.request.update_mask.paths) == ["label", "note", "tag_ids"]
    assert capture.request.entry.label == "L"
    assert capture.request.entry.note == ""
    assert list(capture.request.entry.tag_ids) == []
    assert "new_tags" not in {f.name for f in capture.request.DESCRIPTOR.fields}


@pytest.mark.asyncio
async def test_address_book_tag_omit_name_vs_clear_color() -> None:
    capture = CaptureUnary(address_book_pb2.UpdateAddressBookTagResponse())
    with patch("polyester.services.address_book.unary_auth_decoded", capture):
        service = AsyncAddressBookService(transport=MagicMock(), default_sub_account_id=None)
        await service.update_tag(tag_id=format_id(40), color="")
    assert capture.request.tag_id == 40
    assert not capture.request.HasField("name")
    assert capture.request.HasField("color")
    assert capture.request.color == ""


@pytest.mark.asyncio
async def test_address_book_tag_set_name_omit_color() -> None:
    capture = CaptureUnary(address_book_pb2.UpdateAddressBookTagResponse())
    with patch("polyester.services.address_book.unary_auth_decoded", capture):
        service = AsyncAddressBookService(transport=MagicMock(), default_sub_account_id=None)
        await service.update_tag(tag_id=format_id(40), name="friends")
    assert capture.request.HasField("name")
    assert capture.request.name == "friends"
    assert not capture.request.HasField("color")


def test_revision_decoded_onto_models() -> None:
    sub = subaccount_from_proto(subaccounts_pb2.Subaccount(id=1, revision=9))
    assert sub.revision == 9

    key = api_key_from_proto(
        api_keys_pb2.ApiKey(key_id="ak_0123456789abcdef0123456789abcdef", revision=7)
    )
    assert key.revision == 7

    sub_policy = subaccount_policy_from_proto(policies_pb2.SubaccountPolicyView(id=2, revision=5))
    assert sub_policy.revision == 5

    api_policy = api_policy_from_proto(policies_pb2.ApiPolicyView(id=3, revision=4))
    assert api_policy.revision == 4

    entry = address_book_entry_from_proto(
        address_book_pb2.AddressBookEntry(address_book_entry_id=8, revision=3)
    )
    assert entry.revision == 3
