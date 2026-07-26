from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError, PolyesterRealtimeError
from polyester.realtime.client import (
    AsyncRealtimeClient,
    AsyncSubscription,
    _ReconnectBackoff,
    is_private_channel,
)
from polyester.realtime.protocol import (
    Ping,
    Publication,
    Reply,
    connect_command,
    decode_replies,
    pong_command,
    subscribe_command,
)

ACK_CONNECT = bytes([2, 8, 1])
ACK_SUBSCRIBE = bytes([2, 8, 2])
PUBLICATION = bytes([9, 34, 7, 34, 5, 34, 3, 1, 2, 3])


def test_is_private_channel() -> None:
    assert is_private_channel("private:spot:orders:acct:proto")
    assert not is_private_channel("public:spot:market:trades:1:proto")


@pytest.mark.asyncio
async def test_async_subscription_context_manager_closes_subscription() -> None:
    queue: asyncio.Queue[object | None] = asyncio.Queue()
    close = asyncio.Event()
    subscription = AsyncSubscription[object](queue=queue, close=close)

    async with subscription as entered:
        assert entered is subscription
        assert not close.is_set()

    assert close.is_set()


def test_async_subscription_error_callback_is_observable_and_isolated() -> None:
    queue: asyncio.Queue[object | None] = asyncio.Queue()
    close = asyncio.Event()
    subscription = AsyncSubscription[object](queue=queue, close=close)
    observed: list[str] = []
    subscription.set_on_error(lambda exc: observed.append(str(exc)))
    subscription._set_error(PolyesterRealtimeError("feed stopped"))
    assert observed == ["feed stopped"]
    assert str(subscription.error) == "feed stopped"

    subscription.set_on_error(lambda _exc: (_ for _ in ()).throw(RuntimeError("callback")))
    subscription._notify_error(PolyesterRealtimeError("ignored callback failure"))


def test_reconnect_backoff_is_bounded_exponential_and_jittered() -> None:
    backoff = _ReconnectBackoff()
    delays = [backoff.next_delay() for _ in range(10)]
    caps = [0.5, 1, 2, 4, 8, 16, 30, 30, 30, 30]
    for delay, cap in zip(delays, caps, strict=True):
        assert cap / 2 <= delay <= cap
    assert len(set(delays)) > 1
    backoff.reset()
    assert 0.25 <= backoff.next_delay() <= 0.5


@pytest.mark.asyncio
async def test_subscribe_proto_private_requires_credentials() -> None:
    client = AsyncRealtimeClient(
        "wss://api-devnet.polyester.ai",
        api_url="https://api-devnet.polyester.ai",
        http=MagicMock(),
    )
    with pytest.raises(PolyesterAuthError, match="without API-key credentials"):
        await client.subscribe_proto(
            "private:spot:orders:acct:proto",
            decode=lambda payload: payload,
        )


@pytest.mark.asyncio
async def test_subscribe_proto_private_fetches_tokens_before_subscribe() -> None:
    credentials = ApiKeyCredentials(key_id="ak_test", private_key=b"\x01" * 32)
    http = MagicMock()
    client = AsyncRealtimeClient(
        "wss://api-devnet.polyester.ai",
        api_url="https://api-devnet.polyester.ai",
        credentials=credentials,
        http=http,
    )

    class FakeWS:
        sent: list[bytes] = []
        subprotocol = "centrifuge-protobuf"
        messages = [
            ACK_CONNECT,
            ACK_SUBSCRIBE,
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: bytes) -> None:
            self.sent.append(payload)

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            raise StopAsyncIteration

    with (
        patch(
            "polyester.realtime.client.fetch_connection_token",
            AsyncMock(return_value="conn-token"),
        ) as fetch_conn,
        patch(
            "polyester.realtime.client.fetch_subscription_token",
            AsyncMock(return_value="sub-token"),
        ) as fetch_sub,
        patch("polyester.realtime.client.websockets.connect", return_value=FakeWS()),
    ):
        subscription = await client.subscribe_proto(
            "private:spot:orders:acct_test:proto",
            decode=lambda payload: payload,
        )
        await asyncio.sleep(0.05)
        await subscription.aclose()
        await asyncio.sleep(0.05)

    fetch_conn.assert_awaited_once()
    fetch_sub.assert_awaited_once()
    assert fetch_sub.await_args.kwargs["channel"] == "private:spot:orders:acct_test:proto"
    assert FakeWS.sent == [
        connect_command(1, "conn-token"),
        subscribe_command(
            2,
            "private:spot:orders:acct_test:proto",
            "sub-token",
        ),
    ]


def test_binary_protocol_commands_and_replies() -> None:
    assert connect_command(1) == bytes([4, 8, 1, 34, 0])
    assert subscribe_command(2, "x") == bytes([7, 8, 2, 42, 3, 10, 1, ord("x")])
    assert pong_command() == b"\x00"
    assert decode_replies(ACK_CONNECT + b"\x00" + PUBLICATION) == [
        Reply(1, None),
        Ping(),
        Publication(b"\x01\x02\x03"),
    ]


