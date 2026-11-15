"""TWAP, ladder and dead-man-switch inputs the published contract refuses are
refused locally with PolyesterValidationError, before anything is sent; a
wrong type is never a raw TypeError. The limits come from the contract's
validation rules, and these tests break if the contract changes them."""

from __future__ import annotations

from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.codecs.orders import (
    CANCEL_ALL_AFTER_MAX_TIMEOUT_SEC,
    CANCEL_ALL_AFTER_MIN_TIMEOUT_SEC,
    cancel_all_after_to_proto,
)
from polyester.codecs.triggers import (
    LADDER_LEVELS_MAX,
    LADDER_LEVELS_MIN,
    TWAP_DURATION_MS_MIN,
    TWAP_SLICE_INTERVAL_MS_MIN,
    create_trigger_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

INT64_MAX = 2**63 - 1
WRONG_TYPES: list[Any] = [60000.0, 5.0, True, False, "60000", b"5", None]


def _twap(**overrides: Any) -> triggers_pb2.CreateTriggerRequest:
    kwargs: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "twap",
        "side": "buy",
        "qty": "0.0005",
        "order_type": "market",
        "quantity_scale": 8,
        "twap_duration_ms": 60_000,
        "twap_slice_interval_ms": 1_000,
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)


def _ladder(**overrides: Any) -> triggers_pb2.CreateTriggerRequest:
    kwargs: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "ladder",
        "side": "buy",
        "qty": "0.001",
        "order_type": "limit",
        "quantity_scale": 8,
        "ladder_price_min": "30000",
        "ladder_price_max": "31000",
        "ladder_levels": 5,
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)


# --- the limits are the contract's --------------------------------------------


def _field_rules(message: Any, name: str) -> Any:
    options = message.DESCRIPTOR.fields_by_name[name].GetOptions()
    return options.Extensions[validate_pb2.field]


def _cel(message: Any) -> list[tuple[str, str]]:
    rules = message.DESCRIPTOR.GetOptions().Extensions[validate_pb2.message]
    return [(rule.id, rule.expression) for rule in rules.cel]


def test_limits_are_the_contract_published_values() -> None:
    assert _field_rules(triggers_pb2.TwapTrigger, "duration_ms").int64.gte == TWAP_DURATION_MS_MIN
    assert (
        _field_rules(triggers_pb2.TwapTrigger, "slice_interval_ms").int64.gte
        == TWAP_SLICE_INTERVAL_MS_MIN
    )
    levels = _field_rules(triggers_pb2.LadderTrigger, "levels").int32
    assert (levels.gte, levels.lte) == (LADDER_LEVELS_MIN, LADDER_LEVELS_MAX)
    # Published values, so a contract change shows up here too.
    assert (TWAP_DURATION_MS_MIN, TWAP_SLICE_INTERVAL_MS_MIN) == (1000, 100)
    assert (LADDER_LEVELS_MIN, LADDER_LEVELS_MAX) == (2, 100)


def test_twap_window_rule_is_the_contract_rule() -> None:
    assert _cel(triggers_pb2.TwapTrigger) == [
        ("twap_trigger.window", "this.slice_interval_ms <= this.duration_ms")
    ]


def test_cancel_all_after_timeout_constants_rebuild_the_contract_rule() -> None:
    # The contract publishes the timeout range only as a CEL rule, so the SDK
    # keeps constants and this test rebuilds the rule from them.
    lo, hi = CANCEL_ALL_AFTER_MIN_TIMEOUT_SEC, CANCEL_ALL_AFTER_MAX_TIMEOUT_SEC
    assert _cel(orders_pb2.CancelAllAfterRequest) == [
        (
            "cancel_all_after.timeout_range",
            f"this.timeout_sec == 0u || (this.timeout_sec >= {lo}u && this.timeout_sec <= {hi}u)",
        )
    ]
    assert (lo, hi) == (10, 120)


# --- TWAP ---------------------------------------------------------------------


@pytest.mark.parametrize(("duration", "interval"), [(500, 100), (0, 100), (-1000, 100), (999, 100)])
def test_twap_duration_below_contract_minimum_is_refused(duration: int, interval: int) -> None:
    with pytest.raises(PolyesterValidationError, match="twap_duration_ms"):
        _twap(twap_duration_ms=duration, twap_slice_interval_ms=interval)


@pytest.mark.parametrize("interval", [0, -5, 99])
def test_twap_slice_interval_below_contract_minimum_is_refused(interval: int) -> None:
    with pytest.raises(PolyesterValidationError, match="twap_slice_interval_ms"):
        _twap(twap_duration_ms=60_000, twap_slice_interval_ms=interval)


