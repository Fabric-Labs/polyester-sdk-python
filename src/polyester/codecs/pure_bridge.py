"""The SDK's calls into ``polyester.pure``, the single-file request builders.

``polyester.pure`` holds the client-side rules the SDK shares with a restricted
Python runtime: it refuses with ``ValueError`` and, in CPython, tags the error
with the server's ``code``, its field ``violations`` and whether a digit fell
past a scale. :func:`call` raises those refusals as the SDK's own
:class:`PolyesterValidationError` (or :class:`FractionalDigitsError`), with the
same message, code and violations.
"""

from __future__ import annotations

import numbers
import operator
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, TypeVar

from google.protobuf import json_format
from google.protobuf.message import Message

from polyester import pure as _module
from polyester.errors import PolyesterValidationError

# The rules: every name defined inside polyester.pure, which keeps them out
# of the namespace a restricted runtime shares with other code.
_namespace: Any = _module.polyester
pure: Any = SimpleNamespace(**_namespace._sdk)
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


def exact_index(value: object) -> object:
    """A non-``int`` exact integer (NumPy's) as the plain ``int`` it is.

    The SDK takes any :class:`numbers.Integral` where it takes an integer ID,
    count or duration; the shared rules take a plain ``int``. numbers.Integral,
    not __index__: a float subclass may implement __index__ and would read 8.9
    as 8. Everything else, floats and bools included, is passed on to be refused.
    """
    if isinstance(value, numbers.Integral) and not isinstance(value, (bool, int)):
        return operator.index(value)
    return value


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
