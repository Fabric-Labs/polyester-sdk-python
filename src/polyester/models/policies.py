from __future__ import annotations

from datetime import datetime

import msgspec


class SpotMarketRule(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol: str = ""


class PerpMarketRule(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol: str = ""
    max_leverage_x: int = 0


class SubaccountPolicy(msgspec.Struct, kw_only=True, omit_defaults=True):
    id: str = ""
    name: str = ""
    description: str = ""
    spot_markets: list[SpotMarketRule] = []
    perp_markets: list[PerpMarketRule] = []
    spot_market_scope: str = ""
    perp_market_scope: str = ""
    actions: list[str] = []
    is_template: bool = False
    source_template_id: str = ""
    global_notional_cap: int = 0
    max_order_notional: int = 0
    max_open_orders: int = 0
    max_open_positions: int = 0
    global_perp_leverage_x: int = 0
    daily_internal_transfer_out_limit: int = 0
    daily_withdraw_limit: int = 0
    internal_transfers_own_only: bool = False
    enforce_withdraw_whitelist: bool = False
    trading_halted: bool = False
    liquidation_only: bool = False
    daily_loss_limit: int = 0
    intraday_drawdown_limit_bps: int = 0
    locked: bool = False
    review_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApiPolicy(msgspec.Struct, kw_only=True, omit_defaults=True):
    id: str = ""
    name: str = ""
    description: str = ""
    spot_markets: list[SpotMarketRule] = []
    perp_markets: list[PerpMarketRule] = []
    actions: list[str] = []
    spot_market_scope: str = ""
    perp_market_scope: str = ""
    max_order_notional: int = 0
    daily_internal_transfer_out_limit: int = 0
    daily_withdraw_limit: int = 0
    is_template: bool = False
    source_template_id: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SubaccountPoliciesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    policies: list[SubaccountPolicy]


class ApiPoliciesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    policies: list[ApiPolicy]
