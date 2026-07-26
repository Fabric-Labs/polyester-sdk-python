"""POLY-3746 L1 helper-level regressions (private fetch_rt_token / local stall HTTP).

Public-API L2 coverage lives in ``tests/hardening/test_hardening_l2.py``.
"""

from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError
from polyester.realtime.auth import fetch_rt_token


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _StallHandler(BaseHTTPRequestHandler):
    stall_seconds = 30.0

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        # Headers flushed; stall body past client timeout (F-18).
        time.sleep(self.stall_seconds)

    def do_POST(self) -> None:  # noqa: N802
        self.do_GET()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


@pytest.fixture
def stall_server():
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _StallHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


@pytest.mark.asyncio
async def test_l1_token_headers_then_stalled_body_times_out(stall_server: str) -> None:
    """L1: private fetch_rt_token respects httpx body timeout (F-18)."""
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    creds = ApiKeyCredentials(key_id="ak_test", private_key=private)
    timeout = httpx.Timeout(0.4)
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as http:
        with pytest.raises(Exception) as exc_info:
            await fetch_rt_token(
                http,
                creds,
                url=f"{stall_server}/v1/rt/token",
                label="realtime connection token",
            )
    elapsed = time.monotonic() - started
    assert elapsed < 1.2, f"body likely outside timeout; elapsed={elapsed}"
    msg = str(exc_info.value).lower()
    assert "timeout" in msg or "timed out" in msg or isinstance(
        exc_info.value, (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout)
    )


@pytest.mark.asyncio
async def test_l1_token_slow_drip_hits_wall_clock_deadline() -> None:
    """L1: slow-drip chunks each under read timeout still fail total deadline."""
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    creds = ApiKeyCredentials(key_id="ak_test", private_key=private)
    timeout = 0.4

    class _SlowHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for part in (b'{"tok', b'en":"', b"abc", b'"}'):
                time.sleep(0.15)
                self.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as http:
            with pytest.raises(Exception) as exc_info:
                await fetch_rt_token(
                    http,
                    creds,
                    url=f"http://127.0.0.1:{port}/v1/rt/token",
                    label="realtime connection token",
                )
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"slow-drip escaped wall clock; elapsed={elapsed}"
        msg = str(exc_info.value).lower()
        assert "timeout" in msg or "timed out" in msg
    finally:
        server.shutdown()


@pytest.mark.asyncio
async def test_l1_token_403_is_auth_not_realtime() -> None:
    body = b'{"code":"permission_denied","message":"missing transfer:read"}'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=body)

    private = Ed25519PrivateKey.generate().private_bytes_raw()
    creds = ApiKeyCredentials(key_id="ak_test", private_key=private)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, timeout=2.0) as http:
        with pytest.raises(PolyesterAuthError) as exc_info:
            await fetch_rt_token(
                http,
                creds,
                url="https://api.example.test/v1/rt/token",
                label="realtime connection token",
            )
    assert exc_info.value.status_code == 403
    assert "permission" in str(exc_info.value).lower()
