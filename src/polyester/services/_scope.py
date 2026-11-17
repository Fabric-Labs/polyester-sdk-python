from __future__ import annotations

from typing import Any, Literal

from polyester.codecs.scalars import format_id, parse_account_id
from polyester.errors import PolyesterValidationError

# The account a call acts on:
#
# - ``None`` (unset) or ``"active"``: the client's ``default_sub_account_id``,
#   or the main account when none is configured;
# - ``"main"``: always the main account, whatever the default is;
# - any other string: that sub-account's base58 public ID;
# - a dict naming the sub-account under ``"subaccountId"`` or
#   ``"sub_account_id"``, as a base58 public ID string or the numeric ID.
#
# Only ``None`` means no sub-account. A supplied ID that is not one, ``""`` or
# whitespace included, raises ``PolyesterValidationError``: it is never read as
# the main account or the default. Pass ``account`` or ``sub_account_id``, not
# both.
AccountScope = (
    Literal["main", "active"] | str | dict[str, str] | dict[str, int] | dict[str, str | int]
)


def _public_id(value: str | int, label: str) -> str:
    """A supplied account or sub-account ID as its public string, or refused.

    An ``int`` is the numeric ID, returned as its canonical base58 string:
    downstream parsing reads every string as base58, so ``str(42)`` would
    address ID 175. A string must be a base58 public ID, as
    :func:`parse_account_id` reads it, and is returned as given; ``""`` and
    whitespace are refused. An ID that decodes to 0, which the wire reads as
    unset (the main account), is refused, as is ``bool``.
    """
    if isinstance(value, bool):
        raise PolyesterValidationError(f"{label} must be a base58 string or an integer ID")
    if isinstance(value, int):
        if value == 0:
            raise PolyesterValidationError(f"{label} must be a non-zero ID, not 0")
        try:
            return format_id(value)
        except PolyesterValidationError as exc:
            raise PolyesterValidationError(f"{label} must be a uint64") from exc
    parse_account_id(value, label)
    return value


def default_sub_account_scope(value: str | int | None) -> str | None:
    """Check a client's ``default_sub_account_id`` and return it as a string.

    ``None`` means no default. A string must be a sub-account's base58 public
    ID and is kept as given; an ``int`` is the numeric ID, as its canonical
    public string. ``""``, whitespace, an ID that decodes to 0 (the main
    account on the wire) and any other type, ``bool`` included, are refused,
    so a default that is not an ID can't silently address the main account.
    """
    if value is None:
        return None
    if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)):
        return _public_id(value, "default_sub_account_id")
    raise PolyesterValidationError(
        "default_sub_account_id must be a sub-account ID as a str or int, "
        f"not {type(value).__name__}"
    )


def scoped_sub_account_id(
    *,
    account: AccountScope | None = None,
    sub_account_id: str | int | None = None,
    default: str | None = None,
) -> str | None:
    """Resolve the sub-account of a call from ``account`` (see ``AccountScope``)
    or the legacy ``sub_account_id``. ``None`` means the main account; the
    default applies only when both are unset or ``account`` is ``"active"``."""
    return resolve_sub_account_from_scope(
        account=account,
        sub_account_id=sub_account_id,
        default=default,
    )


def resolve_sub_account_from_scope(
    *,
    account: AccountScope | None = None,
    sub_account_id: str | int | None = None,
    default: str | None = None,
) -> str | None:
    if sub_account_id is not None and account is not None:
        raise PolyesterValidationError("Pass account or sub_account_id, not both")
    if sub_account_id is not None:
        return _public_id(sub_account_id, "sub_account_id")
    if account is None or account == "active":
        return default
    if account == "main":
        return None
    if isinstance(account, dict):
        scoped = account.get("subaccountId")
        if scoped is None:
            scoped = account.get("sub_account_id")
        if scoped is None:
            raise PolyesterValidationError("account dict requires subaccountId or sub_account_id")
        if not isinstance(scoped, (str, int)):
            raise PolyesterValidationError(
                "account subaccountId must be a base58 string or an integer ID"
            )
        return _public_id(scoped, "sub_account_id")
    if isinstance(account, str):
        return _public_id(account, "sub_account_id")
    raise PolyesterValidationError("account must be 'main', 'active', a subaccount id, or a dict")


def resolve_account_id(value: str | int | None, default: str | int | None) -> str:
    """Resolve the public account ID from ``value``, or, when it is ``None``,
    from ``default``.

    A supplied ID is used or refused, never replaced by the default: ``""``,
    whitespace and an ID that decodes to 0, such as ``"1"``, are refused (0
    would name the channel of account 0).
    """
    candidate = value if value is not None else default
    if candidate is None:
        raise PolyesterValidationError(
            "account_id is required; set POLYESTER_ACCOUNT_ID or pass account_id explicitly"
        )
    return _public_id(candidate, "account_id")


def lifecycle_account_fields(msg: Any) -> dict[str, str]:
    fields: dict[str, str] = {}
    smart_account_address = str(getattr(msg, "smart_account_address", "") or "")
    if smart_account_address:
        fields["smart_account_address"] = smart_account_address
    return fields


class ScopedSubAccountMixin:
    """Shared ``account`` / ``sub_account_id`` resolution for trading services."""

    _default_sub_account_id: str | None

    def _resolve_sub_account_id(
        self,
        sub_account_id: str | int | None = None,
        *,
        account: AccountScope | None = None,
    ) -> str | None:
        return scoped_sub_account_id(
            account=account,
            sub_account_id=sub_account_id,
            default=self._default_sub_account_id,
        )
