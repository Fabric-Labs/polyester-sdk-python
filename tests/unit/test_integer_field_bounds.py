"""Caller-supplied integers are checked before anything is sent.

Every value bound for a protobuf integer field is held to the field's type
(so the protobuf assignment can never raise), and the contract's own range
from its ``buf.validate`` rules is checked before sending. Each failure is a
``PolyesterValidationError``, and nothing reaches the transport.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.guard_signer import protected_action_args_to_proto
from polyester.codecs.request_rules import check_request_ranges
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.codecs.withdraw import trading_withdraw_payload_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import OrderId
from polyester.services.address_book import AsyncAddressBookService
from polyester.services.balances import AsyncBalancesService
from polyester.services.chain_analytics import AsyncChainAnalyticsService
from polyester.services.deposit import AsyncDepositService
from polyester.services.fees import AsyncFeeService
from polyester.services.internal_transfers import AsyncInternalTransfersService
from polyester.services.layout import AsyncLayoutService
from polyester.services.market_data import AsyncMarketDataService
from polyester.services.orders import AsyncOrdersService
from polyester.services.polychart import AsyncPolychartService
from polyester.services.trades import AsyncTradesService
from polyester.services.triggers import AsyncTriggersService
from polyester.services.whiteboard import AsyncWhiteboardService
from polyester.services.withdraw import AsyncWithdrawService

U32_OVER = 2**32
U64_OVER = 2**64
I64_OVER = 2**63


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return catalogs


def _assert_not_sent(transport: MagicMock) -> None:
    transport.create_auth_client.assert_not_called()
    transport.create_public_client.assert_not_called()


Call = Callable[[MagicMock], Awaitable[Any]]

SERVICE_CASES: dict[str, Call] = {
    # Trigger strategy integers.
    "twap_duration_ms_int64": lambda t: AsyncTriggersService(t, _catalogs(), None).create(
        symbol="BTC-USDT",
        trigger_type="twap",
        side="sell",
        qty="0.01",
        twap_duration_ms=I64_OVER,
        twap_slice_interval_ms=10_000,
    ),
    "twap_slice_interval_ms_int64": lambda t: AsyncTriggersService(t, _catalogs(), None).create(
        symbol="BTC-USDT",
        trigger_type="twap",
        side="sell",
        qty="0.01",
        twap_duration_ms=60_000,
        twap_slice_interval_ms=I64_OVER,
    ),
    "ladder_levels_int32": lambda t: AsyncTriggersService(t, _catalogs(), None).create(
        symbol="BTC-USDT",
        trigger_type="ladder",
        side="sell",
        qty="0.01",
        ladder_price_min="80000",
        ladder_price_max="90000",
        ladder_levels=2**31,
    ),
    "ladder_levels_contract_2_to_100": lambda t: AsyncTriggersService(t, _catalogs(), None).create(
        symbol="BTC-USDT",
        trigger_type="ladder",
        side="sell",
        qty="0.01",
        ladder_price_min="80000",
        ladder_price_max="90000",
        ladder_levels=101,
    ),
    # Orders.
    "cancel_all_after_timeout_sec_uint32": lambda t: AsyncOrdersService(
        t, _catalogs(), None
    ).cancel_all_after(timeout_sec=U32_OVER),
    "cancel_all_after_negative_timeout": lambda t: AsyncOrdersService(
        t, _catalogs(), None
    ).cancel_all_after(timeout_sec=-1),
    "cancel_symbol_id_uint32": lambda t: AsyncOrdersService(t, _catalogs(), None).cancel(
        key=OrderId("5"), symbol_id=U32_OVER
    ),
    "list_history_symbol_id_uint32": lambda t: AsyncOrdersService(
        t, _catalogs(), None
    ).list_history(symbol_id=U32_OVER),
    "list_open_limit_uint32": lambda t: AsyncOrdersService(t, _catalogs(), None).list_open(
        limit=U32_OVER
    ),
    "list_open_limit_contract_1000": lambda t: AsyncOrdersService(
        t, _catalogs(), None
    ).list_open(limit=1_001),
    # Trades and market data.
    "user_trades_through_generation_uint32": lambda t: AsyncTradesService(
        t, _catalogs(), None
    ).list(lineage_id="1", through_generation=U32_OVER),
    "user_trades_after_match_id_uint64": lambda t: AsyncTradesService(
        t, _catalogs(), None
    ).list(symbol_id=1, after_match_id=U64_OVER),
    "user_trades_limit_contract_1000": lambda t: AsyncTradesService(
        t, _catalogs(), None
    ).list(limit=1_001),
    "public_trades_limit_contract_1000": lambda t: AsyncMarketDataService(
        t, _catalogs()
    ).get_trades(symbol="BTC-USDT", limit=1_001),
    "public_trades_symbol_id_uint32": lambda t: AsyncMarketDataService(t, _catalogs()).get_trades(
        symbol_id=U32_OVER
    ),
    # Account services.
    "balance_history_ledger_uint32": lambda t: AsyncBalancesService(t).get_balance_history(
        ledger=U32_OVER
    ),
    "balance_history_account_code_enum": lambda t: AsyncBalancesService(t).get_balance_history(
        account_codes=[2**31]
    ),
    "holds_limit_contract_1000": lambda t: AsyncBalancesService(t).list_holds(limit=1_001),
    "analytics_zipped_asset_id_uint32": lambda t: AsyncChainAnalyticsService(
        t
    ).get_zipped_asset_supply(zipped_asset_id=U32_OVER, range="7d"),
    "analytics_start_ts_sec_fixed32": lambda t: AsyncChainAnalyticsService(
        t
    ).get_unified_asset_balances(asset_id=1, range="7d", start_ts_sec=U32_OVER),
    "deposit_chain_id_uint32": lambda t: AsyncDepositService(t, None).list_addresses(
        chain_id=U32_OVER
    ),
    "fee_symbol_id_uint32": lambda t: AsyncFeeService(t, None).get_spot_fee_rates(
        symbol_id=[U32_OVER]
    ),
    "internal_transfer_asset_id_uint32": lambda t: AsyncInternalTransfersService(
        t, _catalogs(), None
    ).create(
        asset_id=U32_OVER,
        quantity="1",
        idempotency_key="k",
        destination_account_id="2",
    ),
    "address_book_view_revision_uint64": lambda t: AsyncAddressBookService(t, None).get_view(
        minimum_view_revision=U64_OVER
    ),
    "address_book_view_limit_contract_200": lambda t: AsyncAddressBookService(t, None).get_view(
        limit=201
    ),
    "address_book_chain_id_uint32": lambda t: AsyncAddressBookService(t, None).create_entry(
        label="x", address="0xabc", polychain_chain_id=U32_OVER
    ),
    "address_book_expected_revision_uint64": lambda t: AsyncAddressBookService(
        t, None
    ).update_entry(address_book_entry_id="1", expected_revision=U64_OVER, label="x"),
    "withdraw_destination_chain_uint64": lambda t: AsyncWithdrawService(
        t, None
    ).validate_destination(destination_chain_id=U64_OVER, destination_address="0xabc"),
    # Layout, chart and whiteboard.
    "layouts_limit_uint32": lambda t: AsyncLayoutService(t).get_layouts(limit=U32_OVER),
    "layout_template_version_uint32": lambda t: AsyncLayoutService(
        t
    ).get_layout_template_version(owner_id="1", template_id="1", version=U32_OVER),
    "layout_share_expiry_fixed64": lambda t: AsyncLayoutService(t).create_layout_share_link(
        layout_id="1", expires_at_ms=U64_OVER
    ),
    "polychart_engine_symbol_id_uint32": lambda t: AsyncPolychartService(t).get_market_layers(
        engine_symbol_id=U32_OVER
    ),
    "polychart_perms_uint32": lambda t: AsyncPolychartService(t).create_layer_share_link(
        layer={}, perms=U32_OVER
    ),
    "polychart_expected_revision_fixed64": lambda t: AsyncPolychartService(t).delete_layer(
        layer={}, expected_revision=U64_OVER
    ),
    "polychart_mapping_integer_out_of_range": lambda t: AsyncPolychartService(
        t
    ).upsert_layer(layer={"engineSymbolId": U32_OVER}),
    "whiteboard_limit_uint32": lambda t: AsyncWhiteboardService(t).list(limit=U32_OVER),
}


# The field each case must name, so a case can't pass on an unrelated error.
FIELD_NAMED = {
    "twap_duration_ms_int64": "twap_duration_ms must be between",
    "twap_slice_interval_ms_int64": "twap_slice_interval_ms must be between",
    "ladder_levels_int32": "ladder_levels must be between",
    "ladder_levels_contract_2_to_100": "trigger.ladder.levels must be >= 2 and <= 100",
    "cancel_all_after_timeout_sec_uint32": "timeout_sec must be between",
    "cancel_all_after_negative_timeout": "timeout_sec must be between",
    "cancel_symbol_id_uint32": "symbol_id must be between",
    "list_history_symbol_id_uint32": "symbol_id must be between",
    "list_open_limit_uint32": "limit must be between",
    "list_open_limit_contract_1000": "limit must be >= 1 and <= 1000",
    "user_trades_through_generation_uint32": "through_generation must be between",
    "user_trades_after_match_id_uint64": "after_match_id must be between",
    "user_trades_limit_contract_1000": "limit must be >= 1 and <= 1000",
    "public_trades_limit_contract_1000": "limit must be <= 1000",
    "public_trades_symbol_id_uint32": "symbol_id must be between",
    "balance_history_ledger_uint32": "ledger must be between",
    "balance_history_account_code_enum": "account_codes must be between",
    "holds_limit_contract_1000": "limit must be <= 1000",
    "analytics_zipped_asset_id_uint32": "zipped_asset_id must be between",
    "analytics_start_ts_sec_fixed32": "start_ts_sec must be between",
    "deposit_chain_id_uint32": "chain_id must be between",
    "fee_symbol_id_uint32": "symbol_ids must be between",
    "internal_transfer_asset_id_uint32": "asset_id must be between",
    "address_book_view_revision_uint64": "minimum_view_revision must be between",
    "address_book_view_limit_contract_200": "limit must be <= 200",
    "address_book_chain_id_uint32": "polychain_chain_id must be between",
    "address_book_expected_revision_uint64": "expected_revision must be between",
    "withdraw_destination_chain_uint64": "destination_chain_id must be between",
    "layouts_limit_uint32": "limit must be between",
    "layout_template_version_uint32": "version must be between",
    "layout_share_expiry_fixed64": "expires_at_ms must be between",
    "polychart_engine_symbol_id_uint32": "engine_symbol_id must be between",
    "polychart_perms_uint32": "perms must be between",
    "polychart_expected_revision_fixed64": "expected_revision must be between",
    "polychart_mapping_integer_out_of_range": "engineSymbolId",
    "whiteboard_limit_uint32": "limit must be between",
}


def test_every_case_names_its_field() -> None:
    assert FIELD_NAMED.keys() == SERVICE_CASES.keys()


@pytest.mark.parametrize("name", SERVICE_CASES.keys())
@pytest.mark.asyncio
async def test_out_of_range_integer_raises_before_sending(name: str) -> None:
    transport = MagicMock()
    with pytest.raises(PolyesterValidationError) as excinfo:
        await SERVICE_CASES[name](transport)
    assert FIELD_NAMED[name] in str(excinfo.value)
    _assert_not_sent(transport)


@pytest.mark.asyncio
async def test_triggers_create_ladder_levels_no_send_names_the_field() -> None:
    transport = MagicMock()
    with pytest.raises(PolyesterValidationError, match=r"levels must be >= 2 and <= 100"):
        await AsyncTriggersService(transport, _catalogs(), None).create(
            symbol="BTC-USDT",
            trigger_type="ladder",
            side="sell",
            qty="0.01",
            ladder_price_min="80000",
            ladder_price_max="90000",
            ladder_levels=1,
        )
    _assert_not_sent(transport)


def test_codec_integers_are_type_bounded() -> None:
    with pytest.raises(PolyesterValidationError, match="external_polychain_chain_id"):
        protected_action_args_to_proto(
            external_polychain_chain_id=U32_OVER, external_addresses=["0xabc"]
        )
    for field, value in (
        ("asset_id", U32_OVER),
        ("destination_chain_id", U64_OVER),
        ("deadline_ts_sec", U64_OVER),
    ):
        kwargs: dict[str, Any] = {
            "action": "to_external_chain",
            "asset_id": 1,
            "amount": "1",
            "idempotency_key": "k",
            "destination_chain_id": 1,
            "deadline_ts_sec": 1_900_000_000,
            "nonce": 7,
            "destination_address": "0xabc",
        }
        kwargs[field] = value
        with pytest.raises(PolyesterValidationError, match=field):
            trading_withdraw_payload_to_proto(**kwargs)
    with pytest.raises(PolyesterValidationError, match="ladder_levels"):
        create_trigger_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            trigger_type="ladder",
            side="sell",
            qty="0.01",
            quantity_scale=8,
            ladder_price_min="80000",
            ladder_price_max="90000",
            ladder_levels=2**31,
        )


# --- the contract range check itself ---------------------------------------------


def test_range_check_uses_the_contract_rules() -> None:
    check_request_ranges(orders_read_pb2.GetOpenOrdersRequest(limit=1_000))
    with pytest.raises(PolyesterValidationError, match=r"^limit must be >= 1 and <= 1000$"):
        check_request_ranges(orders_read_pb2.GetOpenOrdersRequest(limit=1_001))


def test_range_check_leaves_unset_fields_to_the_server() -> None:
    # limit is implicit-presence and left at 0: not sent, so not checked.
    check_request_ranges(orders_read_pb2.GetOpenOrdersRequest())


def test_range_check_honours_ignore_if_zero() -> None:
    # CancelAllAfterRequest.symbol_id is gt 0 but ignored when zero.
    check_request_ranges(orders_pb2.CancelAllAfterRequest(request_id="r", timeout_sec=5))


def test_range_check_walks_repeated_items_and_counts() -> None:
    with pytest.raises(PolyesterValidationError, match=r"symbol_id accepts at most 2000 values"):
        check_request_ranges(
            marketoverview_pb2.ListMarketOverviewRequest(symbol_id=list(range(1, 2_002)))
        )
    with pytest.raises(PolyesterValidationError, match="unique"):
        check_request_ranges(orders_read_pb2.GetOpenOrdersRequest(symbol_id=[1, 1]))
    with pytest.raises(PolyesterValidationError, match=r"symbol_id\[1\] must be > 0"):
        check_request_ranges(orders_read_pb2.GetOpenOrdersRequest(symbol_id=[1, 0]))


def test_range_check_walks_nested_messages() -> None:
    request = triggers_pb2.CreateTriggerRequest(
        trigger=triggers_pb2.TriggerIntent(
            symbol_id=1,
            qty_scaled=1,
            ladder=triggers_pb2.LadderTrigger(
                side=orders_pb2.SELL, price_min_ticks=1, price_max_ticks=2, levels=101
            ),
        )
    )
    with pytest.raises(PolyesterValidationError, match=r"^trigger\.ladder\.levels must be"):
        check_request_ranges(request)


def test_range_check_explicit_presence_zero_is_checked() -> None:
    # after_match_id is optional with gt 0: an explicit zero is sent, so it is checked.
    request = orders_read_pb2.GetUserTradesRequest(limit=10, symbol_id=1)
    request.after_match_id = 0
    with pytest.raises(PolyesterValidationError, match="after_match_id must be > 0"):
        check_request_ranges(request)
    check_request_ranges(ledger_read_pb2.GetBalanceHistoryRequest(ledger=7))


# --- message-level contract ranges (expressed as rule expressions, not field rules)


def _twap(**overrides: object):
    kwargs: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "twap",
        "side": "sell",
        "qty": "0.01",
        "quantity_scale": 8,
        "twap_duration_ms": 1_000,
        "twap_slice_interval_ms": 100,
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)  # type: ignore[arg-type]


def test_twap_duration_and_interval_follow_the_contract() -> None:
    twap = _twap().trigger.twap
    assert (twap.duration_ms, twap.slice_interval_ms) == (1_000, 100)
    assert _twap(twap_slice_interval_ms=1_000).trigger.twap.slice_interval_ms == 1_000
    with pytest.raises(PolyesterValidationError, match="twap_duration_ms must be between 1000"):
        _twap(twap_duration_ms=999)
    with pytest.raises(
        PolyesterValidationError, match="twap_slice_interval_ms must be between 100"
    ):
        _twap(twap_slice_interval_ms=99)
    with pytest.raises(
        PolyesterValidationError, match="twap_slice_interval_ms must be between 100 and 1000"
    ):
        _twap(twap_slice_interval_ms=1_001)
    with pytest.raises(PolyesterValidationError, match="requires twap_duration_ms and"):
        _twap(twap_duration_ms=None)


@pytest.mark.parametrize("timeout", [0, 10, 120])
def test_cancel_all_after_accepts_off_or_10_to_120(timeout: int) -> None:
    from polyester.codecs.orders import cancel_all_after_to_proto

    assert cancel_all_after_to_proto(timeout_sec=timeout).timeout_sec == timeout


@pytest.mark.parametrize("timeout", [1, 9, 121])
@pytest.mark.asyncio
async def test_cancel_all_after_rejects_other_timeouts_without_sending(timeout: int) -> None:
    transport = MagicMock()
    with pytest.raises(
        PolyesterValidationError, match="timeout_sec must be 0 or between 10 and 120"
    ):
        await AsyncOrdersService(transport, _catalogs(), None).cancel_all_after(timeout_sec=timeout)
    _assert_not_sent(transport)
