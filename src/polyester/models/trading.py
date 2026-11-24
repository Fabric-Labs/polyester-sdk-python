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
    quote amount (``submitted_max_quote_debit_scaled``) its fills used. A sell
    sized by a quote proceeds target (``submitted_quote_proceeds_scaled``)
    reads its proceeds before fees from ``cum_notional_scaled``
    (:meth:`cum_quote`): never above the target, and the target less it is what
    the order did not receive.

    An iceberg order shows ``display_qty`` (the display it was placed with)
    on the order book at a time; ``hidden_qty`` is the part of ``leaves_qty``
    the book does not show, so the book shows ``leaves_qty - hidden_qty``.
    Both are zero for a plain order, and ``hidden_qty`` is zero once the order
    has ended. Lowering an iceberg's quantity in place to its display or below
    keeps its queue priority and shows all of it (``hidden_qty`` zero). A
    replace keeps the display while the new quantity is above it; otherwise
    the new order is a plain limit order with ``display_qty`` zero, and it
    stays plain.

    A refused batch replacement carries no order terms. When a
    ``batch_replace`` item is admitted and then refused as it applies, the
    successor order it would have created never exists, but for 60 seconds
    from the batch's acceptance ``orders.get`` of that successor's ID answers
    it: ``status`` ``"rejected"`` with the refusal in ``reject_reason`` (for
    example ``"modify_apply_expired"``), ``batch_request_id`` set,
    ``version`` 1, ``created_ts_ns`` the batch's admission, no
    ``terminal_ts_ns``, and its own ``lineage`` at generation 1. Its
    ``symbol_id``, ``side``, ``order_type``, ``tif``,
    ``self_trade_prevention_mode`` and ``fee_asset`` are ``None``, and its
    quantities and prices are 0 placeholders that name no pair, so the
    catalogs give them no scale. Take its terms from the batch you sent.
    After the 60 seconds it is not found. Open orders, order history and the
    order streams always carry the terms.
    """

    order_id: str
    # The order's pair. ``None`` only for a refused batch replacement read
    # through ``orders.get`` (see above).
    symbol_id: int | None = None
    client_order_id: str = ""
    # ``buy`` or ``sell``. ``side``, ``order_type``, ``tif``,
    # ``self_trade_prevention_mode`` and ``fee_asset`` are ``None`` when the
    # server does not report them, as for a refused batch replacement.
    side: str | None = None
    status: str = ""
    order_type: str | None = None
    tif: str | None = None
    orig_qty: Quantity | None = None
    cum_qty: Quantity | None = None
    inherited_cum_qty: Quantity | None = None
    leaves_qty: Quantity | None = None
    # Iceberg display quantity, and the part of ``leaves_qty`` the order book
    # does not show; both zero for a plain order (base quantity, as
    # ``leaves_qty``).
    display_qty: Quantity | None = None
    hidden_qty: Quantity | None = None
    # A LIMIT order's limit price. A MARKET order's protection price: the worst
    # price it may fill at (a BUY at or below it, a SELL at or above it), its
    # reference price moved by its maximum slippage, or by the pair's default
    # market slippage, on the tick grid. Every market order has one, whatever
    # placed it: a direct market order, a stop-loss's, take-profit's, trailing
    # stop's or attached leg's market order, or a TWAP slice. A stop's or
    # trailing stop's market order takes the price that fired it as its
    # reference. Tell a market order from a limit order by ``order_type``, never
    # by a missing or zero price.
    price: Price | None = None
    avg_px: Price | None = None
    created_ts_ns: str = ""
    # When the order became terminal, in Unix nanoseconds (UTC) as a decimal
    # string; empty while it is open.
    terminal_ts_ns: str = ""
    version: int = 0
    post_only: bool = False
    # ``quote`` or ``base``; ``None`` when the server does not report it.
    fee_asset: str | None = None
    # ``expire_taker``, ``expire_maker``, ``expire_both`` or ``decrement``,
    # which the order's attached exits use too; ``None`` when unset. A mode
    # newer than this SDK reads as its number.
    self_trade_prevention_mode: str | None = None
    # A BUY's submitted all-in quote budget, scaled by the pair's quote
    # quantity scale; empty when the order was not sized that way.
    submitted_max_quote_debit_scaled: str = ""
    # A SELL's submitted quote proceeds target, scaled by the pair's quote
    # quantity scale; empty when the order was not sized that way.
    submitted_quote_proceeds_scaled: str = ""
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
    # Public ID of the batch replace that admitted the order, as
    # ``BatchReplaceResult.batch_request_id`` (pass it to
    # ``orders.get_batch_replace_status``); "" for every other origin.
    batch_request_id: str = ""
    # Why a ``rejected`` order was refused: the Orders API error code for the
    # same refusal, in lower case without its ``ERROR_CODE_`` prefix (for
    # example ``post_only_cross``). ``None`` for every other status. A code
    # this SDK does not know reads ``UNKNOWN_ERROR_CODE(n)``.
    reject_reason: str | None = None
    # Why a ``canceled`` order ended, in lower case without the
    # ``CANCEL_REASON_`` prefix (for example ``user_request``, ``replaced`` or
    # ``stp_decrement``). ``None`` for every other
    # status. A number this SDK does not know reads ``UNKNOWN_CANCEL_REASON(n)``.
    cancel_reason: str | None = None
    avg_price: Decimal | None = None
    cum_notional_scaled: str = "0"
    fee_total: OrderFeeTotal | None = None
    # The pair's quote quantity scale from the catalogs, attached when the
    # order was read with the catalogs loaded; ``None`` otherwise. The base
    # quantity scale is ``cum_qty.scale``.
    quote_quantity_scale: int | None = None

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
        self,
        *,
        quote_quantity_scale: int | None = None,
        base_quantity_scale: int | None = None,
    ) -> Decimal | None:
        """The part of a buy's quote amount its fills did not use.

        ``submitted_max_quote_debit_scaled`` (at the pair's
        ``quote_quantity_scale``) less :meth:`quote_used`. ``None`` for an
        order not sized by a quote amount, or while ``quote_used`` is ``None``.
        ``quote_quantity_scale`` defaults to the scale the order was read
        with (:attr:`quote_quantity_scale`).
        """
        if quote_quantity_scale is None:
            quote_quantity_scale = self.quote_quantity_scale
        if quote_quantity_scale is None:
            from polyester.errors import PolyesterValidationError

            raise PolyesterValidationError(
                "quote_quantity_scale is required: pass the pair's quote quantity scale"
            )
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
    ``distance_ticks`` (``trailing_distance_ticks`` in a dict) is a price delta in
    1e-9 quote-unit ticks, the scale of every price tick: ``500_000_000`` is 0.5
    quote units, not 500 million of the pair's tick size.
    ``trigger_price_source`` is ``last``, ``index`` or ``mark``; unset on a
    write means the last trade price. ``order_type`` is rejected if supplied
    under ``attached_risk.trailing_stop``.

    ``limit_price`` is the most the exit pays per unit when the trailing stop
    buys back: required when the order sells, unset when it buys, and at least
    ``activation_price`` when both are set. Order reads return it as the server
    sends it, and ``None`` when it sends none, as for an order that buys. When
    a trailing stop with a ``limit_price`` fires, its child is a limit IOC order
    at that price (lower when a slippage cap sets it below): it fills what it
    can at or below the limit and the rest is canceled, not left resting.
    Without one the child is a market order.
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


class OrderPeg(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A static entry peg: a limit order's price, chosen once at entry.

    ``reference`` is ``"best_bid"`` or ``"best_ask"`` (any case): the highest
    live bid or lowest live ask when the order arrives. ``offset_ticks`` is a
    signed count of the pair's price increments (its tick size) added to that
    reference: ``-2`` is two tick-size increments below it. It is not a count
    of 1e-9 price ticks, and it does not select occupied book levels. The
    price never follows later book changes.

    The limit order still needs its ``price``: a BUY's cap or a SELL's floor.
    A derived price beyond it is refused ``PEG_LIMIT_VIOLATION``, an empty
    reference side ``PEG_REFERENCE_UNAVAILABLE``, and unsupported terms
    ``INVALID_PEG``.
    """

    reference: str
    offset_ticks: int = 0


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
    # The create's quote sizing echoed back, scaled by the pair's quote
    # quantity scale: a BUY's all-in budget or a SELL's proceeds target.
    # Empty when the order was not sized that way.
    submitted_max_quote_debit_scaled: str = ""
    submitted_quote_proceeds_scaled: str = ""
    # Trigger IDs of the attached-risk legs this order configured; empty for a
    # leg the order does not have.
    take_profit_trigger_id: str = ""
    stop_loss_trigger_id: str = ""
    trailing_stop_trigger_id: str = ""
    # When a create's admission completed, in nanoseconds since the Unix
    # epoch; None when the server sent no time, and on a cancel.
    accepted_ts_ns: int | None = None


