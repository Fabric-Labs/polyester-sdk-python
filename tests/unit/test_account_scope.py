import pytest

from polyester.errors import PolyesterValidationError
from polyester.services._scope import (
    ScopedSubAccountMixin,
    resolve_sub_account_from_scope,
    scoped_sub_account_id,
)
from polyester.services.address_book import AsyncAddressBookService
from polyester.services.api_keys import AsyncApiKeysService
from polyester.services.balances import AsyncBalancesService
from polyester.services.deposit import AsyncDepositService
from polyester.services.guard_signer import AsyncGuardSignerService
from polyester.services.internal_transfers import AsyncInternalTransfersService
from polyester.services.orders import AsyncOrdersService
from polyester.services.sub_accounts import AsyncSubAccountsService
from polyester.services.trades import AsyncTradesService
from polyester.services.transfers import AsyncTransfersService
from polyester.services.triggers import AsyncTriggersService
from polyester.services.withdraw import AsyncWithdrawService


class _StubService(ScopedSubAccountMixin):
    _default_sub_account_id = "default-sub"


def test_resolve_sub_account_from_scope_main_uses_default() -> None:
    assert resolve_sub_account_from_scope(account="main", default="sub-123") == "sub-123"
    assert resolve_sub_account_from_scope(account="active", default=None) is None


def test_resolve_sub_account_from_scope_dict() -> None:
    assert resolve_sub_account_from_scope(account={"subaccountId": "abc"}) == "abc"


def test_resolve_sub_account_from_scope_rejects_both() -> None:
    with pytest.raises(PolyesterValidationError):
        resolve_sub_account_from_scope(account="main", sub_account_id="x")


def test_scoped_sub_account_id_prefers_account_scope() -> None:
    assert (
        scoped_sub_account_id(
            account={"subaccountId": "scoped"},
            default="default",
        )
        == "scoped"
    )
    assert scoped_sub_account_id(sub_account_id="legacy", default="default") == "legacy"


def test_scoped_sub_account_mixin_on_service() -> None:
    service = _StubService()
    assert service._resolve_sub_account_id(account="main") == "default-sub"
    assert service._resolve_sub_account_id(account={"subaccountId": "x"}) == "x"


@pytest.mark.parametrize(
    "service_cls",
    [
        AsyncAddressBookService,
        AsyncApiKeysService,
        AsyncBalancesService,
        AsyncDepositService,
        AsyncGuardSignerService,
        AsyncInternalTransfersService,
        AsyncOrdersService,
        AsyncSubAccountsService,
        AsyncTradesService,
        AsyncTransfersService,
        AsyncTriggersService,
        AsyncWithdrawService,
    ],
)
def test_scoped_services_use_shared_resolver(service_cls: type[ScopedSubAccountMixin]) -> None:
    assert issubclass(service_cls, ScopedSubAccountMixin)
    assert "_resolve_sub_account_id" not in service_cls.__dict__
