import pytest

from polyester.codecs.orders import batch_replace_orders_to_proto, risk_policy_from_dict
from polyester.errors import PolyesterValidationError


def test_risk_policy_from_dict_empty() -> None:
    assert risk_policy_from_dict(None) is None


def test_risk_policy_trailing_stop_requires_positive_distance() -> None:
    with pytest.raises(PolyesterValidationError, match="trailing_distance_ticks must be positive"):
        risk_policy_from_dict({"trailing_stop": {"trailing_distance_ticks": 0}})


def test_risk_policy_trailing_stop_rejects_order_type() -> None:
    with pytest.raises(PolyesterValidationError, match="always market"):
        risk_policy_from_dict(
            {
                "trailing_stop": {
                    "trailing_distance_bps": 25,
                    "order_type": "limit",
                }
            }
        )


def test_risk_policy_trailing_stop_encodes_positive_distance() -> None:
    risk = risk_policy_from_dict(
        {"trailing_stop": {"trailing_distance_bps": 25, "max_slippage_ticks": 10}}
    )
    assert risk is not None
    assert risk.WhichOneof("stop_leg") == "trailing_stop"
    assert risk.trailing_stop.trailing_distance_bps == 25
    assert risk.trailing_stop.max_slippage_ticks == 10


def test_batch_replace_requires_items() -> None:
    with pytest.raises(PolyesterValidationError):
        batch_replace_orders_to_proto(items=[], symbol_id=1)
