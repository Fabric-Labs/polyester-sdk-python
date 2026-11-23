from __future__ import annotations

from polyester.codecs.pure_bridge import call, pure

MAX_BPS: int = pure._MAX_BPS
# A slippage cap on anything that sells, and on every trailing stop, stops
# short of 100%, which would leave no positive price to sell at.
MAX_SELL_SLIPPAGE_BPS = MAX_BPS - 1


def validate_bps(
    value: object,
    field_name: str,
    *,
    allow_clear: bool = False,
    max_value: int = MAX_BPS,
) -> int:
    """Validate a basis-point field before assigning it to protobuf."""
    return call(pure._bps, value, field_name, allow_clear, max_value)


def max_slippage_bps_for_side(side: str) -> int:
    """Largest market slippage cap for an execution on ``side``: 10000 bps to
    buy, 9999 to sell."""
    return int(pure._max_slippage_bps_for_side(side))
