from __future__ import annotations

import asyncio
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
            "private:spot:orders:RLxqJGUDg92:proto",
            decode=lambda payload: payload,
        )
        await asyncio.sleep(0.05)
        await subscription.aclose()
        await asyncio.sleep(0.05)

    fetch_conn.assert_awaited_once()
    fetch_sub.assert_awaited_once()
    assert fetch_sub.await_args.kwargs["channel"] == "private:spot:orders:RLxqJGUDg92:proto"
