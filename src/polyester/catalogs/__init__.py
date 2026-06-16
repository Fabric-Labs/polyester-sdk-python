from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CatalogManager:
    spot_config: dict[str, Any] = field(default_factory=dict)
    zipper_config: dict[str, Any] = field(default_factory=dict)

    def hydrate_spot_config(self, config: dict[str, Any]) -> None:
        self.spot_config = config

    def hydrate_zipper_config(self, config: dict[str, Any]) -> None:
        self.zipper_config = config

    def symbol_id_for_symbol(self, symbol: str) -> int | None:
        for pair in self._pairs():
            if pair.get("symbol") == symbol:
                value = pair.get("symbol_id") or pair.get("symbolId")
                return int(value) if value is not None else None
        return None

    def base_quantity_scale_for_symbol(self, symbol: str) -> int:
        for pair in self._pairs():
            if pair.get("symbol") == symbol:
                value = (
                    pair.get("base_quantity_scale")
                    or pair.get("baseQuantityScale")
                    or pair.get("qtyScale")
                )
                return int(value) if value is not None else 8
        return 8

    def _pairs(self) -> list[dict[str, Any]]:
        pairs = self.spot_config.get("pairs") or self.spot_config.get("symbols") or []
        return [pair for pair in pairs if isinstance(pair, dict)]
