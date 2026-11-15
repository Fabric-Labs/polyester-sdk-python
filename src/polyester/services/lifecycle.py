from __future__ import annotations

from collections.abc import AsyncIterator

from polyester.codecs.contract_limits import contract_uint32_max
from polyester.codecs.decode.lifecycle import (
    account_flows_list_from_proto,
    flow_from_get_account_flow_response,
    flow_from_get_response,
    flows_by_tx_list_from_proto,
    flows_list_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_flow_detail_bytes, decode_flow_summary_bytes
from polyester.codecs.scalars import exact_integer
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2
from polyester.gen.chain.lifecycle.v1.lifecycle_read_connect import LifecycleReadServiceClient
from polyester.gen.chain.lifecycle.v1.lifecycle_read_pb2 import (
    GetAccountFlowRequest,
    GetFlowByIdRequest,
    ListAccountFlowsRequest,
    ListFlowsByTxRequest,
    ListFlowsRequest,
)
from polyester.models import LifecycleFlowsList, LifecycleFlowSummary
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded, unary_public_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto, subscribe_public_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._validation import validate_limit

# The most flows one ListAccountFlows page returns, from the contract.
ACCOUNT_FLOWS_MAX_LIMIT = contract_uint32_max(lifecycle_read_pb2.ListAccountFlowsRequest, "limit")


def _flow_list_filters(
    request: lifecycle_read_pb2.ListFlowsRequest | lifecycle_read_pb2.ListAccountFlowsRequest,
    *,
    page_token: str | None,
    scope: str | None,
    reversed: bool,
    participation: str | None,
) -> None:
    """Set the filters ``list_flows`` and ``list_account_flows`` share."""
    if participation and participation.strip():
        name = participation.strip().upper().removeprefix("PARTICIPATION_")
        if name not in ("OWNER", "RECIPIENT"):
            raise PolyesterValidationError("participation must be one of 'owner' or 'recipient'")
        request.participation = getattr(lifecycle_read_pb2, f"PARTICIPATION_{name}")
    if reversed:
        request.sort = lifecycle_read_pb2.SORT_OLDEST
    else:
        request.sort = lifecycle_read_pb2.SORT_NEWEST
    if page_token:
        request.page_token = page_token
    if scope:
        scope_name = scope.upper()
        if not scope_name.startswith("LIST_"):
            scope_name = f"LIST_{scope_name}"
        scope_enum = getattr(lifecycle_read_pb2, scope_name, None)
        if scope_enum is None:
            raise PolyesterValidationError(
                "scope must be one of 'all', 'open_only', or 'terminal_only'"
            )
        request.scope = scope_enum


class AsyncLifecycleService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        *,
        realtime: AsyncRealtimeClient | None = None,
        default_sub_account_id: str | None = None,
    ) -> None:
        super().__init__(transport)
        self._realtime = realtime
        self._default_sub_account_id = default_sub_account_id

    async def list_flows(
        self,
        *,
        limit: int = 50,
        page_token: str | None = None,
        scope: str | None = None,
        smart_account_address: str | None = None,
        reversed: bool = False,
        participation: str | None = None,
    ) -> LifecycleFlowsList:
        """List the flows a chain transaction started, newest first unless
        ``reversed``. Public and unsigned.

        Flows settled without a chain transaction, such as a transfer between
        Trading accounts or a Trading withdrawal not yet sent to a chain, are
        not listed: an account reads all of its own flows with
        :meth:`list_account_flows`. A list that selects an account by
        ``smart_account_address`` returns the flows it owns and the transfers
        other accounts sent to it; each row's ``participation`` says which.
        ``participation`` (``"owner"`` or ``"recipient"``) narrows it to one
        side; ``None`` or ``""`` returns both, and the server refuses it
        without an account. A ``page_token`` is bound to the request it was
        returned for: keep the same account, participation, scope and order;
        only ``limit`` may change.
        """
        request = ListFlowsRequest(limit=validate_limit(limit))
        _flow_list_filters(
            request,
            page_token=page_token,
            scope=scope,
            reversed=reversed,
            participation=participation,
        )
        if smart_account_address:
            request.smart_account_address = smart_account_address

        return await unary_public_decoded(
            self._transport,
            LifecycleReadServiceClient,
            lambda client, req: client.list_flows(req),
            request,
            flows_list_from_proto,
        )

    async def list_account_flows(
        self,
        *,
        limit: int = 50,
        page_token: str | None = None,
        scope: str | None = None,
        reversed: bool = False,
        participation: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> LifecycleFlowsList:
        """List the signed-in account's own flows, newest first unless
        ``reversed``: the flows it owns and the transfers it receives,
        including those no chain transaction started (transfers between
        Trading accounts, Trading withdrawals not yet on chain).

        Signed. An API key needs ``READ_FUNDING_FLOWS`` on its policy. The list
        covers one account, resolved as ``transfers.list`` resolves it: with
        neither ``account`` nor ``sub_account_id``, the client's default
        sub-account, else the account the key is scoped to. ``limit`` is 0 to
        ``ACCOUNT_FLOWS_MAX_LIMIT`` (500; 0 means the server's 100). ``scope``,
        ``participation``, ``reversed`` and ``page_token`` work as for
        :meth:`list_flows`; a page token is bound to the account and the
        request it came from, and only ``limit`` may change. Each row's
        ``participation`` is ``"owner"`` or ``"recipient"``.
        """
        request = ListAccountFlowsRequest(
            limit=exact_integer(limit, "limit", min_value=0, max_value=ACCOUNT_FLOWS_MAX_LIMIT)
        )
        _flow_list_filters(
            request,
            page_token=page_token,
            scope=scope,
            reversed=reversed,
            participation=participation,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            LifecycleReadServiceClient,
            lambda client, req: client.list_account_flows(req),
            request,
            account_flows_list_from_proto,
        )

    async def iter_account_flows(
        self,
        *,
        limit: int = 50,
        page_token: str | None = None,
        scope: str | None = None,
        reversed: bool = False,
        participation: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> AsyncIterator[LifecycleFlowSummary]:
        """Every flow :meth:`list_account_flows` lists, fetching pages as
        needed with the same arguments."""
        requested: set[str] = set()
        token = page_token
        while True:
            if token:
                requested.add(token)
            page = await self.list_account_flows(
                limit=limit,
                page_token=token,
                scope=scope,
                reversed=reversed,
                participation=participation,
                account=account,
                sub_account_id=sub_account_id,
            )
            for flow in page.flows:
                yield flow
            if not page.next_page_token:
                return
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ListAccountFlows", "next_page_token repeats an earlier page token"
                )
            token = page.next_page_token

    async def get_account_flow(
        self,
        *,
        flow_id: str,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> LifecycleFlowSummary:
        """One flow the signed-in account owns or receives, including one no
        chain transaction started; its ``participation`` says which. A flow
        the account takes no part in is not found. Signed; an API key needs
        ``READ_FUNDING_FLOWS``. The account resolves as for
        :meth:`list_account_flows`."""
        if not isinstance(flow_id, str) or not flow_id:
            raise PolyesterValidationError("flow_id is required")
        request = GetAccountFlowRequest(flow_id=flow_id)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            LifecycleReadServiceClient,
            lambda client, req: client.get_account_flow(req),
            request,
            flow_from_get_account_flow_response,
        )

    async def get_flow(
        self,
        *,
        intent_id: str | None = None,
        flow_id: str | None = None,
    ) -> LifecycleFlowSummary:
        resolved_flow_id = flow_id or intent_id
        if not resolved_flow_id:
            raise PolyesterValidationError("flow_id or intent_id is required")
        return await unary_public_decoded(
            self._transport,
            LifecycleReadServiceClient,
            lambda client, req: client.get_flow_by_id(req),
            GetFlowByIdRequest(flow_id=resolved_flow_id),
            flow_from_get_response,
        )

    async def get_flow_by_tx(
        self,
        *,
        tx_hash: str,
        lookup_kind: str = "any",
        limit: int = 50,
    ) -> LifecycleFlowsList:
        """Return all matches in the first page for a transaction lookup.

        A chain transaction can contain multiple bundled lifecycle flows.
        Use ``list_flows_by_tx`` directly when following pagination tokens.
        """
        return await self.list_flows_by_tx(
            tx_hash=tx_hash,
            lookup_kind=lookup_kind,
            limit=limit,
        )

    async def list_flows_by_tx(
        self,
        *,
        tx_hash: str,
        lookup_kind: str = "any",
        limit: int = 50,
        page_token: str | None = None,
    ) -> LifecycleFlowsList:
        kind_name = lookup_kind.upper()
        if not kind_name.startswith("TX_"):
            kind_name = f"TX_{kind_name}"
        lookup_enum = getattr(lifecycle_read_pb2, kind_name, lifecycle_read_pb2.TX_ANY)
        request = ListFlowsByTxRequest(
            tx_hash=tx_hash,
            lookup_kind=lookup_enum,
            limit=validate_limit(limit),
        )
        if page_token:
            request.page_token = page_token
        return await unary_public_decoded(
            self._transport,
            LifecycleReadServiceClient,
            lambda client, req: client.list_flows_by_tx(req),
            request,
            flows_by_tx_list_from_proto,
        )

    async def subscribe_open_flows(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[LifecycleFlowSummary]:
        if account_id is not None and str(account_id).strip():
            return await subscribe_account_proto(
                self._realtime,
                channel_template="private:chain:lifecycle:flows:{account_id}:proto",
                account_id=account_id,
                default_account_id=None,
                decode=decode_flow_summary_bytes,
            )
        return await subscribe_public_proto(
            self._realtime,
            channel="public:chain:lifecycle:flows:proto",
            decode=decode_flow_summary_bytes,
        )

    async def subscribe_flow_detail(
        self,
        *,
        flow_id: str,
    ) -> AsyncSubscription[LifecycleFlowSummary]:
        if not flow_id.strip():
            raise PolyesterValidationError("flow_id is required")
        channel = f"public:chain:lifecycle:flow:{flow_id}:proto"
        return await subscribe_public_proto(
            self._realtime,
            channel=channel,
            decode=decode_flow_detail_bytes,
        )
