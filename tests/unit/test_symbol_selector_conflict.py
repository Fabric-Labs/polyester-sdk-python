"""A market name and a numeric market ID that name different markets are
refused before sending; either alone, or both for one market, is sent."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.services._symbols import resolve_optional_symbol_id, resolve_symbol_id
from polyester.services.triggers import AsyncTriggersService

UNARY = "polyester.services.triggers.unary_auth_decoded"


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                    "tick_size": "0.01",
                },
                {
                    "symbol": "LTC-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                    "tick_size": "0.01",
                },
            ]
        }
    )
    return catalogs


class _Sent(Exception):
    pass


class _CaptureRequest:
    """Record the request the service would send, then stop the call."""

    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def __call__(
        self, _transport: Any, _client: Any, _call: Any, request: Any, *_a: Any, **_k: Any
    ) -> Any:
        self.requests.append(request)
        raise _Sent


def _service() -> AsyncTriggersService:
    return AsyncTriggersService(MagicMock(), _catalogs(), None)


async def _modify(service: AsyncTriggersService, **selectors: Any) -> None:
    await service.modify(trigger_id=9, trigger_price="95200", **selectors)


async def _resume(service: AsyncTriggersService, **selectors: Any) -> None:
    await service.resume(trigger_id=9, **selectors)


CONTROLS = [_modify, _resume]


@pytest.mark.asyncio
@pytest.mark.parametrize("control", CONTROLS, ids=["modify", "resume"])
async def test_trigger_control_refuses_a_name_and_id_of_different_markets(control: Any) -> None:
    capture = _CaptureRequest()
    with patch(UNARY, capture), pytest.raises(PolyesterValidationError, match="mismatch"):
        await control(_service(), symbol="LTC-USDT", symbol_id=1)
    assert capture.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("control", CONTROLS, ids=["modify", "resume"])
@pytest.mark.parametrize(
    ("selectors", "sent"),
    [
        ({"symbol": "LTC-USDT"}, 2),
        ({"symbol_id": 1}, 1),
        ({"symbol": "BTC-USDT", "symbol_id": 1}, 1),
        ({}, 0),
    ],
    ids=["name", "id", "matching", "omitted"],
)
async def test_trigger_control_sends_consistent_selectors(
    control: Any, selectors: dict[str, Any], sent: int
) -> None:
    capture = _CaptureRequest()
    with patch(UNARY, capture), pytest.raises(_Sent):
        await control(_service(), **selectors)
    assert [request.symbol_id for request in capture.requests] == [sent]


@pytest.mark.parametrize("resolve", [resolve_symbol_id, resolve_optional_symbol_id])
def test_resolving_a_name_and_id_of_different_markets_is_refused(resolve: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="mismatch"):
        resolve(_catalogs(), symbol="LTC-USDT", symbol_id=1, label="trades.list")
    assert resolve(_catalogs(), symbol="LTC-USDT", symbol_id=2, label="trades.list") == 2
    # An ID the catalog doesn't know is sent when the name names no other market.
    assert resolve(_catalogs(), symbol="DOGE-USDT", symbol_id=7, label="trades.list") == 7
    assert resolve(None, symbol="LTC-USDT", symbol_id=1, label="trades.list") == 1


def test_resolving_an_unknown_name_with_a_known_id_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="mismatch"):
        resolve_symbol_id(_catalogs(), symbol="DOGE-USDT", symbol_id=1, label="trades.list")
