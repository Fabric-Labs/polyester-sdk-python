"""A private order subscription counts each reconnect, as every subscription does.

``resubscribed`` and ``take_resubscribed()`` move on each successful resume
after a gap and never on the first connect. Driven through the public
``AsyncPolyester.realtime.subscribe_private_orders`` against a local
``/v1/ws/private`` server that drops its socket without a close frame.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio

from polyester import AsyncPolyester
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models import (
    PrivateOrdersConnected,
    PrivateOrdersDisconnected,
    PrivateOrdersReady,
    PrivateOrdersSnapshot,
    PrivateOrdersUnit,
)
from polyester.realtime.client import AsyncSubscription
from tests.unit.test_private_orders_stream import (
    ACCOUNT,
    ACCOUNT_B58,
    EVENT_TIMEOUT,
    FakeConnection,
    FakePrivateWsServer,
    fast_backoff,  # noqa: F401  (autouse fixture)
    next_event,
    order,
)


@pytest_asyncio.fixture(loop_scope="function")
async def server() -> AsyncIterator[FakePrivateWsServer]:
    fake = FakePrivateWsServer()
    await fake.start()
    yield fake
    await fake.aclose()


@pytest_asyncio.fixture(loop_scope="function")
async def client(server: FakePrivateWsServer) -> AsyncIterator[AsyncPolyester]:
    polyester = AsyncPolyester(
        api_key_id="ak_test",
        api_private_key="a1" * 32,
        api_url=server.api_url,
        ws_url="ws://127.0.0.1:1",
        hydrate_catalogs=False,
    )
    yield polyester
    await polyester.aclose()


async def subscribe(
    client: AsyncPolyester, server: FakePrivateWsServer
) -> tuple[AsyncSubscription[Any], FakeConnection]:
    task = asyncio.create_task(client.realtime.subscribe_private_orders(ACCOUNT_B58))
    conn = await server.next_connection()
    await conn.expect("auth")
    assert (await conn.confirm("s1")).cursor == ""
    sub = await asyncio.wait_for(task, EVENT_TIMEOUT)
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    return sub, conn


async def drop(conn: FakeConnection, sub: AsyncSubscription[Any]) -> None:
    """End the socket without a close frame, as a lost TCP connection does."""
    conn.ws.transport.abort()
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)


async def resume(server: FakePrivateWsServer, sub_id: str, cursor: str) -> FakeConnection:
    conn = await server.next_connection()
    await conn.expect("auth")
    assert (await conn.confirm(sub_id)).cursor == cursor
    return conn


def assert_no_reconnect_pending(sub: AsyncSubscription[Any], count: int) -> None:
    assert sub.resubscribed == count
    assert sub.take_resubscribed() is False


def assert_one_reconnect_taken(sub: AsyncSubscription[Any], count: int) -> None:
    assert sub.resubscribed == count
    assert sub.take_resubscribed() is True
    assert sub.take_resubscribed() is False
    assert sub.resubscribed == count


async def test_each_resume_after_an_abrupt_drop_is_counted_once(
    client: AsyncPolyester,
    server: FakePrivateWsServer,
) -> None:
    sub, first = await subscribe(client, server)
    # The first connect is not a reconnect.
    assert_no_reconnect_pending(sub, 0)
    await first.snapshot("s1", "c1", [order(1)])
    await first.send("s1", 4, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    assert isinstance(await next_event(sub), PrivateOrdersReady)
    assert_no_reconnect_pending(sub, 0)

    await drop(first, sub)
    # A gap that has not resumed yet is no reconnect either.
    assert_no_reconnect_pending(sub, 0)
    second = await resume(server, "s2", "c1")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert_one_reconnect_taken(sub, 1)
    # The resumed subscription still reaches Ready and moves its cursor.
    await second.send("s2", 1, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersReady)
    await second.send("s2", 2, unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(2)]))
    assert isinstance(await next_event(sub), PrivateOrdersUnit)
    assert_no_reconnect_pending(sub, 1)

    await drop(second, sub)
    assert_no_reconnect_pending(sub, 1)
    third = await resume(server, "s3", "c2")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert_one_reconnect_taken(sub, 2)
    await third.send("s3", 1, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersReady)
    await third.send("s3", 2, unit=pb.Unit(prev_cursor="c2", next_cursor="c3", orders=[order(3)]))
    assert isinstance(await next_event(sub), PrivateOrdersUnit)
    assert_no_reconnect_pending(sub, 2)
    assert len(server.all) == 3


async def test_reconnects_not_taken_in_between_report_once(
    client: AsyncPolyester,
    server: FakePrivateWsServer,
) -> None:
    sub, first = await subscribe(client, server)
    await first.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await drop(first, sub)
    second = await resume(server, "s2", "c1")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await drop(second, sub)
    await resume(server, "s3", "c1")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert_one_reconnect_taken(sub, 2)


async def test_a_resubscribe_on_the_same_connection_is_a_reconnect(
    client: AsyncPolyester,
    server: FakePrivateWsServer,
) -> None:
    sub, conn = await subscribe(client, server)
    await conn.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    # A sequence gap drops the server subscription and resumes from the cursor.
    await conn.send("s1", 5, unit=pb.Unit(prev_cursor="c1", next_cursor="c9"))
    retry = await conn.expect("subscribe")
    assert retry.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    assert_no_reconnect_pending(sub, 0)
    await conn.send("s2", subscribed=pb.Subscribed(id=retry.id, account=ACCOUNT))
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert_one_reconnect_taken(sub, 1)
    assert len(server.all) == 1


async def test_a_consumer_first_connected_by_a_resume_counts_no_reconnect(
    client: AsyncPolyester,
    server: FakePrivateWsServer,
) -> None:
    sub, first = await subscribe(client, server)
    await first.snapshot("s1", "c1", [order(1)])
    await first.send("s1", 4, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    assert isinstance(await next_event(sub), PrivateOrdersReady)
    await drop(first, sub)

    # Joins while the account is disconnected: the resume is its first connect.
    joining = asyncio.create_task(client.realtime.subscribe_private_orders(ACCOUNT_B58))
    second = await resume(server, "s2", "c1")
    joiner = await asyncio.wait_for(joining, EVENT_TIMEOUT)
    assert len(server.all) == 2
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert isinstance(await next_event(joiner), PrivateOrdersConnected)
    assert isinstance(await next_event(joiner), PrivateOrdersSnapshot)
    assert_one_reconnect_taken(sub, 1)
    assert_no_reconnect_pending(joiner, 0)

    await second.send("s2", 1, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersReady)
    assert isinstance(await next_event(joiner), PrivateOrdersReady)
    await drop(second, sub)
    assert isinstance(await next_event(joiner), PrivateOrdersDisconnected)
    await resume(server, "s3", "c1")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert isinstance(await next_event(joiner), PrivateOrdersConnected)
    assert_one_reconnect_taken(sub, 2)
    assert_one_reconnect_taken(joiner, 1)
