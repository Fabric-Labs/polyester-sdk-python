"""The mocks hide a host port probe, and nothing else, from request counts."""

import asyncio
import http.client

from tests.hardening_support import HttpScript, MockHttpServer, ProbeFreeHTTPServer

PROBE = b"HEAD / HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n"


async def _send(port: int, request: bytes) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(request)
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


async def test_mock_http_server_hides_only_a_port_probe() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request) -> HttpScript:
        seen.append((request.method, request.path))
        return HttpScript.not_found()

    server = await MockHttpServer.spawn(handler)
    try:
        port = int(server.base_url.rsplit(":", 1)[1])
        assert (await _send(port, PROBE)).startswith(b"HTTP/1.1 404")
        assert server.request_count == 0
        assert (await _send(port, PROBE.replace(b"HEAD /", b"HEAD /v1/rt/token"))).startswith(
            b"HTTP/1.1 404"
        )
        assert (await _send(port, PROBE.replace(b"HEAD /", b"GET /"))).startswith(b"HTTP/1.1 404")
        assert server.request_count == 2
        assert seen == [("HEAD", "/v1/rt/token"), ("GET", "/")]
    finally:
        await server.aclose()


def test_probe_free_http_server_logs_everything_but_a_port_probe() -> None:
    server = ProbeFreeHTTPServer(host="127.0.0.1", port=0)
    server.start()
    try:
        for method, path, status in [("HEAD", "/", 404), ("HEAD", "/x", 500), ("GET", "/", 500)]:
            connection = http.client.HTTPConnection("127.0.0.1", server.port)
            connection.request(method, path)
            assert connection.getresponse().status == status
            connection.close()
        assert [(request.method, request.path) for request, _ in server.log] == [
            ("HEAD", "/x"),
            ("GET", "/"),
        ]
    finally:
        server.stop()
