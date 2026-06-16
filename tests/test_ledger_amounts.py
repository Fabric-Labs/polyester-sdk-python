from polyester.codecs.ledger_amounts import format_ledger_u128


def test_format_ledger_u128_zero() -> None:
    assert format_ledger_u128("0") == "0"


def test_format_ledger_u128_one_unit() -> None:
    assert format_ledger_u128(str(10**18)) == "1"
