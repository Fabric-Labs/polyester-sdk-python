from __future__ import annotations

from datetime import datetime

import msgspec


class TradingRateLimitRule(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Weighted placement, cancellation or read quota for one VIP tier."""

    policy_class: str = ""
    vip_tier: int = 0
    quota_weight: int = 0
    period_ms: int = 0
    burst_weight: int = 0


class RateLimitConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Complete public trading rate-limit catalog for one policy version."""

    policy_version: int = 0
    effective_from: datetime | None = None
    rules: list[TradingRateLimitRule]


class TradingRateLimits(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Effective trading limits for one account target and caller.

    Trading limits apply per account: the root account and each sub-account
    have their own, and every API key and session that trades or reads for an
    account shares them. ``rules`` are the enforced placement, cancellation
    and read rules of the selected account, in that order: budget against
    them. A read (orders, fills, triggers, trading limits and fees) and an
    order preview cost units of the read limit of the account they read, the
    root account or a sub-account. ``api_key_rules``, present only for an
    API-key caller, are the rules resolved for that key, in the same order.
    Its read rule is enforced on top of the account's: a read or preview is
    refused when either is exhausted. Its placement and cancellation rules are
    informational only: orders are not limited per API key, so adding keys
    adds no capacity.
    """

    policy_version: int = 0
    effective_from: datetime | None = None
    rules: list[TradingRateLimitRule]
    api_key_rules: list[TradingRateLimitRule]
