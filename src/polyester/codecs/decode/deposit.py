from __future__ import annotations

from polyester.codecs.proto_helpers import has_field
from polyester.gen.chain.deposit.v1 import deposit_pb2
from polyester.models import DepositAddress, DepositAddressesList


def deposit_address_from_proto(msg: deposit_pb2.DepositAddress) -> DepositAddress:
    return DepositAddress(
        chain_id=int(msg.chain_id),
        deposit_address=msg.deposit_address,
    )


def deposit_addresses_list_from_proto(
    msg: deposit_pb2.ListDepositAddressesResponse,
) -> DepositAddressesList:
    return DepositAddressesList(
        addresses=[deposit_address_from_proto(item) for item in msg.deposit_addresses]
    )


def create_deposit_address_from_proto(
    msg: deposit_pb2.CreateDepositAddressResponse,
) -> DepositAddress:
    if has_field(msg, "deposit_address"):
        return deposit_address_from_proto(msg.deposit_address)
    return DepositAddress()
