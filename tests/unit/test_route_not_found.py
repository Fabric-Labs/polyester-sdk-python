from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import PolyesterRouteNotFoundError


def test_map_connect_unimplemented_not_found() -> None:
    exc = ConnectError(Code.UNIMPLEMENTED, "Not Found")
    mapped = map_connect_error(exc)
    assert isinstance(mapped, PolyesterRouteNotFoundError)
