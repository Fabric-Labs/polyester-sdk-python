from polyester.codecs.decode.api_keys import api_key_from_proto, api_keys_list_from_proto
from polyester.codecs.decode.deposit import deposit_address_from_proto
from polyester.codecs.decode.internal_transfers import internal_transfer_from_proto
from polyester.codecs.decode.market_data import market_trade_from_proto, market_trades_from_proto
from polyester.codecs.decode.market_overview import market_overview_list_from_proto
from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.decode.resolve import resolved_accounts_from_proto
from polyester.codecs.decode.transfers import ledger_transfer_from_proto, transfers_list_from_proto
from polyester.codecs.decode.withdraw import withdraw_intent_from_proto
from polyester.codecs.scalars import format_id
from polyester.gen.auth.v1 import api_keys_pb2, resolve_pb2
from polyester.gen.chain.deposit.v1 import deposit_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2


def test_ledger_transfer_from_proto() -> None:
    msg = ledger_read_pb2.TransferRow(
        asset_id=2,
        amount_e18=u128_pb2.U128(hi=0, lo=1000),
        transfer_code=5,
        account_code=1,
        ts_us=999,
        is_debit=True,
        flow_id="flow-abc",
    )
    transfer = ledger_transfer_from_proto(msg)
    assert transfer.amount == "1000"
    assert transfer.transfer_type == 5
    assert transfer.tx_id == "flow-abc"
    assert transfer.is_debit is True


def test_transfers_list_from_proto_parses_cursor() -> None:
    msg = ledger_read_pb2.ListTransfersResponse(
        transfers=[ledger_read_pb2.TransferRow(asset_id=1)],
        next_page_token="12345",
    )
    result = transfers_list_from_proto(msg)
    assert len(result.transfers) == 1
    assert result.next_cursor == 12345


def test_deposit_address_from_proto() -> None:
    msg = deposit_pb2.DepositAddress(chain_id=1, deposit_address="0xabc")
    result = deposit_address_from_proto(msg)
    assert result.chain_id == 1
    assert result.deposit_address == "0xabc"


def test_withdraw_intent_from_proto() -> None:
    msg = withdraw_pb2.CreateTradingWithdrawResponse(intent_id="intent-1")
    result = withdraw_intent_from_proto(msg)
    assert result.intent_id == "intent-1"


def test_internal_transfer_from_proto() -> None:
    msg = internal_transfer_pb2.CreateInternalTransferResponse(
        request_id="req-1",
        transfer_id="xfer-1",
        asset_id=3,
        asset_code="USDT",
        qty_scaled=500,
    )
    result = internal_transfer_from_proto(msg)
    assert result.request_id == "req-1"
    assert result.quantity_scaled == "500"


def test_api_keys_from_proto() -> None:
    msg = api_keys_pb2.ListApiKeysResponse(
        api_keys=[
            api_keys_pb2.ApiKey(
                key_id="key-1",
                label="bot",
                status=api_keys_pb2.ACTIVE,
                subaccount_id=10,
            )
        ]
    )
    result = api_keys_list_from_proto(msg)
    assert len(result.api_keys) == 1
    key = api_key_from_proto(msg.api_keys[0])
    assert key.status == "active"
    assert key.subaccount_id == format_id(10)


def test_resolved_accounts_from_proto() -> None:
    msg = resolve_pb2.ResolveAccountResponse(
        matches=[
            resolve_pb2.ResolvedAccount(
                smart_account_address="0x123",
                kind="subaccount",
                account_id=99,
            )
        ]
    )
    result = resolved_accounts_from_proto(msg)
    assert len(result.matches) == 1
    assert result.matches[0].account_id == format_id(99)


def test_market_trades_from_proto() -> None:
    msg = marketdata_pb2.GetTradesResponse(
        trades=[
            marketdata_pb2.MarketTrade(
                symbol_id=1,
                match_id=55,
                is_buy=True,
                price_ticks=100,
                qty_scaled=200,
                ts_ns=300,
            )
        ],
        next_page_token="56",
    )
    result = market_trades_from_proto(msg)
    assert len(result.trades) == 1
    trade = market_trade_from_proto(msg.trades[0])
    assert trade.match_id == "55"
    assert result.next_match_id == "56"


def test_market_overview_list_from_proto() -> None:
    msg = marketoverview_pb2.ListMarketOverviewResponse(
        markets=[
            marketoverview_pb2.MarketOverview(
                symbol_id=1,
                symbol="BTC-USD",
                last_price_ticks=50_000,
                change_24h_bps=-100,
                volume_24h_quote_scaled=1_000_000,
            )
        ]
    )
    result = market_overview_list_from_proto(msg)
    assert len(result.markets) == 1
    assert result.markets[0].symbol == "BTC-USD"


def test_orderbook_from_proto() -> None:
    msg = orderbook_pb2.GetOrderBookResponse(
        book_seq=42,
        bids=[orderbook_pb2.PriceLevel(price_ticks=100, qty_scaled=50)],
        asks=[orderbook_pb2.PriceLevel(price_ticks=101, qty_scaled=25)],
    )
    result = orderbook_from_proto(msg, symbol="BTC-USD", depth=50)
    assert result.book_seq == "42"
    assert len(result.bids) == 1
    assert result.bids[0].price_ticks == "100"
