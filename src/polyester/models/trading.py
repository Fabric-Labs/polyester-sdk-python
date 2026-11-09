from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import msgspec

from polyester.codecs.scalars import format_qty_scaled, format_scaled, validate_protocol_scale
from polyester.models.order_key import OrderKey
from polyester.models.ratelimit import RateLimitDetail
from polyester.types.money import AssetAmount, Price, Quantity


class Order(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Spot order snapshot.

    ``orig_qty`` is the current accepted total quantity and changes after a
    successful modify. ``cum_qty`` and ``avg_px`` are cumulative execution
    values across the lineage through the returned generation, not values
    limited to one physical order. ``leaves_qty`` is remaining working
    quantity. Retain the first submitted quantity separately if you need it.
    ``inherited_cum_qty`` is the part of ``cum_qty`` carried over from
    predecessors when a replacement was accepted; zero for an order never
    replaced.

    Exact execution totals, across the same lineage:

    - ``avg_price`` is the exact average execution price in quote units per
      base unit (``avg_price_e18``, 18 decimals, rounded half to even);
      ``None`` without fills. Prefer it to ``avg_px``, which is rounded down
      to 9 decimals.
    - ``cum_notional_scaled`` is the quote amount of the fills before fees,
      scaled by ``10^(9 + base_quantity_scale)``; ``"0"`` without fills.
      :meth:`cum_quote` returns it in quote units. Each fill settles its quote
      rounded down to 18 decimals, so it is exactly the settled quote when the
      pair's ``base_quantity_scale`` is at most 9; above that it can exceed
      the settled quote by less than 1e-18 per fill.
    - ``fee_total`` is the fee of those fills net of rebates, in
      ``fee_asset``. Order history reads and single-order reads with
      execution history carry it; open-order reads and stream updates leave it
      ``None``. It can trail the fills: it covers them all once
      ``fee_total.qty`` equals ``cum_qty``.

    :meth:`quote_used` and :meth:`quote_unspent` tell how much of a buy's
    quote amount (``submitted_max_quote_debit_scaled``) its fills used.
    """

    order_id: str
    symbol_id: int
    client_order_id: str = ""
    side: str = ""
    status: str = ""
    order_type: str = ""
    tif: str = ""
    orig_qty: Quantity | None = None
    cum_qty: Quantity | None = None
    inherited_cum_qty: Quantity | None = None
    leaves_qty: Quantity | None = None
    price: Price | None = None
    avg_px: Price | None = None
    created_ts_ns: str = ""
    # When the order became terminal, in Unix nanoseconds (UTC) as a decimal
    # string; empty while it is open.
    terminal_ts_ns: str = ""
    version: int = 0
    post_only: bool = False
    fee_asset: str = ""
    # ``expire_taker``, ``expire_maker`` or ``expire_both``, which the order's
    # attached exits use too; empty when unset. A mode newer than this SDK
    # reads as its number.
    self_trade_prevention_mode: str = ""
    submitted_max_quote_debit_scaled: str = ""
    attached_risk: AttachedRisk | None = None
    lineage: OrderLineage | None = None
    # How the order was created; ``None`` when the server does not say.
    origin: OrderOrigin | None = None
    # A MARKET order's slippage protection: the reference price it was
    # measured from, and its cap as a price distance or in basis points.
    # ``None`` or 0 when the order has none of that form.
    market_client_ref_price: Price | None = None
    market_max_slippage: Price | None = None
    market_max_slippage_bps: int = 0
    # RFC3339 UTC expiry for GTD orders; omitted for every other TIF.
    expire_at: str | None = None
    # Why a ``rejected`` order was refused: the Orders API error code for the
    # same refusal, without its ``ERROR_CODE_`` prefix (for example
    # ``POST_ONLY_CROSS``). ``None`` for every other status.
    reject_reason: str | None = None
    # Why a ``canceled`` order ended, without the ``CANCEL_REASON_`` prefix
    # (for example ``USER_REQUEST`` or ``REPLACED``). ``None`` for every other
    # status. A number this SDK does not know reads ``UNKNOWN_CANCEL_REASON(n)``.
    cancel_reason: str | None = None
    avg_price: Decimal | None = None
    cum_notional_scaled: str = "0"
    fee_total: OrderFeeTotal | None = None

    def _base_scale(self, base_quantity_scale: int | None) -> int | None:
        if base_quantity_scale is not None:
            return base_quantity_scale
        return self.cum_qty.scale if self.cum_qty is not None else None

    def cum_quote(self, base_quantity_scale: int | None = None) -> Decimal:
        """The quote amount of the fills, before fees (REST ``cumQuote``).

        ``base_quantity_scale`` is the pair's base quantity scale
        (``CatalogManager.base_quantity_scale_for_symbol_id``); it defaults to
        ``cum_qty.scale``. Zero without fills. Exactly the settled quote when
        ``base_quantity_scale`` is at most 9; above that it can exceed the
        settled quote by less than 1e-18 per fill. ``base_quantity_scale``
        must be from 0 to 36.
        """
        scale = self._require_base_scale(base_quantity_scale)
        return Decimal(format_scaled(int(self.cum_notional_scaled or 0), 9 + scale))

    def _require_base_scale(self, base_quantity_scale: int | None) -> int:
        scale = self._base_scale(base_quantity_scale)
        if scale is None:
            from polyester.errors import PolyesterValidationError

            raise PolyesterValidationError(
                "base_quantity_scale is required: pass the pair's base quantity scale"
            )
        return validate_protocol_scale(scale, field_name="base_quantity_scale")

    def _quote_used_scaled(self, base_quantity_scale: int | None) -> tuple[int, int] | None:
        """``(amount, scale)`` of the quote the fills used, or ``None``."""
        base_scale = self._require_base_scale(base_quantity_scale)
        notional = int(self.cum_notional_scaled or 0)
        notional_scale = 9 + base_scale
        filled = self.cum_qty.scaled if self.cum_qty is not None else 0
        fee = self.fee_total
        if fee is None:
            # No fills, so no fee to wait for.
            return (0, notional_scale) if filled == 0 and notional == 0 else None
        if (fee.qty.scaled if fee.qty is not None else 0) != filled:
            return None
        if self.fee_asset == "base":
            # The fee came out of the base received.
            return notional, notional_scale
        if self.fee_asset != "quote":
            return None
        scale = max(notional_scale, 18)
        fee_amount = int(fee.amount_e18 or 0) * 10 ** (scale - 18)
        used = notional * 10 ** (scale - notional_scale)
        return (used - fee_amount if fee.is_rebate else used + fee_amount), scale

    def quote_used(self, base_quantity_scale: int | None = None) -> Decimal | None:
        """How much quote the order's fills used, fees included.

        ``cum_quote`` plus the quote fee (less a rebate) when ``fee_asset`` is
        ``quote``; ``cum_quote`` alone when the fee was taken from the base
        received. ``None`` until ``fee_total`` covers every fill (read the
        order again), and for an open-order read, which carries no fee total.
        Exact when the pair's ``base_quantity_scale`` is at most 9; above that
        it can exceed the settled debit by less than 1e-18 per fill (see
        :meth:`cum_quote`).
        """
        used = self._quote_used_scaled(base_quantity_scale)
        if used is None:
            return None
        return Decimal(format_scaled(used[0], used[1]))

    def quote_unspent(
        self, *, quote_quantity_scale: int, base_quantity_scale: int | None = None
    ) -> Decimal | None:
        """The part of a buy's quote amount its fills did not use.

        ``submitted_max_quote_debit_scaled`` (at the pair's
        ``quote_quantity_scale``) less :meth:`quote_used`. ``None`` for an
        order not sized by a quote amount, or while ``quote_used`` is ``None``.
        """
        validate_protocol_scale(quote_quantity_scale, field_name="quote_quantity_scale")
        if not self.submitted_max_quote_debit_scaled:
            return None
        used = self._quote_used_scaled(base_quantity_scale)
        if used is None:
            return None
        scale = max(used[1], quote_quantity_scale)
        budget = int(self.submitted_max_quote_debit_scaled) * 10 ** (scale - quote_quantity_scale)
        spent = used[0] * 10 ** (scale - used[1])
        return Decimal(format_scaled(budget - spent, scale))


class OrderFeeTotal(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Total fee of an order's fills, net of rebates, in the order's ``fee_asset``.

    ``amount_e18`` is the exact amount scaled by 1e18 (as ``fee_amount_e18`` on
    a trade); ``amount`` is the same in asset units. ``is_rebate`` is true when
    rebates exceeded fees, so the amount was credited. ``qty`` is the executed
    quantity of the fills it covers.
    """

    amount_e18: str = "0"
    is_rebate: bool = False
    qty: Quantity | None = None

    @property
    def amount(self) -> Decimal:
        return Decimal(format_qty_scaled(int(self.amount_e18 or 0), 18))


class OrderLineage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Stable replacement-chain identity for an order or execution.

    ``id`` is the first generation's public order ID and stays stable across
    accepted replacements. ``generation`` is one-based and identifies the
    accepted replacement generation, not per-order state ``version``.
    """

    id: str = ""
    generation: int = 0


class OrderOrigin(msgspec.Struct, kw_only=True, omit_defaults=True):
    """How an order was created.

    ``scope`` is ``direct``, ``attached_risk``, ``standalone_trigger`` or
    ``system`` (a scope newer than this SDK reads as its number).
    ``trigger_type`` names the trigger strategy that placed the order
    (``stop_loss``, ``take_profit``, ``trailing_stop``, ``twap`` or
    ``ladder``) and is empty for a direct order. ``trigger_id`` is that
    trigger, ``parent_order_id`` the parent order of an attached-risk child,
    and ``child_seq`` the child's sequence number in a multi-child strategy
    such as a TWAP; each is empty or 0 when it does not apply.
    """

    scope: str = ""
    trigger_type: str = ""
    trigger_id: str = ""
    parent_order_id: str = ""
    child_seq: int = 0


class OrderTransfer(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Settlement leg linked to a match on an order or user-trades page.

    Identify a match by ``(symbol_id, match_id)``. Deduplicate repeated
    settlement legs across pages by ``tx_id``.
    """

    match_id: str = ""
    symbol_id: int = 0
    asset_id: int = 0
    amount_e18: str = "0"
    is_debit: bool = False
    transfer_code: int = 0
    account_code: int = 0
    ts_ns: str = ""
    tx_id: str = ""


class AttachedRiskLegState(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Runtime state for one attached take-profit, stop-loss, or trailing leg."""

    status: str = ""
    armed_ts_ns: str = ""
    terminal_ts_ns: str = ""
    trigger_id: str = ""
    child_order_id: str = ""


class RiskLeg(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_price: Price | None = None
    trigger_price_source: str = ""
    order_type: str = ""
    limit_price: Price | None = None
    state: AttachedRiskLegState | None = None


class TrailingStop(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Attached trailing-stop projection.

    Create/modify dicts must supply a positive ``trailing_distance_ticks`` or
    ``trailing_distance_bps`` (and positive slippage when set).
    ``trigger_price_source`` is ``last``, ``index`` or ``mark``; unset on a
    write means the last trade price. ``order_type`` is rejected if supplied
    under ``attached_risk.trailing_stop``.

    ``limit_price`` is the most the exit pays per unit when the trailing stop
    buys back: required when the order sells, unset when it buys, and at least
    ``activation_price`` when both are set. Order reads do not return it yet.
    """

    distance_ticks: int = 0
    distance_bps: int = 0
    max_slippage_ticks: int = 0
    max_slippage_bps: int = 0
    activation_price: Price | None = None
    limit_price: Price | None = None
    trigger_price_source: str = ""
    order_type: str = ""
    state: AttachedRiskLegState | None = None


class AttachedRisk(msgspec.Struct, kw_only=True, omit_defaults=True):
    take_profit: RiskLeg | None = None
    stop_loss: RiskLeg | None = None
    trailing_stop: TrailingStop | None = None
    oco: bool = False


class OrdersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    orders: list[Order]
    next_page_token: str = ""


class OrderMutationResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str
    order_id: str = ""
    client_order_id: str = ""
    resolved_base_qty_scaled: str = ""
    resolved_base_qty: Quantity | None = None
    submitted_max_quote_debit_scaled: str = ""
    # Trigger IDs of the attached-risk legs this order configured; empty for a
    # leg the order does not have.
    take_profit_trigger_id: str = ""
    stop_loss_trigger_id: str = ""
    trailing_stop_trigger_id: str = ""


class OrderFieldViolation(msgspec.Struct, kw_only=True, omit_defaults=True):
    field_path: str = ""
    rule_id: str = ""
    message: str = ""


class OrderErrorDetail(msgspec.Struct, kw_only=True, omit_defaults=True):
    code: str = ""
    violations: list[OrderFieldViolation] = []
    rate_limit: RateLimitDetail | None = None


class PreviewOrderResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    admissible: bool | None = None
    rejection: OrderErrorDetail | None = None
    resolved_base_qty_scaled: str = ""
    resolved_base_qty: Quantity | None = None
    # Protective execution boundary (not expected fill price).
    protected_price_bound: Price | None = None
    evaluated_at_ms: int = 0


class GetOrderResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    order: Order | None = None
    trades: list[UserTrade] = []
    transfers: list[OrderTransfer] = []
    next_page_token: str = ""
    # True when the order's trades across every page add up to its filled
    # quantity; false while a recent execution is still being recorded.
    executions_complete: bool = False


class UserTrade(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    match_id: str = ""
    order_id: str = ""
    side: str = ""
    is_maker: bool = False
    price: Price | None = None
    qty: Quantity | None = None
    fee_amount_e18: str = "0"
    fee_asset: str = ""
    referral_share_amount_e18: str = "0"
    ts_ns: str = ""
    # True when fee_amount_e18 is a rebate credit instead of a fee debit.
    # Proto3 omits false, so sparse wire encoding only sets this for rebates.
    fee_is_rebate: bool = False
    lineage: OrderLineage | None = None


class UserTradesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    trades: list[UserTrade]
    transfers: list[OrderTransfer] = []
    next_page_token: str = ""


class AssetBalance(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset_id: int
    trading: str = "0"
    funding: str = "0"
    reserved: str = "0"
    available: str = "0"
    trading_revision: int = 0
    funding_revision: int = 0


class BalancesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    balances: list[AssetBalance]


class ZipperReasonDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    code: int = 0
    reason_id: str = ""
    message: str = ""


class LifecycleFlowSummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    intent_id: str
    flow_kind: str = ""
    latest_step: str = ""
    is_open: bool = False
    is_terminal: bool = False
    owner_account_id: str = ""
    smart_account_address: str = ""
    lifecycle_reason: str = "unspecified"
    zipper_reason: ZipperReasonDetails | None = None
    # True when an open flow has made no progress for well beyond its expected
    # step time. Always false for terminal flows and transaction lookups.
    is_delayed: bool = False
    # How the selected account takes part in the flow, on a list_flows row of a
    # list that selects an account: "owner" (its deposit, withdrawal or a
    # transfer it sent, including a move between its own balances) or
    # "recipient" (a transfer another account sent to it). "unspecified" on an
    # unscoped list, a flow detail and a realtime update; empty on a
    # transaction lookup.
    participation: str = ""
    # For a transfer, the counterparty is destination_address when the account
    # sent it and source_address (with owner_account_id) when it received it.
    source_address: str = ""
    destination_address: str = ""


class LifecycleFlowsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    flows: list[LifecycleFlowSummary]
    next_page_token: str = ""


class ModifyOrderResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    action_taken: str = ""
    old_order_id: str = ""
    final_order_id: str = ""
    code: str = ""
    # Trigger IDs of the attached-risk legs this order configured; empty for a
    # leg the order does not have.
    take_profit_trigger_id: str = ""
    stop_loss_trigger_id: str = ""
    trailing_stop_trigger_id: str = ""


class CancelledOrder(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One order whose cancellation a cancel-all requested."""

    order_id: str
    client_order_id: str = ""


class CancelAllOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Cancel-all outcome.

    ``cancelled_orders`` lists up to 200 orders whose cancellation was
    requested, oldest first; ``total_cancelled`` counts all of them and
    ``truncated`` is true when the list is shorter than that. Each order's
    final state comes from the order stream and reads. Empty for a dry run.

    ``listing_status`` is ``included`` when ``cancelled_orders`` is the list
    for this request. A retry with the same ``request_id`` within 120 seconds
    returns the original counts with an empty ``cancelled_orders`` and
    ``not_retained_read_open_orders``: the empty list does not mean nothing
    was cancelled, so read open orders instead. An unknown value keeps its
    number.
    """

    status: str = ""
    matched_orders: int = 0
    submitted_cancels: int = 0
    failed_cancels: int = 0
    cancelled_orders: list[CancelledOrder] = []
    total_cancelled: int = 0
    truncated: bool = False
    listing_status: str = ""


@dataclass(frozen=True, slots=True)
class StopAllTradingTriggerFailure:
    """A trigger ``orders.stop_all_trading`` could not cancel, and why."""

    trigger_id: str
    error: Exception


class StopAllTradingResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Outcome of ``orders.stop_all_trading``.

    ``canceled_trigger_ids`` are the live triggers whose cancel was accepted,
    in the order they were canceled. ``trigger_failures`` are the ones whose
    cancel failed, each with its error: a trigger that ended before its
    cancel arrived, or any other refusal or transport error. Check it: a
    failed trigger may still be live. ``cancel_all`` is the cancel-all that
    followed, for the open orders, those triggers placed included.
    """

    canceled_trigger_ids: list[str] = []
    trigger_failures: list[StopAllTradingTriggerFailure] = []
    cancel_all: CancelAllOrdersResult | None = None


class TriggerStopDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_price: Price | None = None
    trigger_price_source: str = ""
    trigger_direction: str = ""


class TriggerTrailingDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Runtime state of a trailing stop; ``trigger_price`` is the current
    threshold, which moves with the peak (sell) or trough (buy)."""

    trigger_price: Price | None = None
    trailing_distance: Price | None = None
    trailing_distance_bps: int = 0
    activation_price: Price | None = None
    peak_price: Price | None = None
    trough_price: Price | None = None
    max_slippage: Price | None = None
    max_slippage_bps: int = 0
    trigger_price_source: str = ""
    trigger_direction: str = ""


class TriggerTwapDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    twap_duration_ms: int = 0
    twap_slice_interval_ms: int = 0
    slice_idx: int = 0
    slice_count: int = 0
    executed_qty: Quantity | None = None


class TriggerLadderDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    ladder_price_min: Price | None = None
    ladder_price_max: Price | None = None
    ladder_levels: int = 0
    ladder_distribution: str = ""
    executed_levels: int = 0
    executed_qty: Quantity | None = None


class TriggerDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Discriminated trigger strategy payload. ``case`` is stop|trailing|twap|ladder."""

    case: str
    stop: TriggerStopDetails | None = None
    trailing: TriggerTrailingDetails | None = None
    twap: TriggerTwapDetails | None = None
    ladder: TriggerLadderDetails | None = None


class Trigger(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_id: str = ""
    subaccount_id: str = ""
    symbol_id: int = 0
    symbol: str = ""
    trigger_type: str = ""
    status: str = ""
    parent_order_id: str = ""
    side: str = ""
    order_type: str = ""
    time_in_force: str = ""
    qty: Quantity | None = None
    limit_price: Price | None = None
    # Slippage cap of a stop-loss or take-profit market child: ``max_slippage``
    # in ticks (as a Price delta) or ``max_slippage_bps``; both unset means the
    # pair's default market slippage. Trailing stops report theirs on
    # ``details.trailing``.
    max_slippage: Price | None = None
    max_slippage_bps: int = 0
    fee_asset: str = ""
    self_trade_prevention_mode: str = ""
    post_only: bool = False
    trigger_price: Price | None = None
    # Price a stop-loss, take-profit or trailing stop watches: ``last``,
    # ``index`` or ``mark``. Pass it to ``triggers.create`` unchanged.
    trigger_price_source: str = ""
    client_trigger_id: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    armed_at: datetime | None = None
    completed_at: datetime | None = None
    details: TriggerDetails | None = None
    cancel_reason: str = ""
    failure_reason: str = ""
    # 1 for the first state, higher for every later state change. Reads and
    # realtime updates carry the same version for the same state: keep the
    # copy with the highest version and ignore any copy that is not higher.
    # 0 from a server that does not send it.
    version: int = 0


class TriggersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    triggers: list[Trigger]
    total: int = 0
    next_page_token: str = ""


class TriggerMutationResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    trigger_id: str = ""
    status: str = ""


class TransferSide(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One display side of a ledger transfer.

    ``kind`` is a snake_case label (funding_account, trading_account,
    external_address, private_counterparty, fee_account, system_account).
    ``chain_id`` is the Zipper ``ChainConfig.chain_id`` for external-address
    sides, not an EIP-155 or Polyester chain id.
    """

    kind: str = ""
    account_id: str = ""
    address: str = ""
    chain_id: int | None = None


class LedgerTransfer(msgspec.Struct, kw_only=True, omit_defaults=True):
    asset_id: int = 0
    amount: str = "0"
    transfer_type: int = 0
    account_code: int = 0
    timestamp: int = 0
    pending: bool = False
    tx_id: str = ""
    is_debit: bool = False
    source: TransferSide | None = None
    destination: TransferSide | None = None
    # Unsigned 128-bit decimal shared by both legs of one transfer; with
    # ``account_code`` it identifies a leg, so a repeated leg replaces the earlier copy.
    transfer_id: str = ""
    # The account bucket's balance after this transfer, an exact integer at the
    # fixed 18-decimal ledger scale like ``amount``. None when the server sent
    # none; a zero balance is "0".
    balance_after: str | None = None
    # Decimal correlation ID that groups related transfer legs; empty when none.
    link_id: str = ""


class TransfersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    transfers: list[LedgerTransfer]
    # Opaque continuation token; empty means the terminal page.
    next_page_token: str = ""


class InternalTransferResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The receipt of an internal transfer request.

    ``status`` is how the service answered the request: ``"accepted"``,
    ``"rejected"`` or ``"failed"``; empty when the response names none, and
    ``"UNKNOWN(n)"`` for a status this SDK version does not know.
    ``"accepted"`` means the transfer has a durable transfer ID, not that it
    has settled.
    """

    request_id: str = ""
    transfer_id: str = ""
    asset_id: int = 0
    asset_code: str = ""
    quantity: AssetAmount | None = None
    status: str = ""


class DepositAddress(msgspec.Struct, kw_only=True, omit_defaults=True):
    chain_id: int = 0
    deposit_address: str = ""


class DepositAddressesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    addresses: list[DepositAddress]


class TriggerEvent(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One step of a trigger's history.

    ``event_type`` is ``fired``, ``canceled``, ``updated``, ``failed``,
    ``activated``, ``armed`` or ``fire_refused``; a type newer than this SDK
    reads as its lowercase name or number. ``fire_refused`` records an attempt
    whose order was refused while the trigger stayed live (armed or running):
    ``child_seq`` is the refused attempt and ``fire_refusal_reason`` says why,
    as a ``failure_reason`` label (``rate_limited``, ``account_repairing``,
    ``market_halted``, ``min_notional``, ``self_trade_prevented``, ...). It is
    set only on ``fire_refused``; a refusal that ends the trigger is a
    ``failed`` event with ``failure_reason``. With ``self_trade_prevented``
    the attempt placed an order that self-trade prevention expired against
    another of the account's resting orders: ``child_seq`` names that order,
    which ends ``canceled`` with ``STP_EXPIRE_TAKER`` or ``STP_EXPIRE_BOTH``.
    Every other refusal placed no order. See
    :func:`polyester.codecs.decode.triggers.is_terminal_trigger_event`.
    """

    trigger_id: str = ""
    subaccount_id: str = ""
    symbol_id: int = 0
    trigger_type: str = ""
    event_type: str = ""
    ts_ns: str = ""
    child_seq: int = 0
    child_order_id: str = ""
    fire_price: Price | None = None
    cancel_reason: str = ""
    failure_reason: str = ""
    fire_refusal_reason: str = ""


class TriggerEventsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    events: list[TriggerEvent]
    next_page_token: str = ""


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
    portfolio_account_id: str = ""
    portfolio_remaining: bool = False
    equity_q: list[int] = []


class EquityHistory(msgspec.Struct, kw_only=True, omit_defaults=True):
    range: str = ""
    bucket: str = ""
    start_ts_sec: int = 0
    end_ts_sec: int = 0
    quote_asset: str = ""
    points: int = 0
    series: list[EquityHistorySeries] = []
    # Raw BTC-USDT closes scaled by 1e9, aligned to the implicit timestamps.
    btc_prices_q: list[int] = []


class BucketTransferResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    transfer_id: str = ""
    timestamp_ns: str = "0"


class ApiKeySummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    key_id: str = ""
    label: str = ""
    status: str = ""
    subaccount_id: str = ""
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0


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


class BatchReplaceItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One item of ``orders.batch_replace``.

    ``new_attached_risk`` replaces the order's attached risk, as on
    ``orders.modify``. A trailing stop's ``limit_price`` is sent as given: the
    request does not carry the order's side, so the server applies the side
    rule and answers ``ERROR_CODE_BAD_PRICE`` when it is broken.
    """

    key: OrderKey
    new_price: Any | None = None
    new_qty: Any | None = None
    new_client_order_id: str | None = None
    new_attached_risk: AttachedRisk | dict[str, Any] | None = None


class BatchReplaceAdmissionItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One item of a batch replace receipt.

    ``action_taken`` is ``"replaced"`` when the order is replaced by the
    successor ``replacement_order_id``, and ``"amended"`` when the order keeps
    ``old_order_id``: amended in place, or ended at its filled quantity. Empty
    when unset.

    ``replacement_order_id`` is the planned successor ID, not proof of an
    order: the item can still be refused after admission, and then that ID
    never becomes an order. Confirm it with ``wait_batch_replace``,
    ``get_batch_replace_status`` or order reads.
    """

    item_index: int
    status: str = ""
    client_order_id: str = ""
    old_order_id: str = ""
    replacement_order_id: str = ""
    code: str = ""
    rate_limit: RateLimitDetail | None = None
    action_taken: str = ""
    # Field violations a rejection names, in the order the server sent them;
    # empty for an accepted item or a rejection that names no field.
    violations: list[OrderFieldViolation] = []


class BatchReplaceOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    batch_request_id: str
    status: str
    results: list[BatchReplaceAdmissionItem]
    accepted_count: int = 0
    rejected_count: int = 0
    accepted_ts_ns: int = 0


class BatchReplaceStatusItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One item of a batch replace status read; ``action_taken`` as on admission.

    ``phase`` is ``admitted``, ``working``, ``rejected`` or ``terminal``. An
    item refused after admission (for example a post-only price that would
    cross) reads ``rejected``: the order kept its previous price and quantity
    and keeps ``old_order_id``, and ``replacement_order_id`` is empty.

    ``code`` is the refusal as the server sends it, without the
    ``ERROR_CODE_`` prefix (``POST_ONLY_CROSS``). ``error_code`` is the same
    refusal as ``PolyesterApiError.code`` names it
    (``ERROR_CODE_POST_ONLY_CROSS``), or ``code`` unchanged when this SDK does
    not know it.
    """

    item_index: int
    phase: str
    old_order_id: str = ""
    replacement_order_id: str = ""
    order_status: str = ""
    code: str = ""
    error_code: str = ""
    updated_ts_ns: int = 0
    action_taken: str = ""


class BatchReplaceStatusResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    batch_request_id: str
    admission_status: str
    items: list[BatchReplaceStatusItem]
    accepted_count: int = 0
    rejected_count: int = 0
    accepted_ts_ns: int = 0
    updated_ts_ns: int = 0


class BatchCreateResultItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    order_id: str = ""
    client_order_id: str = ""
    code: str = ""
    rate_limit: RateLimitDetail | None = None
    # On a duplicate-client-order-ID rejection: the order that already holds the
    # client order ID, when known; empty otherwise.
    existing_order_id: str = ""
    # Trigger IDs of the attached-risk legs this order configured; empty for a
    # leg the order does not have.
    take_profit_trigger_id: str = ""
    stop_loss_trigger_id: str = ""
    trailing_stop_trigger_id: str = ""
    # Field violations a rejection names, in the order the server sent them;
    # empty for an accepted item or a rejection that names no field.
    violations: list[OrderFieldViolation] = []


class BatchCreateOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchCreateResultItem]
    accepted_count: int = 0
    rejected_count: int = 0


class BatchCancelResultItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    order_id: str = ""
    client_order_id: str = ""
    code: str = ""
    rate_limit: RateLimitDetail | None = None
    # Field violations a rejection names, in the order the server sent them;
    # empty for an accepted item or a rejection that names no field.
    violations: list[OrderFieldViolation] = []


class BatchCancelOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchCancelResultItem]
    accepted_count: int = 0
    rejected_count: int = 0


class DeadManSwitchScope(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Orders an armed cancel-all-after switch cancels on expiry.

    ``symbol_id`` 0 covers every symbol; an empty ``side`` covers both sides.
    Waiting triggers stay active when the switch expires.
    """

    account_id: str = ""
    symbol_id: int = 0
    side: str = ""


class CancelAllAfterResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    effective_timeout_sec: int = 0
    expires_at_ts_ns: str = "0"
    # Scope the armed switch covers; None when the switch is disabled.
    effective_scope: DeadManSwitchScope | None = None


class WithdrawIntentResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    intent_id: str = ""


class WithdrawDestinationValidation(msgspec.Struct, kw_only=True, omit_defaults=True):
    """User-safe outcome of ``WithdrawService.validate_destination``."""

    valid: bool = False
    code: str = "unspecified"
    message: str = ""
    canonical_destination_address: str = ""
