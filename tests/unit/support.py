from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from google.protobuf.message import Message

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
    ) -> T:
        self.request = request
        self.calls += 1
        return decoder(self.response)
