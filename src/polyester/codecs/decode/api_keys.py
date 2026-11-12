from __future__ import annotations

from datetime import UTC

from polyester.codecs.proto_helpers import (
    format_optional_uint64_id,
    format_uint64_id,
    proto_enum_name,
)
from polyester.codecs.scalars import timestamp_dict_to_datetime
from polyester.gen.auth.v1 import api_keys_pb2
from polyester.models import ApiKeysList, ApiKeySummary


def api_key_from_proto(msg: api_keys_pb2.ApiKey) -> ApiKeySummary:
    return ApiKeySummary(
        key_id=msg.key_id,
        label=msg.label,
        status=proto_enum_name(api_keys_pb2.ApiKeyStatus, msg.status),
        subaccount_id=format_uint64_id(msg.subaccount_id),
        created_at=timestamp_dict_to_datetime(msg.created_at),
        last_used_at=timestamp_dict_to_datetime(msg.last_used_at),
        updated_at=timestamp_dict_to_datetime(msg.updated_at),
        revision=int(msg.revision),
        purpose=proto_enum_name(api_keys_pb2.ApiKeyPurpose, msg.purpose),
        policy_id=format_optional_uint64_id(msg.policy_id),
        ip_whitelist=list(msg.ip_whitelist),
        # Integer arithmetic: the exact time to the microsecond.
        expires_at=msg.expires_at.ToDatetime(tzinfo=UTC) if msg.HasField("expires_at") else None,
        public_key_ed25519=msg.public_key_ed25519.hex(),
    )


def api_keys_list_from_proto(msg: api_keys_pb2.ListApiKeysResponse) -> ApiKeysList:
    return ApiKeysList(api_keys=[api_key_from_proto(item) for item in msg.api_keys])


def api_key_from_get_proto(msg: api_keys_pb2.GetApiKeyResponse) -> ApiKeySummary | None:
    if msg.HasField("api_key"):
        return api_key_from_proto(msg.api_key)
    return None


get_api_key_from_proto = api_key_from_get_proto
