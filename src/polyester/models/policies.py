from __future__ import annotations

from datetime import datetime

import msgspec


class SpotMarketRule(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int = 0
    symbol: str = ""


class SubaccountPolicy(msgspec.Struct, kw_only=True, omit_defaults=True):
    id: str = ""
    name: str = ""
    description: str = ""
    spot_markets: list[SpotMarketRule] = []
    spot_market_scope: str = ""
    actions: list[str] = []
    is_template: bool = False
    # The template and template revision a copy was made from, set when the
    # copy is made and never changed; "" and 0 for a policy that is no copy.
    source_template_id: str = ""
    source_template_revision: int = 0
    max_order_notional: int = 0
    max_open_orders: int = 0
    trading_halted: bool = False
    locked: bool = False
    review_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0


class ApiPolicy(msgspec.Struct, kw_only=True, omit_defaults=True):
    id: str = ""
    name: str = ""
    description: str = ""
    spot_markets: list[SpotMarketRule] = []
    actions: list[str] = []
    spot_market_scope: str = ""
    is_template: bool = False
    # The template and template revision a copy was made from, set when the
    # copy is made and never changed; "" and 0 for a policy that is no copy.
    source_template_id: str = ""
    source_template_revision: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0


class SubaccountPoliciesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    policies: list[SubaccountPolicy]


class ApiPoliciesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    policies: list[ApiPolicy]
