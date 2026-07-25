"""Read-only live smoke: concurrent auth + public :proto trades subscription."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()


async def main() -> int:
    from polyester import AsyncPolyester

    if not os.getenv("POLYESTER_API_KEY_ID") or not os.getenv("POLYESTER_API_PRIVATE_KEY"):
        print("FAIL: missing API key env")
        return 2

    client = AsyncPolyester.from_env()
    try:
        await client.wait_for_catalogs()

        # Concurrent identical signed reads (replay-collision regression).
        async def one_list():
            return await client.orders.list_open(limit=1)

        results = await asyncio.gather(*[one_list() for _ in range(32)], return_exceptions=True)
        failures = [r for r in results if isinstance(r, BaseException)]
        if failures:
            print(f"FAIL: concurrent list_open: {len(failures)}/32 errors")
            print(f"  sample: {failures[0]!r}")
            return 1
        print("OK: concurrent list_open 32/32")

        # Public protobuf realtime: must receive at least one publication.
        symbol = os.getenv("POLYESTER_TEST_SMOKE_SYMBOL") or "BTC-USDT"
        sub = await client.market_data.subscribe_trades(symbol=symbol)
        got = 0
        deadline = asyncio.get_running_loop().time() + 25
        try:
            while asyncio.get_running_loop().time() < deadline and got < 1:
                try:
                    await asyncio.wait_for(anext(sub), timeout=3.0)
                    got += 1
                except TimeoutError:
                    continue
                except StopAsyncIteration:
                    print("FAIL: trades subscription ended without publications")
                    return 1
        finally:
            await sub.aclose()

        if got < 1:
            print(f"FAIL: no public trades publications on {symbol} within 25s")
            return 1
        print(f"OK: public trades :proto received {got} publication(s) on {symbol}")
        return 0
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
