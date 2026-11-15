from __future__ import annotations

from polyester._wire import protobuf_to_public_dict
from polyester.errors import PolyesterResponseContractError
from polyester.models import ApiData


def api_data_from_proto(msg) -> ApiData:
    return ApiData(raw=protobuf_to_public_dict(msg))


def require_id(operation: str, field: str, value: int) -> None:
    """Refuse a reply whose required public ID is 0.

    0 is the proto default of an absent field: the reply breaks the response
    contract, and the call may have applied, so the caller must not keep
    ``"0"`` as the ID of what it changed.
    """
    if not value:
        raise PolyesterResponseContractError(operation, f"missing {field}")
