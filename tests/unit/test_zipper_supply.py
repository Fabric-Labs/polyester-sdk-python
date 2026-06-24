from polyester.catalogs.zipper import build_zipper_catalog_data
from polyester.catalogs.zipper_supply import patch_zipper_catalog_supply
from polyester.models.zipper import (
    DepositWithdrawConfig,
    ZipperAssetConfig,
    ZipperAssetChainVariant,
    ZipperChainConfig,
    ZippedAssetSupplyUpdate,
)


def _sample_catalog():
    config = DepositWithdrawConfig(
        chains=[ZipperChainConfig(chain_id=1, code="eth", name="Ethereum")],
        assets=[
            ZipperAssetConfig(
                asset="USDT",
                ledger_id=42,
                quantity_scale=6,
                variants=[
                    ZipperAssetChainVariant(
                        zipped_asset_id=7,
                        chain_id=1,
                        supply="1.0",
                    )
                ],
            )
        ],
    )
    return build_zipper_catalog_data(config)


def test_patch_zipper_catalog_supply_updates_matching_route() -> None:
    catalog = _sample_catalog()
    patched = patch_zipper_catalog_supply(
        catalog,
        [ZippedAssetSupplyUpdate(zipped_asset_id=7, supply="2.5")],
    )
    assert patched is not catalog
    assert patched.assets[0].chains[0].supply == "2.5"


def test_patch_zipper_catalog_supply_noop_when_unchanged() -> None:
    catalog = _sample_catalog()
    patched = patch_zipper_catalog_supply(
        catalog,
        [ZippedAssetSupplyUpdate(zipped_asset_id=7, supply="1.0")],
    )
    assert patched is catalog
