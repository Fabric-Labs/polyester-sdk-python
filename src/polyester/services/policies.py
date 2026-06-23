from __future__ import annotations

from datetime import datetime
from typing import Any

from polyester.codecs.decode.policies import (
    api_policies_list_from_proto,
    create_api_policy_from_proto,
    create_subaccount_policy_from_proto,
    get_api_policy_from_proto,
    get_subaccount_policy_from_proto,
    subaccount_policies_list_from_proto,
    update_api_policy_from_proto,
    update_subaccount_policy_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_subaccount_policy_bytes
from polyester.codecs.scalars import id_to_int
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import policies_pb2
from polyester.gen.auth.v1.policies_connect import PolicyServiceClient
from polyester.gen.auth.v1.policies_pb2 import (
    CreateApiPolicyRequest,
    CreateSubaccountPolicyRequest,
    DeleteApiPolicyRequest,
    DeleteSubaccountPolicyRequest,
    GetApiPolicyRequest,
    GetSubaccountPolicyRequest,
    ListApiPoliciesRequest,
    ListSubaccountPoliciesRequest,
    PerpMarketRule,
    SetApiKeyPolicyRequest,
    SetSubaccountPolicyRequest,
    SpotMarketRule,
    UpdateApiPolicyRequest,
    UpdateSubaccountPolicyRequest,
)
from polyester.models.policies import (
    ApiPoliciesList,
    ApiPolicy,
    SubaccountPoliciesList,
    SubaccountPolicy,
)
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import resolve_sub_account_id


def _market_scope_to_proto(value: str | None) -> int:
    if not value:
        return policies_pb2.MarketScope.Value.ALL
    normalized = value.lower().replace("-", "_")
    if normalized in {"all", "unspecified"}:
        return policies_pb2.MarketScope.Value.ALL
    if normalized == "allowlist":
        return policies_pb2.MarketScope.Value.ALLOWLIST
    raise PolyesterValidationError("market scope must be 'all' or 'allowlist'")


def _policy_action_to_proto(value: str) -> int:
    normalized = value.lower().replace("-", "_")
    if not normalized.startswith("policy_action_"):
        enum_name = normalized.upper()
    else:
        enum_name = normalized.removeprefix("policy_action_").upper()
    action = getattr(policies_pb2, enum_name, None)
    if action is None:
        raise PolyesterValidationError(f"unknown policy action: {value}")
    return action


def _policy_actions_to_proto(values: list[str] | None) -> list[int]:
    if not values:
        return []
    return [_policy_action_to_proto(value) for value in values]


def _spot_markets_to_proto(values: list[dict[str, Any]] | None) -> list[SpotMarketRule]:
    if not values:
        return []
    return [
        SpotMarketRule(symbol=str(item.get("symbol", item.get("symbol_id", ""))))
        for item in values
    ]


def _perp_markets_to_proto(values: list[dict[str, Any]] | None) -> list[PerpMarketRule]:
    if not values:
        return []
    rules: list[PerpMarketRule] = []
    for item in values:
        rule = PerpMarketRule(symbol=str(item.get("symbol", item.get("symbol_id", ""))))
        max_leverage = item.get("max_leverage_x", item.get("maxLeverageX"))
        if max_leverage is not None:
            rule.max_leverage_x = int(max_leverage)
        rules.append(rule)
    return rules


class AsyncPoliciesService(BaseService):
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

    async def list_subaccount_policies(self) -> SubaccountPoliciesList:
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.list_subaccount_policies(req),
            ListSubaccountPoliciesRequest(),
            subaccount_policies_list_from_proto,
        )

    async def get_subaccount_policy(self, *, policy_id: str) -> SubaccountPolicy | None:
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.get_subaccount_policy(req),
            GetSubaccountPolicyRequest(policy_id=id_to_int(policy_id, "policy_id")),
            get_subaccount_policy_from_proto,
        )

    async def create_subaccount_policy(
        self,
        *,
        name: str,
        description: str = "",
        sub_account_id: str | None = None,
        spot_markets: list[dict[str, Any]] | None = None,
        perp_markets: list[dict[str, Any]] | None = None,
        spot_market_scope: str = "all",
        perp_market_scope: str = "all",
        actions: list[str] | None = None,
        global_notional_cap: int | None = None,
        max_order_notional: int | None = None,
        max_open_orders: int | None = None,
        max_open_positions: int | None = None,
        global_perp_leverage_x: int | None = None,
        daily_internal_transfer_out_limit: int | None = None,
        daily_withdraw_limit: int | None = None,
        internal_transfers_own_only: bool = True,
        enforce_withdraw_whitelist: bool = False,
        trading_halted: bool = False,
        liquidation_only: bool = False,
        daily_loss_limit: int | None = None,
        intraday_drawdown_limit_bps: int | None = None,
        locked: bool = False,
        review_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> SubaccountPolicy | None:
        request = CreateSubaccountPolicyRequest(
            name=name,
            description=description,
            spot_markets=_spot_markets_to_proto(spot_markets),
            perp_markets=_perp_markets_to_proto(perp_markets),
            spot_market_scope=_market_scope_to_proto(spot_market_scope),
            perp_market_scope=_market_scope_to_proto(perp_market_scope),
            actions=_policy_actions_to_proto(actions),
            internal_transfers_own_only=internal_transfers_own_only,
            enforce_withdraw_whitelist=enforce_withdraw_whitelist,
            trading_halted=trading_halted,
            liquidation_only=liquidation_only,
            locked=locked,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if global_notional_cap is not None:
            request.global_notional_cap = global_notional_cap
        if max_order_notional is not None:
            request.max_order_notional = max_order_notional
        if max_open_orders is not None:
            request.max_open_orders = max_open_orders
        if max_open_positions is not None:
            request.max_open_positions = max_open_positions
        if global_perp_leverage_x is not None:
            request.global_perp_leverage_x = global_perp_leverage_x
        if daily_internal_transfer_out_limit is not None:
            request.daily_internal_transfer_out_limit = daily_internal_transfer_out_limit
        if daily_withdraw_limit is not None:
            request.daily_withdraw_limit = daily_withdraw_limit
        if daily_loss_limit is not None:
            request.daily_loss_limit = daily_loss_limit
        if intraday_drawdown_limit_bps is not None:
            request.intraday_drawdown_limit_bps = intraday_drawdown_limit_bps
        if review_at is not None:
            request.review_at.FromDatetime(review_at)
        if expires_at is not None:
            request.expires_at.FromDatetime(expires_at)
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.create_subaccount_policy(req),
            request,
            create_subaccount_policy_from_proto,
        )

    async def update_subaccount_policy(
        self,
        *,
        policy_id: str,
        name: str = "",
        description: str = "",
        spot_markets: list[dict[str, Any]] | None = None,
        perp_markets: list[dict[str, Any]] | None = None,
        spot_market_scope: str = "all",
        perp_market_scope: str = "all",
        actions: list[str] | None = None,
        global_notional_cap: int | None = None,
        max_order_notional: int | None = None,
        max_open_orders: int | None = None,
        max_open_positions: int | None = None,
        global_perp_leverage_x: int | None = None,
        daily_internal_transfer_out_limit: int | None = None,
        daily_withdraw_limit: int | None = None,
        internal_transfers_own_only: bool = True,
        enforce_withdraw_whitelist: bool = False,
        trading_halted: bool = False,
        liquidation_only: bool = False,
        daily_loss_limit: int | None = None,
        intraday_drawdown_limit_bps: int | None = None,
        locked: bool = False,
        review_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> SubaccountPolicy | None:
        request = UpdateSubaccountPolicyRequest(
            policy_id=id_to_int(policy_id, "policy_id"),
            name=name,
            description=description,
            spot_markets=_spot_markets_to_proto(spot_markets),
            perp_markets=_perp_markets_to_proto(perp_markets),
            spot_market_scope=_market_scope_to_proto(spot_market_scope),
            perp_market_scope=_market_scope_to_proto(perp_market_scope),
            actions=_policy_actions_to_proto(actions),
            internal_transfers_own_only=internal_transfers_own_only,
            enforce_withdraw_whitelist=enforce_withdraw_whitelist,
            trading_halted=trading_halted,
            liquidation_only=liquidation_only,
            locked=locked,
        )
        if global_notional_cap is not None:
            request.global_notional_cap = global_notional_cap
        if max_order_notional is not None:
            request.max_order_notional = max_order_notional
        if max_open_orders is not None:
            request.max_open_orders = max_open_orders
        if max_open_positions is not None:
            request.max_open_positions = max_open_positions
        if global_perp_leverage_x is not None:
            request.global_perp_leverage_x = global_perp_leverage_x
        if daily_internal_transfer_out_limit is not None:
            request.daily_internal_transfer_out_limit = daily_internal_transfer_out_limit
        if daily_withdraw_limit is not None:
            request.daily_withdraw_limit = daily_withdraw_limit
        if daily_loss_limit is not None:
            request.daily_loss_limit = daily_loss_limit
        if intraday_drawdown_limit_bps is not None:
            request.intraday_drawdown_limit_bps = intraday_drawdown_limit_bps
        if review_at is not None:
            request.review_at.FromDatetime(review_at)
        if expires_at is not None:
            request.expires_at.FromDatetime(expires_at)
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.update_subaccount_policy(req),
            request,
            update_subaccount_policy_from_proto,
        )

    async def delete_subaccount_policy(self, *, policy_id: str) -> None:
        await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.delete_subaccount_policy(req),
            DeleteSubaccountPolicyRequest(policy_id=id_to_int(policy_id, "policy_id")),
            lambda _msg: None,
        )

    async def set_subaccount_policy(
        self,
        *,
        sub_account_id: str | None = None,
        policy_id: str,
    ) -> None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is None:
            raise PolyesterValidationError("sub_account_id is required")
        await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.set_subaccount_policy(req),
            SetSubaccountPolicyRequest(
                subaccount_id=parsed_sub,
                policy_id=id_to_int(policy_id, "policy_id"),
            ),
            lambda _msg: None,
        )

    async def list_api_policies(self) -> ApiPoliciesList:
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.list_api_policies(req),
            ListApiPoliciesRequest(),
            api_policies_list_from_proto,
        )

    async def get_api_policy(self, *, policy_id: str) -> ApiPolicy | None:
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.get_api_policy(req),
            GetApiPolicyRequest(policy_id=id_to_int(policy_id, "policy_id")),
            get_api_policy_from_proto,
        )

    async def create_api_policy(
        self,
        *,
        name: str,
        description: str = "",
        spot_markets: list[dict[str, Any]] | None = None,
        perp_markets: list[dict[str, Any]] | None = None,
        spot_market_scope: str = "all",
        perp_market_scope: str = "all",
        actions: list[str] | None = None,
        max_order_notional: int | None = None,
        daily_internal_transfer_out_limit: int | None = None,
        daily_withdraw_limit: int | None = None,
        is_template: bool = False,
        assign_to_key_id: str | None = None,
    ) -> ApiPolicy | None:
        request = CreateApiPolicyRequest(
            name=name,
            description=description,
            spot_markets=_spot_markets_to_proto(spot_markets),
            perp_markets=_perp_markets_to_proto(perp_markets),
            spot_market_scope=_market_scope_to_proto(spot_market_scope),
            perp_market_scope=_market_scope_to_proto(perp_market_scope),
            actions=_policy_actions_to_proto(actions),
            is_template=is_template,
        )
        if max_order_notional is not None:
            request.max_order_notional = max_order_notional
        if daily_internal_transfer_out_limit is not None:
            request.daily_internal_transfer_out_limit = daily_internal_transfer_out_limit
        if daily_withdraw_limit is not None:
            request.daily_withdraw_limit = daily_withdraw_limit
        if assign_to_key_id:
            request.assign_to_key_id = assign_to_key_id
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.create_api_policy(req),
            request,
            create_api_policy_from_proto,
        )

    async def update_api_policy(
        self,
        *,
        policy_id: str,
        name: str = "",
        description: str = "",
        spot_markets: list[dict[str, Any]] | None = None,
        perp_markets: list[dict[str, Any]] | None = None,
        spot_market_scope: str = "all",
        perp_market_scope: str = "all",
        actions: list[str] | None = None,
        max_order_notional: int | None = None,
        daily_internal_transfer_out_limit: int | None = None,
        daily_withdraw_limit: int | None = None,
        is_template: bool = False,
    ) -> ApiPolicy | None:
        request = UpdateApiPolicyRequest(
            policy_id=id_to_int(policy_id, "policy_id"),
            name=name,
            description=description,
            spot_markets=_spot_markets_to_proto(spot_markets),
            perp_markets=_perp_markets_to_proto(perp_markets),
            spot_market_scope=_market_scope_to_proto(spot_market_scope),
            perp_market_scope=_market_scope_to_proto(perp_market_scope),
            actions=_policy_actions_to_proto(actions),
            is_template=is_template,
        )
        if max_order_notional is not None:
            request.max_order_notional = max_order_notional
        if daily_internal_transfer_out_limit is not None:
            request.daily_internal_transfer_out_limit = daily_internal_transfer_out_limit
        if daily_withdraw_limit is not None:
            request.daily_withdraw_limit = daily_withdraw_limit
        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.update_api_policy(req),
            request,
            update_api_policy_from_proto,
        )

    async def delete_api_policy(self, *, policy_id: str) -> None:
        await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.delete_api_policy(req),
            DeleteApiPolicyRequest(policy_id=id_to_int(policy_id, "policy_id")),
            lambda _msg: None,
        )

    async def set_api_key_policy(self, *, key_id: str, policy_id: str) -> None:
        await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.set_api_key_policy(req),
            SetApiKeyPolicyRequest(
                key_id=key_id,
                policy_id=id_to_int(policy_id, "policy_id"),
            ),
            lambda _msg: None,
        )

    async def subscribe_subaccount_policies(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[SubaccountPolicy]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:auth:subaccount-policies:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_subaccount_policy_bytes,
        )

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
