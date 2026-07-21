from __future__ import annotations

from datetime import UTC, datetime

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.auth import generate_ed25519_keypair
from polyester.codecs.decode.api_keys import (
    api_key_from_create_proto,
    api_key_from_get_proto,
    api_key_from_update_proto,
    api_key_status_from_label,
    api_keys_list_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_api_key_bytes
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1.api_keys_connect import ApiKeyServiceClient
from polyester.gen.auth.v1.api_keys_pb2 import (
    ApiKeyUpdateSpec,
    CreateApiKeyRequest,
    DeleteApiKeyRequest,
    GetApiKeyRequest,
    ListApiKeysRequest,
    UpdateApiKeyRequest,
)
from polyester.models import ApiKeysList, ApiKeySummary
from polyester.models.auth import Ed25519Keypair
from polyester.patch import UNSET, field_mask, is_set, require_positive_revision
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin


def _timestamp_from_datetime(value: datetime) -> Timestamp:
    if value.tzinfo is None:
        raise PolyesterValidationError("expires_at must be timezone-aware")
    utc = value.astimezone(UTC)
    return Timestamp(seconds=int(utc.timestamp()), nanos=utc.microsecond * 1000)


class AsyncApiKeysService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        default_sub_account_id: str | None,
        *,
        default_account_id: str | int | None = None,
        realtime: AsyncRealtimeClient | None = None,
    ) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime

    async def list(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
    ) -> ApiKeysList:
        request = ListApiKeysRequest()
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
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
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        icon: str = "",
        color: str = "",
        ip_whitelist: list[str] | None = None,
        public_key_ed25519: bytes | None = None,
    ) -> ApiKeySummary | None:
        request = CreateApiKeyRequest(label=label, icon=icon, color=color)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
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
        expected_revision: int,
        label: object = UNSET,
        icon: object = UNSET,
        color: object = UNSET,
        status: object = UNSET,
        ip_whitelist: object = UNSET,
        expires_at: datetime | None | object = UNSET,
    ) -> ApiKeySummary | None:
        require_positive_revision(expected_revision)
        spec = ApiKeyUpdateSpec()
        paths: list[str] = []
        if is_set(label):
            paths.append("label")
            spec.label = str(label)
        if is_set(icon):
            paths.append("icon")
            spec.icon = str(icon)
        if is_set(color):
            paths.append("color")
            spec.color = str(color)
        if is_set(status):
            paths.append("status")
            spec.status = api_key_status_from_label(str(status))
        if is_set(ip_whitelist):
            paths.append("ip_whitelist")
            if ip_whitelist is None:
                raise PolyesterValidationError("ip_whitelist cannot be null; pass [] to clear")
            spec.ip_whitelist.extend(list(ip_whitelist))  # type: ignore[arg-type]
        if is_set(expires_at):
            paths.append("expires_at")
            if expires_at is not None:
                spec.expires_at.CopyFrom(_timestamp_from_datetime(expires_at))  # type: ignore[arg-type]
        return await unary_auth_decoded(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.update_api_key(req),
            UpdateApiKeyRequest(
                key_id=key_id,
                api_key=spec,
                update_mask=field_mask(paths),
                expected_revision=expected_revision,
            ),
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

    def generate_keypair(self) -> Ed25519Keypair:
        """Generate a local Ed25519 keypair for API key creation (secret never sent to API)."""
        public_key, secret_key = generate_ed25519_keypair()
        return Ed25519Keypair(
            public_key_hex=public_key.hex(),
            public_key=public_key,
            secret_key_hex=secret_key.hex(),
            secret_key=secret_key,
        )

    async def subscribe(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[ApiKeySummary]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:auth:api-keys:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_api_key_bytes,
        )
