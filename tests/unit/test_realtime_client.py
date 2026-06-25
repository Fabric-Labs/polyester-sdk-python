from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError
from polyester.realtime.client import AsyncRealtimeClient, is_private_channel


def test_is_private_channel() -> None:
    assert is_private_channel("private:spot:orders:acct:proto")
    assert not is_private_channel("public:spot:market:trades:1:proto")


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
        sent: list[str] = []
        messages = [
            '{"id": 1, "connect": {}}',
            '{"id": 2, "subscribe": {}}',
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: str) -> None:
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


@pytest.mark.asyncio
async def test_handle_centrifugo_frame_replies_to_ping() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    ws = AsyncMock()
    publications = await client._handle_centrifugo_frame(ws, "{}", decode=lambda payload: payload)
    assert publications == []
    ws.send.assert_awaited_once_with("{}")


@pytest.mark.asyncio
async def test_handle_centrifugo_frame_replies_to_push_ping() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    ws = AsyncMock()
    publications = await client._handle_centrifugo_frame(
        ws,
        '{"push": {"ping": {}}}',
        decode=lambda payload: payload,
    )
    assert publications == []
    ws.send.assert_awaited_once_with("{}")


@pytest.mark.asyncio
async def test_handle_centrifugo_frame_decodes_base64_publication() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    ws = AsyncMock()
    payload = base64.b64encode(b"trade-bytes").decode("ascii")
    frame = json.dumps({"push": {"pub": {"data": payload}}})
    publications = await client._handle_centrifugo_frame(
        ws,
        frame,
        decode=lambda raw: raw,
    )
    assert publications == [b"trade-bytes"]
    ws.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_centrifugo_frame_ping_and_publication_in_one_batch() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")
    ws = AsyncMock()
    batch = '{"push": {"pub": {"data": [9]}}}\n{}\n'
    publications: list[bytes] = []
    for frame in AsyncRealtimeClient._split_centrifugo_frames(batch):
        publications.extend(
            await client._handle_centrifugo_frame(ws, frame, decode=lambda raw: raw)
        )
    assert publications == [bytes([9])]
    ws.send.assert_awaited_once_with("{}")


@pytest.mark.asyncio
async def test_subscribe_proto_disconnect_ends_stream_without_task_exception() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")

    class FakeWS:
        messages = [
            '{"id": 1, "connect": {}}',
            '{"id": 2, "subscribe": {}}',
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: str) -> None:
            return None

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            raise RuntimeError("connection closed")

    with patch("polyester.realtime.client.websockets.connect", return_value=FakeWS()):
        subscription = await client.subscribe_proto(
            "public:spot:market:trades:1:proto",
            decode=lambda payload: payload,
        )
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(subscription.__anext__(), timeout=1.0)
        assert subscription._task is not None
        await asyncio.wait_for(subscription._task, timeout=1.0)
        assert subscription._task.exception() is None


@pytest.mark.asyncio
async def test_subscribe_proto_replies_to_centrifugo_ping() -> None:
    client = AsyncRealtimeClient("wss://api-devnet.polyester.ai")

    class FakeWS:
        sent: list[str] = []
        messages = [
            '{"id": 1, "connect": {}}',
            '{"id": 2, "subscribe": {}}',
            '{"push": {"pub": {"data": [1, 2, 3]}}}',
            "{}",
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload: str) -> None:
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
    assert "{}" in fake_ws.sent


def test_split_centrifugo_frames_handles_newline_batches() -> None:
    frames = AsyncRealtimeClient._split_centrifugo_frames(
        '{"push":{"pub":{"data":[1]}}}\n{}\n'
    )
    assert frames == ['{"push":{"pub":{"data":[1]}}}', "{}"]
