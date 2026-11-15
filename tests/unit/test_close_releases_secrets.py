"""A closed client forgets its secrets.

Once every client holding a private key or URL userinfo is closed, the process
no longer keeps a copy of it for redaction. While a client holds one, it stays
redacted.
"""

from __future__ import annotations

import threading

from polyester import AsyncPolyester
from polyester._redact import redact_text, register


def _keyed_client(private_key_hex: str) -> AsyncPolyester:
    return AsyncPolyester(
        api_key_id="ak_test_0",
        api_private_key=private_key_hex,
        hydrate_catalogs=False,
    )


async def test_close_releases_each_clients_private_key() -> None:
    key_a = "c3" * 32
    key_b = "d4" * 32
    line = f"leak {key_a} and {key_b}"
    assert redact_text(line) == line

    client_a = _keyed_client(key_a)
    client_b = _keyed_client(key_b)
    assert redact_text(line) == "leak [REDACTED] and [REDACTED]"

    await client_a.aclose()
    assert redact_text(line) == f"leak {key_a} and [REDACTED]"
    await client_b.aclose()
    assert redact_text(line) == line
    # A second close releases nothing again.
    await client_a.aclose()
    assert redact_text(line) == line


async def test_shared_private_key_stays_redacted_while_one_client_holds_it() -> None:
    key = "e5" * 32
    line = f"leak {key}"
    first = _keyed_client(key)
    second = _keyed_client(key)
    await first.aclose()
    await first.aclose()
    assert redact_text(line) == "leak [REDACTED]"
    await second.aclose()
    assert redact_text(line) == line


async def test_close_releases_url_userinfo() -> None:
    client = AsyncPolyester(
        api_url="https://closeuser:close-api-secret-Q7@example.test",
        ws_url="wss://wsuser:close-ws-secret-Q7@example.test",
        hydrate_catalogs=False,
    )
    line = "saw close-api-secret-Q7 and close-ws-secret-Q7"
    assert redact_text(line) == "saw [REDACTED] and [REDACTED]"
    await client.aclose()
    assert redact_text(line) == line


def test_registrations_are_counted_across_threads() -> None:
    secret = "registry-shared-secret-R9"
    keep = register(secret)

    def churn() -> None:
        release = register(secret, "abc")
        release()
        release()

    threads = [threading.Thread(target=churn) for _ in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert redact_text(f"saw {secret}") == "saw [REDACTED]"
    keep()
    assert redact_text(f"saw {secret}") == f"saw {secret}"
