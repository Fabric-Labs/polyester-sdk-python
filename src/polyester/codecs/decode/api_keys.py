from __future__ import annotations

from polyester.codecs.proto_helpers import format_uint64_id, proto_enum_name
from polyester.gen.auth.v1 import api_keys_pb2
from polyester.models import ApiKeysList, ApiKeySummary


def api_key_from_proto(msg: api_keys_pb2.ApiKey) -> ApiKeySummary:
    return ApiKeySummary(
        key_id=msg.key_id,
        label=msg.label,
        status=proto_enum_name(api_keys_pb2.ApiKeyStatus, msg.status),
        subaccount_id=format_uint64_id(msg.subaccount_id),
    )


def api_keys_list_from_proto(msg: api_keys_pb2.ListApiKeysResponse) -> ApiKeysList:
    return ApiKeysList(api_keys=[api_key_from_proto(item) for item in msg.api_keys])


def api_key_from_get_proto(msg: api_keys_pb2.GetApiKeyResponse) -> ApiKeySummary | None:
    if msg.HasField("api_key"):
        return api_key_from_proto(msg.api_key)
    return None


get_api_key_from_proto = api_key_from_get_proto


def api_key_from_create_proto(msg: api_keys_pb2.CreateApiKeyResponse) -> ApiKeySummary | None:
    if msg.HasField("api_key"):
        return api_key_from_proto(msg.api_key)
    return None


def api_key_from_update_proto(msg: api_keys_pb2.UpdateApiKeyResponse) -> ApiKeySummary | None:
    if msg.HasField("api_key"):
        return api_key_from_proto(msg.api_key)
    return None


def api_key_status_from_label(status: str) -> int:
    from polyester.errors import PolyesterValidationError

    aliases = {
        "active": api_keys_pb2.ACTIVE,
        "revoked": api_keys_pb2.REVOKED,
        "disabled": api_keys_pb2.DISABLED,
    }
    key = status.lower()
    if key in aliases:
        return aliases[key]
    enum_name = key.upper()
    value = getattr(api_keys_pb2, enum_name, None)
    if value is None:
        raise PolyesterValidationError(f"Unknown API key status: {status}")
    return value
