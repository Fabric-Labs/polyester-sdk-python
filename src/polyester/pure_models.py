"""Polyester order and trigger decoders for a restricted Python runtime with no C extensions.

Loaded after ``polyester/pure.py``, into the same namespace: it takes ``Price``,
``Quantity`` and the market spec from that file's ``polyester``, once, as it loads.
``polyester_models.order(data, market)`` and ``polyester_models.trigger(data, market)``
decode a canonical proto-JSON ``Order`` or ``Trigger`` (``MessageToDict`` form) into
models with the SDK's field names, types and values. Its one top-level name is
``polyester_models``. Formatted with ``ruff format --config indent-width=2 --line-length 120``.
"""


# Builtins bound at load: code loaded later into the same namespace can't rebind them.
def polyester_models(
  ValueError=ValueError,
  bool=bool,
  dict=dict,
  int=int,
  isinstance=isinstance,
  len=len,
  max=max,
  str=str,
  type=type,
):
  from dataclasses import dataclass as _dataclass
  from datetime import datetime as _datetime
  from datetime import timedelta as _timedelta
  from decimal import Decimal as _Decimal

  _Price = polyester.Price
  _Quantity = polyester.Quantity
  _market = polyester.market
  _encode_id = polyester._sdk["_encode_id"]
  _parse_id = polyester._sdk["_parse_id"]
  _format_scaled = polyester._sdk["_format_scaled"]
  _EPOCH = "1970-01-01T00:00:00"
  _PREFIXES = ("TRIGGER_CANCEL_REASON_", "TRIGGER_FAILURE_REASON_", "STATUS_")

  @_dataclass
  class OrderFeeTotal:
    amount_e18: str = "0"
    is_rebate: bool = False
    qty: _Quantity | None = None

  @_dataclass
  class OrderLineage:
    id: str = ""
    generation: int = 0

  @_dataclass
  class OrderOrigin:
    scope: str = ""
    trigger_type: str = ""
    trigger_id: str = ""
    parent_order_id: str = ""
    child_seq: int = 0

  @_dataclass
  class AttachedRiskLegState:
    status: str = ""
    armed_ts_ns: str = ""
    terminal_ts_ns: str = ""
    trigger_id: str = ""
    child_order_id: str = ""

  @_dataclass
  class RiskLeg:
    trigger_price: _Price | None = None
    trigger_price_source: str = ""
    order_type: str = ""
    limit_price: _Price | None = None
    state: AttachedRiskLegState | None = None

  @_dataclass
  class TrailingStop:
    distance_ticks: int = 0
    distance_bps: int = 0
    max_slippage_ticks: int = 0
    max_slippage_bps: int = 0
    activation_price: _Price | None = None
    limit_price: _Price | None = None
    trigger_price_source: str = ""
    order_type: str = ""
    state: AttachedRiskLegState | None = None

  @_dataclass
  class AttachedRisk:
    take_profit: RiskLeg | None = None
    stop_loss: RiskLeg | None = None
    trailing_stop: TrailingStop | None = None
    oco: bool = False

  @_dataclass
  class Order:
    """The SDK's ``Order`` fields; its quantities and prices are bound to ``market``."""

    order_id: str
    symbol_id: int | None = None
    client_order_id: str = ""
    side: str | None = None
    status: str = ""
    order_type: str | None = None
    tif: str | None = None
    orig_qty: _Quantity | None = None
    cum_qty: _Quantity | None = None
    inherited_cum_qty: _Quantity | None = None
    leaves_qty: _Quantity | None = None
    display_qty: _Quantity | None = None
    hidden_qty: _Quantity | None = None
    price: _Price | None = None
    avg_px: _Price | None = None
    created_ts_ns: str = ""
    terminal_ts_ns: str = ""
    version: int = 0
    post_only: bool = False
    fee_asset: str | None = None
    self_trade_prevention_mode: str | None = None
    submitted_max_quote_debit_scaled: str = ""
    submitted_quote_proceeds_scaled: str = ""
    attached_risk: AttachedRisk | None = None
    lineage: OrderLineage | None = None
    origin: OrderOrigin | None = None
    market_client_ref_price: _Price | None = None
    market_max_slippage: _Price | None = None
    market_max_slippage_bps: int = 0
    expire_at: str | None = None
    batch_request_id: str = ""
    reject_reason: str | None = None
    cancel_reason: str | None = None
    avg_price: _Decimal | None = None
    cum_notional_scaled: str = "0"
    fee_total: OrderFeeTotal | None = None
    quote_quantity_scale: int | None = None

  @_dataclass
  class TriggerStopDetails:
    trigger_price: _Price | None = None
    trigger_price_source: str = ""
    trigger_direction: str = ""

  @_dataclass
  class TriggerTrailingDetails:
    trigger_price: _Price | None = None
    trailing_distance: _Price | None = None
    trailing_distance_bps: int = 0
    activation_price: _Price | None = None
    peak_price: _Price | None = None
    trough_price: _Price | None = None
    max_slippage: _Price | None = None
    max_slippage_bps: int = 0
    trigger_price_source: str = ""
    trigger_direction: str = ""

  @_dataclass
  class TriggerTwapDetails:
    twap_duration_ms: int = 0
    twap_slice_interval_ms: int = 0
    slice_idx: int = 0
    slice_count: int = 0
    executed_qty: _Quantity | None = None

  @_dataclass
  class TriggerLadderDetails:
    ladder_price_min: _Price | None = None
    ladder_price_max: _Price | None = None
    ladder_levels: int = 0
    ladder_distribution: str = ""
    executed_levels: int = 0
    executed_qty: _Quantity | None = None
    requested_levels: int = 0
    placed_levels: int = 0
    rejected_levels: int = 0
    canceled_levels: int = 0
    outcome: str = ""

  @_dataclass
  class TriggerDetails:
    case: str
    stop: TriggerStopDetails | None = None
    trailing: TriggerTrailingDetails | None = None
    twap: TriggerTwapDetails | None = None
    ladder: TriggerLadderDetails | None = None

  @_dataclass
  class Trigger:
    """The SDK's ``Trigger`` fields; its quantities and prices are bound to ``market``."""

    trigger_id: str = ""
    subaccount_id: str = ""
    symbol_id: int = 0
    symbol: str = ""
    trigger_type: str = ""
    status: str = ""
    parent_order_id: str = ""
    order_list_id: str = ""
    client_list_id: str = ""
    side: str = ""
    order_type: str = ""
    time_in_force: str = ""
    qty: _Quantity | None = None
    limit_price: _Price | None = None
    max_slippage: _Price | None = None
    max_slippage_bps: int = 0
    fee_asset: str = ""
    self_trade_prevention_mode: str = ""
    post_only: bool = False
    trigger_price: _Price | None = None
    trigger_price_source: str = ""
    client_trigger_id: str = ""
    created_at: _datetime | None = None
    updated_at: _datetime | None = None
    armed_at: _datetime | None = None
    completed_at: _datetime | None = None
    details: TriggerDetails | None = None
    cancel_reason: str = ""
    failure_reason: str = ""
    version: int = 0

  def _num(data, key):
    return int(data.get(key, 0))

  def _qty_scaled(value, field):
    # The SDK's refusal of a negative quantity, naming the field.
    scaled = int(value)
    if scaled < 0:
      raise ValueError(f"{field}: negative quantity {scaled}")
    return scaled

  def _id(value):
    # The SDK's public ID, and "0" for 0.
    value = _parse_id(int(value), "id")
    return _encode_id(value) if value else "0"

  def _id_if_set(data, key):
    return _id(data[key]) if key in data else ""

  def _id_or_empty(data, key):
    return _id(data[key]) if _num(data, key) else ""

  def _ts_ns(data, key):
    value = _num(data, key)
    return str(value) if value else ""

  def _u128(data):
    return int(data.get("hi", 0)) * 18446744073709551616 + int(data.get("lo", 0))

  def _label(value):
    # An enum as the SDK names it: lower case, without its prefix; a number
    # (a value newer than the contract this file knows) as its decimal.
    if isinstance(value, int):
      return str(value) if value else ""
    if value.endswith("UNSPECIFIED"):
      return ""
    for prefix in _PREFIXES:
      if value.startswith(prefix):
        return value[len(prefix) :].lower()
    return value.lower()

  def _or_none(value):
    return _label(value) or None

  def _code(value, prefix, unknown):
    if not value or value == prefix + "UNSPECIFIED":
      return None
    if isinstance(value, int):
      return f"{unknown}({value})"
    return (value[len(prefix) :] if value.startswith(prefix) else value).lower()

  def _source(data):
    name = _label(data.get("triggerPriceSource", 0))
    return name[:-6] if name.endswith("_price") else name

  def _price(data, key, symbol, positive=False):
    ticks = _num(data, key)
    if ticks > 0 if positive else ticks:
      return _Price.from_ticks(ticks, symbol=symbol)
    return None

  def _time(text):
    # (the second as RFC 3339 text, nanoseconds), as proto-JSON writes a Timestamp.
    if not isinstance(text, str) or not text.endswith("Z"):
      raise ValueError(f"timestamp must be an RFC 3339 UTC string, not {text!r}")
    base, _, fraction = text[:-1].partition(".")
    return base, int((fraction + "000000000")[:9])

  def _datetime_of(data, key):
    if key not in data:
      return None
    base, nanos = _time(data[key])
    if base == _EPOCH and not nanos:
      return None
    return _datetime.fromisoformat(base + "+00:00") + _timedelta(microseconds=nanos // 1000)

  def _bind(data, market, kind):
    # The market the values bind to: None without one, and for a message that names no pair.
    if not isinstance(data, dict):
      raise ValueError(f"{kind} must be a proto-JSON dict, not {type(data).__name__}")
    symbol_id = _num(data, "symbolId")
    spec = None if market is None else _market(market)
    if spec is None or not symbol_id:
      return None
    if spec.symbol_id != symbol_id:
      raise ValueError(f"{kind} symbol_id {symbol_id} is not the market's symbol_id {spec.symbol_id}")
    return spec

  def _leg_state(data):
    status = data.get("status", 0)
    if status == "NOT_CONFIGURED":
      return None
    return AttachedRiskLegState(
      _label(status),
      _ts_ns(data, "armedTsNs"),
      _ts_ns(data, "terminalTsNs"),
      _id_if_set(data, "triggerId"),
      _id_if_set(data, "childOrderId"),
    )

  def _risk_leg(data, symbol):
    if data is None:
      return None
    state = _leg_state(data["state"]) if "state" in data else None
    policy = data.get("policy", {})
    if not _num(policy, "triggerPriceTicks"):
      return RiskLeg(state=state) if state is not None else None
    child = policy.get("child", {})
    order_type = "limit" if "limitGtc" in child else "market" if "marketIoc" in child else ""
    return RiskLeg(
      _price(policy, "triggerPriceTicks", symbol),
      _source(policy),
      order_type,
      _price(child.get("limitGtc", {}), "priceTicks", symbol),
      state,
    )

  def _trailing_stop(data, symbol):
    if data is None:
      return None
    state = _leg_state(data["state"]) if "state" in data else None
    policy = data.get("policy", {})
    ticks = _num(policy, "trailingDistanceTicks")
    bps = _num(policy, "trailingDistanceBps")
    if ticks <= 0 and bps <= 0:
      return TrailingStop(state=state) if state is not None else None
    return TrailingStop(
      ticks,
      bps,
      max(_num(policy, "maxSlippageTicks"), 0),
      max(_num(policy, "maxSlippageBps"), 0),
      _price(policy, "activationPriceTicks", symbol),
      _price(policy, "limitPriceTicks", symbol, True),
      _source(policy),
      "",
      state,
    )

  def _attached_risk(data, symbol):
    # The SDK's order: a refusal names the first bad value it reads.
    take_profit = _risk_leg(data.get("takeProfit"), symbol)
    trailing_stop = _trailing_stop(data.get("trailingStop"), symbol)
    stop_loss = _risk_leg(data.get("stopLoss"), symbol)
    if take_profit is None and stop_loss is None and trailing_stop is None:
      return None
    return AttachedRisk(take_profit, stop_loss, trailing_stop, bool(data.get("oco", False)))

  def _origin(data):
    origin = OrderOrigin(
      _label(data.get("scope", 0)),
      _label(data.get("triggerType", 0)),
      _id_if_set(data, "triggerId"),
      _id_if_set(data, "parentOrderId"),
      _num(data, "childSeq"),
    )
    return None if origin == OrderOrigin() else origin

  def _order(data, market=None):
    """The SDK's ``Order`` of a proto-JSON ``orders.v1.Order``.

    ``market`` is the order's pair (a ``GetSpotConfig`` pair dict or ``polyester.market(pair)``),
    to bind its prices and quantities to; ``None`` leaves them unbound, as the SDK without
    its catalogs. An order that names no pair is never bound.
    """
    spec = _bind(data, market, "order")
    symbol = spec.symbol if spec else None
    scale = spec.base_quantity_scale if spec else None
    symbol_id = _num(data, "symbolId")

    def qty(value, field):
      scaled = _qty_scaled(value, field)
      return _Quantity.from_scaled(scaled, scale=scale, symbol=symbol, symbol_id=symbol_id or None)

    def quantity(key, field):
      return qty(data.get(key, 0), field)

    attached = _attached_risk(data["attachedRisk"], symbol) if "attachedRisk" in data else None
    lineage = data.get("lineage")
    if lineage is not None and (_num(lineage, "id") or _num(lineage, "generation")):
      lineage = OrderLineage(_id(lineage.get("id", 0)), _num(lineage, "generation"))
    else:
      lineage = None
    expire_at = None
    if "expireAt" in data:
      base, nanos = _time(data["expireAt"])
      if base != _EPOCH or nanos:
        expire_at = base + (f".{nanos:09d}Z" if nanos else "Z")

    def fee(total):
      amount = str(_u128(total["amountE18"])) if "amountE18" in total else "0"
      return OrderFeeTotal(
        amount, bool(total.get("isRebate", False)), qty(total.get("qtyScaled", 0), "OrderFeeTotal.qty_scaled")
      )

    # Read in the SDK's order, so a refusal names the same first bad value.
    return Order(
      order_id=_id(data.get("orderId", 0)),
      symbol_id=symbol_id or None,
      client_order_id=data.get("clientOrderId", ""),
      side=_or_none(data.get("side", 0)),
      status=_label(data.get("status", 0)),
      order_type=_or_none(data.get("orderType", 0)),
      tif=_or_none(data.get("timeInForce", 0)),
      orig_qty=quantity("origQtyScaled", "Order.orig_qty_scaled"),
      cum_qty=quantity("cumQtyScaled", "Order.cum_qty_scaled"),
      inherited_cum_qty=quantity("inheritedCumQtyScaled", "Order.inherited_cum_qty_scaled"),
      leaves_qty=quantity("leavesQtyScaled", "Order.leaves_qty_scaled"),
      display_qty=quantity("displayQtyScaled", "Order.display_qty_scaled"),
      hidden_qty=quantity("hiddenQtyScaled", "Order.hidden_qty_scaled"),
      price=_price(data, "priceTicks", symbol),
      avg_px=_price(data, "avgPriceTicks", symbol),
      created_ts_ns=_ts_ns(data, "createdTsNs"),
      terminal_ts_ns=_ts_ns(data, "terminalTsNs"),
      version=_num(data, "version"),
      post_only=bool(data.get("postOnly", False)),
      fee_asset=_or_none(data.get("feeAsset", 0)),
      self_trade_prevention_mode=_or_none(data.get("selfTradePreventionMode", 0)),
      submitted_max_quote_debit_scaled=str(_num(data, "submittedMaxQuoteDebitScaled"))
      if "submittedMaxQuoteDebitScaled" in data
      else "",
      submitted_quote_proceeds_scaled=str(_num(data, "submittedQuoteProceedsScaled"))
      if "submittedQuoteProceedsScaled" in data
      else "",
      attached_risk=attached,
      lineage=lineage,
      origin=_origin(data["origin"]) if "origin" in data else None,
      market_client_ref_price=_price(data, "marketClientRefPriceTicks", symbol, True),
      market_max_slippage=_price(data, "marketMaxSlippageTicks", symbol, True),
      market_max_slippage_bps=_num(data, "marketMaxSlippageBps"),
      expire_at=expire_at,
      batch_request_id=_id_or_empty(data, "batchRequestId"),
      reject_reason=_code(data.get("rejectReason", 0), "ERROR_CODE_", "UNKNOWN_ERROR_CODE"),
      cancel_reason=_code(data.get("cancelReason", 0), "CANCEL_REASON_", "UNKNOWN_CANCEL_REASON"),
      avg_price=_Decimal(_format_scaled(_u128(data["avgPriceE18"]), 18)) if "avgPriceE18" in data else None,
      cum_notional_scaled=str(_u128(data["cumNotional"])) if "cumNotional" in data else "0",
      fee_total=fee(data["feeTotal"]) if "feeTotal" in data else None,
      quote_quantity_scale=spec.quote_quantity_scale if spec else None,
    )

  def _executed(data, scale, symbol, symbol_id, field):
    scaled = _num(data, "executedQtyScaled")
    if not scaled:
      return None
    return _Quantity.from_scaled(_qty_scaled(scaled, field), scale=scale, symbol=symbol, symbol_id=symbol_id)

  def _details(data, scale, symbol, symbol_id):
    if "stop" in data:
      stop = data["stop"]
      return TriggerDetails(
        "stop",
        stop=TriggerStopDetails(
          _price(stop, "triggerPriceTicks", symbol), _source(stop), _label(stop.get("triggerDirection", 0))
        ),
      )
    if "trailing" in data:
      trailing = data["trailing"]
      return TriggerDetails(
        "trailing",
        trailing=TriggerTrailingDetails(
          _price(trailing, "triggerPriceTicks", symbol),
          _price(trailing, "trailingDistanceTicks", symbol),
          _num(trailing, "trailingDistanceBps"),
          _price(trailing, "activationPriceTicks", symbol),
          _price(trailing, "peakPriceTicks", symbol),
          _price(trailing, "troughPriceTicks", symbol),
          _price(trailing, "maxSlippageTicks", symbol),
          _num(trailing, "maxSlippageBps"),
          _source(trailing),
          _label(trailing.get("triggerDirection", 0)),
        ),
      )
    if "twapState" in data:
      twap = data["twapState"]
      return TriggerDetails(
        "twap",
        twap=TriggerTwapDetails(
          _num(twap, "twapDurationMs"),
          _num(twap, "twapSliceIntervalMs"),
          _num(twap, "sliceIdx"),
          _num(twap, "sliceCount"),
          _executed(twap, scale, symbol, symbol_id, "Trigger.twap_state.executed_qty_scaled"),
        ),
      )
    if "ladderState" in data:
      ladder = data["ladderState"]
      return TriggerDetails(
        "ladder",
        ladder=TriggerLadderDetails(
          _price(ladder, "ladderPriceMinTicks", symbol),
          _price(ladder, "ladderPriceMaxTicks", symbol),
          _num(ladder, "ladderLevels"),
          _label(ladder.get("ladderDistribution", 0)),
          _num(ladder, "executedLevels"),
          _executed(ladder, scale, symbol, symbol_id, "Trigger.ladder_state.executed_qty_scaled"),
          _num(ladder, "requestedLevels"),
          _num(ladder, "placedLevels"),
          _num(ladder, "rejectedLevels"),
          _num(ladder, "canceledLevels"),
          _label(ladder.get("outcome", 0)),
        ),
      )
    return None

  def _config(data, symbol):
    # The SDK's projection of the trigger's configuration onto its top-level fields.
    config = {}

    def cap(execution):
      if "maxSlippageTicks" in execution:
        config["max_slippage"] = _price(execution, "maxSlippageTicks", symbol)
      elif "maxSlippageBps" in execution:
        config["max_slippage_bps"] = _num(execution, "maxSlippageBps")

    def child(kind, order_type, tif, execution):
      config.update(trigger_type=kind, order_type=order_type, time_in_force=tif)
      if execution is not None:
        config["limit_price"] = _price(execution, "priceTicks", symbol)

    conditional = data.get("stopLoss", data.get("takeProfit"))
    if conditional is not None:
      config.update(
        trigger_type="stop_loss" if "stopLoss" in data else "take_profit",
        side=_label(conditional.get("side", 0)),
        trigger_price=_price(conditional, "triggerPriceTicks", symbol),
        trigger_price_source=_source(conditional),
      )
      execution = conditional.get("child", {})
      if "marketIoc" in execution:
        config.update(order_type="market", time_in_force="ioc")
        cap(execution["marketIoc"])
      elif "limitGtc" in execution:
        config.update(order_type="limit", time_in_force="gtc")
        config["post_only"] = bool(execution["limitGtc"].get("postOnly", False))
        config["limit_price"] = _price(execution["limitGtc"], "priceTicks", symbol)
      elif "limitIoc" in execution:
        config.update(order_type="limit", time_in_force="ioc")
        config["limit_price"] = _price(execution["limitIoc"], "priceTicks", symbol)
      elif "limitFok" in execution:
        config.update(order_type="limit", time_in_force="fok")
        config["limit_price"] = _price(execution["limitFok"], "priceTicks", symbol)
    elif "trailingStop" in data:
      trailing = data["trailingStop"]
      limit = _price(trailing, "limitPriceTicks", symbol)
      config.update(
        trigger_type="trailing_stop",
        side=_label(trailing.get("side", 0)),
        trigger_price_source=_source(trailing),
        time_in_force="ioc",
        order_type="market" if limit is None else "limit",
        limit_price=limit,
      )
      cap(trailing)
    elif "trailing" in data:
      config["max_slippage"] = _price(data["trailing"], "maxSlippageTicks", symbol)
      config["max_slippage_bps"] = _num(data["trailing"], "maxSlippageBps")
    elif "twap" in data:
      twap = data["twap"]
      config.update(trigger_type="twap", side=_label(twap.get("side", 0)))
      if "limitGtc" in twap:
        child("twap", "limit", "gtc", twap["limitGtc"])
      else:
        child("twap", "market", "ioc", None)
        if "marketIoc" in twap:
          cap(twap["marketIoc"])
    elif "ladder" in data:
      ladder = data["ladder"]
      child("ladder", "limit", "gtc", None)
      config.update(side=_label(ladder.get("side", 0)), post_only=bool(ladder.get("postOnly", False)))
    return config

  def _trigger(data, market=None):
    """The SDK's ``Trigger`` of a proto-JSON ``triggers.v1.Trigger``.

    ``market`` binds its prices and quantities, as for ``order``; ``symbol`` is the market's name.
    """
    spec = _bind(data, market, "trigger")
    name = spec.symbol if spec else ""
    symbol = name or None
    scale = spec.base_quantity_scale if spec else None
    symbol_id = _num(data, "symbolId")
    details = _details(data, scale, symbol, symbol_id)
    config = _config(data, symbol)
    if config.get("trigger_price") is None and details is not None and details.stop is not None:
      config["trigger_price"] = details.stop.trigger_price
    reason = {}
    for field, key in (("cancel_reason", "cancelReason"), ("failure_reason", "failureReason")):
      if key in data:
        reason[field] = _label(data[key])
    return Trigger(
      trigger_id=_id(data.get("triggerId", 0)),
      subaccount_id=_id_or_empty(data, "subaccountId"),
      symbol_id=symbol_id,
      symbol=name,
      status=_label(data.get("status", 0)),
      parent_order_id=_id_or_empty(data, "parentOrderId"),
      order_list_id=_id_or_empty(data, "orderListId"),
      client_list_id=data.get("clientListId", ""),
      qty=_Quantity.from_scaled(
        _qty_scaled(_num(data, "qtyScaled"), "Trigger.qty_scaled"), scale=scale, symbol=symbol, symbol_id=symbol_id
      ),
      fee_asset=_label(data.get("feeAsset", 0)),
      self_trade_prevention_mode=_label(data.get("selfTradePreventionMode", 0)),
      client_trigger_id=data.get("clientTriggerId", ""),
      created_at=_datetime_of(data, "createdAt"),
      updated_at=_datetime_of(data, "updatedAt"),
      armed_at=_datetime_of(data, "armedAt"),
      completed_at=_datetime_of(data, "completedAt"),
      details=details,
      version=_num(data, "version"),
      **config,
      **reason,
    )

  _types = (
    Order,
    OrderFeeTotal,
    OrderLineage,
    OrderOrigin,
    AttachedRisk,
    AttachedRiskLegState,
    RiskLeg,
    TrailingStop,
    Trigger,
    TriggerDetails,
    TriggerStopDetails,
    TriggerTrailingDetails,
    TriggerTwapDetails,
    TriggerLadderDetails,
  )

  class _Namespace:
    """``order`` and ``trigger`` decode; the model classes, as the SDK names them."""

    order = _order
    trigger = _trigger
    Order = _types[0]
    OrderFeeTotal = _types[1]
    OrderLineage = _types[2]
    OrderOrigin = _types[3]
    AttachedRisk = _types[4]
    AttachedRiskLegState = _types[5]
    RiskLeg = _types[6]
    TrailingStop = _types[7]
    Trigger = _types[8]
    TriggerDetails = _types[9]
    TriggerStopDetails = _types[10]
    TriggerTrailingDetails = _types[11]
    TriggerTwapDetails = _types[12]
    TriggerLadderDetails = _types[13]

  return _Namespace


polyester_models = polyester_models()
