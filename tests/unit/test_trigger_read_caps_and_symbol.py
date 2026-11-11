"""Typed trigger reads keep every slippage cap and name the pair.

POLY-9396: a market TWAP's per-slice cap (``configuration.twap.market_ioc``)
reads back on the top-level ``max_slippage`` / ``max_slippage_bps``, with its
exact variant, and an unset cap stays unset (the pair's default).

POLY-9425: a trailing stop's cap reads back on the same top-level fields, as a
stop-loss or take-profit market child's does; ``details.trailing`` is
unchanged.

POLY-9424: with the catalogs loaded, ``triggers.get``, ``triggers.list`` and
the trigger stream fill ``symbol`` from ``symbol_id``; without them it stays
empty.

Each read is checked through ``trigger_from_proto``, the binary stream decoder
and the Get/List responses over the binary and the JSON wire.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from google.protobuf.json_format import MessageToDict

from polyester import AsyncPolyester
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.realtime_decode import decode_trigger_bytes
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.trading import Trigger
from polyester.services.triggers import AsyncTriggersService
from polyester.types.money import Price
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

BTC_USDT = {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}
TICKS = 25_000_000_000


def _twap(**cap: int) -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=21,
        symbol_id=1,
        status=triggers_pb2.STATUS_RUNNING,
        qty_scaled=100_000,
        twap=triggers_pb2.TwapTrigger(
            side=orders_pb2.BUY,
            duration_ms=60_000,
            slice_interval_ms=10_000,
            market_ioc=triggers_pb2.TwapMarketIoc(**cap),
        ),
    )


def _trailing(**cap: int) -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=22,
        symbol_id=1,
        status=triggers_pb2.STATUS_ARMED,
        qty_scaled=10_000,
        trailing_stop=triggers_pb2.TrailingStopTrigger(
            side=orders_pb2.SELL, trailing_distance_bps=200, **cap
        ),
        trailing=triggers_pb2.TrailingDetails(trailing_distance_bps=200, **cap),
    )


def _stop(kind: str, **cap: int) -> triggers_pb2.Trigger:
    conditional = triggers_pb2.ConditionalTrigger(
        trigger_price_ticks=50_000_000_000_000,
        side=orders_pb2.SELL,
        child=triggers_pb2.ConditionalChildExecution(
            market_ioc=triggers_pb2.TriggerMarketIoc(**cap)
        ),
    )
    return triggers_pb2.Trigger(
        trigger_id=23, symbol_id=1, status=triggers_pb2.STATUS_ARMED, **{kind: conditional}
    )


# (fixture, expected max_slippage ticks or None, expected max_slippage_bps)
CAP_CASES: dict[str, tuple[Callable[[], triggers_pb2.Trigger], int | None, int]] = {
    "twap_10bps": (lambda: _twap(max_slippage_bps=10), None, 10),
    "twap_50bps": (lambda: _twap(max_slippage_bps=50), None, 50),
    "twap_ticks": (lambda: _twap(max_slippage_ticks=TICKS), TICKS, 0),
    "twap_unset": (lambda: _twap(), None, 0),
    "trailing_100bps": (lambda: _trailing(max_slippage_bps=100), None, 100),
    "trailing_ticks": (lambda: _trailing(max_slippage_ticks=TICKS), TICKS, 0),
    "trailing_unset": (lambda: _trailing(), None, 0),
    "stop_loss_50bps": (lambda: _stop("stop_loss", max_slippage_bps=50), None, 50),
    "take_profit_50bps": (lambda: _stop("take_profit", max_slippage_bps=50), None, 50),
}


def _assert_cap(trigger: Trigger | None, ticks: int | None, bps: int) -> None:
    assert trigger is not None
    if ticks is None:
        assert trigger.max_slippage is None
    else:
        assert trigger.max_slippage is not None
        assert trigger.max_slippage.ticks == ticks
    assert trigger.max_slippage_bps == bps


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config({"pairs": [BTC_USDT]})
    return catalogs


@pytest.mark.parametrize("case", sorted(CAP_CASES))
def test_trigger_from_proto_keeps_the_cap(case: str) -> None:
    build, ticks, bps = CAP_CASES[case]
    msg = build()
    _assert_cap(trigger_from_proto(msg), ticks, bps)
    # The generated round trip keeps the cap: the loss, if any, is the SDK's.
    assert triggers_pb2.Trigger.FromString(msg.SerializeToString()) == msg


@pytest.mark.parametrize("case", sorted(CAP_CASES))
def test_trigger_stream_keeps_the_cap(case: str) -> None:
    build, ticks, bps = CAP_CASES[case]
    _assert_cap(decode_trigger_bytes(build().SerializeToString()), ticks, bps)


def test_trailing_details_are_unchanged() -> None:
    trigger = trigger_from_proto(_trailing(max_slippage_bps=100))
    assert trigger.details is not None and trigger.details.trailing is not None
    assert trigger.details.trailing.max_slippage_bps == 100
    assert trigger.details.trailing.max_slippage is None
    trigger = trigger_from_proto(_trailing(max_slippage_ticks=TICKS))
    assert trigger.details is not None and trigger.details.trailing is not None
    assert trigger.details.trailing.max_slippage == Price.from_ticks(TICKS)
    assert trigger.details.trailing.max_slippage_bps == 0


def test_trailing_cap_falls_back_to_runtime_details() -> None:
    """A read without the configuration still reports the runtime cap."""
    msg = triggers_pb2.Trigger(
        trigger_id=24,
        symbol_id=1,
        trailing=triggers_pb2.TrailingDetails(trailing_distance_bps=200, max_slippage_bps=75),
    )
    _assert_cap(trigger_from_proto(msg), None, 75)


def _mock_responses(trigger: triggers_pb2.Trigger) -> dict[str, Any]:
    return {
        "GetTrigger": triggers_pb2.GetTriggerResponse(trigger=trigger),
        "ListTriggers": triggers_pb2.ListTriggersResponse(triggers=[trigger]),
    }


async def _reads(
    trigger: triggers_pb2.Trigger, *, json_wire: bool, catalogs: bool
) -> list[Trigger | None]:
    responses = _mock_responses(trigger)

    async def handler(req: ParsedRequest) -> HttpScript:
        response = responses[req.path.rsplit("/", 1)[-1]]
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    if catalogs:
        client.catalogs.hydrate_spot_config({"pairs": [BTC_USDT]})
    try:
        got = await client.triggers.get(trigger_id="21")
        listed = (await client.triggers.list()).triggers
        return [got, listed[0]]
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("case", sorted(CAP_CASES))
async def test_get_and_list_keep_the_cap(json_wire: bool, case: str) -> None:
    build, ticks, bps = CAP_CASES[case]
    for trigger in await _reads(build(), json_wire=json_wire, catalogs=True):
        _assert_cap(trigger, ticks, bps)


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("catalogs", [True, False])
async def test_get_and_list_name_the_pair(json_wire: bool, catalogs: bool) -> None:
    for trigger in await _reads(
        _stop("stop_loss", max_slippage_bps=100), json_wire=json_wire, catalogs=catalogs
    ):
        assert trigger is not None and trigger.symbol_id == 1
        assert trigger.symbol == ("BTC-USDT" if catalogs else "")


def test_trigger_stream_names_the_pair() -> None:
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    payload = _stop("stop_loss").SerializeToString()
    assert service._decode_trigger(payload).symbol == "BTC-USDT"
    # The pair is unknown to the catalogs: the name stays empty.
    unknown = triggers_pb2.Trigger(trigger_id=25, symbol_id=9)
    assert service._decode_trigger(unknown.SerializeToString()).symbol == ""
    # Without catalogs the decoder leaves the name empty, as before.
    assert decode_trigger_bytes(payload).symbol == ""
