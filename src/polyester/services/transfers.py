from __future__ import annotations

from polyester.codecs.decode.transfers import transfers_list_from_proto
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.gen.ledger.read.v1.ledger_read_connect import LedgerReadServiceClient
from polyester.gen.ledger.read.v1.ledger_read_pb2 import ListTransfersRequest
from polyester.models import TransfersList
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import resolve_sub_account_id


class AsyncTransfersService(BaseService):
    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def list(
        self,
        *,
        sub_account_id: str | None = None,
        limit: int = 50,
        reversed: bool = False,
        since: int | None = None,
    ) -> TransfersList:
        request = ListTransfersRequest(limit=limit, reversed=reversed)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if since is not None:
            request.since = since
        return await unary_auth_decoded(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.list_transfers(req),
            request,
            transfers_list_from_proto,
        )

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
