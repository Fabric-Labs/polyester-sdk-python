class PolyesterError(Exception):
    """Base class for all SDK-raised errors."""


class PolyesterAuthError(PolyesterError):
    """Raised when credentials are missing or rejected."""


class PolyesterValidationError(PolyesterError):
    """Raised when public SDK input cannot be converted to wire input."""


class PolyesterTransportError(PolyesterError):
    """Raised for network, timeout, or transport/runtime failures."""


class PolyesterRateLimitError(PolyesterTransportError):
    """Raised when the API returns a rate-limit response."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PolyesterServerError(PolyesterTransportError):
    """Raised for server-side 5xx failures."""


class PolyesterApiError(PolyesterError):
    """Raised for structured Connect/API errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        metadata: dict[str, str] | None = None,
        raw: object | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}
        self.raw = raw


class PolyesterRouteNotFoundError(PolyesterApiError):
    """Raised when the gateway has no route for a Connect RPC (plain HTTP 404)."""

    def __init__(self, procedure: str | None = None) -> None:
        hint = (
            f"RPC not exposed on this API host{f': {procedure}' if procedure else ''}. "
            "The procedure may be unimplemented on devnet or disabled in this environment."
        )
        super().__init__(hint, code="route_not_found")
        self.procedure = procedure


class PolyesterRealtimeError(PolyesterError):
    """Raised for realtime connection, subscription, or decode failures."""


class PolyesterRealtimeOverflowError(PolyesterRealtimeError):
    """Raised when a realtime subscription queue is full.

    Subscriptions fail instead of silently dropping updates so callers can
    recover (reconnect, resubscribe, or slow their consumer).
    """
