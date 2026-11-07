"""wait_for_order_trades_complete over local GetOrder execution pages.

A schedule of polls answers GetOrder: a request without a page token starts
the next poll (the last one repeats), and page ``i`` of a poll is requested
with page token ``t<i>``. Pages can be slow, never answer, or point back at an
earlier page token.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest

import polyester.services.orders as orders_service
from polyester import AsyncPolyester
from polyester.errors import PolyesterResponseContractError, PolyesterTransportError
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.models import OrderId
from polyester.models.trading import GetOrderResult
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

# Far above every wait timeout below: a page read that outlives its wait
# shows up as a multi-second return.
HTTP_TIMEOUT = 5.0
TIMEOUT_MESSAGE = "timed out waiting for order trades"
# An order the server answers outside its schedule, to warm a client up.
WARMUP_ORDER_ID = 999


@dataclass
class Page:
    trades: list[int] = field(default_factory=list)
    next: str = ""
    complete: bool = False
    delay: float = 0.0
    hang: bool = False


@dataclass
class TradesServer:
    cum: int
    polls: list[list[Page]]
    # The order's status on each poll, the last one repeating; FILLED when empty.
    statuses: list[int] = field(default_factory=list)
    poll: int = 0
    # Polls started after the first.
    reads: int = 0
    started: bool = False
    arrivals: list[float] = field(default_factory=list)
    served: list[float] = field(default_factory=list)

    async def handle(self, req: ParsedRequest) -> HttpScript:
        if "GetOrder" not in req.path:
            return HttpScript.not_found()
        request = orders_read_pb2.GetOrderRequest.FromString(req.body)
        if request.order_id == WARMUP_ORDER_ID:
            order = orders_read_pb2.Order(order_id=WARMUP_ORDER_ID, symbol_id=1)
            response = orders_read_pb2.GetOrderResponse(order=order)
            return connect_proto_response(response.SerializeToString())
        self.arrivals.append(time.monotonic())
        token = request.page_token
        if not token:
            if self.started:
                self.reads += 1
                if self.poll < len(self.polls) - 1:
                    self.poll += 1
            self.started = True
        pages = self.polls[self.poll]
        status = (
            self.statuses[min(self.reads, len(self.statuses) - 1)]
            if self.statuses
            else orders_read_pb2.FILLED
        )
        index = int(token.removeprefix("t")) if token else 0
        page = pages[index]
        if page.hang:
            return HttpScript.never_respond()
        if page.delay:
            await asyncio.sleep(page.delay)
        self.served.append(time.monotonic())
        response = orders_read_pb2.GetOrderResponse(
            order=orders_read_pb2.Order(
                order_id=1, symbol_id=1, status=status, cum_qty_scaled=self.cum
            ),
            next_page_token=page.next,
            executions_complete=page.complete,
            trades=[
                orders_read_pb2.UserTrade(
                    symbol_id=1, order_id=1, match_id=1000 * index + i + 1, qty_scaled=qty
                )
                for i, qty in enumerate(page.trades)
            ],
        )
        return connect_proto_response(response.SerializeToString())


@asynccontextmanager
async def trades_client(server: TradesServer) -> AsyncIterator[AsyncPolyester]:
    http = await MockHttpServer.spawn(server.handle)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        timeout=HTTP_TIMEOUT,
    )
    try:
        yield client
    finally:
        await client.aclose()
        await http.aclose()


async def wait_trades(client: AsyncPolyester, timeout: float) -> GetOrderResult:
    return await client.orders.wait_for_order_trades_complete(
        key=OrderId(1), timeout=timeout, poll_interval=0.1
    )


def trade_qtys(result: GetOrderResult) -> list[int]:
    return [trade.qty.scaled for trade in result.trades if trade.qty is not None]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("polls", "want"),
    [
        pytest.param([[Page([100], complete=True)]], True, id="single page"),
        pytest.param(
            [
                [
                    Page([40], next="t1", complete=True),
                    Page([20], next="t2", complete=True),
                    Page([40], complete=True),
                ]
            ],
            True,
            id="terminal page of three",
        ),
        pytest.param(
            [
                [Page([40], next="t1"), Page([])],
                [Page([40], next="t1", complete=True), Page([60], complete=True)],
            ],
            True,
            id="recorded on a later poll",
        ),
        pytest.param(
            [[Page([50], next="t1"), Page([50])]], False, id="server still reports incomplete"
        ),
    ],
)
async def test_wait_keeps_the_final_reads_executions_complete(
    polls: list[list[Page]], want: bool
) -> None:
    async with trades_client(TradesServer(cum=100, polls=polls)) as client:
        result = await wait_trades(client, 2.0)
    assert sum(trade_qtys(result)) == 100
    assert result.executions_complete is want


WORKING = orders_read_pb2.WORKING
FILLED = orders_read_pb2.FILLED
CANCELED = orders_read_pb2.CANCELED
REJECTED = orders_read_pb2.REJECTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cum", "trades", "statuses", "want_status"),
    [
        pytest.param(100, [60, 40], [FILLED], "filled", id="terminal fully filled order"),
        pytest.param(
            40, [40], [CANCELED], "canceled", id="terminal canceled order with partial fills"
        ),
        pytest.param(0, [], [REJECTED], "rejected", id="terminal order with no fills"),
        pytest.param(
            40,
            [40],
            [WORKING, WORKING, CANCELED],
            "canceled",
            id="partially filled order canceled on a later poll",
        ),
    ],
)
async def test_wait_completes_on_a_terminal_order(
    cum: int, trades: list[int], statuses: list[int], want_status: str
) -> None:
    """The wait reports completion only for a terminal order (filled, canceled
    or rejected) whose recorded trades add up to its cum_qty. The Go and Rust
    SDKs run the same cases."""
    server = TradesServer(cum=cum, polls=[[Page(trades, complete=True)]], statuses=statuses)
    async with trades_client(server) as client:
        result = await wait_trades(client, 0.5)
    assert result.order is not None
    assert result.order.status == want_status
    assert trade_qtys(result) == trades
    assert result.executions_complete is True


@pytest.mark.asyncio
async def test_wait_keeps_polling_a_partially_filled_working_order() -> None:
    """executions_complete is also true for a working order whose fills so far
    are all recorded: that is no completion, so the wait times out."""
    server = TradesServer(cum=40, polls=[[Page([40], complete=True)]], statuses=[WORKING])
    async with trades_client(server) as client:
        try:
            result = await wait_trades(client, 0.5)
        except PolyesterTransportError as exc:
            assert TIMEOUT_MESSAGE in str(exc)
        else:
            assert result.order is not None
            pytest.fail(f"wait reported a {result.order.status} order complete")
    assert server.reads >= 1


@pytest.mark.asyncio
async def test_wait_follows_fast_pages() -> None:
    pages = [
        Page([10], next="t1", complete=True),
        Page([20], next="t2", complete=True),
        Page([30], next="t3", complete=True),
        Page([40], complete=True),
    ]
    async with trades_client(TradesServer(cum=100, polls=[pages])) as client:
        result = await wait_trades(client, 1.0)
    assert trade_qtys(result) == [10, 20, 30, 40]


@pytest.mark.asyncio
async def test_wait_times_out_across_slow_pages() -> None:
    """Four 35 ms pages need about 140 ms; a 50 ms wait must time out."""
    pages = [Page([25], next=f"t{i + 1}", complete=True, delay=0.035) for i in range(3)]
    pages.append(Page([25], complete=True, delay=0.035))
    async with trades_client(TradesServer(cum=100, polls=[pages])) as client:
        started = time.monotonic()
        try:
            result = await wait_trades(client, 0.05)
        except PolyesterTransportError as exc:
            assert TIMEOUT_MESSAGE in str(exc)
        else:
            elapsed = time.monotonic() - started
            pytest.fail(
                f"wait with a 50 ms timeout succeeded after {elapsed * 1000:.0f} ms "
                f"with {len(result.trades)} trades"
            )


@pytest.mark.asyncio
async def test_wait_abandons_a_page_at_its_timeout() -> None:
    """A page still in flight at the timeout is abandoned, not awaited until
    the HTTP timeout ends it."""
    server = TradesServer(cum=100, polls=[[Page([40], next="t1"), Page(hang=True)]])
    async with trades_client(server) as client:
        started = time.monotonic()
        with pytest.raises(PolyesterTransportError) as caught:
            await wait_trades(client, 0.1)
        elapsed = time.monotonic() - started
    assert elapsed < 1.1, f"wait with a 100 ms timeout returned after {elapsed:.2f} s"
    assert TIMEOUT_MESSAGE in str(caught.value)


@pytest.mark.asyncio
async def test_wait_refuses_a_success_finished_after_its_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A complete page answered in time whose decoding ends after the timeout
    is no success. The decoder runs synchronously, so the timeout's callback
    cannot run before the read hands back its result."""
    timeout = 0.05
    decode = orders_service.get_order_from_proto

    def late_decode(msg: orders_read_pb2.GetOrderResponse) -> GetOrderResult:
        result = decode(msg)
        time.sleep(timeout + 0.03)  # holds the event loop past the deadline
        return result

    server = TradesServer(cum=100, polls=[[Page([100], complete=True)]])
    async with trades_client(server) as client:
        await client.orders.get(key=OrderId(WARMUP_ORDER_ID))
        monkeypatch.setattr(orders_service, "get_order_from_proto", late_decode)
        with pytest.raises(PolyesterTransportError, match=TIMEOUT_MESSAGE):
            await wait_trades(client, timeout)
    assert len(server.arrivals) == 1


