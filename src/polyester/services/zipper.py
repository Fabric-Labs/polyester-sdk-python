from __future__ import annotations

from polyester.codecs.decode.zipper import deposit_withdraw_config_from_proto
from polyester.gen.chain.zipper.v1.zipper_connect import ZipperServiceClient
from polyester.gen.chain.zipper.v1.zipper_pb2 import GetDepositWithdrawConfigRequest
from polyester.models import ApiData
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded


class AsyncZipperService(BaseService):
    async def get_deposit_withdraw_config(self) -> ApiData:
        return await unary_public_decoded(
            self._transport,
            ZipperServiceClient,
            lambda client, request: client.get_deposit_withdraw_config(request),
            GetDepositWithdrawConfigRequest(),
            deposit_withdraw_config_from_proto,
        )
