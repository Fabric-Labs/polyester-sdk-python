"""Reads by ID that refuse a reply naming another object than requested."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from polyester.errors import PolyesterResponseContractError

M = TypeVar("M")
T = TypeVar("T")


def echoed(
    operation: str,
    field: str,
    requested: str,
    replied: Callable[[M], str | None],
    decode: Callable[[M], T],
) -> Callable[[M], T]:
    """Wrap the decoder of a read by ID.

    A reply that names another object than the one the request asked for
    breaks the response contract, however well formed it is, and raises
    :class:`~polyester.errors.PolyesterResponseContractError`. ``replied``
    returns the identity the reply names, or ``None`` when the reply holds no
    object (left to ``decode``); ``requested`` is the identity as the request
    sent it, in the form ``replied`` returns.
    """

    def checked(msg: M) -> T:
        out = decode(msg)
        got = replied(msg)
        if got is not None and got != requested:
            raise PolyesterResponseContractError(
                operation, f"reply names {field} {got!r}, not the requested {requested!r}"
            )
        return out

    return checked
