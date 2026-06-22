from __future__ import annotations

from polyester.codecs.decode.sub_accounts import (
    create_subaccount_from_proto,
    get_subaccount_from_proto,
    invite_subaccount_member_from_proto,
    respond_subaccount_invite_from_proto,
    subaccount_activity_list_from_proto,
    subaccount_invites_list_from_proto,
    subaccount_members_list_from_proto,
    subaccounts_list_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.scalars import id_to_int
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import subaccounts_pb2
from polyester.gen.auth.v1.subaccounts_connect import (
    SubaccountServiceClient,
    SubaccountViewServiceClient,
)
from polyester.gen.auth.v1.subaccounts_pb2 import (
    CreateSubaccountRequest,
    GetSubaccountRequest,
    InviteSubaccountMemberRequest,
    ListSubaccountEventsRequest,
    ListSubaccountInvitesRequest,
    ListSubaccountMembersRequest,
    ListSubaccountsRequest,
    RemoveSubaccountMemberRequest,
    RespondSubaccountInviteRequest,
    SetSubaccountMemberMFARequirementRequest,
    UpdateSubaccountMemberRoleRequest,
    UpdateSubaccountRequest,
)
from polyester.models.sub_accounts import (
    CreateSubaccountResult,
    GetSubaccountResult,
    SubAccountActivityList,
    SubAccountInvite,
    SubAccountInvitesList,
    SubAccountMembersList,
    SubAccountsList,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import resolve_sub_account_id


def _subaccount_role_to_proto(value: str) -> int:
    normalized = value.lower().replace("-", "_")
    if normalized.startswith("subaccount_role_"):
        enum_name = normalized.upper()
    else:
        enum_name = normalized.upper()
    role = getattr(subaccounts_pb2, enum_name, None)
    if role is None:
        raise PolyesterValidationError(f"unknown subaccount role: {value}")
    return role


def _invite_action_to_proto(value: str) -> int:
    normalized = value.lower().replace("-", "_")
    aliases = {
        "accept": subaccounts_pb2.SUBACCOUNT_INVITE_ACTION_ACCEPT,
        "decline": subaccounts_pb2.SUBACCOUNT_INVITE_ACTION_DECLINE,
        "cancel": subaccounts_pb2.SUBACCOUNT_INVITE_ACTION_CANCEL,
    }
    if normalized in aliases:
        return aliases[normalized]
    action = getattr(subaccounts_pb2, f"SUBACCOUNT_INVITE_ACTION_{normalized.upper()}", None)
    if action is None:
        raise PolyesterValidationError("invite action must be 'accept', 'decline', or 'cancel'")
    return action


class AsyncSubAccountsService(BaseService):
    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def list(self) -> SubAccountsList:
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
        sub_account_id: str | None = None,
        include_api_keys: bool = False,
        include_members: bool = False,
        include_invites: bool = False,
        include_policy: bool = False,
        include_balances: bool = False,
        invites_direction: str = "",
    ) -> GetSubaccountResult:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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
            invites_direction=invites_direction,
        )
        return await unary_auth_decoded(
            self._transport,
            SubaccountViewServiceClient,
            lambda client, req: client.get_subaccount(req),
            request,
            get_subaccount_from_proto,
        )

    async def create(
        self,
        *,
        smart_account_address: str,
        nonce: str,
        signature: str,
        label: str = "",
        icon: str = "",
        color: str = "",
        primary_wallet_address: str = "",
        wallet_provider: str = "",
    ) -> CreateSubaccountResult:
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.create_subaccount(req),
            CreateSubaccountRequest(
                label=label,
                icon=icon,
                color=color,
                smart_account_address=smart_account_address,
                nonce=nonce,
                signature=signature,
                primary_wallet_address=primary_wallet_address,
                wallet_provider=wallet_provider,
            ),
            create_subaccount_from_proto,
        )

    async def update(
        self,
        *,
        sub_account_id: str | None = None,
        label: str = "",
        icon: str = "",
        color: str = "",
        status: str = "",
    ) -> None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.update_subaccount(req),
            UpdateSubaccountRequest(
                subaccount_id=parsed_sub,
                label=label,
                icon=icon,
                color=color,
                status=status,
            ),
            lambda _msg: None,
        )

    async def delete(self, *, sub_account_id: str | None = None) -> None:
        """Soft-delete a subaccount by setting status to deleted."""
        await self.update(sub_account_id=sub_account_id, status="deleted")

    async def set_member_mfa_requirement(
        self,
        *,
        sub_account_id: str | None = None,
        require_member_mfa: bool,
    ) -> None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.set_subaccount_member_m_f_a_requirement(req),
            SetSubaccountMemberMFARequirementRequest(
                subaccount_id=parsed_sub,
                require_member_mfa=require_member_mfa,
            ),
            lambda _msg: None,
        )

    async def list_members(
        self,
        *,
        sub_account_id: str | None = None,
    ) -> SubAccountMembersList:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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

    async def remove_member(
        self,
        *,
        sub_account_id: str | None = None,
        grantee_account_id: str,
    ) -> None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.remove_subaccount_member(req),
            RemoveSubaccountMemberRequest(
                subaccount_id=parsed_sub,
                grantee_account_id=id_to_int(grantee_account_id, "grantee_account_id"),
            ),
            lambda _msg: None,
        )

    async def update_member_role(
        self,
        *,
        sub_account_id: str | None = None,
        grantee_account_id: str,
        role: str,
    ) -> None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.update_subaccount_member_role(req),
            UpdateSubaccountMemberRoleRequest(
                subaccount_id=parsed_sub,
                grantee_account_id=id_to_int(grantee_account_id, "grantee_account_id"),
                role=_subaccount_role_to_proto(role),
            ),
            lambda _msg: None,
        )

    async def invite_member(
        self,
        *,
        sub_account_id: str | None = None,
        grantee_account_id: str,
        role: str,
    ) -> SubAccountInvite | None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.invite_subaccount_member(req),
            InviteSubaccountMemberRequest(
                subaccount_id=parsed_sub,
                grantee_account_id=id_to_int(grantee_account_id, "grantee_account_id"),
                role=_subaccount_role_to_proto(role),
            ),
            invite_subaccount_member_from_proto,
        )

    async def list_invites(self, *, direction: str = "") -> SubAccountInvitesList:
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.list_subaccount_invites(req),
            ListSubaccountInvitesRequest(direction=direction),
            subaccount_invites_list_from_proto,
        )

    async def respond_invite(
        self,
        *,
        invite_id: str,
        action: str,
    ) -> SubAccountInvite | None:
        return await unary_auth_decoded(
            self._transport,
            SubaccountServiceClient,
            lambda client, req: client.respond_subaccount_invite(req),
            RespondSubaccountInviteRequest(
                invite_id=id_to_int(invite_id, "invite_id"),
                action=_invite_action_to_proto(action),
            ),
            respond_subaccount_invite_from_proto,
        )

    async def list_activity(
        self,
        *,
        sub_account_id: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> SubAccountActivityList:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        request = ListSubaccountEventsRequest(subaccount_id=parsed_sub, limit=limit)
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            SubaccountViewServiceClient,
            lambda client, req: client.list_subaccount_activity(req),
            request,
            subaccount_activity_list_from_proto,
        )

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
