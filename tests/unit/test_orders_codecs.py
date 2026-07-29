import pytest

from polyester.codecs.orders import batch_replace_orders_to_proto, risk_policy_from_dict
from polyester.errors import PolyesterValidationError


def test_risk_policy_from_dict_empty() -> None:
    assert risk_policy_from_dict(None) is None


def test_batch_replace_requires_items() -> None:
    with pytest.raises(PolyesterValidationError):
        batch_replace_orders_to_proto(items=[], symbol_id=1)
