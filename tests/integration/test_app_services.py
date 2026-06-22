import pytest

from polyester.models import ApiData
from tests.integration.support import assert_api_data_shape, call_optional


@pytest.mark.integration
@pytest.mark.optional
async def test_whiteboard_list_boards(live_client) -> None:
    result = await call_optional(live_client.whiteboard.list(limit=10), label="whiteboard.list")
    assert isinstance(result, ApiData)
    assert_api_data_shape(result.raw, "boards", "nextPageToken")


@pytest.mark.integration
@pytest.mark.optional
async def test_layout_get_layouts(live_client) -> None:
    result = await call_optional(
        live_client.layout.get_layouts(limit=10),
        label="layout.get_layouts",
    )
    assert isinstance(result, ApiData)
    assert_api_data_shape(result.raw, "layouts", "nextPageToken")


@pytest.mark.integration
@pytest.mark.optional
async def test_social_verification_get_twitter(live_client) -> None:
    result = await call_optional(
        live_client.social_verification.get(provider="twitter"),
        label="social_verification.get",
    )
    assert isinstance(result, ApiData)
    assert "verification" in result.raw


@pytest.mark.integration
@pytest.mark.optional
async def test_polychart_get_market_layers(live_client, smoke_symbol) -> None:
    spot = await live_client.market_data.get_spot_config()
    pair = next(
        (p for p in spot.raw.get("pairs") or [] if p.get("symbol") == smoke_symbol),
        None,
    )
    if pair is None:
        pytest.skip(f"no spot pair for {smoke_symbol}")
    symbol_id = pair.get("symbolId") or pair.get("symbol_id")
    if symbol_id is None:
        pytest.skip("spot pair missing symbol id")
    result = await call_optional(
        live_client.polychart.get_market_layers(engine_symbol_id=int(symbol_id)),
        label="polychart.get_market_layers",
    )
    assert isinstance(result, ApiData)
    assert_api_data_shape(result.raw, "engineSymbolId", "layers", "drawings")
