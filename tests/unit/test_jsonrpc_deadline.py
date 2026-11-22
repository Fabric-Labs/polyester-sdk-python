"""JsonRpcClient.request ends by its deadline in every phase of a call.

Loopback servers stall a call at each phase: plain HTTP and HTTPS, directly
and through an HTTP CONNECT proxy (the tunnel's CONNECT answer, the TLS
handshake inside it, partial or complete headers, the body). The call must end
within its budget, not a per-phase read timeout later. The HTTPS server uses a
throwaway self-signed certificate that the client trusts through
SSL_CERT_FILE.
"""

from __future__ import annotations

import contextlib
import datetime
import ipaddress
import json
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from polyester.chain.rpc import JsonRpcClient, JsonRpcError

BUDGET_S = 0.65
# The budget plus scheduling slack; a per-phase read timeout would add a
# whole second budget.
LIMIT_S = 0.95
STALL_S = 3.0

Handler = Callable[[socket.socket], None]


def _read_head(conn: socket.socket) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    return data


def _partial_headers(conn: socket.socket) -> None:
    """Read the request, then send the status line and some headers at 350 ms
    and never the blank line that ends them."""
    _read_head(conn)
    time.sleep(0.35)
    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\n")
    time.sleep(STALL_S)


def _headers_then_stall(conn: socket.socket) -> None:
    _read_head(conn)
    time.sleep(0.35)
    conn.sendall(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n"
    )
    time.sleep(STALL_S)


def _answer(conn: socket.socket) -> None:
    head = _read_head(conn)
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    body = head.split(b"\r\n\r\n", 1)[1]
    while len(body) < length:
        body += conn.recv(65536)
    request = json.loads(body)
    payload = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": "0x1"}).encode()
    conn.sendall(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
        + payload
    )


class _Server:
    """A loopback listener running ``handler`` for each connection."""

    def __init__(self, handler: Handler, *, tls: ssl.SSLContext | None = None) -> None:
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._handler = handler
        self._tls = tls
        self._closed = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while not self._closed:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            if self._tls is None and conn.recv(7, socket.MSG_PEEK) == b"HEAD / ":
                # A tool on the host probing listening ports, not the client.
                conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                return
            if self._tls is not None:
                conn = self._tls.wrap_socket(conn, server_side=True)
            self._handler(conn)
        except OSError:
            pass  # the client gave up
        finally:
            conn.close()

    def close(self) -> None:
        self._closed = True
        self._listener.close()


def _proxy(target_port: int, *, answer_after_s: float = 0.0, forward: bool = True) -> Handler:
    """An HTTP CONNECT proxy to the loopback ``target_port``.

    It answers CONNECT after ``answer_after_s``; with ``forward`` False it then
    passes nothing on, so the TLS handshake inside the tunnel stalls.
    """

    def handle(conn: socket.socket) -> None:
        head = _read_head(conn)
        assert head.startswith(b"CONNECT "), head[:40]
        time.sleep(answer_after_s)
        conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        if not forward:
            time.sleep(STALL_S)
            return
        upstream = socket.create_connection(("127.0.0.1", target_port))

        def pipe(src: socket.socket, dst: socket.socket) -> None:
            try:
                while chunk := src.recv(65536):
                    dst.sendall(chunk)
            except OSError:
                pass
            finally:
                for s in (src, dst):
                    with contextlib.suppress(OSError):
                        s.shutdown(socket.SHUT_RDWR)

        threading.Thread(target=pipe, args=(upstream, conn), daemon=True).start()
        pipe(conn, upstream)
        upstream.close()

    return handle


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A throwaway self-signed certificate for 127.0.0.1 and localhost."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    directory = tmp_path_factory.mktemp("tls")
    cert_path = directory / "cert.pem"
    key_path = directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


@pytest.fixture
def servers(
    certificate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., _Server]]:
    cert_path, key_path = certificate
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(cert_path, key_path)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))
    for name in (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    started: list[_Server] = []

    def start(handler: Handler, *, tls: bool = False) -> _Server:
        server = _Server(handler, tls=server_tls if tls else None)
        started.append(server)
        return server

    yield start
    for server in started:
        server.close()


def _timed_request(url: str) -> tuple[float, BaseException | None, object]:
    started = time.monotonic()
    try:
        result = JsonRpcClient(url, timeout=5.0).request("eth_chainId", [], timeout=BUDGET_S)
    except Exception as exc:  # noqa: BLE001 - the test inspects it
        return time.monotonic() - started, exc, None
    return time.monotonic() - started, None, result


def _assert_ends_by_the_deadline(url: str) -> None:
    elapsed, error, _ = _timed_request(url)
    assert isinstance(error, JsonRpcError), error
    assert "timed out" in str(error)
    assert elapsed < LIMIT_S, f"took {elapsed:.3f}s on a {BUDGET_S}s budget"


@pytest.mark.parametrize("stall", [_partial_headers, _headers_then_stall])
@pytest.mark.parametrize("tls", [False, True], ids=["http", "https"])
def test_direct_stall_after_the_request_ends_by_the_deadline(
    servers: Callable[..., _Server], stall: Handler, tls: bool
) -> None:
    server = servers(stall, tls=tls)
    scheme = "https" if tls else "http"
    _assert_ends_by_the_deadline(f"{scheme}://127.0.0.1:{server.port}")


@pytest.mark.parametrize("stall", [_partial_headers, _headers_then_stall])
def test_stall_inside_a_proxy_tunnel_ends_by_the_deadline(
    servers: Callable[..., _Server], stall: Handler, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = servers(stall, tls=True)
    proxy = servers(_proxy(target.port))
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{proxy.port}")
    _assert_ends_by_the_deadline(f"https://localhost:{target.port}")


def test_stalled_tls_handshake_in_a_proxy_tunnel_ends_by_the_deadline(
    servers: Callable[..., _Server], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The proxy answers CONNECT at 350 ms and then passes nothing on, so the
    # TLS handshake inside the tunnel never completes.
    target = servers(_answer, tls=True)
    proxy = servers(_proxy(target.port, answer_after_s=0.35, forward=False))
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{proxy.port}")
    _assert_ends_by_the_deadline(f"https://localhost:{target.port}")


def test_stalled_connect_answer_ends_by_the_deadline(
    servers: Callable[..., _Server], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = servers(_answer, tls=True)
    proxy = servers(_proxy(target.port, answer_after_s=STALL_S))
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{proxy.port}")
    _assert_ends_by_the_deadline(f"https://localhost:{target.port}")


@pytest.mark.parametrize("proxied", [False, True], ids=["direct", "proxy"])
def test_an_answer_in_time_is_returned(
    servers: Callable[..., _Server], monkeypatch: pytest.MonkeyPatch, proxied: bool
) -> None:
    # Control: the same HTTPS setup answers normally within the budget.
    target = servers(_answer, tls=True)
    if proxied:
        proxy = servers(_proxy(target.port))
        monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{proxy.port}")
    elapsed, error, result = _timed_request(f"https://localhost:{target.port}")
    assert error is None, error
    assert result == "0x1"
    assert elapsed < LIMIT_S
