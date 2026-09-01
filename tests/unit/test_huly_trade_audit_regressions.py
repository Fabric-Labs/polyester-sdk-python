import pytest

from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.orders import batch_create_orders_to_proto, risk_policy_from_dict
from polyester.codecs.scalars import format_id
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.orderbook.local_book import apply_delta


def _batch_item(client_order_id: str | None = None) -> dict[str, object]:
    item: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "buy",
        "order_type": "limit",
        "qty": "0.1",
        "price": "50000",
    }
    if client_order_id is not None:
        item["client_order_id"] = client_order_id
    return item


def _create_trailing(**overrides: int):
    kwargs = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "trailing_stop",
        "side": "sell",
        "qty": "0.1",
        "quantity_scale": 8,
        "trailing_distance_bps": 100,
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)


def test_poly_4684_attached_trailing_slippage_bps_is_capped() -> None:
    risk_policy_from_dict(
        {"trailing_stop": {"trailing_distance_bps": 100, "max_slippage_bps": 10_000}}
    )
    with pytest.raises(PolyesterValidationError, match="max_slippage_bps.*1.*10000"):
        risk_policy_from_dict(
            {"trailing_stop": {"trailing_distance_bps": 100, "max_slippage_bps": 10_001}}
        )


def test_poly_4684_standalone_trailing_slippage_cap_is_retained() -> None:
    _create_trailing(max_slippage_bps=10_000)
    with pytest.raises(PolyesterValidationError, match="max_slippage_bps.*1.*10000"):
        _create_trailing(max_slippage_bps=10_001)
    with pytest.raises(PolyesterValidationError, match="max_slippage_bps.*1.*10000"):
        modify_trigger_to_proto(trigger_id="1", symbol_id=1, max_slippage_bps=10_001)
    assert (
        modify_trigger_to_proto(trigger_id="1", symbol_id=1, max_slippage_bps=0).max_slippage_bps
        == 0
    )


def test_poly_4686_batch_create_rejects_duplicate_nonempty_client_order_ids() -> None:
    with pytest.raises(PolyesterValidationError, match="duplicate client_order_id.*duplicate"):
        batch_create_orders_to_proto(
            items=[_batch_item("duplicate"), _batch_item("duplicate")],
            quantity_scale=8,
        )


def test_poly_4686_batch_create_allows_empty_or_omitted_client_order_ids() -> None:
    proto = batch_create_orders_to_proto(
        items=[_batch_item(), _batch_item(""), _batch_item()],
        quantity_scale=8,
    )
    assert [item.client_order_id for item in proto.items] == ["", "", ""]


def test_poly_4687_attached_risk_preserves_fired_leg_runtime_state_and_ids() -> None:
    # The current orders_read contract names the successfully fired terminal state COMPLETED.
    state = orders_read_pb2.AttachedRiskLegState(
        status=orders_read_pb2.AttachedRiskLegState.COMPLETED,
        armed_ts_ns=1_700_000_000_000_000_001,
        terminal_ts_ns=1_700_000_000_000_000_999,
        trigger_id=41,
        child_order_id=42,
    )
    msg = orders_read_pb2.Order(
        order_id=1,
        symbol_id=1,
        attached_risk=orders_read_pb2.AttachedRisk(
            take_profit=orders_read_pb2.AttachedRiskTakeProfit(
                policy=orders_pb2.TakeProfitPolicy(
                    trigger_price_ticks=60_000_000_000,
                    child=orders_pb2.RiskExecution(market_ioc=orders_pb2.RiskMarketIoc()),
                ),
                state=state,
            )
        ),
    )

    order = order_from_proto(msg)

    assert order.attached_risk is not None
    assert order.attached_risk.take_profit is not None
    assert order.attached_risk.take_profit.state.status == "completed"
    assert order.attached_risk.take_profit.state.armed_ts_ns == "1700000000000000001"
    assert order.attached_risk.take_profit.state.terminal_ts_ns == "1700000000000000999"
    assert order.attached_risk.take_profit.state.trigger_id == format_id(41)
    assert order.attached_risk.take_profit.state.child_order_id == format_id(42)


