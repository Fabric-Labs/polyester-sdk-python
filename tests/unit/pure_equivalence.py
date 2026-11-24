"""Shared harness: the request the SDK sends against what ``polyester.pure`` builds.

The SDK side runs the real service method on a client whose catalogs hold one
pair, and captures the protobuf request it would send. The pure side runs the
builder of the same name with that pair as its market spec. Both see the same
arguments; typed values (``P``, ``Q``) become each side's own ``Price`` and
``Quantity``, and ``Expires`` an RFC3339 time relative to now.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from google.protobuf import json_format
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.codecs.scalars import FractionalDigitsError
from polyester.errors import PolyesterValidationError
from polyester.models.order_key import ClientOrderId, OrderId
from polyester.pure import polyester as pure
from polyester.services import orders as orders_service
from polyester.services import triggers as triggers_service
from polyester.types.money import Price, Quantity, QuantityDomain
from tests.hardening_support import make_test_credentials

SYMBOL = "BTC-USDT"
SYMBOL_ID = 7
BASE_SCALE = 8
QUOTE_SCALE = 6
# The pair as GetSpotConfig serves it (proto-JSON), and as the SDK's catalogs hold it.
MARKET = {
    "symbol": SYMBOL,
    "symbolId": SYMBOL_ID,
    "baseQuantityScale": BASE_SCALE,
    "quoteQuantityScale": QUOTE_SCALE,
    "tickSize": "0.01",
    "stepSize": "0.0001",
    "minQtyBase": "0.0001",
    "minNotionalQuote": "5",
}
CATALOG = {
    "pairs": [
        {
            "symbol": SYMBOL,
            "symbol_id": SYMBOL_ID,
            "base_quantity_scale": BASE_SCALE,
            "quote_quantity_scale": QUOTE_SCALE,
        }
    ]
}


@dataclass(frozen=True)
class P:
    """A typed price: ``Price.from_ticks(ticks, symbol=symbol)`` on each side."""

    ticks: Any
    symbol: str | None = None
    raw: bool = False  # the plain constructor, which checks nothing


@dataclass(frozen=True)
class Q:
    """A typed quantity: ``Quantity.from_scaled(...)`` on each side."""

    scaled: Any
    scale: int | None = BASE_SCALE
    quote: bool = False
    symbol: str | None = None
    symbol_id: int | None = None
    raw: bool = False


@dataclass(frozen=True)
class Expires:
    """An RFC3339 ``expires_at`` this many seconds from now."""

    seconds: int


@dataclass(frozen=True)
class Key:
    """An order key: ``OrderId`` (or ``ClientOrderId`` with ``client``) on each side."""

    value: Any
    client: bool = False


def materialize(value: Any, *, sdk: bool, now: datetime) -> Any:
    if isinstance(value, P):
        cls = Price if sdk else pure.Price
        if value.raw:
            return cls(value.ticks, value.symbol)
        return cls.from_ticks(value.ticks, symbol=value.symbol)
    if isinstance(value, Q):
        if sdk:
            domain = QuantityDomain.ORDER_QUOTE if value.quote else QuantityDomain.ORDER_BASE
            if value.raw:
                return Quantity(value.scaled, value.scale, domain, value.symbol, value.symbol_id)
            return Quantity.from_scaled(
                value.scaled,
                scale=value.scale,
                domain=domain,
                symbol=value.symbol,
                symbol_id=value.symbol_id,
            )
        if value.raw:
            domain_name = "order_quote" if value.quote else "order_base"
            return pure.Quantity(
                value.scaled, value.scale, domain_name, value.symbol, value.symbol_id
            )
        return pure.Quantity.from_scaled(
            value.scaled,
            scale=value.scale,
            domain="order_quote" if value.quote else "order_base",
            symbol=value.symbol,
            symbol_id=value.symbol_id,
        )
    if isinstance(value, Expires):
        return (now + timedelta(seconds=value.seconds)).isoformat().replace("+00:00", "Z")
    if isinstance(value, Key):
        if value.client:
            return (ClientOrderId if sdk else pure.ClientOrderId)(value.value)
        return (OrderId if sdk else pure.OrderId)(value.value)
    if isinstance(value, dict):
        return {key: materialize(item, sdk=sdk, now=now) for key, item in value.items()}
    if isinstance(value, list):
        return [materialize(item, sdk=sdk, now=now) for item in value]
    return value


class WeirdInt(int):
    """An int whose operators lie about its value; its true value is operator.index's."""

    def __neg__(self) -> int:
        return -9

    def __int__(self) -> int:
        return 1

    def __index__(self) -> int:
        return 3


