"""AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED raises PolyesterSubaccountOwnerRoleLockedError,
from a Connect failed_precondition with an AuthErrorDetail and from a REST 412."""

from __future__ import annotations

import json

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from pytest_httpserver import HTTPServer

from polyester import (
    AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED,
    PolyesterApiError,
    PolyesterSubaccountOwnerRoleLockedError,
    auth_error_code,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester._wire import map_connect_error
from polyester.gen.auth.v1 import auth_pb2
from polyester.services.market_data import AsyncMarketDataService
from polyester.transport import TransportConfig, TransportFactory


def test_connect_failed_precondition_with_auth_detail_is_typed() -> None:
    detail = auth_pb2.AuthErrorDetail(
        code=auth_pb2.AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED,
        message="the owner's role cannot change",
    )
    mapped = map_connect_error(
        ConnectError(Code.FAILED_PRECONDITION, "failed precondition", details=[detail])
    )

    assert isinstance(mapped, PolyesterSubaccountOwnerRoleLockedError)
    # Existing PolyesterApiError handling and code checks keep working.
    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED
    assert auth_error_code(mapped) == AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED
    assert str(mapped) == "the owner's role cannot change"
    assert mapped.status_code == 412
    assert not is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


def test_other_auth_detail_codes_stay_plain_api_errors() -> None:
    detail = auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_INVALID_REQUEST)
    mapped = map_connect_error(ConnectError(Code.INVALID_ARGUMENT, "bad", details=[detail]))

    assert type(mapped) is PolyesterApiError
    assert mapped.code == "AUTH_INVALID_REQUEST"


@pytest.mark.asyncio
@pytest.mark.parametrize("content_type", ["application/problem+json", "application/json"])
async def test_rest_412_problem_body_is_typed(httpserver: HTTPServer, content_type: str) -> None:
    # REST answers the refusal as HTTP 412 with the auth code in the problem body.
    httpserver.expect_request(
        "/marketdata.v1.MarketDataService/GetSpotConfig", method="POST"
    ).respond_with_data(
        json.dumps(
            {
                "status": 412,
                "code": AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED,
                "title": "Subaccount Owner Role Locked",
            }
        ),
        status=412,
        content_type=content_type,
    )
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        with pytest.raises(PolyesterSubaccountOwnerRoleLockedError) as caught:
            await AsyncMarketDataService(transport).get_spot_config()
    finally:
        await transport.aclose()

    assert caught.value.code == AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED
    assert caught.value.status_code == 412
    assert not is_retryable_error(caught.value)
