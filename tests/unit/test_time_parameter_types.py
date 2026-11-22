"""Time parameters take a timezone-aware ``datetime`` and nothing else.

An int (seconds or milliseconds?), a float, an ISO string or a naive
datetime (local time or UTC?) used to reach protobuf's ``FromDatetime``, which
raised a bare ``TypeError`` naming no parameter, or was silently read as UTC.
Every public time parameter now refuses them with
:class:`PolyesterValidationError` naming the parameter, the expected type and
the type received, before any catalog wait or request.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, Polyester
from polyester.codecs import proto_helpers, scalars
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from tests.hardening_support import make_test_credentials

_CREDS = make_test_credentials()
_AWARE = datetime(2026, 11, 22, 10, tzinfo=UTC)
_LATER = _AWARE + timedelta(hours=1)
_SPOT_CONFIG = {
    "pairs": [
        {
            "symbol": "BTC-USDT",
            "symbol_id": 1,
            "base_asset": "BTC",
            "base_quantity_scale": 8,
            "quote_quantity_scale": 6,
        }
    ],
    "assets": [{"asset": "BTC", "market_data_volume_scale": 8}],
}

# (value, the type the message names)
_WRONG_TYPES: list[tuple[Any, str]] = [
    (1_763_805_600, "int"),
    (1_763_805_600_000, "int"),
    (1_763_805_600.5, "float"),
    ("2026-11-22T10:00:00Z", "str"),
    (datetime(2026, 11, 22, 10), "a naive datetime"),
    (_AWARE.date(), "date"),
    (True, "bool"),
]

Call = Callable[[Any, str, Any], Any]


def _market(method: str) -> Call:
    def call(client: Any, name: str, value: Any) -> Any:
        return getattr(client.market_data, method)(symbol="BTC-USDT", **{name: value})

    return call


def _heatmap(client: Any, name: str, value: Any) -> Any:
    return client.heatmap.get(symbol="BTC-USDT", **{name: value})


def _changes(client: Any, name: str, value: Any) -> Any:
    return client.changelog.list_changes(**{name: value})


def _activity(client: Any, name: str, value: Any) -> Any:
    return client.sub_accounts.list_account_activity(**{name: value})


def _export(client: Any, name: str, value: Any) -> Any:
    times = {"start_time": _AWARE, "end_time": _LATER, name: value}
    return client.statements.create_export(idempotency_key="export-1", **times)


def _since(method: str) -> Call:
    def call(client: Any, name: str, value: Any) -> Any:
        return getattr(client.changelog, method)(value)

    return call


# (call, parameter, None allowed)
_TIME_PARAMETERS: dict[str, tuple[Call, str, bool]] = {}
for _method in ("get_candles", "get_candles_columns", "get_trades"):
    for _name in ("start_time", "end_time"):
        _TIME_PARAMETERS[f"market_data.{_method}:{_name}"] = (_market(_method), _name, True)
for _name in ("start_time", "end_time"):
    _TIME_PARAMETERS[f"heatmap.get:{_name}"] = (_heatmap, _name, True)
    _TIME_PARAMETERS[f"changelog.list_changes:{_name}"] = (_changes, _name, True)
    _TIME_PARAMETERS[f"sub_accounts.list_account_activity:{_name}"] = (_activity, _name, True)
    _TIME_PARAMETERS[f"statements.create_export:{_name}"] = (_export, _name, False)
for _method in ("breaking_changes_since", "action_required_since"):
    _TIME_PARAMETERS[f"changelog.{_method}:since"] = (_since(_method), "since", False)

_REFUSALS = [
    pytest.param(key, value, shown, id=f"{key}-{shown}-{value!r}")
    for key in _TIME_PARAMETERS
    for value, shown in _WRONG_TYPES
] + [
    pytest.param(key, None, "None", id=f"{key}-None")
    for key, (_, _, none_allowed) in _TIME_PARAMETERS.items()
    if not none_allowed
]


def _message(name: str, shown: str) -> str:
    return rf"^{name} must be a timezone-aware datetime, not {shown}$"


def _recording(httpserver: HTTPServer) -> list[Request]:
    seen: list[Request] = []

    def handler(request: Request) -> Response:
        seen.append(request)
        return Response("{}", status=500, content_type="application/json")

    httpserver.expect_request("").respond_with_handler(handler)
    return seen


def _catalog_wait(waits: list[str]) -> Callable[[], Awaitable[None]]:
    async def wait() -> None:
        waits.append("waited")
        await asyncio.Event().wait()

    return wait


@pytest.mark.parametrize(("key", "value", "shown"), _REFUSALS)
async def test_async_time_parameters_refuse_other_types_before_sending(
    httpserver: HTTPServer, key: str, value: Any, shown: str
) -> None:
    call, name, _ = _TIME_PARAMETERS[key]
    seen = _recording(httpserver)
    waits: list[str] = []
    async with AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    ) as client:
        # A catalog wait that never ends: the refusal comes before it.
        client.market_data._wait_for_catalogs = _catalog_wait(waits)
        client.heatmap._wait_for_catalogs = _catalog_wait(waits)
        with pytest.raises(PolyesterValidationError, match=_message(name, shown)):
            await asyncio.wait_for(call(client, name, value), 5)
    assert waits == []
    assert seen == []
    assert httpserver.log == []


@pytest.mark.parametrize(("key", "value", "shown"), _REFUSALS)
def test_sync_time_parameters_refuse_other_types_before_sending(
    httpserver: HTTPServer, key: str, value: Any, shown: str
) -> None:
    call, name, _ = _TIME_PARAMETERS[key]
    seen = _recording(httpserver)
    with Polyester(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    ) as client:
        client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
        with pytest.raises(PolyesterValidationError, match=_message(name, shown)):
            call(client, name, value)
    assert seen == []
    assert httpserver.log == []


def _serve_market(httpserver: HTTPServer) -> list[Any]:
    """Answer the three market-data calls with empty pages, keeping each request."""
    sent: list[Any] = []
    routes = {
        "GetCandles": (marketdata_pb2.GetCandlesRequest, marketdata_pb2.GetCandlesResponse),
        "GetCandlesColumns": (
            marketdata_pb2.GetCandlesRequest,
            marketdata_pb2.GetCandlesColumnsResponse,
        ),
        "GetTrades": (marketdata_pb2.GetTradesRequest, marketdata_pb2.GetTradesResponse),
    }
    for method, (request_type, response_type) in routes.items():

        def handler(request: Request, request_type=request_type, response_type=response_type):
            sent.append(request_type.FromString(request.get_data()))
            return Response(
                response_type().SerializeToString(),
                status=200,
                content_type="application/proto",
            )

        httpserver.expect_request(
            f"/marketdata.v1.MarketDataService/{method}", method="POST"
        ).respond_with_handler(handler)
    return sent


_PLUS_TWO = timezone(timedelta(hours=2))


def _check_sent(sent: list[Any]) -> None:
    assert len(sent) == 3
    for request in sent:
        assert request.symbol_id == 1
        assert request.start_time.seconds == int(_AWARE.timestamp())
        # 13:00 at +02:00 is 11:00 UTC: an offset is kept, not dropped.
        assert request.end_time.seconds == int(_LATER.timestamp())
        assert request.end_time.nanos == 250_000_000


_LATER_AT_PLUS_TWO = (_LATER + timedelta(milliseconds=250)).astimezone(_PLUS_TWO)


async def test_async_market_data_sends_aware_datetimes(httpserver: HTTPServer) -> None:
    sent = _serve_market(httpserver)
    async with AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"), hydrate_catalogs=False
    ) as client:
        client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
        for method in ("get_candles", "get_candles_columns", "get_trades"):
            await getattr(client.market_data, method)(
                symbol="BTC-USDT", start_time=_AWARE, end_time=_LATER_AT_PLUS_TWO
            )
    _check_sent(sent)


def test_sync_market_data_sends_aware_datetimes(httpserver: HTTPServer) -> None:
    sent = _serve_market(httpserver)
    with Polyester(api_url=httpserver.url_for("").rstrip("/"), hydrate_catalogs=False) as client:
        client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
        for method in ("get_candles", "get_candles_columns", "get_trades"):
            getattr(client.market_data, method)(
                symbol="BTC-USDT", start_time=_AWARE, end_time=_LATER_AT_PLUS_TWO
            )
    _check_sent(sent)


# --- the shared conversion ------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "shown"), _WRONG_TYPES + [(None, "None")], ids=repr)
def test_shared_conversion_refuses_other_types(value: Any, shown: str) -> None:
    for convert in (
        scalars.aware_datetime,
        scalars.datetime_to_timestamp_dict,
        proto_helpers.datetime_to_timestamp,
    ):
        with pytest.raises(PolyesterValidationError, match=_message("when", shown)):
            convert(value, "when")


def test_shared_conversion_is_exact_for_aware_datetimes() -> None:
    value = datetime(1969, 12, 31, 23, 59, 59, 999_999, tzinfo=UTC)
    assert scalars.aware_datetime(value, "when") is value
    timestamp = proto_helpers.datetime_to_timestamp(value, "when")
    assert (timestamp.seconds, timestamp.nanos) == (-1, 999_999_000)
    parts = scalars.datetime_to_timestamp_dict(value, "when")
    assert parts == {"seconds": -1, "nanos": 999_999_000}


@pytest.mark.parametrize(
    "value",
    [
        datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
        datetime.max.replace(tzinfo=timezone(timedelta(hours=-1))),
    ],
    ids=["before year 1 in UTC", "after year 9999 in UTC"],
)
def test_shared_conversion_refuses_a_time_outside_the_utc_range(value: datetime) -> None:
    with pytest.raises(PolyesterValidationError, match="^when is outside the supported range"):
        proto_helpers.datetime_to_timestamp(value, "when")


async def test_statement_export_near_year_9999_is_sent_not_overflowed(
    httpserver: HTTPServer,
) -> None:
    seen = _recording(httpserver)
    start = datetime(9999, 12, 31, tzinfo=UTC)
    async with AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    ) as client:
        # The window check used to add 366 days to start_time: OverflowError.
        with pytest.raises(Exception) as caught:
            await client.statements.create_export(
                start_time=start, end_time=start + timedelta(hours=1), idempotency_key="k"
            )
    assert not isinstance(caught.value, OverflowError | PolyesterValidationError)
    assert len(seen) == 1


# --- integer time parameters with a unit ----------------------------------------------------------

_NOT_INTEGERS: list[tuple[Any, str]] = [
    (1_763_805_600.0, "float"),
    ("1763805600", "'1763805600'"),
    (_AWARE, "datetime"),
    (True, "bool"),
]


def _from_ts_sec(client: Any, value: Any) -> Any:
    return client.heatmap.get(symbol="BTC-USDT", from_ts_sec=value)


def _analytics(method: str, name: str, **fixed: Any) -> Callable[[Any, Any], Any]:
    def call(client: Any, value: Any) -> Any:
        return getattr(client.chain_analytics, method)(range="1d", **fixed, **{name: value})

    return call


_INTEGER_TIME_PARAMETERS: dict[str, tuple[Callable[[Any, Any], Any], str]] = {
    "heatmap.get:from_ts_sec": (_from_ts_sec, "from_ts_sec"),
}
for _name in ("start_ts_sec", "end_ts_sec"):
    _INTEGER_TIME_PARAMETERS[f"get_zipped_asset_supply:{_name}"] = (
        _analytics("get_zipped_asset_supply", _name, zipped_asset_id=1),
        _name,
    )
    _INTEGER_TIME_PARAMETERS[f"get_zipped_asset_supply_group:{_name}"] = (
        _analytics("get_zipped_asset_supply_group", _name, group_id="g"),
        _name,
    )
    _INTEGER_TIME_PARAMETERS[f"get_unified_asset_balances:{_name}"] = (
        _analytics("get_unified_asset_balances", _name, asset_id=1),
        _name,
    )


@pytest.mark.parametrize(("value", "shown"), _NOT_INTEGERS + [(-1, None), (2**64, None)], ids=repr)
@pytest.mark.parametrize("key", list(_INTEGER_TIME_PARAMETERS))
async def test_integer_time_parameters_refuse_other_values_before_sending(
    httpserver: HTTPServer, key: str, value: Any, shown: str | None
) -> None:
    call, name = _INTEGER_TIME_PARAMETERS[key]
    seen = _recording(httpserver)
    waits: list[str] = []
    expected = rf"^{name} must be an integer, not {shown}$" if shown else rf"^{name} .*outside"
    async with AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"), hydrate_catalogs=False
    ) as client:
        client.heatmap._wait_for_catalogs = _catalog_wait(waits)
        with pytest.raises(PolyesterValidationError, match=expected):
            await asyncio.wait_for(call(client, value), 5)
    assert waits == []
    assert seen == []
