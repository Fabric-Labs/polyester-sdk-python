from __future__ import annotations

from polyester.codecs.decode.resolve import resolved_accounts_from_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1.resolve_connect import ResolveServiceClient
from polyester.gen.auth.v1.resolve_pb2 import ResolveAccountRequest
from polyester.models import ResolvedAccountsList
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded


class AsyncResolveService(BaseService):
    async def resolve_account(
        self,
        *,
        query: str,
        hint: str = "auto",
        include_subaccounts: bool = False,
    ) -> ResolvedAccountsList:
        from polyester.gen.auth.v1 import resolve_pb2

        hint_aliases = {
            "auto": "RESOLVE_HINT_UNSPECIFIED",
            "unspecified": "RESOLVE_HINT_UNSPECIFIED",
            "username": "USERNAME",
            "id": "ID",
            "smart_account": "SMART_ACCOUNT",
        }
        hint_key = hint.lower()
        hint_name = hint_aliases.get(hint_key, hint.upper())
        if not hint_name.startswith("RESOLVE_HINT_") and hint_name not in (
            "USERNAME",
            "ID",
            "SMART_ACCOUNT",
        ):
            hint_name = f"RESOLVE_HINT_{hint_name}"
        hint_enum = getattr(resolve_pb2, hint_name, None)
        if hint_enum is None:
            raise PolyesterValidationError(
                "hint must be one of 'auto', 'username', 'id', or 'smart_account'"
            )
        request = ResolveAccountRequest(
            query=query,
            hint=hint_enum,
            include_subaccounts=include_subaccounts,
        )
        return await unary_auth_decoded(
            self._transport,
            ResolveServiceClient,
            lambda client, req: client.resolve_account(req),
            request,
            resolved_accounts_from_proto,
        )
