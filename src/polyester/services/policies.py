from __future__ import annotations

from datetime import UTC, datetime
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
from polyester.codecs.realtime_decode import (
    decode_api_policy_bytes,
    decode_subaccount_policy_bytes,
)
from polyester.codecs.scalars import id_to_int
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import policies_pb2
from polyester.gen.auth.v1.policies_connect import PolicyServiceClient
from polyester.gen.auth.v1.policies_pb2 import (
    ApiPolicySpec,
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
    SubaccountPolicySpec,
    UpdateApiPolicyRequest,
    UpdateSubaccountPolicyRequest,
)
from polyester.models.policies import (
    ApiPoliciesList,
    ApiPolicy,
    SubaccountPoliciesList,
    SubaccountPolicy,
)
from polyester.patch import UNSET, field_mask, is_set, require_positive_revision
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin


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
        SpotMarketRule(symbol=str(item.get("symbol", item.get("symbol_id", "")))) for item in values
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


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise PolyesterValidationError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _apply_optional_timestamp(target, value: datetime | None, field_name: str) -> None:
    if value is None:
        return
    getattr(target, field_name).FromDatetime(_require_timezone_aware(value, field_name))


class AsyncPoliciesService(ScopedSubAccountMixin, BaseService):
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
        account: AccountScope | None = None,
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
        policy = SubaccountPolicySpec(
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
            policy.global_notional_cap = global_notional_cap
        if max_order_notional is not None:
            policy.max_order_notional = max_order_notional
        if max_open_orders is not None:
            policy.max_open_orders = max_open_orders
        if max_open_positions is not None:
            policy.max_open_positions = max_open_positions
        if global_perp_leverage_x is not None:
            policy.global_perp_leverage_x = global_perp_leverage_x
        if daily_internal_transfer_out_limit is not None:
            policy.daily_internal_transfer_out_limit = daily_internal_transfer_out_limit
        if daily_withdraw_limit is not None:
            policy.daily_withdraw_limit = daily_withdraw_limit
        if daily_loss_limit is not None:
            policy.daily_loss_limit = daily_loss_limit
        if intraday_drawdown_limit_bps is not None:
            policy.intraday_drawdown_limit_bps = intraday_drawdown_limit_bps
        _apply_optional_timestamp(policy, review_at, "review_at")
        _apply_optional_timestamp(policy, expires_at, "expires_at")
        request = CreateSubaccountPolicyRequest(policy=policy)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
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
        expected_revision: int,
        name: object = UNSET,
        description: object = UNSET,
        spot_markets: object = UNSET,
        perp_markets: object = UNSET,
        spot_market_scope: object = UNSET,
        perp_market_scope: object = UNSET,
        actions: object = UNSET,
        global_notional_cap: object = UNSET,
        max_order_notional: object = UNSET,
        max_open_orders: object = UNSET,
        max_open_positions: object = UNSET,
        global_perp_leverage_x: object = UNSET,
        daily_internal_transfer_out_limit: object = UNSET,
        daily_withdraw_limit: object = UNSET,
        internal_transfers_own_only: object = UNSET,
        enforce_withdraw_whitelist: object = UNSET,
        trading_halted: object = UNSET,
        liquidation_only: object = UNSET,
        daily_loss_limit: object = UNSET,
        intraday_drawdown_limit_bps: object = UNSET,
        locked: object = UNSET,
        review_at: datetime | None | object = UNSET,
        expires_at: datetime | None | object = UNSET,
    ) -> SubaccountPolicy | None:
        require_positive_revision(expected_revision)
        policy = SubaccountPolicySpec()
        paths: list[str] = []

        if is_set(name):
            paths.append("name")
            policy.name = str(name)
        if is_set(description):
            paths.append("description")
            policy.description = str(description)
        if is_set(spot_markets):
            paths.append("spot_markets")
            policy.spot_markets.extend(_spot_markets_to_proto(spot_markets))  # type: ignore[arg-type]
        if is_set(perp_markets):
            paths.append("perp_markets")
            policy.perp_markets.extend(_perp_markets_to_proto(perp_markets))  # type: ignore[arg-type]
        if is_set(spot_market_scope):
            paths.append("spot_market_scope")
            policy.spot_market_scope = _market_scope_to_proto(str(spot_market_scope))
        if is_set(perp_market_scope):
            paths.append("perp_market_scope")
            policy.perp_market_scope = _market_scope_to_proto(str(perp_market_scope))
        if is_set(actions):
            paths.append("actions")
            policy.actions.extend(_policy_actions_to_proto(actions))  # type: ignore[arg-type]
        if is_set(global_notional_cap):
            paths.append("global_notional_cap")
            policy.global_notional_cap = int(global_notional_cap)  # type: ignore[arg-type]
        if is_set(max_order_notional):
            paths.append("max_order_notional")
            policy.max_order_notional = int(max_order_notional)  # type: ignore[arg-type]
        if is_set(max_open_orders):
            paths.append("max_open_orders")
            policy.max_open_orders = int(max_open_orders)  # type: ignore[arg-type]
        if is_set(max_open_positions):
            paths.append("max_open_positions")
            policy.max_open_positions = int(max_open_positions)  # type: ignore[arg-type]
        if is_set(global_perp_leverage_x):
            paths.append("global_perp_leverage_x")
            policy.global_perp_leverage_x = int(global_perp_leverage_x)  # type: ignore[arg-type]
        if is_set(daily_internal_transfer_out_limit):
            paths.append("daily_internal_transfer_out_limit")
            policy.daily_internal_transfer_out_limit = int(daily_internal_transfer_out_limit)  # type: ignore[arg-type]
        if is_set(daily_withdraw_limit):
            paths.append("daily_withdraw_limit")
            policy.daily_withdraw_limit = int(daily_withdraw_limit)  # type: ignore[arg-type]
        if is_set(internal_transfers_own_only):
            paths.append("internal_transfers_own_only")
            policy.internal_transfers_own_only = bool(internal_transfers_own_only)
        if is_set(enforce_withdraw_whitelist):
            paths.append("enforce_withdraw_whitelist")
            policy.enforce_withdraw_whitelist = bool(enforce_withdraw_whitelist)
        if is_set(trading_halted):
            paths.append("trading_halted")
            policy.trading_halted = bool(trading_halted)
        if is_set(liquidation_only):
            paths.append("liquidation_only")
            policy.liquidation_only = bool(liquidation_only)
        if is_set(daily_loss_limit):
            paths.append("daily_loss_limit")
            policy.daily_loss_limit = int(daily_loss_limit)  # type: ignore[arg-type]
        if is_set(intraday_drawdown_limit_bps):
            paths.append("intraday_drawdown_limit_bps")
            policy.intraday_drawdown_limit_bps = int(intraday_drawdown_limit_bps)  # type: ignore[arg-type]
        if is_set(locked):
            paths.append("locked")
            policy.locked = bool(locked)
        if is_set(review_at):
            paths.append("review_at")
            if review_at is not None:
                policy.review_at.FromDatetime(_require_timezone_aware(review_at, "review_at"))  # type: ignore[arg-type]
        if is_set(expires_at):
            paths.append("expires_at")
            if expires_at is not None:
                policy.expires_at.FromDatetime(_require_timezone_aware(expires_at, "expires_at"))  # type: ignore[arg-type]

        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.update_subaccount_policy(req),
            UpdateSubaccountPolicyRequest(
                policy_id=id_to_int(policy_id, "policy_id"),
                policy=policy,
                update_mask=field_mask(paths),
                expected_revision=expected_revision,
            ),
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
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        policy_id: str,
    ) -> None:
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
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
        policy = ApiPolicySpec(
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
            policy.max_order_notional = max_order_notional
        if daily_internal_transfer_out_limit is not None:
            policy.daily_internal_transfer_out_limit = daily_internal_transfer_out_limit
        if daily_withdraw_limit is not None:
            policy.daily_withdraw_limit = daily_withdraw_limit
        request = CreateApiPolicyRequest(policy=policy)
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
        expected_revision: int,
        name: object = UNSET,
        description: object = UNSET,
        spot_markets: object = UNSET,
        perp_markets: object = UNSET,
        spot_market_scope: object = UNSET,
        perp_market_scope: object = UNSET,
        actions: object = UNSET,
        max_order_notional: object = UNSET,
        daily_internal_transfer_out_limit: object = UNSET,
        daily_withdraw_limit: object = UNSET,
        is_template: object = UNSET,
    ) -> ApiPolicy | None:
        require_positive_revision(expected_revision)
        policy = ApiPolicySpec()
        paths: list[str] = []

        if is_set(name):
            paths.append("name")
            policy.name = str(name)
        if is_set(description):
            paths.append("description")
            policy.description = str(description)
        if is_set(spot_markets):
            paths.append("spot_markets")
            policy.spot_markets.extend(_spot_markets_to_proto(spot_markets))  # type: ignore[arg-type]
        if is_set(perp_markets):
            paths.append("perp_markets")
            policy.perp_markets.extend(_perp_markets_to_proto(perp_markets))  # type: ignore[arg-type]
        if is_set(spot_market_scope):
            paths.append("spot_market_scope")
            policy.spot_market_scope = _market_scope_to_proto(str(spot_market_scope))
        if is_set(perp_market_scope):
            paths.append("perp_market_scope")
            policy.perp_market_scope = _market_scope_to_proto(str(perp_market_scope))
        if is_set(actions):
            paths.append("actions")
            policy.actions.extend(_policy_actions_to_proto(actions))  # type: ignore[arg-type]
        if is_set(max_order_notional):
            paths.append("max_order_notional")
            policy.max_order_notional = int(max_order_notional)  # type: ignore[arg-type]
        if is_set(daily_internal_transfer_out_limit):
            paths.append("daily_internal_transfer_out_limit")
            policy.daily_internal_transfer_out_limit = int(daily_internal_transfer_out_limit)  # type: ignore[arg-type]
        if is_set(daily_withdraw_limit):
            paths.append("daily_withdraw_limit")
            policy.daily_withdraw_limit = int(daily_withdraw_limit)  # type: ignore[arg-type]
        if is_set(is_template):
            paths.append("is_template")
            policy.is_template = bool(is_template)

        return await unary_auth_decoded(
            self._transport,
            PolicyServiceClient,
            lambda client, req: client.update_api_policy(req),
            UpdateApiPolicyRequest(
                policy_id=id_to_int(policy_id, "policy_id"),
                policy=policy,
                update_mask=field_mask(paths),
                expected_revision=expected_revision,
            ),
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

    async def subscribe_api_policies(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[ApiPolicy]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:auth:api-policies:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_api_policy_bytes,
        )
