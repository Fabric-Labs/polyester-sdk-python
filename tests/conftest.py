from __future__ import annotations

import os

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterApiError, PolyesterRouteNotFoundError
from tests.helpers import (
    live_client_kwargs_from_env,
    min_trading_quote_required,
    pick_smoke_symbol,
    pick_trade_symbol,
    quote_asset_id_for_symbol,
    skip_funding_check,
    trading_balance_decimal,
)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment,misc]

if load_dotenv is not None:
    load_dotenv()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: live devnet (requires POLYESTER_* env)")
    config.addinivalue_line(
        "markers",
        "mutation: writes state on devnet (POLYESTER_TEST_MUTATION=1)",
    )
    config.addinivalue_line(
        "markers",
        "funded: balance-changing devnet tests (POLYESTER_TEST_FUNDED=1)",
    )
    config.addinivalue_line("markers", "treasury: withdraw/guard ops (POLYESTER_TEST_TREASURY=1)")
    config.addinivalue_line("markers", "realtime: Centrifugo subscriptions")
    config.addinivalue_line("markers", "optional: may skip when route unavailable on devnet")
    config.addinivalue_line(
        "markers",
        "jwt_session: JWT/session or app-user route; not part of API-key SDK acceptance",
    )
    config.addinivalue_line(
        "markers",
        "smoke: shallow live RPC check (shape only; empty results OK)",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if _env_truthy("POLYESTER_TEST_STRICT_LIVE") and report.skipped:
        report.outcome = "failed"
        report.longrepr = (
            f"{item.nodeid}: strict live mode forbids skipped tests; "
            "unset POLYESTER_TEST_STRICT_LIVE for capability discovery"
        )


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes")


def _optional_route_unavailable(exc: Exception) -> bool:
    if isinstance(exc, PolyesterRouteNotFoundError):
        return True
    if isinstance(exc, PolyesterApiError):
        return str(exc.code or "").lower() in {"route_not_found", "unimplemented", "not_found"}
    return False


@pytest.fixture(scope="session")
def live_credentials() -> None:
    from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV

    if live_client_kwargs_from_env() is None:
        pytest.skip(f"Set {API_KEY_ID_ENV} and {API_PRIVATE_KEY_ENV} in .env for live tests")


@pytest.fixture(scope="session")
def mutation_enabled() -> None:
    if not _env_truthy("POLYESTER_TEST_MUTATION"):
        pytest.skip("Set POLYESTER_TEST_MUTATION=1 to run mutation tests")


@pytest.fixture(scope="session")
def funded_enabled() -> None:
    if not _env_truthy("POLYESTER_TEST_FUNDED"):
        pytest.skip("Set POLYESTER_TEST_FUNDED=1 to run funded tests")


@pytest.fixture(scope="session")
def treasury_enabled() -> None:
    if not _env_truthy("POLYESTER_TEST_TREASURY"):
        pytest.skip("Set POLYESTER_TEST_TREASURY=1 to run treasury tests")


@pytest.fixture(scope="session")
async def live_client(live_credentials):
    kwargs = live_client_kwargs_from_env(hydrate_catalogs=True)
    assert kwargs is not None
    client = AsyncPolyester(**kwargs)
    try:
        yield client
    finally:
        await client.aclose()


async def _ensure_zipper_catalog(live_client) -> None:
    if live_client.catalogs.zipper is not None:
        return
    zipper = await live_client.zipper.get_deposit_withdraw_config()
    live_client.catalogs.hydrate_zipper_config(zipper)


@pytest.fixture(scope="session")
async def smoke_symbol(live_client) -> str:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    await _ensure_zipper_catalog(live_client)
    return pick_smoke_symbol(spot.raw)


@pytest.fixture(scope="session")
async def trade_symbol(live_client) -> str:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    await _ensure_zipper_catalog(live_client)
    return pick_trade_symbol(spot.raw)


@pytest.fixture(scope="session")
async def account_balances(live_client):
    return await live_client.balances.list()


@pytest.fixture(scope="session")
async def capabilities(live_client, smoke_symbol):
    caps = {"orderbook": True, "list_holds": True, "get_current_candle": True}
    try:
        await live_client.orderbook.get(symbol=smoke_symbol, depth=5)
    except Exception as exc:
        if not _optional_route_unavailable(exc):
            raise
        caps["orderbook"] = False
    try:
        await live_client.balances.list_holds(limit=1)
    except Exception as exc:
        if not _optional_route_unavailable(exc):
            raise
        caps["list_holds"] = False
    try:
        await live_client.market_data.get_current_candle(symbol=smoke_symbol)
    except Exception as exc:
        if not _optional_route_unavailable(exc):
            raise
        caps["get_current_candle"] = False
    return caps


async def _require_trading_balance_for_symbol(live_client, symbol: str) -> None:
    if skip_funding_check():
        return
    await _ensure_zipper_catalog(live_client)
    spot = await live_client.market_data.get_spot_config()
    quote_asset_id = quote_asset_id_for_symbol(
        spot.raw,
        symbol,
        zipper_raw=live_client.catalogs.zipper_config,
    )
    if quote_asset_id is None:
        pytest.skip(f"Cannot resolve quote asset for {symbol}")
    account_balances = await live_client.balances.list()
    balance = trading_balance_decimal(account_balances, quote_asset_id)
    minimum = min_trading_quote_required()
    if balance < minimum:
        pytest.skip(
            f"Trading balance {balance} below minimum {minimum} for asset {quote_asset_id}; "
            "fund trading ledger on devnet or set POLYESTER_TEST_SKIP_FUNDING_CHECK=1"
        )


@pytest.fixture
async def require_trading_balance(live_client, smoke_symbol):
    await _require_trading_balance_for_symbol(live_client, smoke_symbol)


@pytest.fixture
async def require_trade_trading_balance(live_client, trade_symbol):
    await _require_trading_balance_for_symbol(live_client, trade_symbol)