def test_poly_4687_malformed_response_preserves_stop_loss_and_trailing_stop() -> None:
    msg = orders_read_pb2.Order(
        order_id=1,
        symbol_id=1,
        attached_risk=orders_read_pb2.AttachedRisk(
            stop_loss=orders_read_pb2.AttachedRiskStopLoss(
                policy=orders_pb2.StopLossPolicy(
                    trigger_price_ticks=49_000_000_000,
                    child=orders_pb2.RiskExecution(market_ioc=orders_pb2.RiskMarketIoc()),
                ),
                state=orders_read_pb2.AttachedRiskLegState(
                    status=orders_read_pb2.AttachedRiskLegState.ARMED,
                    armed_ts_ns=101,
                    trigger_id=43,
                ),
            ),
            trailing_stop=orders_read_pb2.AttachedRiskTrailingStop(
                policy=orders_pb2.TrailingStopPolicy(trailing_distance_bps=100),
                state=orders_read_pb2.AttachedRiskLegState(
                    status=orders_read_pb2.AttachedRiskLegState.RUNNING,
                    armed_ts_ns=102,
                    trigger_id=44,
                    child_order_id=45,
                ),
            ),
        ),
    )

    order = order_from_proto(msg)

    assert order.attached_risk is not None
    assert order.attached_risk.stop_loss is not None
    assert order.attached_risk.trailing_stop is not None
    assert order.attached_risk.stop_loss.state is not None
    assert order.attached_risk.stop_loss.state.status == "armed"
    assert order.attached_risk.stop_loss.state.trigger_id == format_id(43)
    assert order.attached_risk.trailing_stop.state is not None
    assert order.attached_risk.trailing_stop.state.status == "running"
    assert order.attached_risk.trailing_stop.state.trigger_id == format_id(44)
    assert order.attached_risk.trailing_stop.state.child_order_id == format_id(45)


def _state_only_leg(status: int, *, seed: int) -> orders_read_pb2.AttachedRiskLegState:
    return orders_read_pb2.AttachedRiskLegState(
        status=status,
        armed_ts_ns=1_700_000_000_000_000_000 + seed,
        terminal_ts_ns=1_700_000_000_000_001_000 + seed,
        trigger_id=100 + seed,
        child_order_id=200 + seed,
    )


def test_poly_4687_state_only_take_profit_is_preserved_without_fabricated_policy() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=1,
            symbol_id=1,
            attached_risk=orders_read_pb2.AttachedRisk(
                take_profit=orders_read_pb2.AttachedRiskTakeProfit(
                    state=_state_only_leg(
                        orders_read_pb2.AttachedRiskLegState.COMPLETED,
                        seed=1,
                    )
                )
            ),
        )
    )

    assert order.attached_risk is not None
    assert order.attached_risk.take_profit is not None
    assert order.attached_risk.take_profit.trigger_price is None
    assert order.attached_risk.take_profit.order_type == ""
    assert order.attached_risk.take_profit.limit_price is None
    state = order.attached_risk.take_profit.state
    assert state is not None
    assert state.status == "completed"
    assert state.armed_ts_ns == "1700000000000000001"
    assert state.terminal_ts_ns == "1700000000000001001"
    assert state.trigger_id == format_id(101)
    assert state.child_order_id == format_id(201)


def test_poly_4687_state_only_stop_loss_is_preserved_without_fabricated_policy() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=1,
            symbol_id=1,
            attached_risk=orders_read_pb2.AttachedRisk(
                stop_loss=orders_read_pb2.AttachedRiskStopLoss(
                    state=_state_only_leg(
                        orders_read_pb2.AttachedRiskLegState.FAILED,
                        seed=2,
                    )
                )
            ),
        )
    )

    assert order.attached_risk is not None
    assert order.attached_risk.stop_loss is not None
    assert order.attached_risk.stop_loss.trigger_price is None
    assert order.attached_risk.stop_loss.order_type == ""
    assert order.attached_risk.stop_loss.limit_price is None
    state = order.attached_risk.stop_loss.state
    assert state is not None
    assert state.status == "failed"
    assert state.armed_ts_ns == "1700000000000000002"
    assert state.terminal_ts_ns == "1700000000000001002"
    assert state.trigger_id == format_id(102)
    assert state.child_order_id == format_id(202)


