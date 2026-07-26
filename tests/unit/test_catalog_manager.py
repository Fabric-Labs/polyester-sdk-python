from polyester.catalogs import CatalogManager


def test_orderbook_price_buckets_for_symbol_reads_spot_marketdata() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "marketdata": {"orderbook_price_buckets": [0.01, 0.1, 1.0]},
                }
            ]
        }
    )
    assert catalogs.orderbook_price_buckets_for_symbol("BTC-USDT") == ["0.01", "0.1", "1"]


def test_ledger_id_for_asset_uses_typed_zipper_catalog() -> None:
    from polyester.models.zipper import DepositWithdrawConfig, ZipperAssetConfig

    catalogs = CatalogManager()
    catalogs.hydrate_zipper_config(
        DepositWithdrawConfig(
            assets=[ZipperAssetConfig(asset="USDT", ledger_id=99, quantity_scale=6)]
        )
    )
    assert catalogs.ledger_id_for_asset("USDT") == 99