@pytest.mark.asyncio
async def test_subscribe_proto_reconnects_after_disconnect() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    connect_calls = 0

    class FakeWS:
        subprotocol = "centrifuge-protobuf"
        messages = [
            ACK_CONNECT,
            ACK_SUBSCRIBE,
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: bytes) -> None:
            return None

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            raise RuntimeError("connection closed")

    def fake_connect(*args, **kwargs):
        nonlocal connect_calls
        connect_calls += 1
        return FakeWS()

    with patch("polyester.realtime.client.websockets.connect", side_effect=fake_connect):
        subscription = await client.subscribe_proto(
            "public:spot:market:trades:1:proto",
            decode=lambda payload: payload,
        )
        await asyncio.sleep(2.5)
        assert connect_calls >= 2
        assert subscription._task is not None
        assert not subscription._task.done()
        await subscription.aclose()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(subscription._task, timeout=1.0)


@pytest.mark.asyncio
async def test_subscribe_proto_replies_to_centrifugo_ping() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")

    class FakeWS:
        sent: list[bytes] = []
        subprotocol = "centrifuge-protobuf"
        messages = [
            ACK_CONNECT,
            ACK_SUBSCRIBE,
            PUBLICATION,
            b"\x00",
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: bytes) -> None:
            self.sent.append(payload)

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            await asyncio.sleep(3600)

    fake_ws = FakeWS()
    with patch("polyester.realtime.client.websockets.connect", return_value=fake_ws):
        subscription = await client.subscribe_proto(
            "public:spot:market:trades:1:proto",
            decode=lambda payload: payload,
        )
        first = await asyncio.wait_for(subscription.__anext__(), timeout=1.0)
        await asyncio.sleep(0.05)
        await subscription.aclose()
        await asyncio.wait_for(subscription._task, timeout=1.0)

    assert first == b"\x01\x02\x03"
    assert pong_command() in fake_ws.sent


@pytest.mark.asyncio
async def test_subscribe_proto_read_timeout_is_connection_death_no_reconnect() -> None:
    """Read timeout must not hang in a continue loop; with auto_reconnect=False, surface error."""
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")

    class SilentWS:
        subprotocol = "centrifuge-protobuf"
        messages = [ACK_CONNECT, ACK_SUBSCRIBE]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: bytes) -> None:
            return None

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            await asyncio.sleep(3600)

    with (
        patch("polyester.realtime.client.CENTRIFUGO_READ_TIMEOUT", 0.05),
        patch("polyester.realtime.client.websockets.connect", return_value=SilentWS()),
    ):
        subscription = await client.subscribe_proto(
            "public:spot:market:trades:1:proto",
            decode=lambda payload: payload,
            auto_reconnect=False,
        )
        with pytest.raises(PolyesterRealtimeError, match="timeout"):
            await asyncio.wait_for(subscription.__anext__(), timeout=2.0)
        assert subscription.error is not None
        assert "timeout" in str(subscription.error).lower()


@pytest.mark.asyncio
async def test_subscribe_proto_read_timeout_reconnects_when_enabled() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    connect_calls = 0

    class SilentThenAliveWS:
        subprotocol = "centrifuge-protobuf"

        def __init__(self) -> None:
            self.messages = [ACK_CONNECT, ACK_SUBSCRIBE]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: bytes) -> None:
            return None

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            await asyncio.sleep(3600)

    def fake_connect(*args, **kwargs):
        nonlocal connect_calls
        connect_calls += 1
        return SilentThenAliveWS()

    with (
        patch("polyester.realtime.client.CENTRIFUGO_READ_TIMEOUT", 0.05),
        patch.object(_ReconnectBackoff, "next_delay", return_value=0.01),
        patch("polyester.realtime.client.websockets.connect", side_effect=fake_connect),
    ):
        subscription = await client.subscribe_proto(
            "public:spot:market:trades:1:proto",
            decode=lambda payload: payload,
            auto_reconnect=True,
        )
        await asyncio.sleep(0.25)
        assert connect_calls >= 2
        assert subscription.resubscribed >= 1
        assert subscription.take_resubscribed() is True
        assert subscription.take_resubscribed() is False
        await subscription.aclose()


@pytest.mark.asyncio
async def test_subscribe_proto_resubscribed_increments_after_forced_reconnect() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    connect_calls = 0

    class FakeWS:
        subprotocol = "centrifuge-protobuf"

        def __init__(self) -> None:
            self.messages = [ACK_CONNECT, ACK_SUBSCRIBE]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: bytes) -> None:
            return None

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            raise RuntimeError("connection closed")

    def fake_connect(*args, **kwargs):
        nonlocal connect_calls
        connect_calls += 1
        return FakeWS()

    with (
        patch.object(_ReconnectBackoff, "next_delay", return_value=0.01),
        patch("polyester.realtime.client.websockets.connect", side_effect=fake_connect),
    ):
        subscription = await client.subscribe_proto(
            "public:spot:market:trades:1:proto",
            decode=lambda payload: payload,
        )
        assert subscription.resubscribed == 0
        assert subscription.take_resubscribed() is False
        await asyncio.sleep(0.2)
        assert connect_calls >= 2
        assert subscription.resubscribed >= 1
        assert subscription.take_resubscribed() is True
        await subscription.aclose()