class _Sent(Exception):
    def __init__(self, request: Message) -> None:
        super().__init__("captured")
        self.request = request


@asynccontextmanager
async def sdk_client(catalog: dict[str, Any] | None = None) -> AsyncIterator[AsyncPolyester]:
    """A client whose unary calls raise the request they would send."""

    async def capture(_transport: Any, _client: Any, _call: Any, request: Any, _decoder: Any):
        raise _Sent(request)

    creds = make_test_credentials()
    saved = (orders_service.unary_auth_decoded, triggers_service.unary_auth_decoded)
    orders_service.unary_auth_decoded = capture  # type: ignore[assignment]
    triggers_service.unary_auth_decoded = capture  # type: ignore[assignment]
    client = AsyncPolyester(
        api_url="http://127.0.0.1:9",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(catalog or CATALOG)

    async def loaded() -> None:
        return None

    # As a client that loads its catalogs: the symbol is resolved before its scale.
    for service in (client.orders, client.triggers):
        service._wait_for_catalogs = loaded
    try:
        yield client
    finally:
        orders_service.unary_auth_decoded, triggers_service.unary_auth_decoded = saved
        await client.aclose()


@dataclass
class Outcome:
    request: Any = None
    error: BaseException | None = None


async def sdk_outcome(call: Callable[[], Awaitable[Any]]) -> Outcome:
    try:
        await call()
    except _Sent as sent:
        return Outcome(request=sent.request)
    except Exception as exc:  # noqa: BLE001 - compared below
        return Outcome(error=exc)
    raise AssertionError("the SDK call neither sent nor refused")


def pure_outcome(call: Callable[[], Any]) -> Outcome:
    try:
        return Outcome(request=call())
    except Exception as exc:  # noqa: BLE001 - compared below
        return Outcome(error=exc)


def _violations(exc: BaseException) -> list[dict[str, str]]:
    found = getattr(exc, "violations", None) or []
    return [
        item
        if isinstance(item, dict)
        else {"field_path": item.field_path, "rule_id": item.rule_id, "message": item.message}
        for item in found
    ]


def assert_same(
    sdk: Outcome,
    built: Outcome,
    *,
    generated: tuple[tuple[str, str], ...] = (),
) -> None:
    """``built`` refuses as ``sdk`` refuses, or builds the request it sent.

    ``generated`` names (path, prefix) of IDs the SDK generates and the host
    fills instead; they are checked for their prefix and cleared first.
    """
    if sdk.error is not None:
        assert built.error is not None, f"SDK refused {sdk.error!r}; pure built {built.request!r}"
        if isinstance(sdk.error, PolyesterValidationError):
            assert type(built.error) is ValueError, repr(built.error)
            assert str(built.error) == str(sdk.error)
            assert getattr(built.error, "code", None) == sdk.error.code
            assert _violations(built.error) == _violations(sdk.error)
            fractional = isinstance(sdk.error, FractionalDigitsError)
            assert bool(getattr(built.error, "fractional", False)) == fractional
        else:
            assert type(built.error) is type(sdk.error), (sdk.error, built.error)
            assert str(built.error) == str(sdk.error)
        return
    assert built.error is None, f"SDK sent {sdk.request}; pure refused {built.error!r}"
    expected = type(sdk.request)()
    expected.CopyFrom(sdk.request)
    for path, prefix in generated:
        *parents, name = path.split(".")
        holder = expected
        for parent in parents:
            holder = getattr(holder, parent)
        assert getattr(holder, name).startswith(prefix), getattr(holder, name)
        holder.ClearField(name)
    assert json_format.MessageToDict(expected) == built.request
    assert json_format.ParseDict(built.request, type(expected)()) == expected


def now_utc() -> datetime:
    return datetime.now(UTC)
