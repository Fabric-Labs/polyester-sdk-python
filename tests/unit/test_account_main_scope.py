"""``account="main"`` always addresses the main account, whatever default
sub-account the client has; only an unset account and ``"active"`` take the
default."""

import pytest

from polyester.services._scope import resolve_sub_account_from_scope


@pytest.mark.parametrize(
    "account,expected",
    [
        (None, "Bht3tfQZv8E"),
        ("active", "Bht3tfQZv8E"),
        ("main", None),
        ("", None),
    ],
)
def test_main_ignores_the_default_sub_account(account, expected) -> None:
    assert resolve_sub_account_from_scope(account=account, default="Bht3tfQZv8E") == expected


@pytest.mark.parametrize("account", [None, "active", "main", ""])
def test_without_a_default_every_selector_is_the_main_account(account) -> None:
    assert resolve_sub_account_from_scope(account=account, default=None) is None