class OrderFieldViolation(msgspec.Struct, kw_only=True, omit_defaults=True):
    field_path: str = ""
    rule_id: str = ""
    message: str = ""


class OrderErrorDetail(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Why an order would be refused (``PreviewOrderResult.rejection``).

    ``price_band_limit`` is set only on a preview refused with ``code``
    ``"PRICE_BAND_VIOLATION"``: the band limit the order's limit price
    is past, the highest admitted price for a buy and the lowest for a sell,
    as the market last published its band. ``None`` otherwise.
    """

    code: str = ""
    violations: list[OrderFieldViolation] = []
    rate_limit: RateLimitDetail | None = None
    price_band_limit: Price | None = None


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
    """One asset's balances, exact integers at the 18-decimal ledger scale.

    ``trading``, ``reserved`` and ``available`` are the Trading values;
    ``funding`` and ``funding_revision`` the Funding ones. A Funding value is
    newer than another of the same asset when its ``funding_revision`` is
    higher. Trading values are ordered by the position of the read or update
    that carries them (``trading_epoch``, ``trading_sequence``), not per asset.
    """

    asset_id: int
    trading: str = "0"
    funding: str = "0"
    reserved: str = "0"
    available: str = "0"
    funding_revision: int = 0


class BalancesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    """``balances.list``: every asset's balances, and the position the Trading
    values are at.

    The Trading values of every asset are one cut, taken at
    ``(trading_epoch, trading_sequence)``: apply the balance stream's Trading
    updates of that epoch from ``trading_sequence + 1`` on. Compare
    ``trading_epoch`` only for equality; it is an opaque number that changes
    when the numbering restarts. Every Trading transfer of the account with a
    ``ts_ns`` at or below ``trading_applied_through_ts_ns`` is applied in
    these balances. The three are 0 from a server that predates them.
    """

    balances: list[AssetBalance]
    trading_epoch: int = 0
    trading_sequence: int = 0
    trading_applied_through_ts_ns: int = 0


class ZipperReasonDetails(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The bridge's reason on a lifecycle flow, as the server sent it.

    ``code`` is the bridge's code (0 when it gave none), ``reason_id`` a stable
    identifier to localize, and ``message`` English text to show. Prefer
    ``reason_id`` or ``message`` over text keyed by ``code``: a withdrawal
    whose execution failed (lifecycle reason
    ``zipper_withdraw_execution_failed``) reads ``reason_id``
    ``withdrawal.execution_failed.under_review`` whatever its code, and its
    ``message`` says it is under review by the bridge operator and its funds
    were not returned to the account. It is not a refund, and the user may
    have received the funds on the destination chain.
    """

    code: int = 0
    reason_id: str = ""
    message: str = ""


class LifecycleFlowSummary(msgspec.Struct, kw_only=True, omit_defaults=True):
    intent_id: str
    flow_kind: str = ""
    latest_step: str = ""
    is_open: bool = False
    is_terminal: bool = False
    # The account the flow belongs to, by its public identity on Polyester
    # Chain: its smart account address.
    smart_account_address: str = ""
    # Why the flow ended or stalled, as a lowercase label such as
    # "zipper_validation_rejected"; "unspecified" when there is none. One
    # completed flow carries a reason too: "zipper_deposit_delivered_to_wallet",
    # a deposit delivered as zTokens to the account's own Polyester Chain
    # wallet (``smart_account_address``) instead of its Funding or Trading
    # balance, which was not credited. It is a completed outcome, not a
    # failure. A reason newer than this SDK reads "unknown_reason_<n>".
    lifecycle_reason: str = "unspecified"
    zipper_reason: ZipperReasonDetails | None = None
    # True when an open flow has made no progress for well beyond its expected
    # step time. Always false for terminal flows and transaction lookups.
    is_delayed: bool = False
    # How the selected account takes part in the flow, on a row of a list_flows
    # that selects an account, of list_account_flows and of get_account_flow:
    # "owner" (its deposit, withdrawal or a transfer it sent, including a move
    # between its own balances) or "recipient" (a transfer another account sent
    # to it). "unspecified" on an unscoped list, get_flow and a realtime
    # update; empty on a transaction lookup.
    participation: str = ""
    # For a transfer, the counterparty is destination_address when the account
    # sent it and source_address when it received it.
    source_address: str = ""
    destination_address: str = ""
    # The flow's asset: the chain-specific asset mapping (zToken) row, and the
    # unified asset Funding, Trading and the other balances count it in. 0 when
    # the server sends none.
    zipped_asset_id: int = 0
    unified_asset_id: int = 0
    # The Polyester Chain the flow belongs to; 0 when it is not known.
    polyester_chain_id: int = 0
    # The flow's gross principal, exact, at the 18-decimal ledger scale
    # (domain ``ledger_e18``) in units of ``unified_asset_id``; never a float.
    # It does not include the request fee (``request_fee``). A deposit keeps
    # its deposited amount after Zipper returned it or transferred it out,
    # which is not the amount Zipper paid. None when the server sends none.
    amount: AssetAmount | None = None
    # The request's fee when one applies and is visible for the current step;
    # None otherwise. Transaction lookups do not carry it.
    request_fee: LifecycleRequestFee | None = None
    # The first observed source transaction of the flow; for a transfer
    # between Trading accounts, the Polyester Chain transaction that records
    # the settled transfer. Empty until it is observed.
    source_tx_hash: str = ""
    # Tells apart the flows of one transaction: the leg index of a batched
    # source-chain deposit, or the log (or equivalent) index of an on-chain
    # fact. 0 when none is available, which is also a first leg's index.
    tx_occurrence_index: int = 0
    # The latest transaction behind the current visible state. Opaque: a chain
    # transaction hash or another reference, such as a decimal ID, depending
    # on the step. Empty when there is none.
    latest_tx_ref: str = ""
    # The product domains where the whole flow starts and where it ends or
    # currently settles, for route labels such as Funding to Trading:
    # "external_chain", "zipper", "funding", "trading" or "lending";
    # "unspecified" when the server sends none, and "unknown_domain_<n>" for a
    # domain newer than this SDK.
    source_domain: str = "unspecified"
    destination_domain: str = "unspecified"
    # The flow's first observed business time and the summary's last update,
    # as aware UTC datetimes; None when the server sends none. Transaction
    # lookups carry neither.
    started_at: datetime | None = None
    updated_at: datetime | None = None
    # When the flow reached its final state; None while it is open.
    # Transaction lookups do not carry it.
    terminal_at: datetime | None = None
    # The time lists order flows by; None when the server sends none.
    last_activity_at: datetime | None = None
    # When the flow is expected to complete; None when the server sends none,
    # as transaction lookups do.
    #
    # The contract sends no estimate (None here) while ``is_delayed`` is true,
    # because no reliable one exists then.
    #
    # The contract does not say what a terminal flow carries here. Devnet
    # sends the flow's terminal time, the same as ``terminal_at``, but do not
    # rely on that: read ``terminal_at`` for when a flow ended.
    estimated_completion_at: datetime | None = None
    # The one-based position of ``latest_step`` in ``progress_timeline``; 0
    # when the server sends none.
    current_step_sequence: int = 0
    # The current step's progress while the flow is open; None when the server
    # sends none. On a flow that is no longer open it may be present with
    # every field zero. Transaction lookups do not carry it.
    current_progress: LifecycleFlowProgress | None = None
    # The flow's expected steps in order, for a progress bar. Its current step
    # may be derived ahead of the latest step actually observed. Empty when
    # the server sends none, as transaction lookups do.
    progress_timeline: list[LifecycleFlowTimelineItem] = []


class LifecycleRequestFee(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The fee a lifecycle flow's request pays, apart from the flow's gross
    ``amount``.

    ``zipped_asset_id`` and ``unified_asset_id`` name the fee asset, as on
    :class:`LifecycleFlowSummary`. ``amount`` is the fee, exact, at the
    18-decimal ledger scale in units of the fee asset; None when the server
    sends none. ``recipient_address`` receives the fee once it settles on
    chain; empty before. ``status`` is ``"locked"`` (the request locked the fee
    when it was created), ``"settled"`` (the request completed far enough for
    the fee to settle) or ``"kept"`` (the request did not complete and the fee
    was charged anyway: Zipper does not refund a withdrawal's fee when it
    rejects the withdrawal or its execution fails); ``"unspecified"`` when the
    server sends none, and ``"unknown_fee_status_<n>"`` for a status newer than
    this SDK.
    """

    zipped_asset_id: int = 0
    unified_asset_id: int = 0
    amount: AssetAmount | None = None
    recipient_address: str = ""
    status: str = "unspecified"


class LifecycleFlowProgress(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The progress of an open lifecycle flow's current step.

    ``current_step_started_at`` is when the current step started (aware UTC;
    None when the server sends none), and ``current_step_expected_duration_ms``
    how long it is expected to take, in milliseconds. The counts are 0 when
    they do not apply to the step: confirmations to a step waiting on
    source-chain confirmations, approvals and rejections to a validation step.
    ``validator_count`` is the validator set's size, ``required_approvals`` the
    approvals the step needs and ``required_rejections`` the rejections that
    would fail it.
    """

    current_step_started_at: datetime | None = None
    current_step_expected_duration_ms: int = 0
    current_confirmations: int = 0
    required_confirmations: int = 0
    approve_count: int = 0
    reject_count: int = 0
    validator_count: int = 0
    required_approvals: int = 0
    required_rejections: int = 0


class LifecycleFlowTimelineItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One step of a lifecycle flow's progress timeline.

    ``sequence`` is the step's one-based position in the timeline, and
    ``step`` names the step as :attr:`LifecycleFlowSummary.latest_step` does.
    ``status`` is ``"completed"`` (observed, or behind the current step),
    ``"current"`` or ``"planned"`` (expected, not observed yet);
    ``"unspecified"`` when the server sends none, and
    ``"unknown_timeline_status_<n>"`` for a status newer than this SDK.
    ``expected_duration_ms`` is how long the step is expected to take, in
    milliseconds, from recent timing of the same kind of flow; 0 when there is
    no estimate.
    """

    sequence: int = 0
    step: str = "unspecified"
    status: str = "unspecified"
    expected_duration_ms: int = 0


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
    # When the server answered the modify, in nanoseconds since the Unix
    # epoch; None when it sent no time.
    ts_ns: int | None = None


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

    ``matched_triggers`` counts, with ``include_triggers=True``, the triggers
    that matched, each stopped (canceled with reason ``cancel_all``) unless
    it is a dry run; 0 without it.
    """

    status: str = ""
    matched_orders: int = 0
    submitted_cancels: int = 0
    failed_cancels: int = 0
    cancelled_orders: list[CancelledOrder] = []
    total_cancelled: int = 0
    truncated: bool = False
    listing_status: str = ""
    matched_triggers: int = 0
    # When the server answered, in nanoseconds since the Unix epoch; None when
    # it sent no time. A retry with the same request_id returns the original
    # cancel-all's time.
    ts_ns: int | None = None


@dataclass(frozen=True, slots=True)
class StopAllTradingTriggerFailure:
    """A trigger ``orders.stop_all_trading`` could not cancel, and why."""

    trigger_id: str
    error: Exception


class StopAllTradingResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Outcome of ``orders.stop_all_trading``.

    ``canceled_trigger_ids`` are the live triggers whose cancel was accepted,
    in the order they were canceled, both legs of a canceled OCO included.
    ``trigger_failures`` are the ones whose cancel failed, each with its
    error: a refusal or transport error. Check it: a failed trigger may still
    be live. A listed trigger that had already ended when its cancel arrived
    is in neither list: it is stopped. ``cancel_all`` is the cancel-all that
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
    """A ladder trigger's levels and how their placement went.

    ``requested_levels`` counts the child orders the ladder requested, one per
    level; ``placed_levels`` those placed on the book, open ones included;
    ``rejected_levels`` those rejected before they were placed; and
    ``canceled_levels`` placed ones canceled or expired, partly filled or not
    (when the ladder itself ends, its open child orders count here). A placed
    child rejected after a partial fill counts as neither rejected nor
    canceled. ``outcome`` is ``"all_admitted"``, ``"mixed_rejections"`` or
    ``"all_children_rejected"`` once the ladder has ended, "" while it runs
    (and for a ladder rejected at its creation); an outcome this SDK does not
    know reads as its decimal string.
    """

    ladder_price_min: Price | None = None
    ladder_price_max: Price | None = None
    ladder_levels: int = 0
    ladder_distribution: str = ""
    executed_levels: int = 0
    executed_qty: Quantity | None = None
    requested_levels: int = 0
    placed_levels: int = 0
    rejected_levels: int = 0
    canceled_levels: int = 0
    outcome: str = ""


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
    # The pair's name from the loaded catalogs (``triggers.get``,
    # ``triggers.list`` and ``triggers.subscribe``); empty without them.
    symbol: str = ""
    trigger_type: str = ""
    status: str = ""
    parent_order_id: str = ""
    # Both triggers of an OCO created with ``triggers.create_oco`` carry the
    # OCO's ``order_list_id`` (a public ID, the one ``triggers.cancel_oco``
    # takes) and the ``client_list_id`` it was created with, and neither has a
    # parent order. Both are empty for any other trigger.
    order_list_id: str = ""
    client_list_id: str = ""
    side: str = ""
    order_type: str = ""
    time_in_force: str = ""
    qty: Quantity | None = None
    limit_price: Price | None = None
    # Slippage cap, as configured: of a stop-loss or take-profit market
    # child, of a trailing stop, or of each market TWAP slice.
    # ``max_slippage`` in ticks (as a Price delta) or ``max_slippage_bps``,
    # whichever was set; both unset means the pair's default market slippage
    # (no explicit cap), not an unprotected order. A trailing stop also
    # reports its cap on ``details.trailing``.
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


class CreateOcoResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """An admitted OCO: its ID and the trigger IDs of its two legs.

    ``order_list_id`` is the ID ``triggers.cancel_oco`` takes; both legs carry
    it. The legs are triggers: read, modify or cancel them by their trigger IDs.
    """

    order_list_id: str = ""
    client_list_id: str = ""
    take_profit_trigger_id: str = ""
    stop_loss_trigger_id: str = ""
    # When admission completed, in nanoseconds since the Unix epoch; None when
    # the server sent no time.
    accepted_ts_ns: int | None = None


class CancelOcoResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    order_list_id: str = ""
    # Both legs' status after the cancel: ``canceled``.
    status: str = ""
    # When the cancel was answered, in nanoseconds since the Unix epoch; None
    # when the server sent no time.
    ts_ns: int | None = None


class BatchCancelTriggerResultItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    status: str = ""
    trigger_id: str = ""
    code: str = ""
    rate_limit: RateLimitDetail | None = None
    # Field violations a rejection names, in the order the server sent them;
    # empty for an accepted item or a rejection that names no field.
    violations: list[OrderFieldViolation] = []


class BatchCancelTriggersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchCancelTriggerResultItem]
    accepted_count: int = 0
    rejected_count: int = 0
    # The server time of the answer, in nanoseconds since the Unix epoch; None
    # when the server sent no time.
    ts_ns: int | None = None


class CancelAllTriggersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Outcome of ``triggers.cancel_all``.

    ``status`` is ``"submitted"``, or ``"dry_run"`` for a dry run, which
    cancels nothing. ``matched_triggers`` counts every trigger that matched,
    each leg canceled together with a matching one included (an order's
    attached legs, an OCO's two legs). The answer lists no trigger IDs: read
    the triggers again for their state. ``ts_ns`` is the server time of the
    answer in nanoseconds since the Unix epoch; None when the server sent no
    time.
    """

    status: str = ""
    matched_triggers: int = 0
    ts_ns: int | None = None


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
    # The ``ledger.v1.TransferCode`` number, such as 1074 (SYSTEM_ADJUSTMENT);
    # 0 when the server names none or a name this SDK does not know. It names
    # the reason, not the direction: read ``is_debit``. A system adjustment
    # can credit (account seeding) or debit (a correction) the account.
    # 1065 (TRADING_WITHDRAW_REQUEST_FEE) and 1075 (WITHDRAW_FAILED) are the
    # debit of a withdrawal that was rejected or failed to execute, from the
    # Trading and the Funding account respectively: its whole amount, request
    # fee included, not a fee. A rejected withdrawal is refunded less the
    # request fee to the account's own wallet; one that failed to execute is
    # not refunded.
    transfer_type: int = 0
    account_code: int = 0
    timestamp: int = 0
    pending: bool = False
    # The transfer's lifecycle flow ID (the contract's ``flow_id``), for
    # ``client.lifecycle.get_flow(flow_id=...)``; empty when it has none. The
    # ``withdraw_failed`` (1075) debit of a failed withdrawal carries its
    # withdrawal's flow ID in ``transfers.list``, joined when read, so an
    # early read may still show it empty; the realtime transfer stream does
    # not carry it for that debit. A new Trading-to-Funding transfer carries
    # it on its first realtime update.
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
    # The transfer's exact time in Unix nanoseconds; ``timestamp`` is the same
    # time in microseconds. 0 from a server that predates it. A Trading
    # transfer with ``ts_ns`` at or below a ``trading_applied_through_ts_ns``
    # of the account's current epoch is applied in those balances.
    ts_ns: int = 0


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

    ``flow_id`` is the transfer's lifecycle flow ID, for
    ``client.lifecycle.get_flow(flow_id=...)``; empty when the response names none.
    """

    request_id: str = ""
    transfer_id: str = ""
    asset_id: int = 0
    asset_code: str = ""
    quantity: AssetAmount | None = None
    status: str = ""
    flow_id: str = ""


class InternalTransferLeg(msgspec.Struct, kw_only=True):
    """One transfer of :meth:`internal_transfers.batch_create
    <polyester.services.AsyncInternalTransfersService.batch_create>`.

    It takes the arguments of ``internal_transfers.create`` except the
    idempotency key, which the batch carries: ``asset_id``, ``quantity`` (a
    decimal string, ``Decimal`` or ``AssetAmount`` in whole units of the
    asset, or at ``quantity_scale``; never a float), exactly one destination,
    and the source account by ``account`` or ``sub_account_id``, resolved as
    for ``create``: with neither, the client's default sub-account. Legs of
    one batch may debit different source accounts.
    """

    asset_id: int
    quantity: str | Decimal | AssetAmount
    destination_account_id: str | int | None = None
    destination_subaccount_id: str | int | None = None
    destination_smart_account_address: str | None = None
    sub_account_id: str | int | None = None
    account: str | dict[str, Any] | None = None
    quantity_scale: int | None = None


class InternalTransferBatchLegResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The state of one leg of a batch, in request order.

    A batch moves as one, so every leg has the status its batch's status
    admits: ``"credited"`` (the leg is credited to its destination;
    ``credited_at_ts_ns`` and ``flow_id`` say when and which lifecycle flow),
    ``"processing"`` (the leg's outcome is the batch's, not known yet) or
    ``"not_moved"`` (its batch was refused and the leg moved nothing).
    ``transfer_id`` is the leg's stable transfer identifier, set once the
    batch is processing or accepted. ``error_code`` is set only on the legs
    that caused a refusal: the transfer error as a lowercase label without
    the ``ERROR_CODE_`` prefix, such as ``"insufficient_funds"``, and
    ``"UNKNOWN_ERROR_CODE(n)"`` for a code this SDK does not know.
    ``credited_at_ts_ns`` is the credit time in nanoseconds since the Unix
    epoch, ``None`` before the leg is credited. ``quantity`` is the echoed
    amount, exact at 18 decimals. ``destination`` is the destination the
    server resolved for the leg, ``None`` when the reply carries none.
    """

    leg_index: int = 0
    status: str = ""
    transfer_id: str = ""
    flow_id: str = ""
    credited_at_ts_ns: int | None = None
    asset_id: int = 0
    asset_code: str = ""
    quantity: AssetAmount | None = None
    destination: ResolvedDestination | None = None
    error_code: str = ""
    error_message: str = ""


class ResolvedDestination(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The destination the server resolved for a transfer: the destination's
    root account public ID, its sub-account public ID when the transfer
    targets one, and its smart account address. Each is "" when the server
    does not name it."""

    root_account_public_id: str = ""
    subaccount_public_id: str = ""
    smart_account_address: str = ""


class InternalTransferBatchResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A batch of internal transfers, which moves as one: every leg is
    credited, or none moves.

    ``status`` is ``"accepted"`` (every leg is credited), ``"processing"``
    (the outcome is not known yet; the batch completes on its own and ends
    accepted or refused: read it with ``internal_transfers.get_batch`` or
    ``wait_batch``) or ``"refused"`` (nothing moved, and nothing will under
    this idempotency key; the legs that caused it carry ``error_code``).
    ``request_id`` is the batch's identifier, "" when it was refused before it
    was accepted for processing. ``legs`` holds one result per requested leg,
    in request order.
    """

    request_id: str = ""
    status: str = ""
    legs: list[InternalTransferBatchLegResult] = []


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
    which ends ``canceled`` with ``stp_expire_taker`` or ``stp_expire_both``.
    Every other refusal placed no order. A ladder keeps working when the
    order book rejects one of its levels on arrival (a post-only level that
    would cross, for example): that level's ``fired`` event, which names the
    rejected child order, is followed by a ``fire_refused`` event with the
    same ``child_seq``, its ``fire_refusal_reason`` and the level's price as
    ``fire_price``. Such a level was not placed: do not count it among the
    ladder's placed levels. A ladder ends ``failed`` only when every level was
    rejected. See
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
    """One asset's balance in one account bucket over the history window.

    ``balance`` holds the exact balance at each point, aligned 1:1 with the
    response's points (``points`` of them, from ``start_ts_sec`` every
    ``bucket``): an :class:`~polyester.types.money.AssetAmount` in 18-decimal
    ledger units (``scale`` 18, domain ``ledger_e18``) for ``asset_id``. Read
    whole units with ``amount.as_decimal()`` or ``amount.format()``; never
    through a float.
    """

    asset_id: int = 0
    account_code: int = 0
    balance: list[AssetAmount] = []


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
    # User-chosen icon or emoji and color token for display, as sent (at
    # most 32 characters each); "" when none is set.
    icon: str = ""
    color: str = ""
    # Read-only label of who created the key, such as a username or account
    # label; "" when the server sends none.
    created_by_actor: str = ""
    status: str = ""
    # Public ID of the sub-account the key is scoped to; "" for a key of the
    # main account.
    subaccount_id: str = ""
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0
    # "standard" for a key the user created, "assistant" for a key of the
    # Polyester assistant, "admin_key" for an admin key, "strategy_bot" for a
    # strategy bot's trade key; "" when the server does not say. A strategy
    # bot manages its key: an update, policy change or delete of it is
    # refused with AUTH_STRATEGY_BOT_MANAGED.
    purpose: str = ""
    # Public ID of the API policy attached to the key, as ``ApiPolicy.id``;
    # "" when none is attached, in which case the key has no permissions.
    policy_id: str = ""
    # CIDR allowlist of the addresses the key may be used from, as sent;
    # empty means no IP restriction.
    ip_whitelist: list[str] = []
    # UTC time after which the key cannot authenticate, whatever its status;
    # ``None`` when the key does not expire.
    expires_at: datetime | None = None
    # Hex of the key's Ed25519 public key; "" when the server sends none.
    public_key_ed25519: str = ""
    # Public ID of the strategy bot a "strategy_bot" key trades for; "" on
    # every other key.
    strategy_bot_id: str = ""


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
    ``orders.modify``; an empty one raises ``PolyesterValidationError``. A
    trailing stop's ``limit_price`` is sent as given: the request does not
    carry the order's side, so the server applies the side rule and answers
    ``ERROR_CODE_BAD_PRICE`` when it is broken. ``clear_attached_risk=True``
    removes the order's take-profit, stop-loss and trailing stop, alone or
    with a new price or quantity; with ``new_attached_risk`` it raises.
    """

    key: OrderKey
    new_price: Any | None = None
    new_qty: Any | None = None
    new_client_order_id: str | None = None
    new_attached_risk: AttachedRisk | dict[str, Any] | None = None
    clear_attached_risk: bool = False


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
    # Field violations a rejection names, in the order the server sent them,
    # as the request item names them and without its index (for example
    # ``new_attached_risk.stop_loss`` or ``order_id``; REST:
    # ``newAttachedRisk.stopLoss``): the item is ``item_index``. Empty for an
    # accepted item or a rejection that names no field.
    violations: list[OrderFieldViolation] = []
    # On a duplicate-client-order-ID rejection: the order that already holds
    # the client order ID, when known; empty otherwise.
    existing_order_id: str = ""


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
    # Field violations a rejection names, in the order the server sent them,
    # as a CreateOrderRequest carrying the item would, under ``order`` and
    # without the item's index (for example ``order.limit_gtc.price_ticks``;
    # REST: ``order.limitGtc.price``): the item is this result's position in
    # ``results``. Empty for an accepted item or a rejection that names no
    # field.
    violations: list[OrderFieldViolation] = []
    # An accepted item's quote sizing echoed back, scaled by the pair's quote
    # quantity scale: a BUY's all-in budget or a SELL's proceeds target.
    # Empty when the item was not sized that way, and for a rejection.
    submitted_max_quote_debit_scaled: str = ""
    submitted_quote_proceeds_scaled: str = ""
    # An accepted item's gross base quantity resolved for execution, as on a
    # single create: scaled by the pair's base quantity scale, which
    # ``resolved_base_qty`` carries when the catalogs know the pair. Empty and
    # None for a rejection.
    resolved_base_qty_scaled: str = ""
    resolved_base_qty: Quantity | None = None


class BatchCreateOrdersResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    results: list[BatchCreateResultItem]
    accepted_count: int = 0
    rejected_count: int = 0
    # When the server answered the batch, in nanoseconds since the Unix epoch;
    # None when it sent no time.
    ts_ns: int | None = None


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
    # When the server answered the batch cancel, in nanoseconds since the Unix
    # epoch; None when it sent no time.
    ts_ns: int | None = None


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
    # When the server answered, in nanoseconds since the Unix epoch; None when
    # it sent no time. Not the switch's expiry, which is expires_at_ts_ns.
    ts_ns: int | None = None


class WithdrawIntentResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    intent_id: str = ""


class WithdrawDestinationValidation(msgspec.Struct, kw_only=True, omit_defaults=True):
    """User-safe outcome of ``WithdrawService.validate_destination``."""

    valid: bool = False
    code: str = "unspecified"
    message: str = ""
    canonical_destination_address: str = ""


class WalletBalance(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One nonzero zToken balance of the account's smart account wallet.

    ``amount_e18`` is the exact amount scaled by 1e18; ``amount`` is the same
    in whole units of the asset. ``zipped_asset_id`` names the zToken,
    ``unified_asset_id`` the asset it wraps and ``chain_id`` the chain it
    came from.
    """

    zipped_asset_id: int = 0
    unified_asset_id: int = 0
    chain_id: int = 0
    ztoken_address: str = ""
    amount_e18: str = "0"

    @property
    def amount(self) -> Decimal:
        return Decimal(format_qty_scaled(int(self.amount_e18 or 0), 18))


class UnavailableWalletAsset(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A zToken whose balance a wallet read could not read: its balance is
    unknown, not zero, and the wallet may hold some of it.

    ``reason`` is ``"no_contract"`` (no zToken contract exists at
    ``ztoken_address`` on Polyester Chain), ``"read_failed"`` (the chain
    answered the read with an error) or ``"invalid_balance"`` (the read
    returned a value that is not a valid balance); "" when the server names
    none, and a reason this SDK does not know reads as its decimal string.
    """

    zipped_asset_id: int = 0
    unified_asset_id: int = 0
    chain_id: int = 0
    ztoken_address: str = ""
    reason: str = ""


class WalletBalances(msgspec.Struct, kw_only=True, omit_defaults=True):
    """zTokens held by the account's smart account wallet, read live from
    Polyester Chain, such as the refund of a rejected withdrawal. Ordered by
    ``zipped_asset_id``.

    A read can be incomplete: ``unavailable_assets`` lists, by
    ``zipped_asset_id``, the zTokens whose balance could not be read. An asset
    missing from ``balances`` is held at zero only when the read
    :attr:`is_complete`; otherwise it may be in ``unavailable_assets``, with
    an unknown balance. Show those as unavailable, never as zero, leave them
    out of any total, and decide nothing that depends on their balance until
    a later read returns it.
    """

    smart_account_address: str = ""
    balances: list[WalletBalance] = msgspec.field(default_factory=list)
    unavailable_assets: list[UnavailableWalletAsset] = msgspec.field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """True when every zToken's balance was read."""
        return not self.unavailable_assets
