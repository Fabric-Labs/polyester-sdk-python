"""POLY-3746: JSON-RPC body cap + envelope validation."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from polyester.chain.rpc import MAX_JSONRPC_RESPONSE_BYTES, JsonRpcClient, JsonRpcError


class _Handler(BaseHTTPRequestHandler):
    responses: list[bytes] = []
    status: int = 200

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        _ = self.rfile.read(length)
        body = self.responses.pop(0) if self.responses else b"{}"
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


@pytest.fixture
def jsonrpc_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}"
    server.shutdown()


def _ok(result, *, req_id: int = 1) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode()


def test_jsonrpc_success(jsonrpc_server: str) -> None:
    _Handler.responses = [_ok({"ok": True}, req_id=1)]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    assert client.request("eth_chainId") == {"ok": True}


def test_jsonrpc_rejects_wrong_version(jsonrpc_server: str) -> None:
    _Handler.responses = [
        json.dumps({"jsonrpc": "1.0", "id": 1, "result": 1}).encode()
    ]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match='jsonrpc="2.0"'):
        client.request("eth_chainId")


def test_jsonrpc_rejects_id_mismatch(jsonrpc_server: str) -> None:
    _Handler.responses = [_ok(1, req_id=999)]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match="id mismatch"):
        client.request("eth_chainId")


def test_jsonrpc_rejects_both_result_and_error(jsonrpc_server: str) -> None:
    _Handler.responses = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": 1,
                "error": {"code": -1, "message": "nope"},
            }
        ).encode()
    ]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match="exactly one"):
        client.request("eth_chainId")


def test_jsonrpc_rejects_neither_result_nor_error(jsonrpc_server: str) -> None:
    _Handler.responses = [json.dumps({"jsonrpc": "2.0", "id": 1}).encode()]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match="exactly one"):
        client.request("eth_chainId")


def test_jsonrpc_rejects_oversized_body(jsonrpc_server: str) -> None:
    oversized = b"x" * (MAX_JSONRPC_RESPONSE_BYTES + 1)
    _Handler.responses = [oversized]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match="exceeds"):
        client.request("eth_chainId")


@pytest.mark.asyncio
async def test_jsonrpc_arequest_error_object(jsonrpc_server: str) -> None:
    _Handler.responses = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32000, "message": "boom", "data": {"x": 1}},
            }
        ).encode()
    ]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match="boom") as exc_info:
        await client.arequest("eth_chainId")
    assert exc_info.value.code == -32000
    assert exc_info.value.data == {"x": 1}


def test_jsonrpc_accepts_null_result(jsonrpc_server: str) -> None:
    _Handler.responses = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": None}).encode()
    ]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    assert client.request("eth_call") is None


def test_jsonrpc_rejects_malformed_error_object(jsonrpc_server: str) -> None:
    _Handler.responses = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "error": "boom"}).encode()
    ]
    client = JsonRpcClient(jsonrpc_server, timeout=2.0)
    with pytest.raises(JsonRpcError, match="error must be an object"):
        client.request("eth_call")
