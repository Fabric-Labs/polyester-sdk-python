from polyester.codecs.decode.transfers import ledger_transfer_from_proto, transfer_side_from_proto
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2


def test_transfer_row_maps_external_side_chain_id() -> None:
    msg = ledger_read_pb2.TransferRow(
        asset_id=2,
        amount_e18=u128_pb2.U128(lo=1000),
        transfer_code=5,
        account_code=1,
        ts_us=999,
        flow_id="flow-abc",
        source=ledger_read_pb2.TransferSide(
            kind=ledger_read_pb2.FUNDING_ACCOUNT,
            account_id=11,
            address="0x1111111111111111111111111111111111111111",
        ),
        destination=ledger_read_pb2.TransferSide(
            kind=ledger_read_pb2.EXTERNAL_ADDRESS,
            address="0x2222222222222222222222222222222222222222",
            chain_id=8453,
        ),
    )
    transfer = ledger_transfer_from_proto(msg)
    assert transfer.source is not None
    assert transfer.source.kind == "funding_account"
    assert transfer.source.account_id == format_uint64_id(11)
    assert transfer.source.chain_id is None
    assert transfer.destination is not None
    assert transfer.destination.kind == "external_address"
    assert transfer.destination.chain_id == 8453


def test_transfer_side_omits_empty_and_unset_chain_id() -> None:
    assert transfer_side_from_proto(None) is None
    assert transfer_side_from_proto(ledger_read_pb2.TransferSide()) is None
    side = transfer_side_from_proto(
        ledger_read_pb2.TransferSide(
            kind=ledger_read_pb2.EXTERNAL_ADDRESS,
            address="0xabc",
        )
    )
    assert side is not None
    assert side.chain_id is None
