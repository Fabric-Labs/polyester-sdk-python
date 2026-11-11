"""alerts.v1.PriceAlertService (devnet): create, list, update, cancel and refusals."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.timestamp_pb2 import Timestamp

from polyester._wire import map_connect_error
from polyester.catalogs import CatalogManager
from polyester.codecs.scalars import format_id
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterResponseContractError,
    PolyesterServerError,
    PolyesterValidationError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.alerts.v1 import price_alerts_pb2 as pb
from polyester.services.alerts import AsyncAlertsService
from polyester.types.money import Price
from tests.unit.support import CaptureUnary

ALERT_ID = 9_000_000_000_000_123
CREATED = datetime(2026, 11, 9, 10, tzinfo=UTC)
FIRED = datetime(2026, 11, 9, 11, tzinfo=UTC)


def _ts(value: datetime) -> Timestamp:
    stamp = Timestamp()
    stamp.FromDatetime(value)
    return stamp


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8},
                {"symbol": "ETH-USDT", "symbol_id": 2, "base_quantity_scale": 8},
            ]
        }
    )
    return catalogs


def _service() -> AsyncAlertsService:
    return AsyncAlertsService(MagicMock(), _catalogs())


def _alert(**overrides: Any) -> pb.PriceAlert:
    fields: dict[str, Any] = {
        "alert_id": ALERT_ID,
        "symbol_id": 1,
        "direction": pb.BELOW,
        "price_source": pb.INDEX_PRICE,
        "price_ticks": 90_000 * 10**9,
        "reference_price_ticks": 95_123_500_000_000,
        "armed": True,
        "status": pb.ACTIVE,
        "channels": [pb.IN_APP, pb.TELEGRAM],
        "revision": 1,
        "created_at": _ts(CREATED),
        "updated_at": _ts(CREATED),
    }
    fields.update(overrides)
    return pb.PriceAlert(**fields)


# --- create -----------------------------------------------------------------------------------


async def test_create_resolves_the_market_and_encodes_the_alert() -> None:
    capture = CaptureUnary(pb.CreateAlertResponse(alert=_alert()))
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        alert = await _service().create(
            symbol="BTC-USDT",
            direction="below",
            price="90000",
            channels=["in_app", "telegram"],
            idempotency_key="run-7:tool-2",
        )
    request = capture.request
    assert isinstance(request, pb.CreateAlertRequest)
    assert request.symbol_id == 1
    assert request.direction == pb.BELOW
    assert request.price_ticks == 90_000 * 10**9
    # Unset: the server picks the index price where the market has one.
    assert request.price_source == pb.PRICE_SOURCE_UNSPECIFIED
    assert list(request.channels) == [pb.IN_APP, pb.TELEGRAM]
    assert request.idempotency_key == "run-7:tool-2"

    assert alert.alert_id == format_id(ALERT_ID)
    assert alert.symbol == "BTC-USDT"
    assert alert.symbol_id == 1
    assert alert.direction == "below"
    assert alert.price_source == "index"
    assert alert.price == Price.from_ticks(90_000 * 10**9, symbol="BTC-USDT")
    assert alert.price.as_decimal() == Decimal("90000")
    assert alert.reference_price is not None
    assert alert.reference_price.as_decimal() == Decimal("95123.5")
    assert alert.armed is True
    assert alert.status == "active"
    assert alert.channels == ["in_app", "telegram"]
    assert alert.revision == 1
    assert alert.created_at == CREATED
    assert alert.triggered_at is None
    assert alert.triggered_price is None


def test_unknown_and_unset_enums_read_unspecified() -> None:
    from polyester.codecs.decode.alerts import price_alert_from_proto

    alert = price_alert_from_proto(
        _alert(direction=0, price_source=0, status=99, channels=[pb.IN_APP, 7]), None
    )
    assert alert.direction == "unspecified"
    assert alert.price_source == "unspecified"
    assert alert.status == "unspecified"
    assert alert.channels == ["in_app", "unspecified"]
    assert alert.symbol == ""


async def test_create_accepts_symbol_id_price_type_and_price_source() -> None:
    capture = CaptureUnary(pb.CreateAlertResponse(alert=_alert(price_source=pb.LAST_PRICE)))
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        await _service().create(
            symbol_id=2,
            direction="above",
            price=Price.from_ticks(3_000 * 10**9),
            price_source="last",
            channels=["in_app"],
        )
    assert capture.request.symbol_id == 2
    assert capture.request.direction == pb.ABOVE
    assert capture.request.price_ticks == 3_000 * 10**9
    assert capture.request.price_source == pb.LAST_PRICE
    assert capture.request.idempotency_key == ""


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"direction": "sideways"}, "direction"),
        ({"price": "0"}, "price"),
        ({"price": "-1"}, "price"),
        ({"price": 90000}, "price"),
        ({"channels": []}, "channels"),
        ({"channels": ["in_app", "in_app"]}, "channels"),
        ({"channels": ["in_app", "telegram", "email"]}, "channels"),
        ({"channels": ["email"]}, "channel"),
        ({"price_source": "last_price"}, "price_source"),
        ({"idempotency_key": "has space"}, "idempotency_key"),
        ({"idempotency_key": "k" * 129}, "idempotency_key"),
        ({"symbol": "NOPE-USDT"}, "NOPE-USDT"),
    ],
)
async def test_create_refuses_bad_input_before_sending(kwargs: dict, match: str) -> None:
    capture = CaptureUnary(pb.CreateAlertResponse(alert=_alert()))
    args: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "direction": "below",
        "price": "90000",
        "channels": ["in_app"],
    }
    args.update(kwargs)
    with (
        patch("polyester.services.alerts.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match=match),
    ):
        await _service().create(**args)
    assert capture.calls == 0


# --- list -------------------------------------------------------------------------------------


async def test_list_encodes_filters_and_reads_the_page() -> None:
    fired = _alert(
        alert_id=ALERT_ID + 1,
        symbol_id=2,
        status=pb.TRIGGERED,
        triggered_at=_ts(FIRED),
        triggered_price_ticks=2_999_500_000_000,
    )
    capture = CaptureUnary(pb.ListAlertsResponse(alerts=[fired], next_page_token="t1"))
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        page = await _service().list(
            statuses=["triggered", "active"], symbol="ETH-USDT", limit=200, page_token="t0"
        )
    request = capture.request
    assert isinstance(request, pb.ListAlertsRequest)
    assert list(request.statuses) == [pb.TRIGGERED, pb.ACTIVE]
    assert request.symbol_id == 2
    assert request.limit == 200
    assert request.page_token == "t0"
    assert page.next_page_token == "t1"
    (alert,) = page.alerts
    assert alert.symbol == "ETH-USDT"
    assert alert.status == "triggered"
    assert alert.triggered_at == FIRED
    assert alert.triggered_price is not None
    assert alert.triggered_price.as_decimal() == Decimal("2999.5")


async def test_list_defaults_to_every_state_and_market() -> None:
    capture = CaptureUnary(pb.ListAlertsResponse())
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        page = await _service().list()
    assert list(capture.request.statuses) == []
    assert capture.request.symbol_id == 0
    assert capture.request.limit == 0
    assert page.alerts == []
    assert page.next_page_token == ""


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"limit": 201}, "limit"),
        ({"statuses": ["armed"]}, "status"),
        ({"statuses": ["active", "active"]}, "statuses"),
    ],
)
async def test_list_refuses_bad_filters(kwargs: dict, match: str) -> None:
    with pytest.raises(PolyesterValidationError, match=match):
        await _service().list(**kwargs)


class _Pages:
    def __init__(self, pages: list[pb.ListAlertsResponse]) -> None:
        self.pages = pages
        self.requests: list[pb.ListAlertsRequest] = []

    async def __call__(self, transport, client_cls, call, request, decoder, **_):  # type: ignore[no-untyped-def]
        copy = pb.ListAlertsRequest()
        copy.CopyFrom(request)
        self.requests.append(copy)
        return decoder(self.pages[len(self.requests) - 1])


async def test_iter_alerts_walks_every_page_with_the_same_filters() -> None:
    pages = _Pages(
        [
            pb.ListAlertsResponse(alerts=[_alert(alert_id=1)], next_page_token="t1"),
            pb.ListAlertsResponse(alerts=[_alert(alert_id=2), _alert(alert_id=3)]),
        ]
    )
    with patch("polyester.services.alerts.unary_auth_decoded", pages):
        ids = [
            alert.alert_id
            async for alert in _service().iter_alerts(statuses=["active"], symbol="BTC-USDT")
        ]
    assert ids == [format_id(1), format_id(2), format_id(3)]
    assert [r.page_token for r in pages.requests] == ["", "t1"]
    assert all(list(r.statuses) == [pb.ACTIVE] and r.symbol_id == 1 for r in pages.requests)


async def test_iter_alerts_stops_on_a_repeated_page_token() -> None:
    pages = _Pages(
        [
            pb.ListAlertsResponse(alerts=[_alert(alert_id=1)], next_page_token="t1"),
            pb.ListAlertsResponse(alerts=[_alert(alert_id=2)], next_page_token="t1"),
        ]
    )
    with (
        patch("polyester.services.alerts.unary_auth_decoded", pages),
        pytest.raises(PolyesterResponseContractError, match="page token"),
    ):
        [alert async for alert in _service().iter_alerts()]


# --- update -----------------------------------------------------------------------------------


async def test_update_sends_only_the_fields_it_sets_and_reads_the_outcome() -> None:
    capture = CaptureUnary(
        pb.UpdateAlertResponse(
            alert=_alert(price_ticks=91_000 * 10**9, revision=2), outcome=pb.APPLIED
        )
    )
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        result = await _service().update(
            alert_id=format_id(ALERT_ID),
            expected_revision=1,
            price="91000",
            idempotency_key="run-7:tool-3",
        )
    request = capture.request
    assert isinstance(request, pb.UpdateAlertRequest)
    assert request.alert_id == ALERT_ID
    assert request.expected_revision == 1
    assert list(request.update_mask.paths) == ["price_ticks"]
    assert request.update.price_ticks == 91_000 * 10**9
    assert request.idempotency_key == "run-7:tool-3"
    assert result.outcome == "applied"
    assert result.alert.revision == 2
    assert result.alert.price.as_decimal() == Decimal("91000")


async def test_update_with_every_field() -> None:
    capture = CaptureUnary(pb.UpdateAlertResponse(alert=_alert(), outcome=pb.UNCHANGED))
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        result = await _service().update(
            alert_id=ALERT_ID,
            expected_revision=4,
            direction="above",
            price="100000",
            channels=["telegram"],
        )
    request = capture.request
    assert list(request.update_mask.paths) == ["direction", "price_ticks", "channels"]
    assert request.update.direction == pb.ABOVE
    assert list(request.update.channels) == [pb.TELEGRAM]
    assert result.outcome == "unchanged"


async def test_update_without_fields_sends_an_empty_mask_to_set_a_fired_alert_again() -> None:
    capture = CaptureUnary(pb.UpdateAlertResponse(alert=_alert(revision=4), outcome=pb.REPLAYED))
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        result = await _service().update(
            alert_id=ALERT_ID, expected_revision=3, idempotency_key="run-7:tool-4"
        )
    request = capture.request
    # Both are required: they must be on the wire even when empty.
    assert request.HasField("update")
    assert request.HasField("update_mask")
    assert list(request.update_mask.paths) == []
    decoded = pb.UpdateAlertRequest.FromString(request.SerializeToString())
    assert decoded.HasField("update") and decoded.HasField("update_mask")
    assert result.outcome == "replayed"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"expected_revision": 0}, "expected_revision"),
        ({"alert_id": 0}, "alert_id"),
        ({"channels": []}, "channels"),
        ({"price": "0"}, "price"),
        ({"idempotency_key": "bad key"}, "idempotency_key"),
    ],
)
async def test_update_refuses_bad_input(kwargs: dict, match: str) -> None:
    args: dict[str, Any] = {"alert_id": ALERT_ID, "expected_revision": 1}
    args.update(kwargs)
    with pytest.raises(PolyesterValidationError, match=match):
        await _service().update(**args)


# --- cancel -----------------------------------------------------------------------------------


async def test_cancel_sends_the_alert_id_and_reads_the_alert() -> None:
    capture = CaptureUnary(pb.CancelAlertResponse(alert=_alert(status=pb.CANCELLED)))
    with patch("polyester.services.alerts.unary_auth_decoded", capture):
        alert = await _service().cancel(alert_id=format_id(ALERT_ID))
    assert isinstance(capture.request, pb.CancelAlertRequest)
    assert capture.request.alert_id == ALERT_ID
    assert alert.status == "cancelled"


# --- refusals ---------------------------------------------------------------------------------


def _alert_error(code: int, connect_code: Code = Code.FAILED_PRECONDITION) -> BaseException:
    return map_connect_error(
        ConnectError(connect_code, "refused", details=[pb.ErrorDetail(code=code)])
    )


def test_subaccount_key_is_refused_as_an_auth_error() -> None:
    err = _alert_error(pb.SUBACCOUNT_KEY_REFUSED, Code.PERMISSION_DENIED)
    assert isinstance(err, PolyesterAuthError)
    assert err.code == "SUBACCOUNT_KEY_REFUSED"
    assert err.status_code == 403
    assert not is_retryable_error(err)


@pytest.mark.parametrize(
    ("code", "connect_code"),
    [
        (pb.PRICE_UNAVAILABLE, Code.UNAVAILABLE),
        (pb.SERVICE_UNAVAILABLE, Code.UNAVAILABLE),
    ],
)
def test_unavailable_refusals_are_retryable_and_changed_nothing(
    code: int, connect_code: Code
) -> None:
    err = _alert_error(code, connect_code)
    assert isinstance(err, PolyesterServerError)
    assert err.code == pb.ErrorCode.Name(code)
    assert is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


@pytest.mark.parametrize(
    ("code", "connect_code"),
    [
        (pb.ALERT_NOT_FOUND, Code.NOT_FOUND),
        (pb.UNKNOWN_SYMBOL, Code.INVALID_ARGUMENT),
        (pb.PRICE_SOURCE_UNSUPPORTED, Code.FAILED_PRECONDITION),
        (pb.ALERT_LIMIT_REACHED, Code.FAILED_PRECONDITION),
        (pb.REVISION_CONFLICT, Code.ABORTED),
        (pb.ALERT_CANCELLED, Code.FAILED_PRECONDITION),
        (pb.ALERT_TRIGGERED, Code.FAILED_PRECONDITION),
        (pb.IDEMPOTENCY_CONFLICT, Code.ALREADY_EXISTS),
        (pb.ALERT_UPDATE_LIMIT_REACHED, Code.FAILED_PRECONDITION),
    ],
)
def test_other_refusals_keep_their_code_and_are_not_retryable(
    code: int, connect_code: Code
) -> None:
    err = _alert_error(code, connect_code)
    assert isinstance(err, PolyesterApiError)
    assert not isinstance(err, PolyesterAuthError)
    assert err.code == pb.ErrorCode.Name(code)
    assert not is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


def test_sync_client_declares_the_alerts_view() -> None:
    from polyester._sync_services import SyncAlertsService

    declared = set(vars(SyncAlertsService))
    assert {"create", "list", "iter_alerts", "update", "cancel"} <= declared
