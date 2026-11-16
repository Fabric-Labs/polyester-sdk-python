"""Codes the server answers for a field it refuses, for the same refusal made locally.

A trigger or OCO field the SDK refuses before sending carries the code the API
answers for the same mistake, so a pre-checked request and a server refusal read
alike (``PolyesterValidationError.code``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from polyester.errors import PolyesterValidationError

BAD_PRICE = "ERROR_CODE_BAD_PRICE"
BAD_QTY = "ERROR_CODE_BAD_QTY"
CLIENT_TRIGGER_ID_INVALID = "ERROR_CODE_CLIENT_TRIGGER_ID_INVALID"
FEE_ASSET_NOT_ALLOWED = "ERROR_CODE_FEE_ASSET_NOT_ALLOWED"
LADDER_LEVELS_INVALID = "ERROR_CODE_LADDER_LEVELS_INVALID"
MAX_SLIPPAGE_INVALID = "ERROR_CODE_MAX_SLIPPAGE_INVALID"
SLIPPAGE_BPS_INVALID = "ERROR_CODE_SLIPPAGE_BPS_INVALID"
SLIPPAGE_TICKS_INVALID = "ERROR_CODE_SLIPPAGE_TICKS_INVALID"
TRAILING_DISTANCE_INVALID = "ERROR_CODE_TRAILING_DISTANCE_INVALID"
TRIGGER_ACTIVATION_PRICE_INVALID = "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_INVALID"
TRIGGER_PRICE_INVALID = "ERROR_CODE_TRIGGER_PRICE_INVALID"
TRIGGER_QTY_INVALID = "ERROR_CODE_TRIGGER_QTY_INVALID"
TWAP_DURATION_INVALID = "ERROR_CODE_TWAP_DURATION_INVALID"
TWAP_INTERVAL_INVALID = "ERROR_CODE_TWAP_INTERVAL_INVALID"


@contextmanager
def refusal_code(code: str | None) -> Iterator[None]:
    """A refusal raised in the block without a code of its own carries ``code``.

    A refusal that already names a code, such as ``PRICE_TICK_SIZE`` for a price
    off the tick grid, keeps it. ``None`` leaves refusals as they are.
    """
    try:
        yield
    except PolyesterValidationError as exc:
        if code is not None and exc.code is None:
            exc.code = code
        raise
