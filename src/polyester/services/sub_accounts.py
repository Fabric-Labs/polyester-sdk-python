from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Any

from polyester.codecs.contract_limits import contract_repeated_items, contract_string_length
from polyester.codecs.decode.sub_accounts import (
    get_subaccount_from_proto,
    subaccount_activity_list_from_proto,
    subaccount_invites_list_from_proto,
    subaccount_members_list_from_proto,
    subaccounts_list_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.proto_helpers import optional_datetime_to_timestamp
from polyester.codecs.realtime_decode import decode_api_key_bytes, decode_subaccount_bytes
from polyester.codecs.scalars import parse_account_id
from polyester.codecs.sub_accounts import invite_direction_from_label
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import subaccounts_pb2
from polyester.gen.auth.v1.activity_connect import AccountActivityServiceClient
from polyester.gen.auth.v1.activity_pb2 import ListAccountActivityRequest
from polyester.gen.auth.v1.subaccounts_connect import (
    SubaccountServiceClient,
    SubaccountViewServiceClient,
)
from polyester.gen.auth.v1.subaccounts_pb2 import (
    GetSubaccountRequest,
    ListSubaccountEventsRequest,
    ListSubaccountInvitesRequest,
    ListSubaccountMembersRequest,
    ListSubaccountsRequest,
)
from polyester.models.sub_accounts import (
    GetSubaccountResult,
    SubAccount,
    SubAccountActivityEvent,
    SubAccountActivityList,
    SubAccountInvitesList,
    SubAccountMembersList,
    SubAccountsList,
)
from polyester.models.trading import ApiKeySummary
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._validation import validate_limit
from polyester.services.changelog import _paginate

# ListAccountActivity filter limits, from the contract's validation rules.
_ACTIVITY_MAX_SUBACCOUNTS = contract_repeated_items(ListAccountActivityRequest, "subaccount_ids")[1]
_ACTIVITY_MAX_ENTITY_KINDS = contract_repeated_items(ListAccountActivityRequest, "entity_kinds")[1]
_ACTIVITY_MAX_ACTIONS = contract_repeated_items(ListAccountActivityRequest, "event_actions")[1]
_ACTIVITY_MAX_SOURCES = contract_repeated_items(ListAccountActivityRequest, "sources")[1]
_ACTIVITY_PAGE_TOKEN_MAX_LEN = contract_string_length(ListAccountActivityRequest, "page_token")[1]


class AsyncSubAccountsService(ScopedSubAccountMixin, BaseService):
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

    async def list(self) -> SubAccountsList:
        """List sub-accounts. An API key needs ``READ_SUBACCOUNTS``."""
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.list_subaccounts(req),
            ListSubaccountsRequest(),
            subaccounts_list_from_proto,
        )

    async def get(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        include_api_keys: bool = False,
        include_members: bool = False,
        include_invites: bool = False,
        include_policy: bool = False,
        include_balances: bool = False,
        invites_direction: str = "",
    ) -> GetSubaccountResult:
        """Read the aggregated view of one sub-account.

        An API key needs ``READ_SUBACCOUNTS``; the members and invites are
        left out, rather than failing, for a key without
        ``READ_SUBACCOUNT_MEMBERS`` or ``READ_SUBACCOUNT_INVITES``.

        ``include_balances=True`` also returns the sub-account's current
        ``balances``, in the shape of ``balances.list``. It needs the
        ``READ_BALANCES`` action on the sub-account (its role, its attached
        policy and, for an API key, the key's policy), or the call raises
        ``PermissionDenied`` (``AUTH_SUBACCOUNT_ACCESS_DENIED``); a root-scoped
        API key cannot read a sub-account's balances. When balances cannot be
        read right now it raises ``AUTH_TEMPORARILY_UNAVAILABLE``, which
        :func:`polyester.is_retryable_error` reports retryable: retry, or omit
        ``include_balances`` for the rest of the view.
        """
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        request = GetSubaccountRequest(
            subaccount_id=parsed_sub,
            include_api_keys=include_api_keys,
            include_members=include_members,
            include_invites=include_invites,
            include_policy=include_policy,
            include_balances=include_balances,
            invites_direction=invite_direction_from_label(invites_direction),
        )
        return await unary_auth_decoded(
            self._transport,
            SubaccountViewServiceClient,
            lambda client, req: client.get_subaccount(req),
            request,
            get_subaccount_from_proto,
        )

    async def list_members(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> SubAccountMembersList:
        """List a sub-account's members. An API key needs
        ``READ_SUBACCOUNT_MEMBERS``."""
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.list_subaccount_members(req),
            ListSubaccountMembersRequest(subaccount_id=parsed_sub),
            subaccount_members_list_from_proto,
        )

    async def list_invites(self, *, direction: str = "") -> SubAccountInvitesList:
        """List sub-account invites. An API key needs ``READ_SUBACCOUNT_INVITES``."""
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.list_subaccount_invites(req),
            ListSubaccountInvitesRequest(direction=invite_direction_from_label(direction)),
            subaccount_invites_list_from_proto,
        )

    async def list_activity(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> SubAccountActivityList:
        """List a sub-account's activity. An API key needs
        ``READ_SUBACCOUNT_ACTIVITY``."""
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        request = ListSubaccountEventsRequest(
            subaccount_id=parsed_sub,
            limit=validate_limit(limit, ListSubaccountEventsRequest),
        )
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            SubaccountViewServiceClient,
            lambda client, req: client.list_subaccount_activity(req),
            request,
            subaccount_activity_list_from_proto,
        )

    async def list_account_activity(
        self,
        *,
        sub_account_ids: Sequence[str | int] | None = None,
        include_main_account: bool = False,
        entity_kinds: Sequence[str] | None = None,
        event_actions: Sequence[str] | None = None,
        sources: Sequence[str] | None = None,
        api_key_id: str | int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> SubAccountActivityList:
        """One page of the activity of the main account and its sub-accounts,
        newest first (``auth.v1.AccountActivityService/ListAccountActivity``).

        ``sub_account_ids`` (public IDs, at most 100, each once) and
        ``include_main_account`` select the accounts: with neither, the main
        account and every sub-account the caller may read; ``include_main_account``
        alone, only the main account's own events, which carry no
        ``subaccount_id``. The client's default sub-account does not apply.
        ``entity_kinds`` (at most 16), ``event_actions`` (at most 32) and
        ``sources`` (at most 8) take the labels events carry, such as
        ``"session"``, ``"created"`` and ``"api"``, each once; ``api_key_id``
        keeps the events performed with that key; ``start_time`` (inclusive)
        and ``end_time`` (exclusive) are timezone-aware ``datetime`` objects,
        ``end_time`` after ``start_time``. ``limit`` is 1 to 200; ``None`` takes the server's 50.
        Reuse ``next_page_token`` only with the same filters. A filter the
        contract refuses raises :class:`PolyesterValidationError` before
        sending. An API key needs ``READ_ACCOUNT_ACTIVITY``
        (``READ_SUBACCOUNT_ACTIVITY`` does not grant it); a key scoped to a
        sub-account may not set ``include_main_account``.
        """
        request = ListAccountActivityRequest(
            include_main_account=_bool(include_main_account, "include_main_account"),
            entity_kinds=_activity_labels(
                subaccounts_pb2.ActivityEntityKind,
                "ACTIVITY_ENTITY_",
                entity_kinds,
                "entity_kinds",
                _ACTIVITY_MAX_ENTITY_KINDS,
            ),
            event_actions=_activity_labels(
                subaccounts_pb2.ActivityEventAction,
                "ACTIVITY_ACTION_",
                event_actions,
                "event_actions",
                _ACTIVITY_MAX_ACTIONS,
            ),
            sources=_activity_labels(
                subaccounts_pb2.ActivityEventSource,
                "ACTIVITY_SOURCE_",
                sources,
                "sources",
                _ACTIVITY_MAX_SOURCES,
            ),
        )
        if sub_account_ids is not None:
            if isinstance(sub_account_ids, str | bytes) or not isinstance(
                sub_account_ids, Sequence
            ):
                raise PolyesterValidationError("sub_account_ids must be a sequence of IDs")
            ids = [
                parse_account_id(value, f"sub_account_ids[{index}]")
                for index, value in enumerate(sub_account_ids)
            ]
            if len(ids) > _ACTIVITY_MAX_SUBACCOUNTS:
                raise PolyesterValidationError(
                    f"sub_account_ids takes at most {_ACTIVITY_MAX_SUBACCOUNTS} IDs"
                )
            if len(set(ids)) != len(ids):
                raise PolyesterValidationError("sub_account_ids must name each sub-account once")
            request.subaccount_ids.extend(ids)
        if api_key_id is not None:
            request.api_key_id = parse_account_id(api_key_id, "api_key_id")
        start_ts = optional_datetime_to_timestamp(start_time, "start_time")
        end_ts = optional_datetime_to_timestamp(end_time, "end_time")
        if start_time is not None and end_time is not None and not end_time > start_time:
            raise PolyesterValidationError("end_time must be after start_time")
        if start_ts is not None:
            request.start_time.CopyFrom(start_ts)
        if end_ts is not None:
            request.end_time.CopyFrom(end_ts)
        checked_limit = validate_limit(limit, ListAccountActivityRequest, allow_none=True)
        if checked_limit is not None:
            if checked_limit == 0:
                raise PolyesterValidationError("limit must be 1 to 200, or None")
            request.limit = checked_limit
        if page_token is not None:
            if not isinstance(page_token, str) or len(page_token) > _ACTIVITY_PAGE_TOKEN_MAX_LEN:
                raise PolyesterValidationError(
                    f"page_token must be a string of at most {_ACTIVITY_PAGE_TOKEN_MAX_LEN} "
                    "characters"
                )
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            AccountActivityServiceClient,
            lambda client, req: client.list_account_activity(req),
            request,
            subaccount_activity_list_from_proto,
        )

    async def iter_account_activity(
        self,
        *,
        sub_account_ids: Sequence[str | int] | None = None,
        include_main_account: bool = False,
        entity_kinds: Sequence[str] | None = None,
        event_actions: Sequence[str] | None = None,
        sources: Sequence[str] | None = None,
        api_key_id: str | int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[SubAccountActivityEvent]:
        """Every event :meth:`list_account_activity` lists with these filters,
        newest first, fetching pages as needed with the same filters."""

        async def fetch(token: str | None) -> tuple[list[SubAccountActivityEvent], str]:
            page = await self.list_account_activity(
                sub_account_ids=sub_account_ids,
                include_main_account=include_main_account,
                entity_kinds=entity_kinds,
                event_actions=event_actions,
                sources=sources,
                api_key_id=api_key_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                page_token=token,
            )
            return page.events, page.next_page_token

        async for event in _paginate("ListAccountActivity", page_token, fetch):
            yield event

    async def subscribe(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[SubAccount]:
        """Updates of the sub-accounts the account owns. An API key needs
        ``READ_SUBACCOUNTS``; a token refusal raises with the read's own error
        code. Records reached through a delegated sub-account role stream on a separate
        channel for signed-in sessions only; an API key cannot subscribe to it.
        """
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:auth:subaccounts:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_subaccount_bytes,
        )

    async def subscribe_api_keys(
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


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise PolyesterValidationError(f"{field} must be a bool")
    return value


def _activity_labels(
    enum_type, prefix: str, labels: Sequence[str] | None, field: str, max_items: int
) -> list[Any]:
    """Activity filter labels as the contract takes them: each a defined,
    specified value (``"session"`` is ``ACTIVITY_ENTITY_SESSION``), each once,
    at most ``max_items``."""
    if labels is None:
        return []
    if isinstance(labels, str | bytes) or not isinstance(labels, Sequence):
        raise PolyesterValidationError(f"{field} must be a sequence of labels, not a string")
    values: list[Any] = []
    for label in labels:
        if not isinstance(label, str) or not label.isascii() or not label:
            raise PolyesterValidationError(f"{field}: unknown value {label!r}")
        name = label.upper()
        if not name.startswith(prefix):
            name = prefix + name
        try:
            value = int(enum_type.Value(name))
        except ValueError:
            value = 0
        if value == 0:
            raise PolyesterValidationError(f"{field}: unknown value {label!r}")
        values.append(value)
    if len(values) > max_items:
        raise PolyesterValidationError(f"{field} takes at most {max_items} values")
    if len(set(values)) != len(values):
        raise PolyesterValidationError(f"{field} must name each value once")
    return values
