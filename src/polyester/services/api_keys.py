from __future__ import annotations

from datetime import UTC, datetime

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.api_keys import (
    api_key_from_create_proto,
    api_key_from_get_proto,
    api_key_from_update_proto,
    api_key_status_from_label,
    api_keys_list_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.gen.auth.v1.api_keys_connect import ApiKeyServiceClient
from polyester.gen.auth.v1.api_keys_pb2 import (
    CreateApiKeyRequest,
    DeleteApiKeyRequest,
    GetApiKeyRequest,
    IpWhitelist,
    ListApiKeysRequest,
    UpdateApiKeyRequest,
)
from polyester.models import ApiKeysList, ApiKeySummary
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import resolve_sub_account_id


class AsyncApiKeysService(BaseService):
    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def list(
        self,
        *,
        sub_account_id: str | None = None,
    ) -> ApiKeysList:
        request = ListApiKeysRequest()
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.list_api_keys(req),
            request,
            api_keys_list_from_proto,
        )

    async def get(self, *, key_id: str) -> ApiKeySummary | None:
        return await unary_auth_decoded(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.get_api_key(req),
            GetApiKeyRequest(key_id=key_id),
            api_key_from_get_proto,
        )

    async def create(
        self,
        *,
        label: str,
        sub_account_id: str | None = None,
        icon: str = "",
        color: str = "",
        ip_whitelist: list[str] | None = None,
        public_key_ed25519: bytes | None = None,
    ) -> ApiKeySummary | None:
        request = CreateApiKeyRequest(label=label, icon=icon, color=color)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if ip_whitelist:
            request.ip_whitelist.extend(ip_whitelist)
        if public_key_ed25519 is not None:
            request.public_key_ed25519 = public_key_ed25519
        return await unary_auth_decoded(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.create_api_key(req),
            request,
            api_key_from_create_proto,
        )

    async def update(
        self,
        *,
        key_id: str,
        label: str = "",
        icon: str = "",
        color: str = "",
        status: str | None = None,
        ip_whitelist: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> ApiKeySummary | None:
        request = UpdateApiKeyRequest(key_id=key_id, label=label, icon=icon, color=color)
        if status:
            request.status = api_key_status_from_label(status)
        if ip_whitelist is not None:
            request.ip_whitelist.CopyFrom(IpWhitelist(cidrs=ip_whitelist))
        if expires_at is not None:
            if expires_at.tzinfo is None:
                from polyester.errors import PolyesterValidationError

                raise PolyesterValidationError("expires_at must be timezone-aware")
            utc = expires_at.astimezone(UTC)
            request.expires_at.CopyFrom(
                Timestamp(
                    seconds=int(utc.timestamp()),
                    nanos=utc.microsecond * 1000,
                )
            )
        return await unary_auth_decoded(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.update_api_key(req),
            request,
            api_key_from_update_proto,
        )

    async def delete(self, *, key_id: str) -> None:
        await unary_auth_decoded(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.delete_api_key(req),
            DeleteApiKeyRequest(key_id=key_id),
            lambda _msg: None,
        )

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
