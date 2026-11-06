"""Trigger options must be represented on the wire or refused before transport."""

import pytest

from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1 import triggers_pb2
from tests.unit.test_request_builder_regressions import capture_transport, triggers

TYPES = ["stop_loss", "take_profit", "trailing_stop", "twap", "ladder"]
# option, value, supported types, wire field (relative to the strategy)
OPTIONS = [
    ("trailing_distance_ticks", 5, ["trailing_stop"], "trailing_distance_ticks"),
    ("trailing_distance_bps", 50, ["trailing_stop"], "trailing_distance_bps"),
    ("activation_price", "90", ["trailing_stop"], "activation_price_ticks"),
    ("twap_duration_ms", 60000, ["twap"], "duration_ms"),
    ("twap_slice_interval_ms", 10000, ["twap"], "slice_interval_ms"),
    ("ladder_price_min", "90", ["ladder"], "price_min_ticks"),
    ("ladder_price_max", "110", ["ladder"], "price_max_ticks"),
    ("ladder_levels", 4, ["ladder"], "levels"),
    ("ladder_distribution", "linear", ["ladder"], "levels"),
    ("trigger_price", "100", ["stop_loss", "take_profit"], "trigger_price_ticks"),
    (
        "trigger_price_source",
        "index",
        ["stop_loss", "take_profit", "trailing_stop"],
        "trigger_price_source",
    ),
]


def base_options(kind):
    kwargs = dict(symbol="BTC-USDT", trigger_type=kind, side="sell", qty="0.01")
    if kind in ("stop_loss", "take_profit"):
        kwargs["trigger_price"] = "100"
    elif kind == "trailing_stop":
        kwargs["trailing_distance_bps"] = 50
    elif kind == "twap":
        kwargs.update(twap_duration_ms=60000, twap_slice_interval_ms=10000)
    else:
        kwargs.update(ladder_price_min="90", ladder_price_max="110", ladder_levels=4)
    return kwargs


@pytest.mark.parametrize("kind", TYPES)
@pytest.mark.parametrize("option,value,allowed,wire", OPTIONS)
async def test_trigger_type_option_matrix(kind, option, value, allowed, wire):
    kwargs = base_options(kind)
    if option == "trailing_distance_ticks":
        kwargs.pop("trailing_distance_bps", None)
    kwargs[option] = value
    async with capture_transport() as (transport, requests):
        if kind not in allowed:
            with pytest.raises(PolyesterValidationError, match=option) as error:
                await triggers(transport).create(**kwargs)
            assert len(requests) == 0
            if option in ("trailing_distance_ticks", "trailing_distance_bps", "activation_price"):
                assert "applies only to trailing_stop" in str(error.value)
        else:
            await triggers(transport).create(**kwargs)
            assert len(requests) == 1
            request = triggers_pb2.CreateTriggerRequest.FromString(requests[0].body)
            assert request.trigger.WhichOneof("strategy") == kind
            strategy = getattr(request.trigger, kind)
            expected = value
            if "price" in option and option != "trigger_price_source":
                expected = int(value) * 10**9
            elif option == "trigger_price_source":
                expected = 2  # INDEX_PRICE
            elif option == "ladder_distribution":
                expected = 4  # LINEAR is the contract's intrinsic ladder layout.
            assert getattr(strategy, wire) == expected


@pytest.mark.parametrize("kind", ["stop_loss", "take_profit", "twap", "ladder"])
@pytest.mark.parametrize("option", ["max_slippage_ticks", "max_slippage_bps"])
@pytest.mark.parametrize("order_type", ["market", "limit"])
async def test_slippage_execution_applicability(kind, option, order_type):
    kwargs = base_options(kind)
    kwargs.update(order_type=order_type, **{option: 5})
    if order_type == "limit" and kind != "ladder":
        kwargs["limit_price"] = "100"
    async with capture_transport() as (transport, requests):
        if kind == "ladder" or order_type == "limit":
            with pytest.raises(PolyesterValidationError, match=option):
                await triggers(transport).create(**kwargs)
            assert len(requests) == 0
        else:
            await triggers(transport).create(**kwargs)
            assert len(requests) == 1
            strategy = getattr(
                triggers_pb2.CreateTriggerRequest.FromString(requests[0].body).trigger, kind
            )
            child = strategy.market_ioc if kind == "twap" else strategy.child.market_ioc
            assert child.WhichOneof("max_slippage") == option
            assert getattr(child, option) == 5


@pytest.mark.parametrize(
    "kind,fields,option",
    [
        (kind, fields, option)
        for kind in TYPES
        for fields, option in [
            ({"post_only": True}, "post_only"),
            ({"limit_price": "100"}, "limit_price"),
            ({"tif": "fok"}, "tif"),
        ]
        if kind != "ladder" or option != "post_only"
    ],
)
async def test_unsupported_execution_options(kind, fields, option):
    kwargs = base_options(kind)
    kwargs.update(fields)
    async with capture_transport() as (transport, requests):
        with pytest.raises(PolyesterValidationError, match=option):
            await triggers(transport).create(**kwargs)
        assert len(requests) == 0


@pytest.mark.parametrize("kind", ["stop_loss", "take_profit", "twap", "ladder"])
async def test_limit_price_and_post_only_controls(kind):
    kwargs = base_options(kind)
    kwargs["order_type"] = "limit"
    if kind != "ladder":
        kwargs["limit_price"] = "100"
    if kind != "twap":
        kwargs["post_only"] = True
    async with capture_transport() as (transport, requests):
        await triggers(transport).create(**kwargs)
        assert len(requests) == 1
        strategy = getattr(
            triggers_pb2.CreateTriggerRequest.FromString(requests[0].body).trigger, kind
        )
        child = (
            strategy
            if kind == "ladder"
            else (strategy.limit_gtc if kind == "twap" else strategy.child.limit_gtc)
        )
        if kind != "ladder":
            assert child.price_ticks == 100 * 10**9
        if kind != "twap":
            assert child.post_only
