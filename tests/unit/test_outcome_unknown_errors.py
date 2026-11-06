"""Retry and outcome classification of structured order and auth error codes."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import (
    AUTH_TEMPORARILY_UNAVAILABLE,
    PolyesterApiError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.orders.v1 import orders_pb2

_OUTCOME_UNKNOWN_CODES = sorted(
    value for name, value in orders_pb2.ErrorCode.items() if name.endswith("_OUTCOME_UNKNOWN")
)


def test_outcome_unknown_codes_include_known_mutations() -> None:
    names = {orders_pb2.ErrorCode.Name(code) for code in _OUTCOME_UNKNOWN_CODES}
    assert {
        "ERROR_CODE_ORDER_CANCEL_OUTCOME_UNKNOWN",
        "ERROR_CODE_ORDER_MODIFY_OUTCOME_UNKNOWN",
        "ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN",
        "ERROR_CODE_TRIGGER_CREATE_OUTCOME_UNKNOWN",
        "ERROR_CODE_TRIGGER_CONTROL_OUTCOME_UNKNOWN",
    } <= names


@pytest.mark.parametrize("code", _OUTCOME_UNKNOWN_CODES, ids=orders_pb2.ErrorCode.Name)
def test_outcome_unknown_order_codes_are_ambiguous_and_not_retryable(code: int) -> None:
    # A blind retry could apply the mutation twice (for example, place an order
    # twice). Callers must read back first, so these are never retryable.
    mapped = map_connect_error(
        ConnectError(
            Code.DEADLINE_EXCEEDED,
            "not confirmed in time",
            details=[orders_pb2.ErrorDetail(code=code)],
        )
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == orders_pb2.ErrorCode.Name(code)
    assert not is_retryable_error(mapped)
    assert mutation_outcome_unknown(mapped)


def test_future_outcome_unknown_code_is_classified_by_suffix() -> None:
    err = PolyesterApiError("not confirmed", code="ERROR_CODE_ORDER_FUTURE_OUTCOME_UNKNOWN")
    assert not is_retryable_error(err)
    assert mutation_outcome_unknown(err)


def test_auth_temporarily_unavailable_is_retryable_and_changed_nothing() -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.UNAVAILABLE,
            "try again",
            details=[auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TEMPORARILY_UNAVAILABLE)],
        )
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == AUTH_TEMPORARILY_UNAVAILABLE
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


@pytest.mark.parametrize(
    "detail",
    [
        orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_TRIGGER_WOULD_TRIGGER_IMMEDIATELY),
        orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_ORDER_ALREADY_TERMINAL),
        auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_INTERNAL_ERROR),
    ],
    ids=["would_trigger_immediately", "already_terminal", "auth_internal"],
)
def test_definite_api_errors_are_neither_retryable_nor_ambiguous(detail: object) -> None:
    mapped = map_connect_error(
        ConnectError(Code.FAILED_PRECONDITION, "refused", details=[detail])  # type: ignore[list-item]
    )
    assert type(mapped) is PolyesterApiError
    assert not is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


@pytest.mark.parametrize("code", _OUTCOME_UNKNOWN_CODES, ids=orders_pb2.ErrorCode.Name)
@pytest.mark.parametrize("status", [504, 503])
async def test_rest_outcome_unknown_matches_connect(httpserver, code: int, status: int) -> None:
    from tests.unit.test_auth_error_codes import _rest_error

    name = orders_pb2.ErrorCode.Name(code)
    mapped = await _rest_error(
        httpserver,
        status,
        {"code": name.removeprefix("ERROR_CODE_"), "detail": "read back first"},
    )
    assert (type(mapped), is_retryable_error(mapped), mutation_outcome_unknown(mapped)) == (
        PolyesterApiError,
        False,
        True,
    )
    assert mapped.code == name
    assert mapped.problem.status == status
    assert str(mapped) == "read back first"


@pytest.mark.parametrize(
    "body,content_type",
    [
        ("<html>Gateway Timeout</html>", "text/html"),
        ('{"code":"UNKNOWN_GATEWAY_FAILURE"}', "application/problem+json"),
    ],
)
async def test_unrecognised_rest_504_remains_ambiguous_transport_failure(
    httpserver,
    body: str,
    content_type: str,
) -> None:
    from polyester.errors import PolyesterServerError
    from polyester.services.market_data import AsyncMarketDataService
    from polyester.transport import TransportConfig, TransportFactory
    from tests.unit.test_auth_error_codes import SPOT_CONFIG_PATH

    httpserver.expect_request(SPOT_CONFIG_PATH, method="POST").respond_with_data(
        body,
        status=504,
        content_type=content_type,
    )
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        with pytest.raises(PolyesterServerError) as caught:
            await AsyncMarketDataService(transport).get_spot_config()
    finally:
        await transport.aclose()
    assert not is_retryable_error(caught.value)
    assert mutation_outcome_unknown(caught.value)


@pytest.mark.parametrize(
    "status,body,content_type",
    [
        (504, '{"code":"ORDER_CREATE_OUTCOME_UNKNOWN"}', "application/problem+json"),
        (504, "<html>Gateway Timeout</html>", "text/html"),
        (
            503,
            '{"code":"unavailable","details":[{"type":"orders.v1.ErrorDetail","value":"CK8C"}]}',
            "application/json",
        ),
        (
            504,
            '{"code":"deadline_exceeded","details":[{"type":"orders.v1.ErrorDetail","value":"CK8C"}]}',
            "application/json",
        ),
    ],
)
@pytest.mark.parametrize("client_order_id", [None, "reconcile-first"])
async def test_order_create_never_resends_unknown_outcome(
    httpserver, status, body, content_type, client_order_id
) -> None:
    from polyester import AsyncPolyester, Quantity

    calls = []

    def respond(request):
        from werkzeug.wrappers import Response

        calls.append(request.path)
        return Response(body, status=status, content_type=content_type)

    path = "/orders.v1.OrdersService/CreateOrder"
    httpserver.expect_request(path, method="POST").respond_with_handler(respond)
    client = AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key_id="ak_test",
        api_private_key="01" * 32,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
        {
            "pairs": [
                {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8},
            ]
        }
    )
    try:
        with pytest.raises(Exception) as caught:
            await client.orders.create(
                symbol="BTC-USDT",
                side="buy",
                order_type="market",
                qty=Quantity.from_scaled(1, scale=8),
                client_order_id=client_order_id,
            )
    finally:
        await client.aclose()
    assert mutation_outcome_unknown(caught.value)
    assert calls == [path]
    assert not is_retryable_error(caught.value)
    if content_type != "text/html":
        assert type(caught.value) is PolyesterApiError
