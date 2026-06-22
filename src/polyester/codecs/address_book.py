from __future__ import annotations

from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import address_book_pb2


def address_book_entry_kind_from_label(kind: str) -> int:
    aliases = {
        "external": address_book_pb2.EXTERNAL_CHAIN,
        "external_chain": address_book_pb2.EXTERNAL_CHAIN,
        "internal": address_book_pb2.INTERNAL_ACCOUNT,
        "internal_account": address_book_pb2.INTERNAL_ACCOUNT,
    }
    key = kind.lower().replace("-", "_")
    if key in aliases:
        return aliases[key]
    enum_name = key.upper()
    if not enum_name.startswith("ENTRY_KIND_") and enum_name not in (
        "EXTERNAL_CHAIN",
        "INTERNAL_ACCOUNT",
    ):
        enum_name = f"ENTRY_KIND_{enum_name}" if enum_name != "EXTERNAL_CHAIN" else enum_name
    value = getattr(address_book_pb2, enum_name, None)
    if value is None and not enum_name.startswith("ENTRY_KIND_"):
        value = getattr(address_book_pb2, f"ENTRY_KIND_{enum_name}", None)
    if value is None:
        raise PolyesterValidationError("kind must be 'external' or 'internal'")
    return value


def transfer_counterparty_direction_from_label(direction: str) -> int:
    aliases = {
        "deposit_from": address_book_pb2.DEPOSIT_FROM,
        "withdraw_to": address_book_pb2.WITHDRAW_TO,
        "internal_transfer_from": address_book_pb2.INTERNAL_TRANSFER_FROM,
        "internal_transfer_to": address_book_pb2.INTERNAL_TRANSFER_TO,
    }
    key = direction.lower().replace("-", "_")
    if key in aliases:
        return aliases[key]
    enum_name = key.upper()
    value = getattr(address_book_pb2, enum_name, None)
    if value is None:
        raise PolyesterValidationError(f"Unknown transfer counterparty direction: {direction}")
    return value


def address_book_tag_input_to_proto(
    *,
    name: str,
    color: str = "",
) -> address_book_pb2.AddressBookTagInput:
    return address_book_pb2.AddressBookTagInput(name=name, color=color)


def create_entry_external_to_proto(
    *,
    polychain_chain_id: int,
    address: str,
) -> address_book_pb2.ExternalWithdrawAddress:
    return address_book_pb2.ExternalWithdrawAddress(
        polychain_chain_id=polychain_chain_id,
        address=address,
    )


def create_entry_internal_to_proto(
    *,
    smart_account_address: str,
) -> address_book_pb2.RequestedInternalTransferAccount:
    return address_book_pb2.RequestedInternalTransferAccount(
        smart_account_address=smart_account_address,
    )
