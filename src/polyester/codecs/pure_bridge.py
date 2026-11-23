"""The SDK's calls into ``polyester.pure``, the single-file request builders.

``polyester.pure`` holds the client-side rules the SDK shares with a restricted
Python runtime: it refuses with ``ValueError`` and, in CPython, tags the error
with the server's ``code``, its field ``violations`` and whether a digit fell
past a scale. :func:`call` raises those refusals as the SDK's own
:class:`PolyesterValidationError` (or :class:`FractionalDigitsError`), with the
same message, code and violations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from google.protobuf import json_format
from google.protobuf.message import Message

from polyester import pure as _pure
from polyester.errors import PolyesterValidationError

pure: Any = _pure
M = TypeVar("M", bound=Message)
R = TypeVar("R")


class FractionalDigitsError(PolyesterValidationError):
    """A decimal with a nonzero digit beyond its scale (zeros beyond it parse).

    Order encoders re-raise it for a quantity or tick-checked price with the
    step or tick code the server answers for the same value.
    """


def translate(exc: ValueError) -> PolyesterValidationError:
    """The SDK refusal for a ``polyester.pure`` refusal."""
    from polyester.models.trading import OrderFieldViolation

    cls = FractionalDigitsError if getattr(exc, "fractional", False) else PolyesterValidationError
    violations = [OrderFieldViolation(**item) for item in getattr(exc, "violations", None) or []]
    return cls(str(exc), code=getattr(exc, "code", None), violations=violations)


def call(fn: Callable[..., R], *args: Any, **kwargs: Any) -> R:
    """``fn(*args, **kwargs)``, a ``polyester.pure`` function, with its
    refusals raised as :class:`PolyesterValidationError`."""
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise translate(exc) from None


def message(built: dict[str, Any], target: M) -> M:
    """``target`` filled from a builder's proto-JSON."""
    return json_format.ParseDict(built, target)
