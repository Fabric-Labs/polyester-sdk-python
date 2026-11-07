"""Private Centrifugo subscriptions renew short-lived tokens on their connection."""

from __future__ import annotations

import asyncio
import contextlib

from polyester.codecs.realtime_decode import decode_ledger_transfer_batch_bytes
from polyester.codecs.scalars import format_id
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from tests.unit.renewal_support import RenewalServer

RENEWAL_ACCOUNT = 2305843009213693953
TRANSFERS_CHANNEL = f"private:ledger:transfers:{format_id(RENEWAL_ACCOUNT)}:proto"


def transfer_publication() -> bytes:
    row = ledger_read_pb2.TransferRow(asset_id=2, transfer_id="7")
    return ledger_read_pb2.TransferRowBatch(events=[row]).SerializeToString()


async def test_transfer_subscription_renews_short_lived_token_without_reconnect() -> None:
    # The subscription token lives one second: across three lifetimes the
    # client stays on its first connection and subscription.
    async with RenewalServer(
        unit=1.0, sub_ttl=1, publication=transfer_publication(), publish_every=0.1
    ) as server:
        rt = server.client()
        sub = await rt.subscribe_proto_batch(
            TRANSFERS_CHANNEL, decode_batch=decode_ledger_transfer_batch_bytes
        )
        errors: list[BaseException] = []
        sub.set_on_error(errors.append)
        seen: list[float] = []

        async def drain() -> None:
            async for _ in sub:
                seen.append(asyncio.get_running_loop().time())

        consumer = asyncio.create_task(drain())
        try:
            await asyncio.sleep(3.6)
            counts = (
                f"expiries={server.sub_expiries} connections={server.accepted} "
                f"subscribes={server.subscribes} renewals={server.sub_renewals}"
            )
            assert server.sub_expiries == 0, f"server ended the subscription: {counts}"
            assert server.accepted == 1, f"client opened {server.accepted} connections"
            assert server.subscribes == 1, f"client subscribed {server.subscribes} times"
            assert server.sub_renewals >= 3, (
                f"client renewed the subscription token {server.sub_renewals} times "
                "in 3.6 token lifetimes"
            )
            assert server.reused == 0, "client presented a used or unknown token"
            assert sub.resubscribed == 0
            assert errors == [], f"healthy renewal reported {errors}"
            before = len(seen)
            await asyncio.sleep(0.5)
            assert len(seen) > before, "no transfer delivered after the renewals"
        finally:
            consumer.cancel()
            with contextlib.suppress(BaseException):
                await consumer
            await rt.aclose()


async def test_private_connection_renews_short_lived_token_without_reconnect() -> None:
    async with RenewalServer(unit=1.0, conn_ttl=1) as server:
        rt = server.client()
        await rt.subscribe_proto_batch(
            TRANSFERS_CHANNEL, decode_batch=decode_ledger_transfer_batch_bytes
        )
        try:
            await asyncio.sleep(3.6)
            counts = (
                f"expiries={server.conn_expiries} connections={server.accepted} "
                f"renewals={server.refreshes}"
            )
            assert server.conn_expiries == 0, f"server closed the connection: {counts}"
            assert server.accepted == 1, f"client opened {server.accepted} connections"
            assert server.refreshes >= 3, (
                f"client renewed the connection token {server.refreshes} times "
                "in 3.6 token lifetimes"
            )
            assert server.reused == 0, "client presented a used or unknown token"
        finally:
            await rt.aclose()
