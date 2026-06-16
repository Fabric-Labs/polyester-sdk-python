from __future__ import annotations

from polyester.gen.chain.zipper.v1.zipper_connect import ZipperServiceClient
from polyester.gen.chain.zipper.v1.zipper_pb2 import GetDepositWithdrawConfigRequest
from polyester.models import ApiData
from polyester.services._base import BaseService
from polyester.services._generated import unary_public


class AsyncZipperService(BaseService):
    async def get_deposit_withdraw_config(self) -> ApiData:
        data = await unary_public(
            self._transport,
            ZipperServiceClient,
            lambda client, request: client.get_deposit_withdraw_config(request),
            GetDepositWithdrawConfigRequest(),
        )
        return ApiData(raw=data)
