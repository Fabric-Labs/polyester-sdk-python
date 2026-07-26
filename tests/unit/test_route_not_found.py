from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import (
    PolyesterRateLimitError,
    PolyesterRouteNotFoundError,
    PolyesterTransportError,
    is_retryable_error,
    mutation_outcome_unknown,
)


def test_map_connect_unimplemented_not_found() -> None:
    exc = ConnectError(Code.UNIMPLEMENTED, "Not Found")
    mapped = map_connect_error(exc)
    assert isinstance(mapped, PolyesterRouteNotFoundError)


def test_map_connect_resource_exhausted_is_rate_limit() -> None:
    mapped = map_connect_error(ConnectError(Code.RESOURCE_EXHAUSTED, "slow down"))
    assert isinstance(mapped, PolyesterRateLimitError)
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


def test_transport_retry_classification_preserves_ambiguity() -> None:
    err = PolyesterTransportError("deadline exceeded")
    assert is_retryable_error(err)
    assert mutation_outcome_unknown(err)
