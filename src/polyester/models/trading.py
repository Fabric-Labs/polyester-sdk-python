from __future__ import annotations

from datetime import datetime

import msgspec

from polyester.types.money import AssetAmount, Price, Quantity


class Order(msgspec.Struct, kw_only=True, omit_defaults=True):
    order_id: str
    symbol_id: int
    client_order_id: str = ""
    side: str = ""
    status: str = ""
    order_type: str = ""
    tif: str = ""
    orig_qty: Quantity | None = None
    cum_qty: Quantity | None = None
    leaves_qty: Quantity | None = None
    price: Price | None = None
    avg_px: Price | None = None
    created_ts_ns: str = ""
    state_revision: int = 0


class OrdersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    orders: list[Order]
    next_page_token: str = ""


class OrderMutationResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str
    order_id: str = ""
    client_order_id: str = ""


class GetOrderResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    order: Order | None = None
    trades: list[UserTrade] = []


class UserTrade(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    match_id: str = ""
    order_id: str = ""
    side: str = ""
    is_maker: bool = False
    price: Price | None = None
    qty: Quantity | None = None
    fee_scaled: str = ""
    ts_ns: str = ""


class UserTradesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    trades: list[UserTrade]
    next_page_token: str = ""


class AssetBalance(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset_id: int
    trading: str = "0"
    funding: str = "0"
    reserved: str = "0"
    available: str = "0"
    trading_version: int = 0
    funding_version: int = 0
    reserved_version: int = 0


class BalancesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    balances: list[AssetBalance]


class LifecycleFlowSummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    intent_id: str
    flow_kind: str = ""
    latest_step: str = ""
    is_open: bool = False
    is_terminal: bool = False
    owner_account_id: str = ""
    smart_account_address: str = ""


class LifecycleFlowsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    flows: list[LifecycleFlowSummary]
    next_page_token: str = ""


class ModifyOrderResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    action_taken: str = ""
    old_order_id: str = ""
    final_order_id: str = ""
    code: str = ""


class CancelAllOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    matched_orders: int = 0
    submitted_cancels: int = 0
    failed_cancels: int = 0


class Trigger(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_id: str = ""
    symbol_id: int = 0
    symbol: str = ""
    trigger_type: str = ""
    status: str = ""
    side: str = ""
    qty: Quantity | None = None
    trigger_price: Price | None = None
    client_trigger_id: str = ""


class TriggersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    triggers: list[Trigger]
    total: int = 0


class TriggerMutationResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_id: str = ""
    status: str = ""


class LedgerTransfer(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset_id: int = 0
    amount: str = "0"
    transfer_type: int = 0
    account_code: int = 0
    timestamp: int = 0
    pending: bool = False
    tx_id: str = ""
    is_debit: bool = False


class TransfersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    transfers: list[LedgerTransfer]
    next_cursor: int | None = None


class InternalTransferResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    request_id: str = ""
    transfer_id: str = ""
    asset_id: int = 0
    asset_code: str = ""
    quantity: AssetAmount | None = None


class DepositAddress(msgspec.Struct, kw_only=True, omit_defaults=True):
    chain_id: int = 0
    deposit_address: str = ""


class DepositAddressesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    addresses: list[DepositAddress]


class TriggerEvent(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_id: str = ""
    symbol_id: int = 0
    trigger_type: str = ""
    event_type: str = ""
    ts_ns: str = ""
    fire_px: Price | None = None
    reason: str = ""


class TriggerEventsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    events: list[TriggerEvent]
    next_before_ts_ns: str = "0"


class BalanceHistorySeries(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset_id: int = 0
    account_code: int = 0
    balance_q: list[int] = []


class BalanceHistory(msgspec.Struct, kw_only=True, omit_defaults=True):
    range: str = ""
    bucket: str = ""
    start_ts_sec: int = 0
    end_ts_sec: int = 0
    points: int = 0
    series: list[BalanceHistorySeries] = []


class EquityHistorySeries(msgspec.Struct, kw_only=True, omit_defaults=True):
    account_code: int = 0
    account_name: str = ""
    asset_id: int = 0
    asset_symbol: str = ""
    equity_q: list[int] = []


class EquityHistory(msgspec.Struct, kw_only=True, omit_defaults=True):
    range: str = ""
    bucket: str = ""
    start_ts_sec: int = 0
    end_ts_sec: int = 0
    quote_asset: str = ""
    points: int = 0
    series: list[EquityHistorySeries] = []


class Hold(msgspec.Struct, kw_only=True, omit_defaults=True):
    hold_id: str = ""
    asset_id: int = 0
    amount_reserved: str = "0"
    expires_at_ns: str = "0"


class HoldsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    holds: list[Hold]


class BucketTransferResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    transfer_id: str = ""
    timestamp_ns: str = "0"


class ApiKeySummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    key_id: str = ""
    label: str = ""
    status: str = ""
    subaccount_id: str = ""
    updated_at: datetime | None = None


class ApiKeysList(msgspec.Struct, kw_only=True, omit_defaults=True):
    api_keys: list[ApiKeySummary]


class ResolvedAccount(msgspec.Struct, kw_only=True, omit_defaults=True):
    smart_account_address: str = ""
    kind: str = ""
    root_username: str = ""
    subaccount_label: str = ""
    account_id: str = ""


class ResolvedAccountsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    matches: list[ResolvedAccount]


class TransferDestination(msgspec.Struct, kw_only=True, omit_defaults=True):
    account_id: str = ""
    subaccount_id: str = ""
    label: str = ""
    smart_account_address: str = ""


class TransferDestinationsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    destinations: list[TransferDestination]


class BatchModifyResultItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    client_order_id: str = ""
    final_order_id: str = ""
    code: str = ""


class BatchModifyOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchModifyResultItem]
    amended_count: int = 0
    replaced_count: int = 0
    rejected_count: int = 0


class BatchCreateResultItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    order_id: str = ""
    client_order_id: str = ""
    code: str = ""


class BatchCreateOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchCreateResultItem]
    accepted_count: int = 0
    rejected_count: int = 0


class BatchCancelResultItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    order_id: str = ""
    client_order_id: str = ""
    code: str = ""


class BatchCancelOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchCancelResultItem]
    accepted_count: int = 0
    rejected_count: int = 0


class CancelAllAfterResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    effective_timeout_sec: int = 0
    expires_at_ts_ns: str = "0"


class WithdrawIntentResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    intent_id: str = ""
