"""POLY-9228: catalog startup through an HTTPS proxy that drops or stalls a read.

A local HTTPS API (a test CA's certificate, HTTP/1.1 keep-alive) sits behind a local
HTTP CONNECT proxy, and the client's pyqwest transports trust the test CA and use the
proxy, so each request crosses a real TLS tunnel. The API can drop its connection
when a request arrives, which the client sees as the reported
``peer closed connection without sending TLS close_notify``, or hold the request
until the client gives up.

Startup must retry a dropped catalog read on a fresh connection, surface a stalled one
within its deadline, keep spot trading independent of the funding config, and name
the failing operation without leaking the proxy's credentials.
"""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import ssl
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pyqwest
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from polyester import AsyncPolyester, Polyester
from polyester.errors import (
    PolyesterCatalogHydrationError,
    PolyesterError,
    PolyesterServerError,
    PolyesterValidationError,
)
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.transport import _ConnectHTTPClient
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

SYMBOL = "BTC-USDT"
SYMBOL_ID = 1
SPOT = "marketdata.v1.MarketDataService/GetSpotConfig"
FUNDING = "chain.zipper.v1.ZipperService/GetDepositWithdrawConfig"
# Synthetic proxy credentials: they must never reach an error message.
PROXY_USER = "sdk-test-user"
PROXY_SECRET = "proxy-secret-9228"

Action = Literal["ok", "drop", "stall"]


def _spot_config_body() -> bytes:
    spot = marketdata_pb2.GetSpotConfigResponse()
    for code, scale in (("BTC", 8), ("USDT", 6)):
        asset = spot.assets.add()
        asset.asset = code
        asset.quantity_scale = scale
        asset.market_data_volume_scale = scale
    pair = spot.pairs.add()
    pair.symbol = SYMBOL
    pair.symbol_id = SYMBOL_ID
    pair.base_asset = "BTC"
    pair.quote_asset = "USDT"
    pair.base_quantity_scale = 8
    pair.quote_quantity_scale = 6
    pair.reference_price_scale = 9
    return spot.SerializeToString()


def _funding_config_body() -> bytes:
    config = zipper_pb2.GetDepositWithdrawConfigResponse()
    asset = config.assets.add()
    asset.asset = "USDT"
    asset.ledger_id = 2
    asset.quantity_scale = 6
    return config.SerializeToString()


def _test_pki() -> tuple[bytes, bytes, bytes]:
    """A throwaway CA and a certificate it signs for localhost and 127.0.0.1."""
    now = datetime.datetime.now(datetime.UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "polyester sdk test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    pem = serialization.Encoding.PEM
    key_pem = key.private_bytes(
        pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return ca.public_bytes(pem), cert.public_bytes(pem), key_pem


@dataclass
class _TlsApi:
    """An HTTPS Connect API whose answer to each request a plan decides."""

    plan: Callable[[str, int], Action]
    requests: list[str] = field(default_factory=list)
    connections: list[int] = field(default_factory=list)
    _server: asyncio.Server | None = None
    _writers: set[asyncio.StreamWriter] = field(default_factory=set)
    port: int = 0

    async def start(self, cert_dir: Path) -> None:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_dir / "cert.pem", cert_dir / "key.pem")
        context.set_alpn_protocols(["http/1.1"])
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0, ssl=context)
        self.port = self._server.sockets[0].getsockname()[1]

    async def aclose(self) -> None:
        for writer in list(self._writers):
            writer.transport.abort()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def count(self, operation: str) -> int:
        return sum(1 for path in self.requests if path.endswith(operation))

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        connection = len(self.connections)
        self.connections.append(connection)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                path = line.split()[1].decode()
                length = 0
                while (header := await reader.readline()) not in (b"\r\n", b""):
                    name, _, value = header.decode().partition(":")
                    if name.strip().lower() == "content-length":
                        length = int(value)
                await reader.readexactly(length)
                operation = path.strip("/")
                self.requests.append(operation)
                action = self.plan(operation, self.count(operation))
                if action == "drop":
                    # No close_notify: the client sees the tunnel close mid-request.
                    writer.transport.abort()
                    return
                if action == "stall":
                    await reader.read()
                    return
                writer.write(_answer(operation))
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, ssl.SSLError):
            return
        finally:
            self._writers.discard(writer)
            writer.transport.abort()


def _answer(operation: str) -> bytes:
    if operation == SPOT:
        body = _spot_config_body()
    elif operation == FUNDING:
        body = _funding_config_body()
    else:
        payload = b'{"code":"failed_precondition","message":"stub"}'
        return (
            b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(payload)}\r\n\r\n".encode()
            + payload
        )
    return (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/proto\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )


