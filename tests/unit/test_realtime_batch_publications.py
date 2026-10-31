"""Batched realtime publications decode to one event per batch member, in order."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from polyester.codecs.realtime_decode import (
    _decode_batch_members,
    decode_ledger_transfer_batch_bytes,
    decode_market_trade_batch_bytes,
    decode_trigger_event_batch_bytes,
    decode_user_trade_batch_bytes,
)
from polyester.errors import PolyesterRealtimeError
from polyester.gen.ledger.read.v1.ledger_read_pb2 import TransferRow, TransferRowBatch
from polyester.gen.marketdata.v1.marketdata_pb2 import MarketTrade, MarketTradeBatch
from polyester.gen.orders.v1.orders_read_pb2 import UserTrade, UserTradeBatch
from polyester.gen.triggers.v1.triggers_pb2 import TriggerEvent, TriggerEventBatch
from polyester.realtime.client import AsyncRealtimeClient

ACK_CONNECT = bytes([2, 8, 1])
ACK_SUBSCRIBE = bytes([2, 8, 2])
PRICE_1 = 1_000_000_000


def _len_field(field: int, payload: bytes) -> bytes:
    return bytes([(field << 3) | 2]) + _varint(len(payload)) + payload


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def publication_frame(data: bytes) -> bytes:
    """One Centrifugo reply frame: Reply.push(4) -> Push.pub(4) -> Publication.data(4)."""
    reply = _len_field(4, _len_field(4, _len_field(4, data)))
    return _varint(len(reply)) + reply


class _FakeWS:
    """Acks the handshake, then serves ``frames`` once ``release`` is set."""

    subprotocol = "centrifuge-protobuf"

    def __init__(self, frames: list[bytes]) -> None:
        self.handshake = [ACK_CONNECT, ACK_SUBSCRIBE]
        self.messages = list(frames)
        self.release = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def send(self, payload: bytes) -> None:
        return None

    async def recv(self):
        if self.handshake:
            return self.handshake.pop(0)
        await self.release.wait()
        if self.messages:
            return self.messages.pop(0)
        await asyncio.sleep(3600)


def _market_trade_batch(*match_ids: int) -> bytes:
    return MarketTradeBatch(
        events=[
            MarketTrade(
                symbol_id=7,
                match_id=match_id,
                is_buy=match_id % 2 == 0,
                price_ticks=PRICE_1 * match_id,
                qty_scaled=match_id * 100,
                ts_ns=1_700_000_000_000_000_000 + match_id,
            )
            for match_id in match_ids
        ]
    ).SerializeToString()


def test_market_trade_batch_decodes_every_trade_in_order() -> None:
    trades = decode_market_trade_batch_bytes(_market_trade_batch(1, 2, 3), quantity_scale=2)

    assert [t.match_id for t in trades] == ["1", "2", "3"]  # type: ignore[union-attr]
    assert [t.qty.format() for t in trades] == ["1", "2", "3"]  # type: ignore[union-attr]
    assert [t.price.format() for t in trades] == ["1", "2", "3"]  # type: ignore[union-attr]
    assert trades[2].ts_ns == "1700000000000000003"  # type: ignore[union-attr]


def test_user_trade_batch_decodes_every_fill_in_order() -> None:
    payload = UserTradeBatch(
        events=[
            UserTrade(symbol_id=7, match_id=10, order_id=100, ts_ns=1),
            UserTrade(symbol_id=7, match_id=11, order_id=101, ts_ns=2),
        ]
    ).SerializeToString()

    fills = decode_user_trade_batch_bytes(payload)

    assert [f.match_id for f in fills] == ["10", "11"]  # type: ignore[union-attr]
    assert [f.ts_ns for f in fills] == ["1", "2"]  # type: ignore[union-attr]


def test_ledger_transfer_batch_decodes_both_legs_with_shared_transfer_id() -> None:
    transfer_id = str(2**127 + 5)
    payload = TransferRowBatch(
        events=[
            TransferRow(asset_id=1, account_code=1, is_debit=True, transfer_id=transfer_id),
            TransferRow(asset_id=1, account_code=2, is_debit=False, transfer_id=transfer_id),
        ]
    ).SerializeToString()

    legs = decode_ledger_transfer_batch_bytes(payload)

    assert [leg.account_code for leg in legs] == [1, 2]  # type: ignore[union-attr]
    assert {leg.transfer_id for leg in legs} == {transfer_id}  # type: ignore[union-attr]


def test_trigger_event_batch_decodes_every_event_with_exact_ts_ns() -> None:
    payload = TriggerEventBatch(
        events=[
            TriggerEvent(trigger_id=5, ts_ns=1_700_000_000_123_456_789, child_seq=0),
            TriggerEvent(trigger_id=5, ts_ns=1_700_000_000_123_456_790, child_seq=1),
        ]
    ).SerializeToString()

    events = decode_trigger_event_batch_bytes(payload)

    assert [e.child_seq for e in events] == [0, 1]  # type: ignore[union-attr]
    assert [e.ts_ns for e in events] == [  # type: ignore[union-attr]
        "1700000000123456789",
        "1700000000123456790",
    ]


def test_malformed_member_becomes_error_without_dropping_the_rest() -> None:
    def decode(event: int) -> int:
        if event == 2:
            raise ValueError("bad member")
        return event * 10

    members = _decode_batch_members([1, 2, 3], decode)

    assert members[0] == 10
    assert isinstance(members[1], PolyesterRealtimeError)
    assert "batch event 1" in str(members[1])
    assert isinstance(members[1].__cause__, ValueError)
    assert members[2] == 30


@pytest.mark.asyncio
async def test_market_trade_subscription_emits_each_batched_trade() -> None:
    client = AsyncRealtimeClient("wss://api.devnet.polyester.com")
    frames = [
        publication_frame(_market_trade_batch(1, 2)),
        publication_frame(_market_trade_batch(3)),
    ]
    ws = _FakeWS(frames)
    with patch("polyester.realtime.client.websockets.connect", return_value=ws):
        sub = await client.subscribe_market_trades(7, quantity_scale=2)
        ws.release.set()
        received = [await asyncio.wait_for(sub.__anext__(), timeout=1.0) for _ in range(3)]
        await sub.aclose()

    assert [t.match_id for t in received] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_batch_member_error_reaches_on_error_and_stream_continues() -> None:
    client = AsyncRealtimeClient("wss://api.devnet.polyester.com")
    member_error = PolyesterRealtimeError("batch event 1: boom")
    frames = [publication_frame(b"a"), publication_frame(b"b")]
    errors: list[BaseException] = []

    def decode_batch(payload: bytes) -> list[str | BaseException]:
        if payload == b"a":
            return ["a0", member_error, "a2"]
        return ["b0"]

    ws = _FakeWS(frames)
    with patch("polyester.realtime.client.websockets.connect", return_value=ws):
        sub = await client.subscribe_proto_batch(
            "public:spot:market:trades:7:proto", decode_batch=decode_batch
        )
        sub.set_on_error(errors.append)
        ws.release.set()
        received = [await asyncio.wait_for(sub.__anext__(), timeout=1.0) for _ in range(3)]
        alive = sub.is_alive
        await sub.aclose()

    assert received == ["a0", "a2", "b0"]
    assert errors == [member_error]
    assert alive
    assert sub.error is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_module", "service_class", "method", "decoder"),
    [
        (
            "polyester.services.trades",
            "AsyncTradesService",
            "subscribe",
            "decode_user_trade_batch_bytes",
        ),
        (
            "polyester.services.transfers",
            "AsyncTransfersService",
            "subscribe",
            "decode_ledger_transfer_batch_bytes",
        ),
        (
            "polyester.services.triggers",
            "AsyncTriggersService",
            "subscribe_events",
            "decode_trigger_event_batch_bytes",
        ),
    ],
)
async def test_private_event_subscriptions_use_batch_decoders(
    service_module: str, service_class: str, method: str, decoder: str
) -> None:
    import importlib
    from unittest.mock import AsyncMock, MagicMock

    module = importlib.import_module(service_module)
    realtime = MagicMock(spec=AsyncRealtimeClient)
    realtime.subscribe_proto_batch = AsyncMock(return_value="sub")
    service = object.__new__(getattr(module, service_class))
    service._realtime = realtime
    service._default_account_id = "42"

    assert await getattr(service, method)() == "sub"

    call = realtime.subscribe_proto_batch.await_args
    assert call.args[0].startswith("private:") and ":42:" in call.args[0]
    assert call.kwargs["decode_batch"].__name__ == decoder
