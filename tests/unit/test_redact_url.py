from __future__ import annotations

import pytest

from polyester._redact import INVALID_URL, url_without_userinfo

FAKE_PASSWORD = "fake-password-marker"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://api.example.test/v1", "https://api.example.test/v1"),
        (f"https://fake-user:{FAKE_PASSWORD}@api.example.test/v1", "https://api.example.test/v1"),
        ("wss://fake-user@ws.example.test/c?x=1", "wss://ws.example.test/c?x=1"),
        (f"http://fake-user:{FAKE_PASSWORD}@127.0.0.1:8080/p", "http://127.0.0.1:8080/p"),
        (f"http://fake-user:{FAKE_PASSWORD}@[::1/p", INVALID_URL),
    ],
)
def test_url_without_userinfo(url: str, expected: str) -> None:
    assert url_without_userinfo(url) == expected