@dataclass
class _ConnectProxy:
    """An HTTP CONNECT proxy that pipes each tunnel to the API."""

    upstream_port: int
    tunnels: int = 0
    _server: asyncio.Server | None = None
    _writers: set[asyncio.StreamWriter] = field(default_factory=set)
    port: int = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def aclose(self) -> None:
        for writer in list(self._writers):
            writer.transport.abort()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            assert head.startswith(b"CONNECT "), head
            self.tunnels += 1
            up_reader, up_writer = await asyncio.open_connection("127.0.0.1", self.upstream_port)
            self._writers.add(up_writer)
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            await asyncio.gather(_pipe(reader, up_writer), _pipe(up_reader, writer))
        except (ConnectionError, asyncio.IncompleteReadError):
            return
        finally:
            writer.transport.abort()


async def _pipe(source: asyncio.StreamReader, sink: asyncio.StreamWriter) -> None:
    try:
        while data := await source.read(65536):
            sink.write(data)
            await sink.drain()
    except ConnectionError:
        pass
    finally:
        # Closing one side closes the tunnel, as a proxy does.
        sink.transport.abort()


class _ProxiedApi:
    """The API behind the proxy, and clients whose transports go through both."""

    def __init__(self, plan: Callable[[str, int], Action], tmp_path: Path) -> None:
        self.api = _TlsApi(plan)
        self.tmp_path = tmp_path
        self.proxy: _ConnectProxy | None = None
        self.ca = b""
        self.clients: list[AsyncPolyester] = []

    async def __aenter__(self) -> _ProxiedApi:
        ca, cert, key = _test_pki()
        self.ca = ca
        (self.tmp_path / "cert.pem").write_bytes(cert)
        (self.tmp_path / "key.pem").write_bytes(key)
        await self.api.start(self.tmp_path)
        self.proxy = _ConnectProxy(self.api.port)
        await self.proxy.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        for client in self.clients:
            await client.aclose()
        if self.proxy is not None:
            await self.proxy.aclose()
        await self.api.aclose()

    @property
    def proxy_url(self) -> str:
        assert self.proxy is not None
        return f"http://{PROXY_USER}:{PROXY_SECRET}@127.0.0.1:{self.proxy.port}"

    def transport(self) -> pyqwest.HTTPTransport:
        return pyqwest.HTTPTransport(tls_ca_cert=self.ca, proxy=self.proxy_url)

    def client(self, **kwargs: Any) -> AsyncPolyester:
        creds = make_test_credentials()
        client = AsyncPolyester(
            api_url=f"https://localhost:{self.api.port}",
            ws_url="ws://127.0.0.1:9/unused",
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            default_account_id=1,
            **kwargs,
        )
        # Construction only schedules hydration, so every request goes through here.
        shared = pyqwest.Client(self.transport())
        client._transport._connect_http = _ConnectHTTPClient(shared, signed=shared)
        client._transport._new_http_transport = self.transport  # type: ignore[attr-defined]
        self.clients.append(client)
        return client


def _drop_once(target: str) -> Callable[[str, int], Action]:
    return lambda operation, seen: "drop" if operation == target and seen == 1 else "ok"


def _stall(target: str) -> Callable[[str, int], Action]:
    return lambda operation, _seen: "stall" if operation == target else "ok"


_LIMIT_ORDER: dict[str, Any] = {
    "symbol": SYMBOL,
    "side": "buy",
    "order_type": "limit",
    "tif": "gtc",
    "qty": "1",
    "price": "0.1",
}


async def _assert_spot_order_path_works(client: AsyncPolyester) -> None:
    """The order reaches the server: it was not refused for its catalogs."""
    with pytest.raises(PolyesterError) as info:
        await client.orders.create(**_LIMIT_ORDER)
    assert not isinstance(info.value, (PolyesterCatalogHydrationError, PolyesterValidationError))
    assert "stub" in str(info.value)


def _assert_redacted(error: BaseException) -> None:
    seen: BaseException | None = error
    while seen is not None:
        for text in (str(seen), repr(seen)):
            assert PROXY_SECRET not in text, text
            assert PROXY_USER not in text, text
        seen = seen.__cause__


@pytest.mark.asyncio
async def test_funding_read_dropped_once_through_the_proxy_recovers(tmp_path: Path) -> None:
    async with _ProxiedApi(_drop_once(FUNDING), tmp_path) as harness:
        client = harness.client(timeout=5.0)
        await asyncio.wait_for(client.wait_for_catalogs(), 10)
        await asyncio.wait_for(client.wait_for_funding_catalog(), 10)
        assert harness.api.count(FUNDING) == 2
        assert client.catalogs.ledger_id_for_asset("USDT") == 2
        assert client.catalogs.symbol_id_for_symbol(SYMBOL) == SYMBOL_ID
        await _assert_spot_order_path_works(client)


