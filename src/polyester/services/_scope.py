from __future__ import annotations

from polyester.errors import PolyesterValidationError


def resolve_sub_account_id(value: str | None, default: str | None) -> str | None:
    if value == "":
        return None
    return value if value is not None else default


def resolve_account_id(value: str | int | None, default: str | int | None) -> str:
    if value is not None and value != "":
        return str(value)
    if default is not None and default != "":
        return str(default)
    raise PolyesterValidationError(
        "account_id is required; set POLYESTER_ACCOUNT_ID or pass account_id explicitly"
    )
