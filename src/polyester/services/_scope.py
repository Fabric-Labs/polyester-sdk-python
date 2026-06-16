from __future__ import annotations


def resolve_sub_account_id(value: str | None, default: str | None) -> str | None:
    if value == "":
        return None
    return value if value is not None else default