@pytest.mark.asyncio
async def test_spot_read_dropped_once_through_the_proxy_recovers(tmp_path: Path) -> None:
    async with _ProxiedApi(_drop_once(SPOT), tmp_path) as harness:
        client = harness.client(timeout=5.0)
        await asyncio.wait_for(client.wait_for_catalogs(), 10)
        assert harness.api.count(SPOT) == 2
        await _assert_spot_order_path_works(client)


@pytest.mark.asyncio
async def test_persistent_funding_stall_leaves_spot_trading_ready(tmp_path: Path) -> None:
    async with _ProxiedApi(_stall(FUNDING), tmp_path) as harness:
        started = time.monotonic()
        client = harness.client(timeout=0.5, catalog_timeout=1.5)
        await asyncio.wait_for(client.wait_for_catalogs(), 5)
        assert time.monotonic() - started < 1.0, "spot readiness waited for the funding config"
        await _assert_spot_order_path_works(client)

        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await asyncio.wait_for(client.wait_for_funding_catalog(), 5)
        elapsed = time.monotonic() - started
        assert elapsed < 1.5 + 0.5, f"the stall surfaced after {elapsed:.2f}s"
        error = info.value
        assert error.catalog == "funding"
        assert error.operation == FUNDING
        assert error.failure == "timeout"
        assert error.attempts == harness.api.count(FUNDING) >= 2
        assert "funding config" in str(error)
        assert FUNDING in str(error)
        assert "timed out" in str(error)
        assert error.__cause__ is not None
        _assert_redacted(error)
        # Each retry opened a tunnel of its own instead of queueing behind the stall.
        assert harness.proxy is not None
        assert harness.proxy.tunnels >= 1 + error.attempts

        with pytest.raises(PolyesterCatalogHydrationError, match="funding config"):
            await client.zipper.subscribe_zipped_asset_supply()
        # Trading still works once funding has failed.
        await _assert_spot_order_path_works(client)
        assert client.catalogs.ledger_id_for_asset("USDT") is None


@pytest.mark.asyncio
async def test_persistent_spot_stall_fails_closed_within_the_deadline(tmp_path: Path) -> None:
    async with _ProxiedApi(_stall(SPOT), tmp_path) as harness:
        started = time.monotonic()
        client = harness.client(timeout=0.5, catalog_timeout=1.5)
        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await asyncio.wait_for(client.wait_for_catalogs(), 5)
        assert time.monotonic() - started < 1.5 + 0.5
        error = info.value
        assert (error.catalog, error.operation, error.failure) == ("spot", SPOT, "timeout")
        assert "spot config" in str(error)
        _assert_redacted(error)
        with pytest.raises(PolyesterCatalogHydrationError, match="spot config"):
            await client.orders.create(**_LIMIT_ORDER)
        assert harness.api.count("CreateOrder") == 0
        # The funding config loaded on its own.
        await client.wait_for_funding_catalog()
        assert client.catalogs.ledger_id_for_asset("USDT") == 2


@pytest.mark.asyncio
async def test_persistently_dropped_funding_read_names_a_closed_connection(
    tmp_path: Path,
) -> None:
    def plan(op: str, _seen: int) -> Action:
        return "drop" if op == FUNDING else "ok"

    async with _ProxiedApi(plan, tmp_path) as harness:
        client = harness.client(timeout=5.0)
        await client.wait_for_catalogs()
        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await asyncio.wait_for(client.wait_for_funding_catalog(), 10)
        error = info.value
        assert error.failure == "connection_closed"
        assert error.attempts == 3 == harness.api.count(FUNDING)
        assert "connection closed" in str(error)
        assert "close_notify" in str(error)
        assert isinstance(error.__cause__, PolyesterServerError)
        _assert_redacted(error)


@pytest.mark.asyncio
async def test_a_dropped_order_is_never_retried(tmp_path: Path) -> None:
    def plan(op: str, _seen: int) -> Action:
        return "drop" if op.endswith("CreateOrder") else "ok"

    async with _ProxiedApi(plan, tmp_path) as harness:
        client = harness.client(timeout=5.0)
        await client.wait_for_catalogs()
        with pytest.raises(PolyesterServerError, match="close_notify"):
            await client.orders.create(**_LIMIT_ORDER)
        assert harness.api.count("orders.v1.OrdersService/CreateOrder") == 1


# Plain-HTTP cases: the retry bound and what a failure reports.


