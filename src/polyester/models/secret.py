from __future__ import annotations

from typing import Any, Generic, NoReturn, TypeVar

T = TypeVar("T")

_REDACTED = "[REDACTED]"
_NOT_SERIALIZABLE = (
    "Secret holds private key material and cannot be pickled; call reveal() to read it"
)


class Secret(Generic[T]):
    """Private key material that rendering and serialization never reveal.

    Call ``reveal()`` to read the value. ``repr``, ``str`` and ``format`` print
    ``[REDACTED]``, so ``print``, logging, ``pprint`` and Rich don't show it.
    Pickling raises ``TypeError``, and msgspec refuses to encode it, so a result
    holding a Secret is never written out whole by accident. Copies share the
    value. Two Secrets are equal when their values are, and a Secret is false
    when its value is empty.
    """

    __slots__ = ("_value",)
    _value: T

    def __init__(self, value: T) -> None:
        object.__setattr__(self, "_value", value)

    def reveal(self) -> T:
        """Return the secret value."""
        return self._value

    def __repr__(self) -> str:
        return f"Secret({_REDACTED!r})"

    def __str__(self) -> str:
        return _REDACTED

    def __format__(self, format_spec: str) -> str:
        return format(_REDACTED, format_spec)

    def __bool__(self) -> bool:
        return bool(self._value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Secret):
            return NotImplemented
        return bool(self._value == other._value)

    def __hash__(self) -> int:
        return hash((Secret, self._value))

    def __setattr__(self, name: str, value: Any) -> NoReturn:
        raise AttributeError("Secret is immutable")

    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError("Secret is immutable")

    def __copy__(self) -> Secret[T]:
        return self

    def __deepcopy__(self, memo: Any) -> Secret[T]:
        return self

    def __reduce_ex__(self, protocol: Any) -> NoReturn:
        raise TypeError(_NOT_SERIALIZABLE)


def as_secret(value: Secret[T] | T) -> Secret[T]:
    """Return ``value`` wrapped in a ``Secret``, unless it already is one."""
    return value if isinstance(value, Secret) else Secret(value)