@pytest.mark.asyncio
async def test_wait_rejects_a_repeated_page_token() -> None:
    server = TradesServer(
        cum=100,
        polls=[[Page([10], next="t1"), Page([10], next="t2"), Page([10], next="t1")]],
    )
    async with trades_client(server) as client:
        # An independent outer bound, so a looping wait fails the test
        # instead of hanging it.
        try:
            async with asyncio.timeout(3.0):
                await wait_trades(client, 5.0)
        except PolyesterResponseContractError:
            pass
        except Exception as exc:  # the outer bound cut a looping wait
            pytest.fail(
                f"wait did not stop on the repeated token ({len(server.arrivals)} page reads): "
                f"{exc!r}"
            )
        else:
            pytest.fail("wait succeeded on a repeating page token")
    assert len(server.arrivals) == 3


@dataclass
class Schedule:
    cum: int
    timeout: float
    polls: list[list[Page]]
    # "success", "cycle" or "timeout" (a hung page, or no poll adds up)
    outcome: str = "timeout"
    want_trades: list[int] = field(default_factory=list)
    want_complete: bool = False


def random_schedule(seed: int) -> Schedule:
    r = random.Random(seed)
    s = Schedule(cum=100, timeout=(30 + r.randrange(270)) / 1000, polls=[])
    n_polls = 1 + r.randrange(3)
    for p in range(n_polls):
        n_pages = 1 + r.randrange(5)
        adds = p == n_polls - 1 and r.randrange(5) != 0
        remaining = s.cum
        pages = []
        for i in range(n_pages):
            page = Page(next=f"t{i + 1}" if i < n_pages - 1 else "")
            page.complete = r.randrange(3) != 0
            if r.randrange(3) == 0:
                page.delay = r.randrange(60) / 1000
            else:
                page.delay = r.randrange(4) / 1000
            for _ in range(r.randrange(3)):
                if remaining <= 1:
                    break
                qty = 1 + r.randrange(remaining - 1)
                page.trades.append(qty)
                remaining -= qty
            pages.append(page)
        if adds and remaining > 0:
            pages[-1].trades.append(remaining)
        fault = r.randrange(8)
        if fault == 0:
            pages[r.randrange(n_pages)].hang = True
        elif fault == 1 and n_pages > 1:
            pages[-1].next = f"t{1 + r.randrange(n_pages - 1)}"
        s.polls.append(pages)
    for pages in s.polls:
        trades: list[int] = []
        seen: set[str] = set()
        token = ""
        result = ""
        while True:
            page = pages[int(token.removeprefix("t")) if token else 0]
            if page.hang:
                result = "timeout"
                break
            trades.extend(page.trades)
            if not page.next:
                if sum(trades) == s.cum:
                    result = "success"
                    s.want_trades = trades
                    s.want_complete = page.complete
                break
            if page.next in seen:
                result = "cycle"
                break
            seen.add(page.next)
            token = page.next
        if result:
            s.outcome = result
            return s
    return s


