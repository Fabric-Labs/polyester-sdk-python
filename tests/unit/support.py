from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from google.protobuf.message import Message

from polyester.codecs.decode.orders import OrderMarket, batch_create_from_proto

T = TypeVar("T")


class CaptureUnary:
    """Capture the protobuf request passed to unary_*_decoded helpers."""

    def __init__(self, response: Message) -> None:
        self.request: Message | None = None
        self.response = response
        self.calls = 0

    async def __call__(
        self,
        transport: Any,
        client_cls: type,
        call: Callable[..., Awaitable[Message]],
        request: Message,
        decoder: Callable[[Message], T],
        **_options: Any,
    ) -> T:
        self.request = request
        self.calls += 1
        return decoder(self.response)


def btc_market(quantity_scale: int | None = 8) -> OrderMarket:
    """The market an order write's decoder binds its resolved quantity to."""
    return OrderMarket("BTC-USDT", 1, quantity_scale)


def decode_btc_batch(msg: Any) -> Any:
    """Decode a batch create answer to a batch of BTC-USDT items, one per result."""
    return batch_create_from_proto(msg, markets=[btc_market()] * len(msg.results))
