from __future__ import annotations

from polyester.codecs.proto_helpers import format_uint64_id, proto_enum_name
from polyester.codecs.scalars import timestamp_dict_to_datetime
from polyester.gen.auth.v1 import policies_pb2
from polyester.models.policies import (
    ApiPolicy,
    PerpMarketRule,
    SpotMarketRule,
    SubaccountPolicy,
)


def _optional_uint64_id(value: int) -> str:
    if value == 0:
        return ""
    return format_uint64_id(value)


def _spot_market_from_proto(msg: policies_pb2.SpotMarketRule) -> SpotMarketRule:
    return SpotMarketRule(symbol=msg.symbol)


def _perp_market_from_proto(msg: policies_pb2.PerpMarketRule) -> PerpMarketRule:
    return PerpMarketRule(symbol=msg.symbol, max_leverage_x=int(msg.max_leverage_x))


def _policy_actions_from_proto(actions: list[int]) -> list[str]:
    return [
        proto_enum_name(policies_pb2.PolicyAction, action)
        for action in actions
        if action != policies_pb2.UNSPECIFIED
    ]


def subaccount_policy_from_proto(msg: policies_pb2.SubaccountPolicyView) -> SubaccountPolicy:
    return SubaccountPolicy(
        id=format_uint64_id(msg.id),
        name=msg.name,
        description=msg.description,
        spot_markets=[_spot_market_from_proto(item) for item in msg.spot_markets],
        perp_markets=[_perp_market_from_proto(item) for item in msg.perp_markets],
        spot_market_scope=proto_enum_name(policies_pb2.MarketScope.Value, msg.spot_market_scope),
        perp_market_scope=proto_enum_name(policies_pb2.MarketScope.Value, msg.perp_market_scope),
        actions=_policy_actions_from_proto(list(msg.actions)),
        is_template=bool(msg.is_template),
        source_template_id=_optional_uint64_id(msg.source_template_id),
        global_notional_cap=int(msg.global_notional_cap),
        max_order_notional=int(msg.max_order_notional),
        max_open_orders=int(msg.max_open_orders),
        max_open_positions=int(msg.max_open_positions),
        global_perp_leverage_x=int(msg.global_perp_leverage_x),
        daily_internal_transfer_out_limit=int(msg.daily_internal_transfer_out_limit),
        daily_withdraw_limit=int(msg.daily_withdraw_limit),
        internal_transfers_own_only=bool(msg.internal_transfers_own_only),
        enforce_withdraw_whitelist=bool(msg.enforce_withdraw_whitelist),
        trading_halted=bool(msg.trading_halted),
        liquidation_only=bool(msg.liquidation_only),
        daily_loss_limit=int(msg.daily_loss_limit),
        intraday_drawdown_limit_bps=int(msg.intraday_drawdown_limit_bps),
        locked=bool(msg.locked),
        review_at=timestamp_dict_to_datetime(msg.review_at),
        expires_at=timestamp_dict_to_datetime(msg.expires_at),
        created_at=timestamp_dict_to_datetime(msg.created_at),
        updated_at=timestamp_dict_to_datetime(msg.updated_at),
        revision=int(msg.revision),
    )


def api_policy_from_proto(msg: policies_pb2.ApiPolicyView) -> ApiPolicy:
    return ApiPolicy(
        id=format_uint64_id(msg.id),
        name=msg.name,
        description=msg.description,
        spot_markets=[_spot_market_from_proto(item) for item in msg.spot_markets],
        perp_markets=[_perp_market_from_proto(item) for item in msg.perp_markets],
        actions=_policy_actions_from_proto(list(msg.actions)),
        spot_market_scope=proto_enum_name(policies_pb2.MarketScope.Value, msg.spot_market_scope),
        perp_market_scope=proto_enum_name(policies_pb2.MarketScope.Value, msg.perp_market_scope),
        max_order_notional=int(msg.max_order_notional),
        daily_internal_transfer_out_limit=int(msg.daily_internal_transfer_out_limit),
        daily_withdraw_limit=int(msg.daily_withdraw_limit),
        is_template=bool(msg.is_template),
        source_template_id=_optional_uint64_id(msg.source_template_id),
        created_at=timestamp_dict_to_datetime(msg.created_at),
        updated_at=timestamp_dict_to_datetime(msg.updated_at),
        revision=int(msg.revision),
    )
