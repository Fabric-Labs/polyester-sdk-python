"""A public ID that decodes to 0 names nothing.

``"1"`` is the base58 form of 0, ``"0"`` and ``"00"`` the decimal, and ``0``
the integer. Every call that takes one refuses it with
``PolyesterValidationError`` and sends no request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_id, id_to_int
from polyester.errors import PolyesterValidationError
from polyester.models import OrderId

ZERO_IDS: list[str | int] = ["1", "0", "00", 0]
TEST_KEY = "0123456789abcdef" * 4

Call = Callable[[AsyncPolyester, Any], Awaitable[object]]

CALLS: dict[str, Call] = {
    "triggers.get": lambda c, i: c.triggers.get(trigger_id=i),
    "triggers.cancel": lambda c, i: c.triggers.cancel(trigger_id=i),
    "triggers.pause": lambda c, i: c.triggers.pause(trigger_id=i),
    "triggers.resume": lambda c, i: c.triggers.resume(trigger_id=i, symbol_id=1),
    "triggers.modify": lambda c, i: c.triggers.modify(
        trigger_id=i, symbol_id=1, max_slippage_bps=10
    ),
    "triggers.list_events": lambda c, i: c.triggers.list_events(trigger_id=i),
    "triggers.cancel_oco": lambda c, i: c.triggers.cancel_oco(order_list_id=i),
    "orders.get": lambda c, i: c.orders.get(key=OrderId(i)),
    "orders.cancel": lambda c, i: c.orders.cancel(key=OrderId(i), symbol_id=1),
    "orders.get_batch_replace_status": lambda c, i: c.orders.get_batch_replace_status(
        batch_request_id=i
    ),
    "address_book.delete_entry": lambda c, i: c.address_book.delete_entry(address_book_entry_id=i),
    "address_book.delete_tag": lambda c, i: c.address_book.delete_tag(tag_id=i),
}


@pytest.mark.parametrize("name", sorted(CALLS))
async def test_call_refuses_a_public_id_that_decodes_to_zero(
    httpserver: HTTPServer, name: str
) -> None:
    requests: list[str] = []

    def record(request: Request) -> Response:
        requests.append(request.path)
        return Response("unexpected request", status=418)

    httpserver.expect_request("", method="POST").respond_with_handler(record)
    async with AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key_id="ak_test",
        api_private_key=TEST_KEY,
        hydrate_catalogs=False,
    ) as client:
        for raw in ZERO_IDS:
            with pytest.raises(PolyesterValidationError, match="non-zero"):
                await CALLS[name](client, raw)
    assert requests == []


def test_id_to_int_refuses_zero_and_keeps_other_ids() -> None:
    for raw in ["1", "0", "00", 0]:
        with pytest.raises(PolyesterValidationError, match="must be a non-zero ID, not 0"):
            id_to_int(raw, "trigger_id")
    assert id_to_int("2", "trigger_id") == 1
    assert id_to_int("10", "trigger_id") == 10
    assert id_to_int(format_id(1 << 63), "trigger_id") == 1 << 63
    # Formatting 0 is unchanged: it still reads "1".
    assert format_id(0) == "1"
