from __future__ import annotations

from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import subaccounts_pb2


def invite_direction_from_label(direction: str) -> int:
    key = direction.strip().lower().replace("-", "_")
    aliases = {
        "": subaccounts_pb2.DIRECTION_UNSPECIFIED,
        "unspecified": subaccounts_pb2.DIRECTION_UNSPECIFIED,
        "incoming": subaccounts_pb2.INCOMING,
        "outgoing": subaccounts_pb2.OUTGOING,
    }
    if key in aliases:
        return aliases[key]
    raise PolyesterValidationError("invites_direction must be incoming, outgoing, or empty")