def test_twap_slice_interval_longer_than_duration_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="must not exceed twap_duration_ms"):
        _twap(twap_duration_ms=1_000, twap_slice_interval_ms=1_001)


@pytest.mark.parametrize("field", ["twap_duration_ms", "twap_slice_interval_ms"])
def test_twap_without_duration_or_interval_is_refused(field: str) -> None:
    # Left out, the field is 0 on the wire, below the contract's minimum.
    with pytest.raises(PolyesterValidationError, match=field):
        _twap(**{field: None})


@pytest.mark.parametrize("field", ["twap_duration_ms", "twap_slice_interval_ms"])
@pytest.mark.parametrize("value", [v for v in WRONG_TYPES if v is not None])
def test_twap_wrong_types_are_validation_errors(field: str, value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        _twap(**{field: value})


@pytest.mark.parametrize("field", ["twap_duration_ms", "twap_slice_interval_ms"])
def test_twap_values_beyond_int64_are_refused(field: str) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        _twap(**{field: INT64_MAX + 1})


@pytest.mark.parametrize(
    ("duration", "interval"),
    [(60_000, 1_000), (1_000, 100), (1_000, 1_000), (INT64_MAX, 100), (INT64_MAX, INT64_MAX)],
)
def test_twap_in_contract_range_is_sent_unchanged(duration: int, interval: int) -> None:
    twap = _twap(twap_duration_ms=duration, twap_slice_interval_ms=interval).trigger.twap
    assert (twap.duration_ms, twap.slice_interval_ms) == (duration, interval)


# --- ladder -------------------------------------------------------------------


@pytest.mark.parametrize("levels", [1, 0, 101, -3, None])
def test_ladder_levels_outside_contract_range_are_refused(levels: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="ladder_levels"):
        _ladder(ladder_levels=levels)


@pytest.mark.parametrize("levels", [v for v in WRONG_TYPES if v is not None])
def test_ladder_levels_wrong_types_are_validation_errors(levels: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="ladder_levels"):
        _ladder(ladder_levels=levels)


@pytest.mark.parametrize("levels", [2, 3, 99, 100])
def test_ladder_levels_in_contract_range_are_sent_unchanged(levels: int) -> None:
    assert _ladder(ladder_levels=levels).trigger.ladder.levels == levels


# --- dead-man switch ----------------------------------------------------------


@pytest.mark.parametrize("timeout_sec", [5, 9, 121, 1, -1, 2**32 - 1, 2**32])
def test_cancel_all_after_timeout_outside_contract_range_is_refused(timeout_sec: int) -> None:
    with pytest.raises(PolyesterValidationError, match="timeout_sec"):
        cancel_all_after_to_proto(timeout_sec=timeout_sec)


@pytest.mark.parametrize("timeout_sec", [10.5, 30.0, True, False, "30", None])
def test_cancel_all_after_wrong_types_are_validation_errors(timeout_sec: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="timeout_sec"):
        cancel_all_after_to_proto(timeout_sec=timeout_sec)


@pytest.mark.parametrize("timeout_sec", [0, 10, 11, 119, 120])
def test_cancel_all_after_timeout_in_contract_range_is_sent_unchanged(timeout_sec: int) -> None:
    assert cancel_all_after_to_proto(timeout_sec=timeout_sec).timeout_sec == timeout_sec


async def _sent(call) -> tuple[BaseException | None, list[Any]]:
    seen: list[Any] = []

    async def handler(req: ParsedRequest):
        seen.append(orders_pb2.CancelAllAfterRequest.FromString(req.body))
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    error: BaseException | None = None
    try:
        await call(client)
    except Exception as exc:
        error = exc
    finally:
        await client.aclose()
        await http.aclose()
    return error, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_sec", [5, 9, 121, 60.0])
async def test_cancel_all_after_refuses_before_sending(timeout_sec: Any) -> None:
    error, seen = await _sent(lambda c: c.orders.cancel_all_after(timeout_sec=timeout_sec))
    assert isinstance(error, PolyesterValidationError), error
    assert seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_sec", [0, 10, 120])
async def test_cancel_all_after_sends_contract_timeouts(timeout_sec: int) -> None:
    # The mock answers an empty response, so only the request sent is checked.
    _, seen = await _sent(lambda c: c.orders.cancel_all_after(timeout_sec=timeout_sec))
    assert [req.timeout_sec for req in seen] == [timeout_sec]
