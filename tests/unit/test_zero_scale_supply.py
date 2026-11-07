"""A quantity scale of 0 is a real scale: BONK and SHIB supplies are whole units."""

from __future__ import annotations

import pytest
from google.protobuf import json_format

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.zipper import (
    deposit_withdraw_config_from_proto,
    zipped_asset_supply_batch_from_proto,
)
from polyester.codecs.ledger_amounts import LEDGER_SCALE, format_ledger_u128
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.services.zipper import AsyncZipperService

# The published config as JSON: a plain proto3 field at 0 is omitted, so BONK
# and SHIB carry no quantityScale. USDT, BTC and ETH are scale 6, 8 and 18.
CONFIG_JSON = """
{
  "chains": [{"chainId": 1, "code": "ethereum", "name": "Ethereum"}],
  "assets": [
    {"asset": "BONK", "ledgerId": 45, "variants": [
      {"zippedAssetId": 245, "chainId": 1, "supplyQ": "3582802",
       "sourceDecimals": 18, "ztokenDecimals": 18}]},
    {"asset": "SHIB", "ledgerId": 47, "variants": [
      {"zippedAssetId": 247, "chainId": 1, "supplyQ": "2232802",
       "sourceDecimals": 18, "ztokenDecimals": 18}]},
    {"asset": "USDT", "ledgerId": 11, "quantityScale": 6, "variants": [
      {"zippedAssetId": 3, "chainId": 1, "supplyQ": "1500000",
       "sourceDecimals": 6, "ztokenDecimals": 18}]},
    {"asset": "BTC", "ledgerId": 12, "quantityScale": 8, "variants": [
      {"zippedAssetId": 1, "chainId": 1, "supplyQ": "150000000",
       "sourceDecimals": 8, "ztokenDecimals": 18}]},
    {"asset": "ETH", "ledgerId": 13, "quantityScale": 18, "variants": [
      {"zippedAssetId": 13, "chainId": 1, "supplyQ": "1500000000000000000",
       "sourceDecimals": 0, "ztokenDecimals": 18}]}
  ]
}
"""

EXPECTED_SUPPLY = {245: "3582802", 247: "2232802", 3: "1.5", 1: "1.5", 13: "1.5"}


def _config_proto() -> zipper_pb2.GetDepositWithdrawConfigResponse:
    return json_format.Parse(CONFIG_JSON, zipper_pb2.GetDepositWithdrawConfigResponse())


@pytest.mark.parametrize(
    ("raw", "scale", "expected"),
    [
        ("3582802", 0, "3582802"),
        (2232802, 0, "2232802"),
        ("0", 0, "0"),
        ("1500000", 6, "1.5"),
        ("150000000", 8, "1.5"),
        ("1500000000000000000", 18, "1.5"),
    ],
)
def test_format_ledger_u128_uses_the_scale_it_is_given(
    raw: str | int, scale: int, expected: str
) -> None:
    assert format_ledger_u128(raw, scale=scale) == expected


def test_format_ledger_u128_default_is_still_ledger_scale() -> None:
    assert LEDGER_SCALE == 18
    assert format_ledger_u128("1500000000000000000") == "1.5"


def test_format_ledger_u128_rejects_negative_scale() -> None:
    with pytest.raises(PolyesterValidationError):
        format_ledger_u128("1", scale=-1)


def test_config_getter_reads_zero_scale_supply_as_whole_units() -> None:
    config = deposit_withdraw_config_from_proto(_config_proto())
    supply = {v.zipped_asset_id: v.supply for a in config.assets for v in a.variants}
    assert supply == EXPECTED_SUPPLY
    scales = {a.asset: a.quantity_scale for a in config.assets}
    assert scales == {"BONK": 0, "SHIB": 0, "USDT": 6, "BTC": 8, "ETH": 18}


def test_config_getter_keeps_zero_token_decimals() -> None:
    config = deposit_withdraw_config_from_proto(_config_proto())
    eth = next(a for a in config.assets if a.asset == "ETH")
    assert eth.variants[0].source_token.decimals == 0
    assert eth.variants[0].z_token.decimals == 18


def test_live_supply_batch_reads_zero_scale_supply_as_whole_units() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_zipper_config(deposit_withdraw_config_from_proto(_config_proto()))
    batch = zipper_pb2.ZippedAssetSupplyBatch(
        updates=[
            zipper_pb2.ZippedAssetSupplyUpdate(zipped_asset_id=zid, supply_q=q)
            for zid, q in [
                (245, 3_582_802),
                (247, 2_232_802),
                (3, 1_500_000),
                (1, 150_000_000),
                (13, 1_500_000_000_000_000_000),
            ]
        ]
    )
    service = AsyncZipperService(None, catalogs=catalogs)
    decoded = service._decode_supply_batch(batch.SerializeToString())
    assert {u.zipped_asset_id: u.supply for u in decoded.updates} == EXPECTED_SUPPLY


def test_live_supply_batch_still_refuses_unknown_scale() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_zipper_config(deposit_withdraw_config_from_proto(_config_proto()))
    batch = zipper_pb2.ZippedAssetSupplyBatch(
        updates=[zipper_pb2.ZippedAssetSupplyUpdate(zipped_asset_id=999, supply_q=3_582_802)]
    )
    with pytest.raises(PolyesterValidationError):
        zipped_asset_supply_batch_from_proto(
            batch,
            quantity_scale_for_zipped_asset_id=catalogs.quantity_scale_for_zipped_asset_id,
        )
