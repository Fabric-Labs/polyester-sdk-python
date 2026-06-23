from __future__ import annotations

from polyester.codecs.decode.zipper import deposit_withdraw_config_from_proto
from polyester.codecs.realtime_decode import decode_zipped_asset_supply_batch_bytes
from polyester.gen.chain.zipper.v1.zipper_connect import ZipperServiceClient
from polyester.gen.chain.zipper.v1.zipper_pb2 import GetDepositWithdrawConfigRequest
from polyester.models import ApiData
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded
from polyester.services._realtime_subscribe import subscribe_public_proto


class AsyncZipperService(BaseService):
    def __init__(self, transport, *, realtime: AsyncRealtimeClient | None = None) -> None:
        super().__init__(transport)
        self._realtime = realtime

    async def get_deposit_withdraw_config(self) -> ApiData:
        return await unary_public_decoded(
            self._transport,
            ZipperServiceClient,
            lambda client, request: client.get_deposit_withdraw_config(request),
            GetDepositWithdrawConfigRequest(),
            deposit_withdraw_config_from_proto,
        )

    async def subscribe_zipped_asset_supply(self) -> AsyncSubscription[ApiData]:
        return await subscribe_public_proto(
            self._realtime,
            channel="public:chain:zipped-asset:supply:proto",
            decode=decode_zipped_asset_supply_batch_bytes,
        )
