from __future__ import annotations

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import PolyesterApiError
from polyester.gen.auth.v1 import auth_pb2


def test_map_connect_error_surfaces_auth_revision_conflict() -> None:
    detail = auth_pb2.AuthErrorDetail(
        code=auth_pb2.AUTH_REVISION_CONFLICT,
        message="resource changed",
    )
    mapped = map_connect_error(ConnectError(Code.ABORTED, "aborted", details=[detail]))
    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == "AUTH_REVISION_CONFLICT"
    assert str(mapped) == "resource changed"