@asynccontextmanager
async def loop_lag() -> AsyncIterator[list[float]]:
    """Measure the worst event-loop lag while the block runs: a loaded
    machine delays the wait's timer as much as any other callback."""
    loop = asyncio.get_running_loop()
    worst = [0.0]

    async def watch() -> None:
        while True:
            before = loop.time()
            await asyncio.sleep(0.005)
            worst[0] = max(worst[0], loop.time() - before - 0.005)

    task = asyncio.create_task(watch())
    try:
        yield worst
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def run_schedule(seed: int) -> None:
    s = random_schedule(seed)
    server = TradesServer(cum=s.cum, polls=s.polls)
    replay = (
        f"WAIT_SEED={seed} (timeout {s.timeout * 1000:.0f} ms, {len(s.polls)} polls, "
        f"outcome {s.outcome})"
    )
    async with trades_client(server) as client, loop_lag() as lag:
        # A client's first request sets it up synchronously; keep that out of
        # the measured wait.
        await client.orders.get(key=OrderId(WARMUP_ORDER_ID))
        lag[0] = 0.0
        started = time.monotonic()
        deadline = started + s.timeout
        result: GetOrderResult | None = None
        error: BaseException | None = None
        try:
            async with asyncio.timeout(4.0):
                result = await wait_trades(client, s.timeout)
        except Exception as exc:
            error = exc
        elapsed = time.monotonic() - started
    # An abandoned read unwinds in the HTTP client's own thread, which a
    # starved machine slows without lagging the loop: the return and page
    # starts get 0.5 s plus the loop's lag. A read held to the HTTP timeout
    # takes 5 s. A success is checked strictly below.
    slack = 0.5 + 2 * lag[0]
    assert elapsed <= s.timeout + slack, f"{replay}: wait returned after {elapsed:.3f} s: {error!r}"
    for i, at in enumerate(server.arrivals):
        assert at <= deadline + slack, f"{replay}: page read {i} started {at - deadline:.3f} s late"
    if error is None:
        assert result is not None
        assert s.outcome == "success", f"{replay}: wait succeeded with trades {trade_qtys(result)}"
        # Every page of a success was served before the deadline: a page
        # served later reached the client after its timeout.
        late = max(server.served) - deadline
        assert late <= 0.005 + 2 * lag[0], f"{replay}: success used a page served {late:.3f} s late"
        assert trade_qtys(result) == s.want_trades, f"{replay}: trades {trade_qtys(result)}"
        assert result.executions_complete is s.want_complete, f"{replay}: executions_complete"
    elif isinstance(error, PolyesterResponseContractError):
        assert s.outcome == "cycle", f"{replay}: unexpected contract error {error!r}"
    elif isinstance(error, PolyesterTransportError) and TIMEOUT_MESSAGE in str(error):
        assert s.outcome == "timeout" or elapsed >= s.timeout, (
            f"{replay}: timed out after {elapsed:.3f} s, before the deadline"
        )
    else:
        pytest.fail(f"{replay}: unexpected error {error!r}")


def _seeds() -> list[int]:
    if replay := os.environ.get("WAIT_SEED"):
        return [int(replay)]
    return list(range(int(os.environ.get("WAIT_SEEDS", "64"))))


@pytest.mark.asyncio
async def test_wait_random_schedules() -> None:
    """Random schedules vary the polls before trades add up (1-3), pages per
    poll (1-5), trades per page (0-3), per-page delays (0-60 ms), the wait
    timeout (30-300 ms), each terminal page's executions_complete, a page that
    never answers and a repeated next_page_token. Whatever the schedule, the
    wait returns within its timeout plus slack and starts no page after its
    deadline; a success is the schedule's, with that read's trades and
    terminal executions_complete; a repeated token raises a contract error;
    anything else is a timeout once the deadline passed.

    Slack grows with the worst event-loop lag measured during the schedule,
    so a loaded machine does not read as a late wait; a success must have
    had every page served before the deadline.

    WAIT_SEEDS sets the seed count (default 64); WAIT_SEED replays one seed.
    Sixteen schedules run at a time.
    """
    seeds = _seeds()
    for start in range(0, len(seeds), 16):
        await asyncio.gather(*(run_schedule(seed) for seed in seeds[start : start + 16]))
