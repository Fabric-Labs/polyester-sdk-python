from polyester.catalogs.zipper import build_zipper_catalog_data
from polyester.codecs.decode.zipper import deposit_withdraw_config_from_proto
from polyester.gen.chain.zipper.v1 import zipper_pb2


def test_deposit_withdraw_config_from_proto_normalizes_supply_and_tokens() -> None:
    msg = zipper_pb2.GetDepositWithdrawConfigResponse(
        ts_sec=1_700_000_000,
        polyester_chain_id=1,
        chains=[
            zipper_pb2.ChainConfig(
                chain_id=1,
                code="eth",
                name="Ethereum",
                native_currency_symbol="ETH",
            )
        ],
        assets=[
            zipper_pb2.AssetConfig(
                asset="USDT",
                ledger_id=42,
                name="Tether",
                quantity_scale=6,
                variants=[
                    zipper_pb2.AssetChainVariant(
                        zipped_asset_id=7,
                        chain_id=1,
                        supply_q=1_500_000,
                        source_address="0xsource",
                        source_decimals=6,
                        ztoken_address="0xz",
                        ztoken_decimals=18,
                    )
                ],
            )
        ],
    )

    config = deposit_withdraw_config_from_proto(msg)
    assert config.ts_ms == 1_700_000_000_000
    assert config.assets[0].variants[0].supply == "1.5"
    assert config.assets[0].variants[0].source_token.address == "0xsource"
    assert config.assets[0].variants[0].z_token.decimals == 18

    catalog = build_zipper_catalog_data(config)
    assert catalog.assets[0].chains[0].code == "eth"
    assert catalog.assets[0].chains[0].supply == "1.5"
