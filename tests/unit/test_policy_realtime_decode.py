from __future__ import annotations

from polyester.codecs.proto_helpers import format_uint64_id
from polyester.codecs.realtime_decode import (
    decode_api_policy_bytes,
    decode_subaccount_policy_bytes,
)
from polyester.gen.auth.v1 import policies_pb2


def test_decode_api_policy_bytes() -> None:
    payload = policies_pb2.ApiPolicyView(
        id=9,
        name="bots",
        description="api key policy",
        revision=4,
    ).SerializeToString()
    policy = decode_api_policy_bytes(payload)
    assert policy.id == format_uint64_id(9)
    assert policy.name == "bots"
    assert policy.revision == 4


def test_decode_subaccount_policy_bytes() -> None:
    payload = policies_pb2.SubaccountPolicyView(
        id=7,
        name="trader",
        revision=3,
    ).SerializeToString()
    policy = decode_subaccount_policy_bytes(payload)
    assert policy.id == format_uint64_id(7)
    assert policy.name == "trader"
    assert policy.revision == 3
