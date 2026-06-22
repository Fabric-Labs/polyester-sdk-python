from __future__ import annotations

from polyester.codecs.decode.common import api_data_from_proto
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.models import ApiData


def deposit_withdraw_config_from_proto(
    msg: zipper_pb2.GetDepositWithdrawConfigResponse,
) -> ApiData:
    return api_data_from_proto(msg)
