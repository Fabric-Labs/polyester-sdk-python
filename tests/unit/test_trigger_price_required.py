"""A stop-loss or take-profit trigger without a trigger price is refused before sending.

The contract requires ``ConditionalTrigger.trigger_price_ticks`` to be positive,
and the API answers a create without one ``ERROR_CODE_TRIGGER_PRICE_INVALID``. A
trigger price left out is refused locally as an explicit 0 is: the same
``PolyesterValidationError``, naming ``trigger_price``, with the same code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from tests.hardening_support import HttpScript, MockHttpServer, ParsedRequest, make_test_credentials

_CREDS = make_test_credentials()
_CODE = "ERROR_CODE_TRIGGER_PRICE_INVALID"
_CHILDREN: list[dict[str, Any]] = [{}, {"order_type": "limit", "limit_price": "95"}]


def _create(**overrides: Any):
    args: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "stop_loss",
        "side": "sell",
        "qty": "0.1",
        "quantity_scale": 8,
    }
    args.update(overrides)
    return create_trigger_to_proto(**args)


def _refusal(**overrides: Any) -> PolyesterValidationError:
    with pytest.raises(PolyesterValidationError) as refused:
        _create(**overrides)
    return refused.value


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
@pytest.mark.parametrize("child", _CHILDREN)
def test_a_missing_trigger_price_is_refused_as_an_explicit_zero_is(
    trigger_type: str, child: dict[str, Any]
) -> None:
    missing = _refusal(trigger_type=trigger_type, **child)
    zero = _refusal(trigger_type=trigger_type, trigger_price="0", **child)
    assert "trigger_price" in str(missing)
    assert missing.code == zero.code == _CODE
    assert type(missing) is type(zero)


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_an_explicit_zero_trigger_price_is_still_refused(trigger_type: str) -> None:
    refused = _refusal(trigger_type=trigger_type, trigger_price="0")
    assert "trigger_price must be positive" in str(refused)
    assert refused.code == _CODE


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_a_limit_child_without_a_limit_price_still_encodes(trigger_type: str) -> None:
    proto = _create(trigger_type=trigger_type, trigger_price="100", order_type="limit")
    conditional = getattr(proto.trigger, trigger_type)
    assert conditional.trigger_price_ticks == 100 * 10**9
    assert conditional.child.HasField("limit_gtc")
    assert conditional.child.limit_gtc.price_ticks == 0


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
@pytest.mark.parametrize("child", _CHILDREN)
def test_a_trigger_price_still_encodes(trigger_type: str, child: dict[str, Any]) -> None:
    proto = _create(trigger_type=trigger_type, trigger_price="100", **child)
    conditional = getattr(proto.trigger, trigger_type)
    assert conditional.trigger_price_ticks == 100 * 10**9
    if child:
        assert conditional.child.limit_gtc.price_ticks == 95 * 10**9
    else:
        assert conditional.child.HasField("market_ioc")


@asynccontextmanager
async def _client() -> AsyncIterator[tuple[AsyncPolyester, list[ParsedRequest]]]:
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return HttpScript.json(400, {"code": _CODE, "message": "trigger price invalid"})

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
@pytest.mark.parametrize("child", _CHILDREN)
async def test_a_trigger_without_a_trigger_price_is_not_sent(
    trigger_type: str, child: dict[str, Any]
) -> None:
    async with _client() as (client, requests):
        with pytest.raises(PolyesterValidationError, match="trigger_price") as refused:
            await client.triggers.create(
                symbol="BTC-USDT", trigger_type=trigger_type, side="sell", qty="0.1", **child
            )
        assert refused.value.code == _CODE
    assert requests == []
