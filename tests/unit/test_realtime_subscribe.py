import pytest

from polyester.services._realtime_subscribe import subscribe_account_proto, subscribe_public_proto


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("private:spot:orders:{account_id}:proto", "private:spot:orders:acct:proto"),
        ("private:ledger:balances:{account_id}:proto", "private:ledger:balances:acct:proto"),
        ("private:auth:api-keys:{account_id}:proto", "private:auth:api-keys:acct:proto"),
    ],
)
@pytest.mark.asyncio
async def test_subscribe_account_proto_formats_channel(template: str, expected: str) -> None:
    from unittest.mock import AsyncMock, MagicMock

    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(return_value="sub")
    result = await subscribe_account_proto(
        realtime,
        channel_template=template,
        account_id="acct",
        default_account_id=None,
        decode=lambda payload: payload,
    )
    assert result == "sub"
    assert realtime.subscribe_proto.await_args.args[0] == expected


@pytest.mark.parametrize(
    ("channel",),
    [
        ("public:spot:market_overview:updates:proto",),
        ("public:chain:zipped-asset:supply:proto",),
        ("public:identity:updates:proto",),
    ],
)
@pytest.mark.asyncio
async def test_subscribe_public_proto_passes_channel(channel: str) -> None:
    from unittest.mock import AsyncMock, MagicMock

    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(return_value="sub")
    await subscribe_public_proto(
        realtime,
        channel=channel,
        decode=lambda payload: payload,
    )
    assert realtime.subscribe_proto.await_args.args[0] == channel