async def _plain_api(
    handler: Callable[[ParsedRequest], HttpScript | Awaitable[HttpScript]],
) -> MockHttpServer:
    return await MockHttpServer.spawn(handler)


def _proto(body: bytes) -> HttpScript:
    return HttpScript.raw(200, headers=[("Content-Type", "application/proto")], body=body)


def _unavailable(ref: str) -> HttpScript:
    payload = b'{"code":"unavailable","message":"edge unavailable"}'
    return HttpScript.raw(
        503,
        headers=[("Content-Type", "application/json"), ("cf-ray", ref)],
        body=payload,
    )


@pytest.mark.asyncio
async def test_unavailable_funding_read_stops_after_three_attempts_with_its_reference() -> None:
    funding_requests = 0

    def handler(req: ParsedRequest) -> HttpScript:
        nonlocal funding_requests
        if req.path.endswith("/GetSpotConfig"):
            return _proto(_spot_config_body())
        if req.path.endswith("/GetDepositWithdrawConfig"):
            funding_requests += 1
            return _unavailable(f"a5711ea9d826{funding_requests:04d}-LAX")
        return HttpScript.json(400, b'{"code":"failed_precondition","message":"stub"}')

    http = await _plain_api(handler)
    client = AsyncPolyester(api_url=http.base_url, ws_url="ws://127.0.0.1:9/unused", timeout=2.0)
    try:
        await client.wait_for_catalogs()
        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await asyncio.wait_for(client.wait_for_funding_catalog(), 10)
        error = info.value
        assert funding_requests == 3 == error.attempts
        assert error.failure == "unavailable"
        assert error.response_ref == "a5711ea9d8260003-LAX"
        assert "response ref a5711ea9d8260003-LAX" in str(error)
        assert isinstance(error.__cause__, PolyesterServerError)
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
async def test_an_invalid_spot_config_is_not_retried_and_fails_closed() -> None:
    spot_requests = 0

    def handler(req: ParsedRequest) -> HttpScript:
        nonlocal spot_requests
        if req.path.endswith("/GetSpotConfig"):
            spot_requests += 1
            return _proto(marketdata_pb2.GetSpotConfigResponse().SerializeToString())
        if req.path.endswith("/GetDepositWithdrawConfig"):
            return _proto(_funding_config_body())
        return HttpScript.json(400, b'{"code":"failed_precondition","message":"stub"}')

    http = await _plain_api(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        ws_url="ws://127.0.0.1:9/unused",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        default_account_id=1,
        timeout=2.0,
    )
    try:
        with pytest.raises(PolyesterCatalogHydrationError) as info:
            await client.wait_for_catalogs()
        error = info.value
        assert spot_requests == 1
        assert (error.catalog, error.failure, error.attempts) == ("spot", "invalid", 1)
        assert isinstance(error.__cause__, PolyesterValidationError)
        assert client.catalogs_last_error is error.__cause__
        with pytest.raises(PolyesterCatalogHydrationError, match="spot config"):
            await client.orders.create(**_LIMIT_ORDER)
        await client.wait_for_funding_catalog()
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("value", [0, -1.0, float("nan"), float("inf"), "10", True])
def test_catalog_timeout_must_be_a_positive_number_of_seconds(value: object) -> None:
    with pytest.raises(PolyesterValidationError, match="catalog_timeout"):
        AsyncPolyester(hydrate_catalogs=False, catalog_timeout=value)  # type: ignore[arg-type]


def test_sync_client_starts_when_only_the_funding_config_stalls() -> None:
    server_loop = asyncio.new_event_loop()
    server_thread = threading.Thread(target=server_loop.run_forever, daemon=True)
    server_thread.start()

    def handler(req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/GetSpotConfig"):
            return _proto(_spot_config_body())
        if req.path.endswith("/GetDepositWithdrawConfig"):
            return HttpScript.never_respond()
        return HttpScript.json(400, b'{"code":"failed_precondition","message":"stub"}')

    http = asyncio.run_coroutine_threadsafe(_plain_api(handler), server_loop).result(10)
    try:
        started = time.monotonic()
        client = Polyester(
            api_url=http.base_url,
            ws_url="ws://127.0.0.1:9/unused",
            timeout=0.5,
            catalog_timeout=1.0,
        )
        try:
            assert time.monotonic() - started < 1.0
            assert client.catalogs.symbol_id_for_symbol(SYMBOL) == SYMBOL_ID
            with pytest.raises(PolyesterCatalogHydrationError, match="funding config"):
                client.wait_for_funding_catalog()
        finally:
            client.close()
    finally:
        asyncio.run_coroutine_threadsafe(http.aclose(), server_loop).result(10)
        server_loop.call_soon_threadsafe(server_loop.stop)
        server_thread.join(5)
