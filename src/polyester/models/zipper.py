from __future__ import annotations

from datetime import datetime

import msgspec

# Supply status labels of ``supply_status`` (``status`` on a supply update).
SUPPLY_STATUS_AVAILABLE = "available"
SUPPLY_STATUS_STALE = "stale"
SUPPLY_STATUS_MISSING = "missing"
# The statuses whose supply is known: current, or no longer refreshed.
_KNOWN_SUPPLY = (SUPPLY_STATUS_AVAILABLE, SUPPLY_STATUS_STALE)

# Route status labels of ``deposit_status`` and ``withdrawal_status``.
ROUTE_STATUS_NORMAL = "normal"
ROUTE_STATUS_SUSPENDED = "suspended"


class ZippedAssetSupplyUpdate(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One route's zToken supply from the supply stream.

    ``status`` is ``"available"`` (current) or ``"stale"`` (not refreshed for
    longer than expected; may no longer be accurate). A route whose supply
    stops being refreshed gets one ``"stale"`` update repeating its last value
    and ``observed_at``; its next reading makes it ``"available"`` again.
    ``supply`` is the exact decimal in whole units, ``None`` when the update
    names no known status. ``observed_at`` is when the supply was read from
    Polyester Chain, ``None`` when not sent.
    """

    zipped_asset_id: int
    supply: str | None = None
    status: str = ""
    observed_at: datetime | None = None


class ZippedAssetSupplyBatch(msgspec.Struct, kw_only=True, omit_defaults=True):
    updates: list[ZippedAssetSupplyUpdate] = msgspec.field(default_factory=list)


class ZipperTokenConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    address: str = ""
    decimals: int = 18


class ZipperAssetChainVariant(msgspec.Struct, kw_only=True, omit_defaults=True):
    zipped_asset_id: int
    chain_id: int
    is_native_asset: bool = False
    network_fee: str = "0"
    network_fee_ts_sec: int = 0
    deposit_min_amount: str = ""
    withdraw_min_amount: str = ""
    # The route's zToken supply, an exact decimal in whole units, and whether
    # it is known: supply_status is "available" (current), "stale" (not
    # refreshed for longer than expected; may no longer be accurate) or
    # "missing" (no supply is known yet); "" when the server names none, and a
    # status this SDK does not know reads as its decimal string. supply and
    # supply_observed_at (when it was read from Polyester Chain) are set only
    # while the status is "available" or "stale", None otherwise: an unknown
    # supply is never 0, and a "0" supply then is a real supply of zero.
    supply: str | None = None
    supply_status: str = ""
    supply_observed_at: datetime | None = None
    source_token: ZipperTokenConfig = msgspec.field(default_factory=ZipperTokenConfig)
    z_token: ZipperTokenConfig = msgspec.field(default_factory=ZipperTokenConfig)
    # Whether this route accepts new deposits and new withdrawals: "normal",
    # "suspended", or "" while the status is not known yet, which is unknown,
    # not suspended. A status this SDK does not know reads as its decimal
    # string. A suspension can stop one direction and not the other. While
    # deposit_status is "suspended", do not send funds to a deposit address on
    # this route; wait until it returns to "normal". While withdrawal_status is
    # "suspended", a new withdrawal is refused with ERROR_CODE_ROUTE_SUSPENDED;
    # a Trading withdrawal accepted before the suspension and not yet sent
    # stays pending, with its funds held, and is sent once the route returns
    # to "normal" (one already being sent may fail instead, and its funds then
    # return to the account).
    deposit_status: str = ""
    withdrawal_status: str = ""

    def known_supply(self) -> str | None:
        """The route's supply while it is known (``"available"`` or
        ``"stale"``), else ``None``: never read an unknown supply as 0."""
        return self.supply if self.supply_status in _KNOWN_SUPPLY else None

    def accepts_deposits(self) -> bool:
        """True only while the route's deposit status is ``"normal"``."""
        return self.deposit_status == ROUTE_STATUS_NORMAL

    def accepts_withdrawals(self) -> bool:
        """True only while the route's withdrawal status is ``"normal"``."""
        return self.withdrawal_status == ROUTE_STATUS_NORMAL


class ZipperChainConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    chain_id: int
    code: str = ""
    name: str = ""
    native_chain_id: str = ""
    native_currency_symbol: str = ""
    explorer_url: str = ""
    icon: str = ""
    required_confirmations: int = 0
    confirmation_time_seconds: int = 0
    is_case_sensitive: bool = False
    min_address_length: int = 0
    max_address_length: int = 0
    # Memo or destination-tag rule for withdrawal destinations on this network:
    # "required", "optional" or "not_supported"; "" when the server names none,
    # which does not mean a memo can be omitted; a number this SDK does not
    # know reads as its decimal string. ``memo_label`` ("Memo", "Destination
    # tag") and ``memo_format_hint`` are display text, kept as sent.
    memo_requirement: str = ""
    memo_label: str = ""
    memo_format_hint: str = ""


class ZipperAssetConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset: str = ""
    ledger_id: int = 0
    name: str = ""
    icon: str = ""
    quantity_scale: int = 18
    quantity_display_decimals: int = 0
    u_asset_id: str = ""
    variants: list[ZipperAssetChainVariant] = msgspec.field(default_factory=list)


class ZipperChainContractConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    name: str = ""
    address: str = ""
    type: str = ""
    description: str = ""
    version: int = 0


class ZipperEnrichedAssetChain(msgspec.Struct, kw_only=True, omit_defaults=True):
    chain_id: int
    code: str = ""
    name: str = ""
    native_chain_id: str = ""
    native_currency_symbol: str = ""
    explorer_url: str = ""
    icon: str = ""
    required_confirmations: int = 0
    confirmation_time_seconds: int = 0
    is_case_sensitive: bool = False
    min_address_length: int = 0
    max_address_length: int = 0
    # Memo or destination-tag rule for withdrawal destinations on this network:
    # "required", "optional" or "not_supported"; "" when the server names none,
    # which does not mean a memo can be omitted; a number this SDK does not
    # know reads as its decimal string. ``memo_label`` ("Memo", "Destination
    # tag") and ``memo_format_hint`` are display text, kept as sent.
    memo_requirement: str = ""
    memo_label: str = ""
    memo_format_hint: str = ""
    zipped_asset_id: int = 0
    is_native_asset: bool = False
    network_fee: str = "0"
    network_fee_ts_sec: int = 0
    deposit_min_amount: str = ""
    withdraw_min_amount: str = ""
    # The route's zToken supply, an exact decimal in whole units, and whether
    # it is known: supply_status is "available" (current), "stale" (not
    # refreshed for longer than expected; may no longer be accurate) or
    # "missing" (no supply is known yet); "" when the server names none, and a
    # status this SDK does not know reads as its decimal string. supply and
    # supply_observed_at (when it was read from Polyester Chain) are set only
    # while the status is "available" or "stale", None otherwise: an unknown
    # supply is never 0, and a "0" supply then is a real supply of zero.
    supply: str | None = None
    supply_status: str = ""
    supply_observed_at: datetime | None = None
    source_token: ZipperTokenConfig = msgspec.field(default_factory=ZipperTokenConfig)
    z_token: ZipperTokenConfig = msgspec.field(default_factory=ZipperTokenConfig)
    # Whether this route accepts new deposits and new withdrawals: "normal",
    # "suspended", or "" while the status is not known yet, which is unknown,
    # not suspended. A status this SDK does not know reads as its decimal
    # string. A suspension can stop one direction and not the other. While
    # deposit_status is "suspended", do not send funds to a deposit address on
    # this route; wait until it returns to "normal". While withdrawal_status is
    # "suspended", a new withdrawal is refused with ERROR_CODE_ROUTE_SUSPENDED;
    # a Trading withdrawal accepted before the suspension and not yet sent
    # stays pending, with its funds held, and is sent once the route returns
    # to "normal" (one already being sent may fail instead, and its funds then
    # return to the account).
    deposit_status: str = ""
    withdrawal_status: str = ""

    def known_supply(self) -> str | None:
        """The route's supply while it is known (``"available"`` or
        ``"stale"``), else ``None``: never read an unknown supply as 0."""
        return self.supply if self.supply_status in _KNOWN_SUPPLY else None

    def accepts_deposits(self) -> bool:
        """True only while the route's deposit status is ``"normal"``."""
        return self.deposit_status == ROUTE_STATUS_NORMAL

    def accepts_withdrawals(self) -> bool:
        """True only while the route's withdrawal status is ``"normal"``."""
        return self.withdrawal_status == ROUTE_STATUS_NORMAL


class ZipperEnrichedAssetConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset: str = ""
    ledger_id: int = 0
    name: str = ""
    icon: str = ""
    quantity_scale: int = 18
    quantity_display_decimals: int = 0
    u_asset_id: str = ""
    chains: list[ZipperEnrichedAssetChain] = msgspec.field(default_factory=list)


class DepositWithdrawConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    chains: list[ZipperChainConfig] = msgspec.field(default_factory=list)
    assets: list[ZipperAssetConfig] = msgspec.field(default_factory=list)
    contracts: list[ZipperChainContractConfig] = msgspec.field(default_factory=list)
    ts_ms: int = 0


class ZipperCatalogData(msgspec.Struct, kw_only=True, omit_defaults=True):
    chains: list[ZipperChainConfig] = msgspec.field(default_factory=list)
    assets: list[ZipperEnrichedAssetConfig] = msgspec.field(default_factory=list)
    contracts: list[ZipperChainContractConfig] = msgspec.field(default_factory=list)
    ts_ms: int = 0
