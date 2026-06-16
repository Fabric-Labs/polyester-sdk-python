from __future__ import annotations

from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.wire_decode import decode_api_key, decode_api_keys_list
from polyester.gen.auth.v1.api_keys_connect import ApiKeyServiceClient
from polyester.gen.auth.v1.api_keys_pb2 import GetApiKeyRequest, ListApiKeysRequest
from polyester.models import ApiKeysList, ApiKeySummary
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth
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
        data = await unary_auth(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.list_api_keys(req),
            request,
        )
        return decode_api_keys_list(data)

    async def get(self, *, key_id: str) -> ApiKeySummary:
        data = await unary_auth(
            self._transport,
            ApiKeyServiceClient,
            lambda client, req: client.get_api_key(req),
            GetApiKeyRequest(key_id=key_id),
        )
        key_raw = data.get("apiKey") or data.get("api_key")
        if isinstance(key_raw, dict):
            return decode_api_key(key_raw)
        return ApiKeySummary(key_id=key_id)

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
