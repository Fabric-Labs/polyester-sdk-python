from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from polyester.catalogs.zipper import build_zipper_catalog_data
from polyester.catalogs.zipper_supply import patch_zipper_catalog_supply
from polyester.models.zipper import (
    DepositWithdrawConfig,
    ZippedAssetSupplyUpdate,
    ZipperCatalogData,
)


@dataclass(slots=True)
class CatalogManager:
    spot_config: dict[str, Any] = field(default_factory=dict)
    zipper: ZipperCatalogData | None = None
    deposit_withdraw_config: DepositWithdrawConfig | None = None
    _legacy_zipper_raw: dict[str, Any] = field(default_factory=dict)

    @property
    def zipper_config(self) -> dict[str, Any]:
        """Backward-compatible raw dict view of the typed zipper catalog."""
        if self.deposit_withdraw_config is None:
            return {}
        config = self.deposit_withdraw_config
        return {
            "chains": [msgspec_to_dict(chain) for chain in config.chains],
            "assets": [
                {
                    **msgspec_to_dict(asset),
                    "variants": [msgspec_to_dict(variant) for variant in asset.variants],
                }
                for asset in config.assets
            ],
            "contracts": [msgspec_to_dict(item) for item in config.contracts],
            "polyesterChainId": config.polyester_chain_id,
            "tsSec": config.ts_ms // 1000 if config.ts_ms else 0,
        }

    def hydrate_spot_config(self, config: dict[str, Any]) -> None:
        self.spot_config = config

    def hydrate_zipper_config(
        self,
        config: DepositWithdrawConfig | dict[str, Any],
    ) -> None:
        if isinstance(config, DepositWithdrawConfig):
            self.deposit_withdraw_config = config
            self.zipper = build_zipper_catalog_data(config)
            return
        self.deposit_withdraw_config = None
        self.zipper = None
        self._legacy_zipper_raw = config

    def hydrate_deposit_withdraw_config(self, config: DepositWithdrawConfig) -> None:
        self.hydrate_zipper_config(config)

    def symbol_id_for_symbol(self, symbol: str) -> int | None:
        for pair in self._pairs():
            if pair.get("symbol") == symbol:
                value = pair.get("symbol_id") or pair.get("symbolId")
                return int(value) if value is not None else None
        return None

    def base_quantity_scale_for_symbol(self, symbol: str) -> int | None:
        """Return the pair base quantity scale, or None when unknown/unhydrated.

        Never invents scale 8 for missing symbols — callers that need a decode
        fallback must choose it explicitly.
        """
        for pair in self._pairs():
            if pair.get("symbol") == symbol:
                value = (
                    pair.get("base_quantity_scale")
                    or pair.get("baseQuantityScale")
                    or pair.get("qtyScale")
                )
                return int(value) if value is not None else None
        return None

    def base_quantity_scale_for_symbol_id(self, symbol_id: int) -> int | None:
        for pair in self._pairs():
            value = pair.get("symbol_id") or pair.get("symbolId")
            if value is not None and int(value) == int(symbol_id):
                symbol = pair.get("symbol")
                if symbol:
                    return self.base_quantity_scale_for_symbol(str(symbol))
                break
        return None

    def orderbook_price_buckets_for_symbol(self, symbol: str) -> list[str]:
        pair = self._pair_for_symbol(symbol)
        if pair is None:
            return []
        marketdata = pair.get("marketdata") or pair.get("marketData") or {}
        buckets = marketdata.get("orderbook_price_buckets") or marketdata.get(
            "orderbookPriceBuckets"
        )
        if not isinstance(buckets, list):
            return []
        result: list[str] = []
        for value in buckets:
            if isinstance(value, (int, float)):
                text = format(value, "f").rstrip("0").rstrip(".") or "0"
                result.append(text)
            elif value is not None:
                result.append(str(value))
        return result

    def ledger_id_for_asset(self, asset_symbol: str) -> int | None:
        catalog = self.zipper
        if catalog is not None:
            for asset in catalog.assets:
                if asset.asset == asset_symbol:
                    return asset.ledger_id or None
        raw = self._legacy_zipper_raw or self.zipper_config
        for row in raw.get("assets") or []:
            symbol = row.get("asset") or row.get("code")
            if symbol == asset_symbol:
                value = row.get("ledgerId") or row.get("ledger_id")
                return int(value) if value is not None else None
        return None

    def quantity_scale_for_asset(self, asset_symbol: str) -> int | None:
        catalog = self.zipper
        if catalog is not None:
            for asset in catalog.assets:
                if asset.asset == asset_symbol:
                    return asset.quantity_scale
        raw = self._legacy_zipper_raw or self.zipper_config
        for row in raw.get("assets") or []:
            symbol = row.get("asset") or row.get("code")
            if symbol == asset_symbol:
                value = row.get("quantityScale") or row.get("quantity_scale")
                return int(value) if value is not None else None
        return None

    def quantity_scale_for_zipped_asset_id(self, zipped_asset_id: int) -> int:
        catalog = self.zipper
        if catalog is not None:
            for asset in catalog.assets:
                for chain in asset.chains:
                    if chain.zipped_asset_id == zipped_asset_id:
                        return asset.quantity_scale
        return 18

    def patch_zipper_supply(self, updates: list[ZippedAssetSupplyUpdate]) -> bool:
        if self.zipper is None or not updates:
            return False
        patched = patch_zipper_catalog_supply(self.zipper, updates)
        if patched is self.zipper:
            return False
        self.zipper = patched
        return True

    def _pair_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        for pair in self._pairs():
            if pair.get("symbol") == symbol:
                return pair
        return None

    def _pairs(self) -> list[dict[str, Any]]:
        pairs = self.spot_config.get("pairs") or self.spot_config.get("symbols") or []
        return [pair for pair in pairs if isinstance(pair, dict)]


def msgspec_to_dict(value: object) -> dict[str, Any]:
    import msgspec

    return msgspec.to_builtins(value)
