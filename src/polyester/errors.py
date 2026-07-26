from __future__ import annotations

# Stable auth.v1.AuthErrorDetail codes used for MFA control flow.
# Prefer these over ConnectError message text.
AUTH_MFA_NOT_ENROLLED = "AUTH_MFA_NOT_ENROLLED"
AUTH_STEP_UP_REQUIRED = "AUTH_STEP_UP_REQUIRED"
AUTH_MFA_ELEVATION_REQUIRED = "AUTH_MFA_ELEVATION_REQUIRED"
AUTH_MFA_LAST_FACTOR_REQUIRED = "AUTH_MFA_LAST_FACTOR_REQUIRED"


class PolyesterError(Exception):
    """Base class for all SDK-raised errors."""


class PolyesterAuthError(PolyesterError):
    """Raised when credentials are missing or rejected."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        label: str | None = None,
        body: str | None = None,
        code: str | None = None,
        context: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.label = label
        self.body = body
        self.code = code
        self.context = context or label
        self.endpoint = endpoint


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


def auth_error_code(err: BaseException) -> str | None:
    """Return the structured auth.v1.AuthErrorDetail code when present."""
    if isinstance(err, PolyesterApiError) and err.code:
        return err.code
    return None


def is_mfa_enrollment_required(err: BaseException) -> bool:
    """True when the caller must enroll an MFA factor before continuing."""
    return auth_error_code(err) == AUTH_MFA_NOT_ENROLLED


def is_step_up_required(err: BaseException) -> bool:
    """True when the caller must retry with a fresh X-Auth-Step-Up proof."""
    return auth_error_code(err) == AUTH_STEP_UP_REQUIRED


def is_mfa_elevation_required(err: BaseException) -> bool:
    """True when the caller needs a recent MFA-elevated interactive session."""
    return auth_error_code(err) == AUTH_MFA_ELEVATION_REQUIRED


def is_mfa_last_factor_required(err: BaseException) -> bool:
    """True when the final active MFA factor cannot be removed."""
    return auth_error_code(err) == AUTH_MFA_LAST_FACTOR_REQUIRED


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
