import asyncio
import os

from polyester import AsyncPolyester


async def main() -> None:
    # Read secrets from env in this example script, then pass them explicitly.
    async with AsyncPolyester(
        api_key_id=os.environ["POLYESTER_API_KEY_ID"],
        api_private_key=os.environ["POLYESTER_API_PRIVATE_KEY"],
        default_account_id=os.environ["POLYESTER_ACCOUNT_ID"],  # Profile → Account ID
        default_sub_account_id="",
    ) as client:
        overview = await client.market_overview.list(limit=3)
        for row in overview.markets:
            print(
                row.symbol or row.symbol_id,
                row.last_price.ticks if row.last_price else None,
            )

        open_orders = await client.orders.list_open()
        print(f"Open orders: {len(open_orders.orders)}")

        # Uncomment when your API key has trade policy on devnet:
        # created = await client.orders.create(
        #     symbol="ETH-USDT",
        #     side="buy",
        #     order_type="limit",
        #     tif="gtc",
        #     qty="0.001",
        #     price="100",
        #     post_only=True,
        # )
        # print("Created", created.status, created.order_id)


if __name__ == "__main__":
    asyncio.run(main())
