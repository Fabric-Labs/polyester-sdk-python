from __future__ import annotations

from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.models import InternalTransferResult
from polyester.types.money import AssetAmount, QuantityDomain


def internal_transfer_from_proto(
    msg: internal_transfer_pb2.CreateInternalTransferResponse,
) -> InternalTransferResult:
    return InternalTransferResult(
        request_id=msg.request_id,
        transfer_id=msg.transfer_id,
        asset_id=int(msg.asset_id),
        asset_code=msg.asset_code,
        quantity=AssetAmount.from_scaled(
            int(msg.qty_scaled),
            domain=QuantityDomain.ASSET,
            asset_id=int(msg.asset_id),
        ),
    )
