from __future__ import annotations

from polyester.codecs.decode.address_book import address_book_entry_from_proto
from polyester.codecs.decode.api_keys import api_key_from_proto
from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
from polyester.codecs.decode.sub_accounts import subaccount_from_proto
from polyester.gen.auth.v1 import address_book_pb2, api_keys_pb2, policies_pb2, subaccounts_pb2


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
