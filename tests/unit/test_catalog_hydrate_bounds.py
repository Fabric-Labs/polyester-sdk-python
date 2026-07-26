"""POLY-3746: catalog hydrate rejects u64→u32 truncation and scales > 36."""

from __future__ import annotations

import pytest

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.models.zipper import DepositWithdrawConfig, ZipperAssetConfig


def test_hydrate_spot_rejects_scale_65535() -> None:
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        catalogs.hydrate_spot_config(
            {
                "pairs": [
                    {
                        "symbol": "ETH-USDT",
                        "symbol_id": 2,
                        "base_quantity_scale": 65535,
                    }
                ]
            }
        )
    assert catalogs.is_unusable
    assert catalogs.base_quantity_scale_for_symbol("ETH-USDT") is None
    assert catalogs.spot_config == {}


def test_hydrate_spot_rejects_symbol_id_above_u32() -> None:
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError, match="uint32"):
        catalogs.hydrate_spot_config(
            {
                "pairs": [
                    {
                        "symbol": "ETH-USDT",
                        "symbol_id": 2**32,  # would truncate as u32
                        "base_quantity_scale": 6,
                    }
                ]
            }
        )
    assert catalogs.is_unusable
    assert catalogs.symbol_id_for_symbol("ETH-USDT") is None


def test_hydrate_spot_accepts_valid_pair() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "ETH-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 6,
                }
            ]
        }
    )
    assert not catalogs.is_unusable
    assert catalogs.base_quantity_scale_for_symbol("ETH-USDT") == 6


def test_hydrate_zipper_rejects_bad_scale() -> None:
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        catalogs.hydrate_zipper_config(
            {
                "assets": [
                    {"asset": "USDT", "ledgerId": 99, "quantityScale": 65535},
                ]
            }
        )
    assert catalogs.is_unusable


def test_hydrate_zipper_config_typed_accepts_deposit_withdraw_config() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_zipper_config_typed(
        DepositWithdrawConfig(
            assets=[ZipperAssetConfig(asset="USDT", ledger_id=99, quantity_scale=6)]
        )
    )
    assert catalogs.ledger_id_for_asset("USDT") == 99
    assert catalogs.quantity_scale_for_asset("USDT") == 6


def test_hydrate_zipper_config_typed_rejects_bad_scale() -> None:
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        catalogs.hydrate_zipper_config_typed(
            DepositWithdrawConfig(
                assets=[ZipperAssetConfig(asset="USDT", ledger_id=1, quantity_scale=37)]
            )
        )
    assert catalogs.is_unusable