def test_poly_4687_state_only_trailing_is_preserved_with_stop_loss() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=1,
            symbol_id=1,
            attached_risk=orders_read_pb2.AttachedRisk(
                stop_loss=orders_read_pb2.AttachedRiskStopLoss(
                    state=_state_only_leg(
                        orders_read_pb2.AttachedRiskLegState.ARMED,
                        seed=3,
                    )
                ),
                trailing_stop=orders_read_pb2.AttachedRiskTrailingStop(
                    state=_state_only_leg(
                        orders_read_pb2.AttachedRiskLegState.RUNNING,
                        seed=4,
                    )
                ),
            ),
        )
    )

    assert order.attached_risk is not None
    assert order.attached_risk.stop_loss is not None
    assert order.attached_risk.trailing_stop is not None
    assert order.attached_risk.trailing_stop.distance_ticks == 0
    assert order.attached_risk.trailing_stop.distance_bps == 0
    assert order.attached_risk.trailing_stop.activation_price is None
    state = order.attached_risk.trailing_stop.state
    assert state is not None
    assert state.status == "running"
    assert state.armed_ts_ns == "1700000000000000004"
    assert state.terminal_ts_ns == "1700000000000001004"
    assert state.trigger_id == format_id(104)
    assert state.child_order_id == format_id(204)


def test_poly_4688_stale_reset_does_not_rewind_newer_snapshot() -> None:
    bids = {100: 5}
    asks = {200: 3}

    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=100,
        delta=OrderBookDeltaUpdate(
            reset=True,
            book_seq_start="95",
            book_seq_end="96",
            bids=[("50", "1")],
        ),
    )

    assert refresh is False
    assert seq == 100
    assert bids == {100: 5}
    assert asks == {200: 3}


@pytest.mark.parametrize(
    ("seq_start", "seq_end", "expected_seq"),
    [("100", "100", 100), ("99", "101", 101), ("101", "102", 102)],
)
def test_poly_4688_reset_sequence_boundary_semantics(
    seq_start: str, seq_end: str, expected_seq: int
) -> None:
    bids = {100: 5}
    asks = {200: 3}

    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=100,
        delta=OrderBookDeltaUpdate(
            reset=True,
            book_seq_start=seq_start,
            book_seq_end=seq_end,
            bids=[("50", "1")],
        ),
    )

    assert refresh is False
    assert seq == expected_seq
    if expected_seq == 100:
        assert bids == {100: 5}
        assert asks == {200: 3}
    else:
        assert bids == {50: 1}
        assert asks == {}


@pytest.mark.parametrize("value", [0, 10_001, 10**12])
def test_poly_4689_attached_trailing_distance_bps_validates_before_proto(value: int) -> None:
    with pytest.raises(PolyesterValidationError, match="trailing_distance_bps.*1.*10000"):
        risk_policy_from_dict({"trailing_stop": {"trailing_distance_bps": value}})


@pytest.mark.parametrize("value", [0, 10_001, 10**12])
def test_poly_4689_standalone_create_distance_bps_is_capped(value: int) -> None:
    with pytest.raises(PolyesterValidationError, match="trailing_distance_bps.*1.*10000"):
        _create_trailing(trailing_distance_bps=value)


@pytest.mark.parametrize("value", [10_001, 10**12])
def test_poly_4689_standalone_modify_distance_bps_is_capped(value: int) -> None:
    with pytest.raises(PolyesterValidationError, match="trailing_distance_bps.*1.*10000"):
        modify_trigger_to_proto(trigger_id="1", symbol_id=1, trailing_distance_bps=value)
    assert (
        modify_trigger_to_proto(
            trigger_id="1", symbol_id=1, trailing_distance_bps=0
        ).trailing_distance_bps
        == 0
    )


@pytest.mark.parametrize(
    ("price_min", "price_max"),
    [("52000", "48000"), ("50000", "50000")],
)
def test_poly_4695_ladder_requires_strictly_increasing_resolved_prices(
    price_min: str, price_max: str
) -> None:
    with pytest.raises(PolyesterValidationError, match="ladder_price_min.*less than.*max"):
        create_trigger_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            trigger_type="ladder",
            side="buy",
            qty="1",
            quantity_scale=8,
            ladder_price_min=price_min,
            ladder_price_max=price_max,
            ladder_levels=5,
        )
