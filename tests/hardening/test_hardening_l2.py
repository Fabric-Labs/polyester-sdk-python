"""POLY-3746 L2 integration tests via public SDK APIs + local mock HTTP/WS.

These exercise production paths (subscribe_proto, JsonRpcClient, wait_for_catalogs,
wait_for_order_trades_complete, balances.list, Quantity/place scale resolution)
against in-process servers — not private helpers like fetch_rt_token.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import time

import httpx
import pytest

from polyester import AsyncPolyester, Quantity
from polyester.auth import (
    MAX_SIGNING_FUTURE_SKEW_MS,
    ApiKeyCredentials,
    sign_request_async,
)
from polyester.catalogs import CatalogManager
from polyester.chain.rpc import MAX_JSONRPC_RESPONSE_BYTES, JsonRpcClient, JsonRpcError
from polyester.codecs import MAX_PROTOCOL_SCALE, format_qty_scaled
from polyester.codecs.ledger_amounts import format_ledger_u128
from polyester.codecs.orders import quantity_scale_for_symbol, resolve_quantity_scale
from polyester.errors import (
    PolyesterAuthError,
    PolyesterRealtimeError,
    PolyesterResponseContractError,
    PolyesterTransportError,
    PolyesterValidationError,
)
from polyester.gen.chain.deposit.v1 import deposit_pb2
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.models import OrderId
from polyester.realtime.client import WS_MAX_MESSAGE_BYTES, AsyncRealtimeClient
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription
from polyester.transport import MAX_CONNECT_RESPONSE_BYTES
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    MockWsServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
    wait_until,
)

PRIVATE_CHANNEL = "private:spot:orders:acct:proto"
PUBLIC_CHANNEL = "public:spot:market:trades:1:proto"


def _identity_decode(payload: bytes) -> bytes:
    return payload


async def _private_rt(
    *,
    ws: MockWsServer,
    http: MockHttpServer,
    timeout: float = 0.4,
) -> tuple[AsyncRealtimeClient, httpx.AsyncClient]:
    creds = make_test_credentials()
    client_http = httpx.AsyncClient(timeout=timeout)
    rt = AsyncRealtimeClient(
        ws.ws_url(),
        api_url=http.base_url,
        credentials=creds,
        http=client_http,
    )
    return rt, client_http


async def _assert_peers_idle(http: MockHttpServer | None, ws: MockWsServer) -> None:
    await wait_until(
        lambda: (http is None or http.active == 0) and ws.active == 0,
        0.75,
    )


# ---------------------------------------------------------------------------
# Authentication burst capacity through the public async signer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_auth_10k_identical_requests_are_unique_bounded_and_runtime_safe() -> None:
    source = make_test_credentials()
    credentials = ApiKeyCredentials(
        key_id=source.key_id,
        private_key=source.private_key,
    )
    timer_ticks: list[float] = []
    ticker_running = True

    async def ticker() -> None:
        while ticker_running:
            timer_ticks.append(asyncio.get_running_loop().time())
            await asyncio.sleep(0.01)

    async def sign() -> tuple[dict[str, str], int]:
        headers = await sign_request_async(
            credentials,
            method="POST",
            url="https://api.example.test/foo",
            body=b"{}",
        )
        return headers, time.time_ns() // 1_000_000

    ticker_task = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    before = time.time_ns() // 1_000_000
    try:
        signed = await asyncio.gather(*(sign() for _ in range(10_000)))
    finally:
        ticker_running = False
        await ticker_task

    headers = [item[0] for item in signed]
    timestamps = [int(item["X-API-TIMESTAMP"]) for item in headers]
    assert min(timestamps) >= before
    assert all(
        int(item["X-API-TIMESTAMP"]) <= observed_at + MAX_SIGNING_FUTURE_SKEW_MS
        for item, observed_at in signed
    )
    assert len(set(timestamps)) == 10_000
    assert len({item["X-API-SIGNATURE"] for item in headers}) == 10_000
    assert len(timer_ticks) > 100
    # A synchronous five-second capacity wait would stall the loop; allow
    # scheduler jitter from creating and hashing 10k runnable tasks.
    assert max(b - a for a, b in zip(timer_ticks, timer_ticks[1:], strict=False)) < 2.0


# ---------------------------------------------------------------------------
# F-18 token path via subscribe_proto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_token_headers_then_stalled_body_times_out_via_subscribe_proto() -> None:
    timeout = 0.4

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.headers_then_stall(
                200,
                headers=[("Transfer-Encoding", "chunked")],
                stall=30.0,
            )
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=timeout)
    try:
        started = time.monotonic()
        with pytest.raises(Exception) as exc_info:
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"body likely outside timeout; elapsed={elapsed}"
        msg = str(exc_info.value).lower()
        assert "timeout" in msg or "timed out" in msg, exc_info.value
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_no_headers_times_out_via_subscribe_proto() -> None:
    timeout = 0.4

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.never_respond()
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=timeout)
    try:
        started = time.monotonic()
        with pytest.raises(Exception) as exc_info:
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"elapsed={elapsed}"
        msg = str(exc_info.value).lower()
        assert "timeout" in msg or "timed out" in msg, exc_info.value
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_slow_drip_exceeds_total_deadline_via_subscribe_proto() -> None:
    """Each chunk arrives before per-read timeout; total must still hit wall clock."""
    timeout = 0.4
    # 4 × 0.15s delays ≈ 0.6s > 0.4s deadline while each gap < read timeout.
    chunks = [b'{"tok', b'en":"', b"abc", b'"}']

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.slow_drip(200, chunks=chunks, delay=0.15)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=timeout)
    try:
        started = time.monotonic()
        with pytest.raises(Exception) as exc_info:
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"slow-drip escaped wall clock; elapsed={elapsed}"
        msg = str(exc_info.value).lower()
        assert "timeout" in msg or "timed out" in msg, exc_info.value
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_content_length_65537_rejected_via_subscribe_proto() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.raw(
                200,
                headers=[
                    ("Content-Type", "application/json"),
                    ("Content-Length", "65537"),
                ],
                body=b"",
            )
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=2.0)
    try:
        with pytest.raises(PolyesterRealtimeError, match="exceeds"):
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_chunked_over_64kib_rejected_via_subscribe_proto() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.chunked_body(200, total_bytes=70_000, chunk_size=4096)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=2.0)
    try:
        with pytest.raises(PolyesterRealtimeError, match="exceeds"):
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_empty_token_rejected_via_subscribe_proto() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.json(200, {"token": ""})
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=2.0)
    try:
        with pytest.raises(PolyesterRealtimeError, match="missing token"):
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_malformed_json_rejected_via_subscribe_proto() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.raw(
                200,
                headers=[("Content-Type", "application/json")],
                body=b"{not-json",
            )
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=2.0)
    try:
        with pytest.raises(PolyesterRealtimeError, match="not valid JSON"):
            await rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode)
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_token_http_403_maps_to_auth_not_realtime() -> None:
    body = b'{"code":"permission_denied","message":"missing transfer:read"}'

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path == "/v1/rt/token":
            return HttpScript.json(200, b'{"token":"connection-ok"}')
        if req.path.startswith("/v1/rt/subscribe"):
            return HttpScript.json(403, body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_centrifugo_public()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=2.0)
    try:
        with pytest.raises(PolyesterAuthError) as exc_info:
            await rt.subscribe_proto(
                "private:auth:transfers:acct:proto",
                decode=_identity_decode,
            )
        err = exc_info.value
        assert err.status_code == 403
        assert err.code == "permission_denied"
        assert err.context is not None and "private:auth:transfers:acct:proto" in err.context
        assert err.endpoint is not None and "/v1/rt/subscribe?channel=" in err.endpoint
        text = str(err).lower()
        assert "permission" in text
        assert "http 403" in text
        assert "transfer:read" in text
        await _assert_peers_idle(http, ws)
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


# ---------------------------------------------------------------------------
# E5 JSON-RPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_jsonrpc_headers_then_stalled_body_times_out() -> None:
    timeout = 0.4
    http = await MockHttpServer.spawn(
        lambda _req: HttpScript.headers_then_stall(
            200,
            headers=[
                ("Content-Type", "application/json"),
                ("Transfer-Encoding", "chunked"),
            ],
            stall=30.0,
        )
    )
    try:
        rpc = JsonRpcClient(http.base_url, timeout=timeout)
        started = time.monotonic()
        with pytest.raises(Exception) as exc_info:
            await asyncio.to_thread(rpc.request, "eth_chainId", [])
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"elapsed={elapsed}"
        assert "timeout" in str(exc_info.value).lower() or "timed" in str(exc_info.value).lower()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_jsonrpc_no_headers_times_out() -> None:
    timeout = 0.4
    http = await MockHttpServer.spawn(lambda _req: HttpScript.never_respond())
    try:
        rpc = JsonRpcClient(http.base_url, timeout=timeout)
        started = time.monotonic()
        with pytest.raises(Exception) as exc_info:
            await asyncio.to_thread(rpc.request, "eth_chainId", [])
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"elapsed={elapsed}"
        assert "timeout" in str(exc_info.value).lower() or "timed" in str(exc_info.value).lower()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_jsonrpc_slow_drip_exceeds_total_deadline() -> None:
    timeout = 0.4
    chunks = [b'{"json', b'rpc":"2', b'.0","id"', b':1,"res', b'ult":1}']

    http = await MockHttpServer.spawn(
        lambda _req: HttpScript.slow_drip(200, chunks=chunks, delay=0.15)
    )
    try:
        rpc = JsonRpcClient(http.base_url, timeout=timeout)
        started = time.monotonic()
        with pytest.raises(Exception) as exc_info:
            await asyncio.to_thread(rpc.request, "eth_chainId", [])
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"slow-drip escaped wall clock; elapsed={elapsed}"
        assert "timeout" in str(exc_info.value).lower() or "timed" in str(exc_info.value).lower()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_jsonrpc_async_slow_drip_exceeds_total_deadline() -> None:
    timeout = 0.4
    chunks = [b'{"json', b'rpc":"2', b'.0","id"', b':1,"res', b'ult":1}']
    http = await MockHttpServer.spawn(
        lambda _req: HttpScript.slow_drip(200, chunks=chunks, delay=0.15)
    )
    try:
        rpc = JsonRpcClient(http.base_url, timeout=timeout)
        started = time.monotonic()
        with pytest.raises(JsonRpcError, match="timed out"):
            await rpc.arequest("eth_chainId", [])
        elapsed = time.monotonic() - started
        assert elapsed < timeout + 0.8, f"elapsed={elapsed}"
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_jsonrpc_rejects_oversized_chunked_and_envelopes() -> None:
    big_body = b"x" * (2 * 1024 * 1024)

    async def handler(req: ParsedRequest) -> HttpScript:
        path = req.path
        if "big" in path:
            return HttpScript.raw(
                200,
                headers=[
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(big_body))),
                ],
                body=big_body,
            )
        if "chunkbig" in path:
            return HttpScript.chunked_body(
                200,
                total_bytes=MAX_JSONRPC_RESPONSE_BYTES + 1,
                chunk_size=64 * 1024,
            )
        if "badjson" in path:
            return HttpScript.raw(
                200,
                headers=[("Content-Type", "application/json")],
                body=b"{not-json",
            )
        if "ver" in path:
            return HttpScript.json(200, b'{"jsonrpc":"1.0","id":1,"result":1}')
        if "noid" in path:
            return HttpScript.json(200, b'{"jsonrpc":"2.0","result":1}')
        if "wrongid" in path:
            return HttpScript.json(200, b'{"jsonrpc":"2.0","id":999,"result":1}')
        if "neither" in path:
            return HttpScript.json(200, b'{"jsonrpc":"2.0","id":1}')
        if "malerr" in path:
            return HttpScript.json(200, b'{"jsonrpc":"2.0","id":1,"error":"boom"}')
        if "nullok" in path:
            return HttpScript.json(200, b'{"jsonrpc":"2.0","id":1,"result":null}')
        return HttpScript.json(
            200,
            b'{"jsonrpc":"2.0","id":1,"result":1,"error":{"code":-1,"message":"x"}}',
        )

    http = await MockHttpServer.spawn(handler)
    try:
        base = http.base_url
        with pytest.raises(JsonRpcError, match="exactly one"):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/ok", timeout=2.0).request, "eth_call", []
            )

        with pytest.raises(JsonRpcError) as big_exc:
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/big", timeout=2.0).request, "eth_call", []
            )
        assert "exceeds" in str(big_exc.value).lower()

        with pytest.raises(JsonRpcError) as chunk_exc:
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/chunkbig", timeout=2.0).request, "eth_call", []
            )
        assert "exceeds" in str(chunk_exc.value).lower()

        with pytest.raises(JsonRpcError, match="not valid JSON"):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/badjson", timeout=2.0).request, "eth_call", []
            )
        with pytest.raises(JsonRpcError, match='jsonrpc="2.0"'):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/ver", timeout=2.0).request, "eth_call", []
            )
        with pytest.raises(JsonRpcError, match="id mismatch"):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/noid", timeout=2.0).request, "eth_call", []
            )
        with pytest.raises(JsonRpcError, match="id mismatch"):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/wrongid", timeout=2.0).request, "eth_call", []
            )
        with pytest.raises(JsonRpcError, match="exactly one"):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/neither", timeout=2.0).request, "eth_call", []
            )
        with pytest.raises(JsonRpcError, match="error must be an object"):
            await asyncio.to_thread(
                JsonRpcClient(f"{base}/malerr", timeout=2.0).request, "eth_call", []
            )
        null_result = await asyncio.to_thread(
            JsonRpcClient(f"{base}/nullok", timeout=2.0).request, "eth_call", []
        )
        assert null_result is None
    finally:
        await http.aclose()


def test_l2_jsonrpc_25_concurrent_reordered_responses_succeed() -> None:
    """25 concurrent JsonRpcClient.request calls; server replies in shuffled id order."""
    import socket
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    barrier = threading.Barrier(25)
    seen: dict[int, None] = {}
    order_lock = threading.Lock()
    release_order: list[int] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            try:
                req_id = int(json.loads(body.decode()).get("id"))
            except Exception:
                self.send_error(400)
                return
            with order_lock:
                seen[req_id] = None
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                self.send_error(500)
                return
            with order_lock:
                if not release_order:
                    release_order.extend(seen.keys())
                    random.shuffle(release_order)
                idx = release_order.index(req_id)
            time.sleep(idx * 0.005)
            resp = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": f"0x{req_id:x}"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        host, port = s.getsockname()
    server = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rpc = JsonRpcClient(f"http://{host}:{port}", timeout=5.0)
        with ThreadPoolExecutor(max_workers=25) as pool:
            futures = [pool.submit(rpc.request, "eth_chainId", []) for _ in range(25)]
            results = [f.result(timeout=10) for f in as_completed(futures)]
        assert len(results) == 25
        assert all(isinstance(r, str) and r.startswith("0x") for r in results)
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# E6 close / cancel / soak
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_close_aborts_subscription_promptly_against_local_ws() -> None:
    ws = await MockWsServer.spawn_centrifugo_public()
    rt = AsyncRealtimeClient(ws.ws_url())
    try:
        sub = await rt.subscribe_proto(PUBLIC_CHANNEL, decode=_identity_decode)
        await wait_until(lambda: ws.active >= 1, 2.0)
        started = time.monotonic()
        await sub.aclose()
        await wait_until(lambda: not sub.is_alive, 0.75)
        await wait_until(lambda: ws.active == 0, 0.75)
        assert time.monotonic() - started < 0.75
    finally:
        await rt.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_hundred_sub_close_returns_conn_count_to_baseline() -> None:
    ws = await MockWsServer.spawn_centrifugo_public()
    rt = AsyncRealtimeClient(ws.ws_url())
    try:
        subs = []
        for _ in range(100):
            subs.append(await rt.subscribe_proto(PUBLIC_CHANNEL, decode=_identity_decode))
        await wait_until(lambda: ws.active >= 100, 5.0)
        started = time.monotonic()
        await asyncio.gather(*(s.aclose() for s in subs))
        await wait_until(lambda: ws.active == 0, 0.75)
        assert time.monotonic() - started < 0.75, "100-sub close soak exceeded 750ms"
    finally:
        await rt.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_realtime_oversized_binary_message_fails_closed() -> None:
    ws = await MockWsServer.spawn_centrifugo_oversized_after_handshake(WS_MAX_MESSAGE_BYTES + 1)
    rt = AsyncRealtimeClient(ws.ws_url())
    try:
        sub = await rt.subscribe_proto(PUBLIC_CHANNEL, decode=_identity_decode)
        await wait_until(lambda: sub.error is not None and not sub.is_alive, 3.0)
        error = str(sub.error).lower()
        assert "exceeds" in error or "too big" in error
        await wait_until(lambda: ws.active == 0, 0.75)
    finally:
        await rt.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_cancel_during_token_body_stall_no_orphan() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.headers_then_stall(
                200,
                headers=[("Transfer-Encoding", "chunked")],
                stall=30.0,
            )
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=30.0)
    try:
        task = asyncio.create_task(rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode))
        await wait_until(lambda: http.active >= 1, 2.0)
        started = time.monotonic()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # subscribe_proto shields teardown up to 1s; HTTP stall peer must drop.
        await wait_until(lambda: http.active == 0, 2.0)
        await wait_until(lambda: ws.active == 0, 2.0)
        assert time.monotonic() - started < 2.0
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_cancel_during_chunked_token_body_no_orphan() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.slow_drip(
                200,
                chunks=[b"x" * 1024 for _ in range(200)],
                delay=0.05,
            )
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    ws = await MockWsServer.spawn_hang_after_accept()
    rt, client_http = await _private_rt(ws=ws, http=http, timeout=30.0)
    try:
        task = asyncio.create_task(rt.subscribe_proto(PRIVATE_CHANNEL, decode=_identity_decode))
        await wait_until(lambda: http.active >= 1, 2.0)
        # Let at least one chunk land so cancel hits mid-body, not headers-only.
        await asyncio.sleep(0.08)
        started = time.monotonic()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await wait_until(lambda: http.active == 0, 2.0)
        await wait_until(lambda: ws.active == 0, 2.0)
        assert time.monotonic() - started < 2.0
    finally:
        await rt.aclose()
        await client_http.aclose()
        await http.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_cancel_during_centrifugo_wait_no_orphan() -> None:
    """Public channel: WS accepts but never replies to connect; cancel cleans up."""
    ws = await MockWsServer.spawn_hang_after_accept()
    rt = AsyncRealtimeClient(ws.ws_url())
    try:
        task = asyncio.create_task(rt.subscribe_proto(PUBLIC_CHANNEL, decode=_identity_decode))
        await wait_until(lambda: ws.active >= 1, 2.0)
        started = time.monotonic()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await wait_until(lambda: ws.active == 0, 2.0)
        assert time.monotonic() - started < 2.0
    finally:
        await rt.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_close_during_reconnect_backoff_no_extra_connect() -> None:
    ws = await MockWsServer.spawn_centrifugo_disconnect_after_handshake()
    rt = AsyncRealtimeClient(ws.ws_url())
    try:
        sub = await rt.subscribe_proto(PUBLIC_CHANNEL, decode=_identity_decode)
        await wait_until(lambda: ws.connects >= 1, 2.0)
        await wait_until(lambda: ws.active == 0, 2.0)
        connects_before = ws.connects
        await sub.aclose()
        await asyncio.sleep(1.2)
        assert ws.connects == connects_before, (
            f"close during reconnect backoff must not start an extra connect "
            f"({connects_before} -> {ws.connects})"
        )
        assert not sub.is_alive
    finally:
        await rt.aclose()
        await ws.aclose()


# ---------------------------------------------------------------------------
# F-19 catalogs via AsyncPolyester
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_wait_for_catalogs_fail_closed_on_http_500() -> None:
    http = await MockHttpServer.spawn(
        lambda _req: HttpScript.json(500, b'{"code":"internal","message":"nope"}')
    )
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            hydrate_catalogs=True,
            timeout=0.5,
        )
        with pytest.raises(Exception) as exc_info:
            await client.wait_for_catalogs()
        assert client.catalogs_last_error is not None
        assert client.catalogs.base_quantity_scale_for_symbol("BTC-USDT") is None
        assert str(exc_info.value)
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_wait_for_catalogs_fail_closed_on_empty_or_malformed() -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetSpotConfig" in req.path:
            body = marketdata_pb2.GetSpotConfigResponse().SerializeToString()
            return connect_proto_response(body)
        if "GetDepositWithdrawConfig" in req.path:
            body = zipper_pb2.GetDepositWithdrawConfigResponse().SerializeToString()
            return connect_proto_response(body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            hydrate_catalogs=True,
            timeout=2.0,
        )
        with pytest.raises(PolyesterValidationError, match="empty"):
            await client.wait_for_catalogs()
        assert client.catalogs.is_unusable
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "label"),
    [
        (b"\x0f", "malformed protobuf"),
        (b"x" * (MAX_CONNECT_RESPONSE_BYTES + 1), "oversized protobuf"),
    ],
)
async def test_l2_wait_for_catalogs_rejects_bad_wire_response(body: bytes, label: str) -> None:
    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetSpotConfig" in req.path:
            return HttpScript.raw(
                200,
                headers=[
                    ("Content-Type", "application/proto"),
                    ("Content-Length", str(len(body))),
                ],
                body=body,
            )
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            hydrate_catalogs=True,
            timeout=2.0,
        )
        with pytest.raises(Exception) as exc_info:
            await client.wait_for_catalogs()
        assert str(exc_info.value), label
        assert client.catalogs_last_error is not None
        assert client.catalogs.is_unusable
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_concurrent_wait_for_catalogs_share_one_attempt() -> None:
    spot = marketdata_pb2.GetSpotConfigResponse()
    pair = spot.pairs.add()
    pair.symbol = "BTC-USDT"
    pair.symbol_id = 1
    pair.base_quantity_scale = 8
    spot_body = spot.SerializeToString()
    zipper_body = zipper_pb2.GetDepositWithdrawConfigResponse().SerializeToString()

    async def handler(req: ParsedRequest) -> HttpScript:
        await asyncio.sleep(0.05)
        if "GetSpotConfig" in req.path:
            return connect_proto_response(spot_body)
        if "GetDepositWithdrawConfig" in req.path:
            return connect_proto_response(zipper_body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            hydrate_catalogs=True,
            timeout=5.0,
        )
        await asyncio.gather(*[client.wait_for_catalogs() for _ in range(10)])
        assert http.request_count <= 2, f"expected spot+zipper once, got {http.request_count}"
        assert client.catalogs.base_quantity_scale_for_symbol("BTC-USDT") == 8
        await client.aclose()
    finally:
        await http.aclose()


# ---------------------------------------------------------------------------
# E9 scale / catalog panic boundary via public wait_for_catalogs + place resolve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_scale_hydrate_via_wait_for_catalogs_then_place_resolve() -> None:
    spot = marketdata_pb2.GetSpotConfigResponse()
    pair = spot.pairs.add()
    pair.symbol = "ETH-USDT"
    pair.symbol_id = 2
    pair.base_quantity_scale = 6
    spot_body = spot.SerializeToString()
    zipper_body = zipper_pb2.GetDepositWithdrawConfigResponse().SerializeToString()

    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetSpotConfig" in req.path:
            return connect_proto_response(spot_body)
        if "GetDepositWithdrawConfig" in req.path:
            return connect_proto_response(zipper_body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            hydrate_catalogs=True,
            timeout=5.0,
        )
        await client.wait_for_catalogs()
        scale = quantity_scale_for_symbol(client.catalogs, "ETH-USDT")
        assert scale == 6
        assert resolve_quantity_scale(client.catalogs, "ETH-USDT", "0.01") == 6
        assert format_qty_scaled(1, scale) == "0.000001"
        assert format_qty_scaled(1, MAX_PROTOCOL_SCALE)
        for bad in (37, 65534, 65535, 65536, 2**32 - 1):
            with pytest.raises(PolyesterValidationError):
                format_qty_scaled(1, bad)
            with pytest.raises(PolyesterValidationError):
                format_ledger_u128("1", scale=bad)
            q = Quantity.from_scaled(1, scale=8)
            with pytest.raises(PolyesterValidationError):
                q.format(scale=bad)
        await client.aclose()
    finally:
        await http.aclose()


def test_l2_scale_format_and_catalog_reject_panic_boundary() -> None:
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError, match="scale"):
        catalogs.hydrate_spot_config(
            {
                "pairs": [
                    {
                        "symbol": "BTC-USDT",
                        "symbol_id": 1,
                        "base_quantity_scale": 65535,
                    }
                ]
            }
        )
    assert catalogs.base_quantity_scale_for_symbol("BTC-USDT") is None


# ---------------------------------------------------------------------------
# E7 snapshot last_error via black-box WS disconnect/reconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_snapshot_reconnect_fail_sets_last_error_blackbox() -> None:
    """Local WS disconnect → reconnect → failing snapshot refresh (no private _ws_sub)."""
    ws = await MockWsServer.spawn_centrifugo_disconnect_after_handshake()
    rt = AsyncRealtimeClient(ws.ws_url())
    attempts = {"n": 0}
    merges = {"n": 0}

    async def fetch_snapshot() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "ok"
        raise PolyesterRealtimeError("snapshot refresh failed")

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=rt,
        channel=PUBLIC_CHANNEL,
        decode=_identity_decode,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda _s, _p: merges.__setitem__("n", merges["n"] + 1),
        apply_live_publications=lambda _p: None,
    )
    try:
        await sub.start()
        assert sub.is_ready()
        assert sub.last_error is None
        assert merges["n"] == 1
        await wait_until(lambda: sub.is_disposed(), 5.0)
        assert sub.last_error is not None
        assert "snapshot" in str(sub.last_error).lower()
        assert not sub.is_ready()
        # initial success + reconnect attempt + one bounded retry
        assert attempts["n"] >= 3
    finally:
        await sub.aclose()
        await rt.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_snapshot_reconnect_success_clears_and_merges_once() -> None:
    ws = await MockWsServer.spawn_centrifugo_disconnect_after_handshake()
    rt = AsyncRealtimeClient(ws.ws_url())
    attempts = {"n": 0}
    merges: list[str] = []

    async def fetch_snapshot() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "initial"
        return "reconnect"

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=rt,
        channel=PUBLIC_CHANNEL,
        decode=_identity_decode,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda snap, _p: merges.append(snap),
        apply_live_publications=lambda _p: None,
    )
    try:
        await sub.start()
        assert merges == ["initial"]
        await wait_until(lambda: len(merges) >= 2, 5.0)
        assert merges == ["initial", "reconnect"]
        assert sub.is_ready()
        assert sub.last_error is None
        assert attempts["n"] == 2
    finally:
        await sub.aclose()
        await rt.aclose()
        await ws.aclose()


@pytest.mark.asyncio
async def test_l2_close_during_snapshot_retry_cancels_fetch_and_socket() -> None:
    ws = await MockWsServer.spawn_centrifugo_disconnect_after_handshake()
    rt = AsyncRealtimeClient(ws.ws_url())
    attempts = {"n": 0}
    retry_stalled = asyncio.Event()
    fetch_cancelled = asyncio.Event()

    async def fetch_snapshot() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "initial"
        if attempts["n"] == 2:
            raise PolyesterRealtimeError("retry once")
        retry_stalled.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            fetch_cancelled.set()
            raise
        return "unreachable"

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=rt,
        channel=PUBLIC_CHANNEL,
        decode=_identity_decode,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda _s, _p: None,
        apply_live_publications=lambda _p: None,
    )
    try:
        await sub.start()
        await asyncio.wait_for(retry_stalled.wait(), timeout=5.0)
        started = time.monotonic()
        await asyncio.wait_for(sub.aclose(), timeout=0.75)
        assert time.monotonic() - started < 0.75
        assert fetch_cancelled.is_set()
        await wait_until(lambda: ws.active == 0, 0.75)
    finally:
        await sub.aclose()
        await rt.aclose()
        await ws.aclose()


# ---------------------------------------------------------------------------
# D1 wait_for_order_trades_complete via public AsyncOrdersService + GetOrder mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_batch_cancel_rejects_inconsistent_counts_via_public_service() -> None:
    response = orders_pb2.BatchCancelOrdersResponse(
        results=[
            orders_pb2.BatchCancelResultItem(
                status=orders_pb2.BatchCancelResultItem.ACCEPTED, order_id=9
            )
        ],
        accepted_count=0,
        rejected_count=1,
    )
    body = response.SerializeToString()

    async def handler(req: ParsedRequest) -> HttpScript:
        if "BatchCancelOrders" in req.path:
            return connect_proto_response(body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
        )
        with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
            await client.orders.batch_cancel(items=[{"key": OrderId("9")}])
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_batch_replace_rejects_inconsistent_counts_via_public_service() -> None:
    spot = marketdata_pb2.GetSpotConfigResponse(
        pairs=[
            marketdata_pb2.PairConfig(
                symbol="BTC-USDT",
                symbol_id=1,
                base_quantity_scale=8,
            )
        ]
    )
    zipper = zipper_pb2.GetDepositWithdrawConfigResponse(
        assets=[zipper_pb2.AssetConfig(asset="USDT", ledger_id=99, quantity_scale=6)]
    )
    response = orders_pb2.BatchReplaceOrdersResponse(
        batch_request_id=1,
        status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
        results=[
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=0,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                replacement_order_id=9,
            )
        ],
        rejected_count=1,
    )

    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetSpotConfig" in req.path:
            return connect_proto_response(spot.SerializeToString())
        if "GetDepositWithdrawConfig" in req.path:
            return connect_proto_response(zipper.SerializeToString())
        if "BatchReplaceOrders" in req.path:
            return connect_proto_response(response.SerializeToString())
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=True,
        )
        await client.wait_for_catalogs()
        with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
            await client.orders.batch_replace(
                items=[{"key": OrderId("9"), "new_price": "1"}],
                symbol="BTC-USDT",
            )
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_columnar_candles_reject_misaligned_columns_via_public_service() -> None:
    spot = marketdata_pb2.GetSpotConfigResponse(
        pairs=[
            marketdata_pb2.PairConfig(
                symbol="BTC-USDT",
                symbol_id=1,
                base_quantity_scale=8,
            )
        ]
    )
    zipper = zipper_pb2.GetDepositWithdrawConfigResponse(
        assets=[zipper_pb2.AssetConfig(asset="USDT", ledger_id=99, quantity_scale=6)]
    )
    candles = marketdata_pb2.GetCandlesColumnsResponse(
        symbol_id=1,
        timeframe=marketdata_pb2.MIN_1,
        ts_sec=[10, 20],
        open=[1, 2],
        high=[1],
        low=[1, 2],
        close=[1, 2],
        volume=[1, 2],
    )

    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetSpotConfig" in req.path:
            return connect_proto_response(spot.SerializeToString())
        if "GetDepositWithdrawConfig" in req.path:
            return connect_proto_response(zipper.SerializeToString())
        if "GetCandlesColumns" in req.path:
            return connect_proto_response(candles.SerializeToString())
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    try:
        client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=True)
        await client.wait_for_catalogs()
        with pytest.raises(PolyesterTransportError, match="response lengths"):
            await client.market_data.get_candles_columns(symbol="BTC-USDT")
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_create_deposit_address_rejects_missing_entity_via_public_service() -> None:
    body = deposit_pb2.CreateDepositAddressResponse().SerializeToString()

    async def handler(req: ParsedRequest) -> HttpScript:
        if "CreateDepositAddress" in req.path:
            return connect_proto_response(body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
        )
        with pytest.raises(PolyesterTransportError, match="missing deposit_address"):
            await client.deposit.create_address(chain_id=1)
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_get_flow_by_tx_returns_all_matches_via_public_service() -> None:
    body = lifecycle_read_pb2.ListFlowsByTxResponse(
        matches=[
            lifecycle_read_pb2.FlowTxMatchView(flow_id="flow-a"),
            lifecycle_read_pb2.FlowTxMatchView(flow_id="flow-b"),
        ]
    ).SerializeToString()

    async def handler(req: ParsedRequest) -> HttpScript:
        if "ListFlowsByTx" in req.path:
            return connect_proto_response(body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    try:
        client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
        result = await client.lifecycle.get_flow_by_tx(tx_hash="0x01")
        assert [flow.intent_id for flow in result.flows] == ["flow-a", "flow-b"]
        await client.aclose()
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_l2_wait_for_order_trades_complete_via_get_order_sequence() -> None:
    calls = {"n": 0}

    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetOrder" not in req.path:
            return HttpScript.not_found()
        calls["n"] += 1
        order = orders_read_pb2.Order(
            order_id=1,
            symbol_id=1,
            cum_qty_scaled=100,
            orig_qty_scaled=100,
            leaves_qty_scaled=0,
        )
        if calls["n"] == 1:
            body = orders_read_pb2.GetOrderResponse(order=order).SerializeToString()
        else:
            body = orders_read_pb2.GetOrderResponse(
                order=order,
                trades=[
                    orders_read_pb2.UserTrade(
                        symbol_id=1,
                        order_id=1,
                        qty_scaled=40,
                        fee_amount_e18=u128_pb2.U128(hi=0, lo=1),
                        fee_asset=orders_pb2.BASE,
                        referral_share_amount_e18=u128_pb2.U128(hi=0, lo=1),
                    ),
                    orders_read_pb2.UserTrade(symbol_id=1, order_id=1, qty_scaled=60),
                ],
            ).SerializeToString()
        return connect_proto_response(body)

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
            timeout=5.0,
        )
        result = await client.orders.wait_for_order_trades_complete(
            key=OrderId(1),
            timeout=2.0,
            poll_interval=0.05,
        )
        assert calls["n"] >= 2
        assert result.order is not None
        assert result.order.cum_qty is not None
        assert result.order.cum_qty.scaled == 100
        assert sum(t.qty.scaled for t in result.trades if t.qty is not None) == 100
        assert result.trades[0].fee_asset == "base"
        assert result.trades[0].fee_amount_e18 == "1"
        assert result.trades[0].referral_share_amount_e18 == "1"
        assert result.trades[0].fee_is_rebate is False
        await client.aclose()
    finally:
        await http.aclose()


# ---------------------------------------------------------------------------
# M5 balances.list through public client + fixture HTTP (not direct decoder L2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_m5_balances_list_preserves_1e18_scaled_string() -> None:
    one_e18 = 10**18
    resp = ledger_read_pb2.GetBalancesResponse(
        balances=[
            ledger_read_pb2.AssetBalance(
                asset_id=1,
                trading=u128_pb2.U128(hi=0, lo=one_e18),
                funding=u128_pb2.U128(hi=0, lo=0),
                reserved=u128_pb2.U128(hi=0, lo=0),
                available=u128_pb2.U128(hi=0, lo=one_e18),
            )
        ]
    )
    body = resp.SerializeToString()

    async def handler(req: ParsedRequest) -> HttpScript:
        if "GetBalances" in req.path:
            return connect_proto_response(body)
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    try:
        client = AsyncPolyester(
            api_url=http.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
            timeout=5.0,
        )
        listed = await client.balances.list()
        assert len(listed.balances) == 1
        row = listed.balances[0]
        assert row.trading == "1000000000000000000"
        assert isinstance(row.trading, str)
        assert row.available == "1000000000000000000"
        assert format_ledger_u128(row.trading, scale=18) == "1"
        await client.aclose()
    finally:
        await http.aclose()
