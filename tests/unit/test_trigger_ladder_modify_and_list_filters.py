"""Trigger create, modify and list follow the contract before sending.

POLY-9423: a ladder places LINEAR limit-GTC orders only, so an explicit
``order_type="market"`` on a ladder is refused before sending, never sent as
a limit ladder. A ladder without an order type, or with ``"limit"``, works.

POLY-9426: ``triggers.modify`` takes ``max_slippage_bps`` 0 to 10000, as the
contract does: a buy stop-loss or take-profit with a market child accepts
10000, and the server refuses it for sells and trailing stops.

POLY-9433: ``triggers.list`` filters by ``trigger_type`` and
``parent_order_id``, as ``ListTriggersRequest`` does.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.codecs.triggers import modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary


def _service() -> AsyncTriggersService:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return AsyncTriggersService(MagicMock(), catalogs, None)


LADDER = {
    "symbol": "BTC-USDT",
    "trigger_type": "ladder",
    "side": "buy",
    "qty": "0.00020",
    "ladder_price_min": "60000",
    "ladder_price_max": "61000",
    "ladder_levels": 2,
    "post_only": True,
}


# --- POLY-9423 ladder order type -----------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("order_type", ["market", "MARKET", "stop", ""])
async def test_ladder_refuses_an_order_type_other_than_limit(order_type: str) -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=1))
    with (
        patch("polyester.services.triggers.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match="ladder"),
    ):
        await _service().create(**LADDER, order_type=order_type)  # type: ignore[arg-type]
    assert capture.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("order_type", [None, "limit", "LIMIT"])
async def test_ladder_without_an_order_type_or_with_limit_is_sent(
    order_type: str | None,
) -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=1))
    kwargs: dict[str, object] = dict(LADDER)
    if order_type is not None:
        kwargs["order_type"] = order_type
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await _service().create(**kwargs)  # type: ignore[arg-type]
    assert capture.calls == 1
    request = capture.request
    assert isinstance(request, triggers_pb2.CreateTriggerRequest)
    ladder = request.trigger.ladder
    assert request.trigger.WhichOneof("strategy") == "ladder"
    assert ladder.levels == 2 and ladder.post_only is True


@pytest.mark.asyncio
async def test_stop_loss_without_an_order_type_is_still_a_market_child() -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=1))
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await _service().create(
            symbol="BTC-USDT",
            trigger_type="stop_loss",
            side="sell",
            qty="0.0003",
            trigger_price="50000",
            max_slippage_bps=100,
        )
    request = capture.request
    assert isinstance(request, triggers_pb2.CreateTriggerRequest)
    child = request.trigger.stop_loss.child
    assert child.WhichOneof("execution") == "market_ioc"
    assert child.market_ioc.max_slippage_bps == 100


# --- POLY-9426 modify slippage bound -------------------------------------------


@pytest.mark.parametrize("bps", [0, 1, 9999, 10000])
def test_modify_encodes_bps_the_contract_accepts(bps: int) -> None:
    request = modify_trigger_to_proto(trigger_id="7", max_slippage_bps=bps)
    assert request.WhichOneof("max_slippage") == "max_slippage_bps"
    assert request.max_slippage_bps == bps


@pytest.mark.parametrize("bps", [10001, -1])
def test_modify_refuses_bps_outside_the_contract(bps: int) -> None:
    with pytest.raises(PolyesterValidationError, match="between 1 and 10000"):
        modify_trigger_to_proto(trigger_id="7", max_slippage_bps=bps)


@pytest.mark.asyncio
async def test_modify_sends_a_10000_bps_cap() -> None:
    capture = CaptureUnary(
        triggers_pb2.ModifyTriggerResponse(trigger_id=7, status=triggers_pb2.STATUS_ARMED)
    )
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await _service().modify(trigger_id="7", symbol="BTC-USDT", max_slippage_bps=10000)
    assert capture.calls == 1
    request = capture.request
    assert isinstance(request, triggers_pb2.ModifyTriggerRequest)
    assert request.max_slippage_bps == 10000
    assert request.symbol_id == 1


@pytest.mark.asyncio
async def test_create_and_modify_accept_the_same_buy_cap() -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=1))
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await _service().create(
            symbol="BTC-USDT",
            trigger_type="stop_loss",
            side="buy",
            qty="0.0001",
            trigger_price="120000",
            order_type="market",
            max_slippage_bps=10000,
        )
    assert modify_trigger_to_proto(trigger_id="1", max_slippage_bps=10000).max_slippage_bps == (
        10000
    )


# --- POLY-9433 list filters -----------------------------------------------------


async def _list(**kwargs: object) -> triggers_pb2.ListTriggersRequest:
    capture = CaptureUnary(triggers_pb2.ListTriggersResponse())
    with patch("polyester.services.triggers.unary_auth_decoded_retry_unavailable", capture):
        await _service().list(**kwargs)  # type: ignore[arg-type]
    assert capture.calls == 1
    assert isinstance(capture.request, triggers_pb2.ListTriggersRequest)
    return capture.request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("stop_loss", triggers_pb2.STOP_LOSS),
        ("take_profit", triggers_pb2.TAKE_PROFIT),
        ("trailing_stop", triggers_pb2.TRAILING_STOP),
        ("twap", triggers_pb2.TWAP),
        ("ladder", triggers_pb2.LADDER),
        ("LADDER", triggers_pb2.LADDER),
        ("trailing-stop", triggers_pb2.TRAILING_STOP),
    ],
)
async def test_list_sends_the_trigger_type(label: str, value: int) -> None:
    request = await _list(trigger_type=label)
    assert request.trigger_type == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("parent", "expected"),
    [
        ("18446744073709551615", 18446744073709551615),
        (42, 42),
        (format_uint64_id(9_007_199_254_740_993), 9_007_199_254_740_993),
    ],
)
async def test_list_sends_the_parent_order_id(parent: str | int, expected: int) -> None:
    request = await _list(parent_order_id=parent)
    assert request.HasField("parent_order_id")
    assert request.parent_order_id == expected


@pytest.mark.asyncio
async def test_list_without_filters_is_unchanged() -> None:
    request = await _list()
    assert request.trigger_type == triggers_pb2.TRIGGER_TYPE_UNSPECIFIED
    assert not request.HasField("parent_order_id")
    assert request.limit == 50


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"trigger_type": "stop"}, "trigger_type"),
        ({"trigger_type": ""}, "trigger_type"),
        ({"parent_order_id": "0"}, "parent_order_id"),
        ({"parent_order_id": "-1"}, "parent_order_id"),
        ({"parent_order_id": "not-an-id"}, "parent_order_id"),
        ({"parent_order_id": "18446744073709551616"}, "parent_order_id"),
    ],
)
async def test_list_refuses_invalid_filters_before_sending(
    kwargs: dict[str, object], match: str
) -> None:
    capture = CaptureUnary(triggers_pb2.ListTriggersResponse())
    with (
        patch("polyester.services.triggers.unary_auth_decoded_retry_unavailable", capture),
        pytest.raises(PolyesterValidationError, match=match),
    ):
        await _service().list(**kwargs)  # type: ignore[arg-type]
    assert capture.calls == 0
