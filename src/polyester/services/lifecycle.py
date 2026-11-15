from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from polyester.codecs.contract_limits import contract_repeated_items, contract_uint32_max
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
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2
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
# The most IDs one ListAccountFlows ID filter takes, from the contract.
ACCOUNT_FLOWS_MAX_FILTER_IDS = contract_repeated_items(
    lifecycle_read_pb2.ListAccountFlowsRequest, "unified_asset_ids"
)[1]

_FLOW_KIND_LABELS = "'deposit', 'withdraw' or 'transfer'"
_FLOW_STATE_LABELS = (
    "'pending_source', 'pending_polyester_chain', 'pending_ledger', 'completed', "
    "'failed' or 'dropped'"
)
_ORDER_BY_LABELS = "'last_activity' or 'started_at'"


def _enum_label(label: str | None, enum: object, prefix: str, field: str, allowed: str) -> int:
    """A lowercase label such as ``"deposit"``, in any case and with or
    without its prefix; ``None`` or ``""`` is the zero value."""
    if label is None:
        return 0
    if not isinstance(label, str):
        raise PolyesterValidationError(f"{field} must be one of {allowed}")
    text = label.strip().upper()
    if not text:
        return 0
    name = prefix + text.removeprefix(prefix)
    try:
        value = int(enum.Value(name))  # type: ignore[attr-defined]
    except ValueError:
        value = 0
    if value == 0:
        raise PolyesterValidationError(f"{field} must be one of {allowed}")
    return value


def _filter_ids(field: str, ids: Sequence[int] | None) -> list[int]:
    """An ID filter as the contract takes it: at most
    ``ACCOUNT_FLOWS_MAX_FILTER_IDS`` unique positive IDs."""
    if ids is None:
        return []
    if isinstance(ids, (str, bytes)):
        raise PolyesterValidationError(f"{field} must be a list of IDs")
    out = [exact_integer(v, field, min_value=1, max_value=2**32 - 1) for v in ids]
    if len(out) > ACCOUNT_FLOWS_MAX_FILTER_IDS:
        raise PolyesterValidationError(
            f"{field} holds at most {ACCOUNT_FLOWS_MAX_FILTER_IDS} IDs, not {len(out)}"
        )
    seen: set[int] = set()
    for v in out:
        if v in seen:
            raise PolyesterValidationError(f"{field} repeats {v}")
        seen.add(v)
    return out


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
        flow_kind: str | None = None,
        flow_state: str | None = None,
        tx_ref: str | None = None,
        polyester_chain_ids: Sequence[int] | None = None,
        zipped_asset_ids: Sequence[int] | None = None,
        unified_asset_ids: Sequence[int] | None = None,
        order_by: str | None = None,
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

        Every filter of the contract's request is available: ``flow_kind``
        (``"deposit"``, ``"withdraw"`` or ``"transfer"``), ``flow_state``
        (``"pending_source"``, ``"pending_polyester_chain"``,
        ``"pending_ledger"``, ``"completed"``, ``"failed"`` or ``"dropped"``),
        ``tx_ref`` (a source or latest activity transaction identifier),
        ``polyester_chain_ids``, ``zipped_asset_ids`` and ``unified_asset_ids``
        (each at most ``ACCOUNT_FLOWS_MAX_FILTER_IDS``, 100, unique positive
        IDs) and ``order_by`` (``"last_activity"``, the default, or
        ``"started_at"``). ``None`` or empty leaves a filter out.
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
        request.flow_kind = _enum_label(  # type: ignore[assignment]
            flow_kind, types_pb2.FlowKind, "KIND_", "flow_kind", _FLOW_KIND_LABELS
        )
        request.flow_state = _enum_label(  # type: ignore[assignment]
            flow_state, types_pb2.FlowState, "STATE_", "flow_state", _FLOW_STATE_LABELS
        )
        request.order_by = _enum_label(  # type: ignore[assignment]
            order_by, lifecycle_read_pb2.ListOrderBy, "ORDER_BY_", "order_by", _ORDER_BY_LABELS
        )
        if tx_ref is not None:
            if not isinstance(tx_ref, str):
                raise PolyesterValidationError("tx_ref must be a string")
            request.tx_ref = tx_ref
        request.polyester_chain_ids.extend(_filter_ids("polyester_chain_ids", polyester_chain_ids))
        request.zipped_asset_ids.extend(_filter_ids("zipped_asset_ids", zipped_asset_ids))
        request.unified_asset_ids.extend(_filter_ids("unified_asset_ids", unified_asset_ids))
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
        flow_kind: str | None = None,
        flow_state: str | None = None,
        tx_ref: str | None = None,
        polyester_chain_ids: Sequence[int] | None = None,
        zipped_asset_ids: Sequence[int] | None = None,
        unified_asset_ids: Sequence[int] | None = None,
        order_by: str | None = None,
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
                flow_kind=flow_kind,
                flow_state=flow_state,
                tx_ref=tx_ref,
                polyester_chain_ids=polyester_chain_ids,
                zipped_asset_ids=zipped_asset_ids,
                unified_asset_ids=unified_asset_ids,
                order_by=order_by,
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
