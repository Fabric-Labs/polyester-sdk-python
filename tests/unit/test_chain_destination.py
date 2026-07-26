from polyester.chain import encode_withdraw_destination, encode_withdraw_destination_hex


def test_encode_withdraw_destination_lowercases_case_insensitive() -> None:
    raw = encode_withdraw_destination(
        address="0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
        is_case_sensitive=False,
    )
    assert raw == b"0xabcdef0123456789abcdef0123456789abcdef01"
    assert (
        encode_withdraw_destination_hex(
            address="0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
            is_case_sensitive=False,
        )
        == "0x" + raw.hex()
    )


def test_encode_withdraw_destination_preserves_case_sensitive() -> None:
    addr = "So11111111111111111111111111111111111111112"
    assert encode_withdraw_destination(address=addr, is_case_sensitive=True) == addr.encode()
