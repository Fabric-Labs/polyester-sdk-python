from __future__ import annotations

from typing import TYPE_CHECKING

from polyester._problem import HTTPProblem

if TYPE_CHECKING:
    from polyester.models.trading import OrderFieldViolation

# Stable auth.v1.AuthErrorDetail codes used for MFA control flow.
# Prefer these over ConnectError message text.
AUTH_MFA_NOT_ENROLLED = "AUTH_MFA_NOT_ENROLLED"
AUTH_STEP_UP_REQUIRED = "AUTH_STEP_UP_REQUIRED"
AUTH_MFA_ELEVATION_REQUIRED = "AUTH_MFA_ELEVATION_REQUIRED"
AUTH_MFA_LAST_FACTOR_REQUIRED = "AUTH_MFA_LAST_FACTOR_REQUIRED"
AUTH_INTERNAL_ERROR = "AUTH_INTERNAL_ERROR"
# The account request changed nothing; retry the same request.
AUTH_TEMPORARILY_UNAVAILABLE = "AUTH_TEMPORARILY_UNAVAILABLE"
# A member call targeted the sub-account's owner: the owner cannot be invited,
# re-roled or removed. The request changed nothing.
AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED = "AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED"

# A session-only method refused an account API key (or a session token that
# carries one): call it with an interactive session token.
AUTH_SESSION_KIND_NOT_ALLOWED = "AUTH_SESSION_KIND_NOT_ALLOWED"
# No credentials, or a missing, malformed or expired session token. REST
# names it ``UNAUTHENTICATED``.
AUTH_AUTHENTICATION_REQUIRED = "AUTH_AUTHENTICATION_REQUIRED"
# Why an API key's credentials were refused. ConnectRPC carries them in
# ``auth.v1.AuthErrorDetail``; REST names them without the ``AUTH_`` prefix.
AUTH_SIGNATURE_INVALID = "AUTH_SIGNATURE_INVALID"
AUTH_TIMESTAMP_SKEW = "AUTH_TIMESTAMP_SKEW"
AUTH_MISSING_HEADERS = "AUTH_MISSING_HEADERS"
AUTH_KEY_EXPIRED = "AUTH_KEY_EXPIRED"
AUTH_KEY_DISABLED = "AUTH_KEY_DISABLED"
AUTH_IP_NOT_ALLOWED = "AUTH_IP_NOT_ALLOWED"
AUTH_API_KEY_NOT_ACCEPTED = "AUTH_API_KEY_NOT_ACCEPTED"
# The ``X-API-RECV-WINDOW`` header is not one whole number of milliseconds from
# 1 to 60000, is empty, or is repeated (REST ``RECV_WINDOW_INVALID``, HTTP 401;
# ConnectRPC ``unauthenticated``). The request was not processed, and the same
# header is refused again: fix ``recv_window_ms``.
AUTH_RECV_WINDOW_INVALID = "AUTH_RECV_WINDOW_INVALID"
API_KEY_AUTH_ERROR_CODES = frozenset(
    {
        AUTH_SIGNATURE_INVALID,
        AUTH_TIMESTAMP_SKEW,
        AUTH_MISSING_HEADERS,
        AUTH_KEY_EXPIRED,
        AUTH_KEY_DISABLED,
        AUTH_IP_NOT_ALLOWED,
        AUTH_API_KEY_NOT_ACCEPTED,
        AUTH_RECV_WINDOW_INVALID,
    }
)

# A signed API-key request was refused because the key, or its account, holds
# its full share of the record that keeps signed requests from being replayed
# until their receive windows end (REST ``REPLAY_CAPACITY_EXHAUSTED``, HTTP 429;
# ConnectRPC ``resource_exhausted`` with ``AuthErrorDetail``). It raises
# :class:`PolyesterRateLimitError` with this ``code``, not an authentication
# error: the credentials are valid, the request was not processed, and the
# share frees as earlier windows end. It is retryable. It carries no
# ``Retry-After``, so ``retry_after`` is ``None`` unless the response named
# one: back off briefly and send again, which signs again with a fresh
# timestamp. A shorter ``recv_window_ms`` makes room sooner.
AUTH_REPLAY_CAPACITY_EXHAUSTED = "AUTH_REPLAY_CAPACITY_EXHAUSTED"

# orders.v1.ErrorCode of an order or trigger write whose receive window ended
# before it was sent on for admission (308; REST 400 ``REQUEST_DEADLINE_EXCEEDED``,
# ConnectRPC ``failed_precondition``). It passed authentication, but nothing
# changed and it is never an unknown outcome: it is retryable, and sending it
# again signs it with a fresh timestamp.
REQUEST_DEADLINE_EXCEEDED = "ERROR_CODE_REQUEST_DEADLINE_EXCEEDED"

# A valid signed wallet login named an account address no account uses, and
# the signing wallet is already linked to another account (ConnectRPC
# ``already_exists``, REST 409). Wallets are not moved between accounts and
# nothing changed. Terminal: the same request is refused again. Log in with
# the account address the wallet already uses.
AUTH_WALLET_ALREADY_LINKED = "AUTH_WALLET_ALREADY_LINKED"

# Code of a PolyesterApiError for a request body over the endpoint's size
# limit (REST problem ``REQUEST_TOO_LARGE``, HTTP 413). The API refuses it
# before reading or authenticating the request, so nothing changed, and the
# same body is refused again: reduce it to fit the limit.
REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"

# Gateway code for an API-key request whose signed timestamp is outside the
# allowed skew window.
TIMESTAMP_SKEW = "TIMESTAMP_SKEW"

# orders.v1.ErrorCode of a cancel (or modify) of an order that has already
# ended: filled, expired, canceled, or canceled by an earlier cancel.
ORDER_ALREADY_TERMINAL = "ERROR_CODE_ORDER_ALREADY_TERMINAL"

# Suffix of orders.v1.ErrorDetail codes for a mutation that was sent but not
# confirmed in time (e.g. ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN). The server
# may still have applied it: read back before retrying. Matching the suffix
# covers codes added to the enum later.
_OUTCOME_UNKNOWN_SUFFIX = "_OUTCOME_UNKNOWN"


class PolyesterError(Exception):
    """Base class for all SDK-raised errors."""

    problem: HTTPProblem | None = None


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
    """Raised when public SDK input cannot be converted to wire input.

    For a check the server makes too, ``code`` is the orders error code the
    server answers (for example ``ERROR_CODE_BAD_PRICE``) and ``violations``
    the field violations it returns, so client-side and server-side refusals
    read the same. Both are empty for SDK-only checks.
    """

    def __init__(
        self,
        message: str = "",
        *,
        code: str | None = None,
        violations: list[OrderFieldViolation] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.violations = list(violations or [])


class PolyesterTransportError(PolyesterError):
    """Raised for network, timeout, or transport/runtime failures."""


class PolyesterRedirectError(PolyesterError):
    """Raised when a request signed with an API key is answered with an HTTP redirect.

    The SDK never follows such a redirect: the signature, key ID and timestamp
    would reach the redirect target, which could replay the request within its
    receive window, and the signature covers the path, so even a same-origin
    redirect to another path could not verify.

    ``status_code`` is the redirect status, such as 307 or 308. ``origin`` is
    the scheme, host and port the redirect named, without its path, query or
    userinfo; ``same_origin`` says whether it is the origin the request was
    sent to.

    Nothing was sent to the redirect target. A redirect does not prove that
    the configured ``api_url`` did not apply the request before answering with
    it, so :func:`mutation_outcome_unknown` is true: read a mutation back
    before sending it again. Sending it again gets the same redirect, so
    :func:`is_retryable_error` is false. Set ``api_url`` to the API's own
    origin.
    """

    def __init__(self, *, status_code: int, origin: str, same_origin: bool) -> None:
        self.status_code = status_code
        self.origin = origin
        self.same_origin = same_origin
        where = "within its origin" if same_origin else "to another origin"
        super().__init__(
            f"signed request was redirected (HTTP {status_code}) {where}, {origin}; "
            "the SDK does not follow redirects of signed requests: "
            "set api_url to the API's origin"
        )


class PolyesterCatalogHydrationError(PolyesterError):
    """Raised when a catalog the client loads at startup could not be loaded.

    The client loads two catalogs when it is created: the spot config, which
    every call that names a market by symbol or needs a pair's scales waits
    for, and the funding (deposit/withdraw) config, which only
    ``zipper.subscribe_zipped_asset_supply`` waits for. When a load failed,
    those calls raise this error instead of refusing the symbol, as do
    :meth:`AsyncPolyester.wait_for_catalogs` (spot config) and
    :meth:`AsyncPolyester.wait_for_funding_catalog` (funding config).
    Create a new client to load the catalogs again.

    ``catalog`` is ``"spot"`` or ``"funding"``; ``operation`` the Connect
    procedure that failed, such as
    ``chain.zipper.v1.ZipperService/GetDepositWithdrawConfig``; ``failure``
    one of ``"timeout"``, ``"connection_closed"``, ``"connect_failed"``,
    ``"unavailable"``, ``"invalid"`` (the response did not validate) or
    ``"error"``; ``attempts`` how many times it was read; and
    ``response_ref`` the edge's reference of the last failed response (the
    ``cf-ray`` header), when one arrived. ``__cause__`` is the last failure,
    the one ``catalogs_last_error`` holds for the spot config. The message
    carries no credentials and no proxy URL. Each attribute is ``None`` when
    the error does not come from a catalog load.
    """

    def __init__(
        self,
        message: str = "",
        *,
        catalog: str | None = None,
        operation: str | None = None,
        failure: str | None = None,
        attempts: int | None = None,
        response_ref: str | None = None,
    ) -> None:
        super().__init__(message)
        self.catalog = catalog
        self.operation = operation
        self.failure = failure
        self.attempts = attempts
        self.response_ref = response_ref


class PolyesterResponseContractError(PolyesterError):
    """Raised when a successful mutation response violates its wire contract."""

    def __init__(self, context: str, message: str) -> None:
        super().__init__(f"{context}: {message}")
        self.context = context


class PolyesterRateLimitError(PolyesterTransportError):
    """Raised when the API returns a rate-limit response.

    ``code`` retains a service error name, or is ``None`` when none was supplied.
    Known order codes use their ``ERROR_CODE_`` enum names. An attached orders
    detail with no code uses ``ERROR_CODE_UNSPECIFIED``; a standalone rate-limit
    detail has no service code.

    ``detail`` is the structured ``polyester.ratelimit.v1.RateLimitDetail``
    payload when the server attached it: ConnectRPC details, an in-band order
    rejection, or the ``rate_limit`` object of a REST ``RATE_LIMIT_EXCEEDED``
    problem, whose fields are all optional. The gateway's own refusal names
    only ``reason`` and ``scope`` (``CLIENT_IP``, no ``operation_id``); a
    service's also names the operation, the policy class and the remaining
    quota. ``retry_after`` prefers ``detail.retry_after_ms``, then the
    ``Retry-After`` header; it is ``None`` when the server gave no hint, as for
    a refusal of too many concurrent requests, so back off on your own
    schedule then.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        detail: object | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.detail = detail
        self.code = code


class PolyesterServerError(PolyesterTransportError):
    """Raised for server-side failures and any HTTP error that can't prove a refusal.

    That is a 5xx, or a 4xx other than 401 and 403 with no code the contract
    defines: a gateway or an edge can send those too. ``code`` keeps an
    unrecognised code for diagnosis, and ``status_code`` the HTTP status.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        raw: object | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.raw = raw


class PolyesterTimeoutError(PolyesterTransportError):
    """Raised when a request deadline expires before a response arrives.

    Non-retryable with outcome unknown: a mutation may still have been
    applied, so reconcile before retrying it (see :func:`mutation_outcome_unknown`).
    """


class PolyesterBatchReplaceTimeoutError(PolyesterTimeoutError):
    """Raised when a batch replace has no status, or still has admitted items,
    at the end of its status window or of the caller's timeout.

    The server keeps a batch's status for 60 seconds from acceptance. A
    ``not_found`` status read does not mean an item was refused, so reconcile
    the orders themselves with order reads.
    ``last_status`` is the last status read, or ``None`` when none succeeded.
    """

    def __init__(self, message: str, *, batch_request_id: str, last_status: object | None) -> None:
        super().__init__(message)
        self.batch_request_id = batch_request_id
        self.last_status = last_status


class PolyesterTimestampSkewError(PolyesterTransportError):
    """Raised when the API-key request timestamp is outside the allowed skew window.

    Retryable: the gateway rejected the request before any service saw it,
    and a retry signs it again with a fresh timestamp. If it persists, the
    local clock is wrong. For large bursts, bound concurrency so requests do
    not wait locally past the skew window.
    """

    code = TIMESTAMP_SKEW

    def __init__(
        self,
        message: str = "API key timestamp is outside the allowed skew window.",
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class PolyesterApiError(PolyesterError):
    """Raised for structured Connect/API errors.

    ``existing_order_id`` is set on an ``ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID``
    order rejection: the public ID of the order that already holds the client
    order ID, when the server knows it.

    ``violations`` names the request fields to fix: the field violations of an
    ``orders.v1.ErrorDetail``, or the ``violations`` of a REST problem body.
    ConnectRPC names request fields by their proto names
    (``order.base_qty_scaled``), REST by the REST request fields
    (``order.baseQty``). Branch on ``code``, then on each ``rule_id``.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        metadata: dict[str, str] | None = None,
        raw: object | None = None,
        existing_order_id: str | None = None,
        violations: list[OrderFieldViolation] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}
        self.raw = raw
        self.existing_order_id = existing_order_id
        self.violations = list(violations or [])


class PolyesterSubaccountOwnerRoleLockedError(PolyesterApiError):
    """Raised when a sub-account member call targets the sub-account's owner.

    Inviting the owner, accepting an invite whose grantee is the owner,
    changing the owner's role and removing the owner are refused with
    ``AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED`` (Connect ``failed_precondition``,
    REST HTTP 412). The request changed nothing; it is not retryable. Show
    "The owner's role can't be changed", and don't offer these actions for
    the member whose role is ``OWNER``.
    """

    def __init__(
        self,
        message: str = "The sub-account owner's role can't be changed.",
        *,
        status_code: int | None = None,
        raw: object | None = None,
    ) -> None:
        super().__init__(message, code=AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED, raw=raw)
        self.status_code = status_code


class PolyesterSessionRequiredError(PolyesterAuthError, PolyesterApiError):
    """Raised when a session-only method is called with an account API key.

    Every method that accepts only a session token answers an API key (or a
    session token that carries one) with ``AUTH_SESSION_KIND_NOT_ALLOWED``:
    Connect ``permission_denied`` with an ``auth.v1.AuthErrorDetail``, REST
    HTTP 403 with that problem ``code``. Withdrawals, auto-withdraw rules and
    portfolio equity reads included. Call the method with an interactive
    session token instead; not retryable.

    It is both a :class:`PolyesterAuthError` and a :class:`PolyesterApiError`,
    the two errors these refusals raised before, so existing handlers keep
    catching it.
    """

    def __init__(
        self,
        message: str = "interactive session required",
        *,
        status_code: int | None = None,
        raw: object | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, code=AUTH_SESSION_KIND_NOT_ALLOWED)
        self.raw = raw


# REST problem codes that differ from their AuthErrorCode by more than the
# ``AUTH_`` prefix.
_REST_AUTH_CODE_ALIASES = {"UNAUTHENTICATED": AUTH_AUTHENTICATION_REQUIRED}


def auth_error_code_from_rest(code: str | None) -> str | None:
    """Map a REST problem ``code`` to its ``auth.v1.AuthErrorCode`` name.

    ``SIGNATURE_INVALID`` becomes ``AUTH_SIGNATURE_INVALID`` and
    ``UNAUTHENTICATED`` becomes ``AUTH_AUTHENTICATION_REQUIRED``; an
    ``AUTH_``-prefixed code stays as is. ``None`` for a code that is not an
    auth error code this SDK knows.
    """
    if not code:
        return None
    if code in _REST_AUTH_CODE_ALIASES:
        return _REST_AUTH_CODE_ALIASES[code]
    from polyester.gen.auth.v1 import auth_pb2

    name = code if code.startswith("AUTH_") else f"AUTH_{code}"
    if name == "AUTH_UNSPECIFIED" or name not in auth_pb2.AuthErrorCode.DESCRIPTOR.values_by_name:
        return None
    return name


def auth_error_code(err: BaseException) -> str | None:
    """Return the ``auth.v1.AuthErrorCode`` name of an error, or ``None``.

    Reads the ``AuthErrorDetail`` of a ConnectRPC error and the ``code`` of a
    REST problem body the same way, so one check covers both transports:
    ``AUTH_SIGNATURE_INVALID``, ``AUTH_TIMESTAMP_SKEW``, ``AUTH_IP_NOT_ALLOWED``,
    ``AUTH_SESSION_KIND_NOT_ALLOWED`` and so on. A REST ``UNAUTHENTICATED``
    reads ``AUTH_AUTHENTICATION_REQUIRED``. ``None`` for an error that carries
    no auth code, such as an orders error.
    """
    if isinstance(err, PolyesterTimestampSkewError):
        return AUTH_TIMESTAMP_SKEW
    if isinstance(err, (PolyesterApiError, PolyesterAuthError)) and err.code:
        return auth_error_code_from_rest(err.code)
    if isinstance(err, PolyesterRateLimitError) and (err.code or "").startswith("AUTH_"):
        return err.code
    return None


def is_session_required(err: BaseException) -> bool:
    """True when a session-only method refused an API key
    (``AUTH_SESSION_KIND_NOT_ALLOWED``); see :class:`PolyesterSessionRequiredError`."""
    return auth_error_code(err) == AUTH_SESSION_KIND_NOT_ALLOWED


def is_wallet_already_linked(err: BaseException) -> bool:
    """True when a wallet login was refused because the wallet is already
    linked to another account (``AUTH_WALLET_ALREADY_LINKED``). It is terminal:
    log in with the account address the wallet already uses."""
    return auth_error_code(err) == AUTH_WALLET_ALREADY_LINKED


def is_recv_window_invalid(err: BaseException) -> bool:
    """True when the request's ``X-API-RECV-WINDOW`` header was refused
    (``AUTH_RECV_WINDOW_INVALID``). Not retryable without fixing the window."""
    return auth_error_code(err) == AUTH_RECV_WINDOW_INVALID


def is_replay_capacity_exhausted(err: BaseException) -> bool:
    """True when the API key's or account's share of the replay record is full
    (``AUTH_REPLAY_CAPACITY_EXHAUSTED``). Retryable after a short backoff."""
    return auth_error_code(err) == AUTH_REPLAY_CAPACITY_EXHAUSTED


def is_request_deadline_exceeded(err: BaseException) -> bool:
    """True when a write's receive window ended before admission
    (``ERROR_CODE_REQUEST_DEADLINE_EXCEEDED``). Nothing changed; retryable."""
    return isinstance(err, PolyesterApiError) and err.code == REQUEST_DEADLINE_EXCEEDED


def is_request_too_large(err: BaseException) -> bool:
    """True when a request body over the endpoint's size limit was refused
    (``REQUEST_TOO_LARGE``, HTTP 413). Nothing changed; reduce the body."""
    return isinstance(err, PolyesterApiError) and err.code == REQUEST_TOO_LARGE


def is_order_already_terminal(err: BaseException) -> bool:
    """True when a cancel (or modify) named an order that has already ended.

    A cancel is refused ``ERROR_CODE_ORDER_ALREADY_TERMINAL`` once its order
    has ended, by this cancel or otherwise (filled, expired, canceled),
    including a repeat of the cancel that ended it. Treat it as "already
    done" and read the order for how it ended.
    """
    return isinstance(err, PolyesterApiError) and err.code == ORDER_ALREADY_TERMINAL


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


class PolyesterNotImplementedError(PolyesterApiError):
    """Raised for Connect ``unimplemented`` or a contract code at HTTP 501: the
    server does not offer this RPC or feature. Not retryable."""

    def __init__(self, message: str, *, code: str | None = "unimplemented") -> None:
        super().__init__(message, code=code)


class PolyesterRouteNotFoundError(PolyesterNotImplementedError):
    """Raised when the gateway has no route for a Connect RPC (plain HTTP 404).

    Outcome unknown: whatever answered isn't the service, so it can't prove that
    a mutation wasn't applied. Not retryable.
    """

    def __init__(self, procedure: str | None = None) -> None:
        hint = (
            f"RPC not exposed on this API host{f': {procedure}' if procedure else ''}. "
            "The procedure may be unimplemented on devnet or disabled in this environment."
        )
        super().__init__(hint, code="route_not_found")
        self.procedure = procedure


def is_not_found(err: BaseException) -> bool:
    """Return whether an API error means the requested resource is absent.

    Gateway route 404s are intentionally excluded: an unavailable RPC is not a
    successful idempotent delete/cancel.
    """
    if not isinstance(err, PolyesterApiError) or isinstance(err, PolyesterRouteNotFoundError):
        return False
    code = str(err.code or "").strip().lower().replace("-", "_")
    return code == "not_found" or code.endswith("_not_found")


class PolyesterRealtimeError(PolyesterError):
    """Raised for realtime connection, subscription, or decode failures.

    ``code`` is the private WebSocket request error code (for example
    ``FORBIDDEN``); ``close_code`` is the WebSocket close code that ended the
    stream (for example ``4403``). Both are ``None`` when not applicable.
    """

    def __init__(
        self,
        message: str = "",
        *,
        code: str | None = None,
        close_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.close_code = close_code


class PolyesterRealtimeOverflowError(PolyesterRealtimeError):
    """Raised when a realtime subscription queue is full.

    Subscriptions fail instead of silently dropping updates so callers can
    recover (reconnect, resubscribe, or slow their consumer).
    """


class PolyesterSubscriptionEndedError(PolyesterRealtimeError):
    """The server ended a realtime subscription and the SDK stopped.

    ``channel`` names it; ``unsubscribe_code`` and ``server_reason`` are the
    server's code and text. ``reason`` says why it did not resume:

    - ``not_resubscribable``: no sub-account's access governs the channel, or
      automatic reconnection is off. Subscribe again if it should still be live.
    - ``access_removed``: a sub-account update on this client said removed true.
    - ``not_listed``: ``ListSubaccounts`` no longer lists it with a role.
    - ``list_refused``: ``ListSubaccounts`` refused this key; ``__cause__`` holds it.
    - ``token_refused``: a fresh subscribe token was refused; ``__cause__`` holds it.
    - ``retries_exhausted``: bounded attempts did not hold; ``__cause__`` holds
      the last failure, if any.
    """

    def __init__(
        self,
        *,
        channel: str,
        unsubscribe_code: int,
        server_reason: str,
        reason: str,
        cause: BaseException | None = None,
    ) -> None:
        message = (
            f"server ended realtime subscription to {channel!r} "
            f"(code {unsubscribe_code}: {server_reason}): {reason}"
        )
        if cause is not None:
            message = f"{message}: {cause}"
        super().__init__(message)
        self.channel = channel
        self.unsubscribe_code = unsubscribe_code
        self.server_reason = server_reason
        self.reason = reason
        self.__cause__ = cause


def _is_outcome_unknown_api_error(err: BaseException) -> bool:
    return (
        isinstance(err, PolyesterApiError)
        and err.code is not None
        and err.code.endswith(_OUTCOME_UNKNOWN_SUFFIX)
    )


def is_retryable_error(err: BaseException) -> bool:
    """True only when retrying may succeed and the mutation outcome is known.

    Unknown outcomes, including client timeouts and bare server/transport
    failures, always return False. Read back before sending a mutation again.
    Safe reads may retry explicitly from read context. A client order ID
    enables reconciliation, not exact replay of a single create.
    """
    if mutation_outcome_unknown(err):
        return False
    if isinstance(err, PolyesterApiError) and err.code in (
        AUTH_TEMPORARILY_UNAVAILABLE,
        "ERROR_CODE_ACCOUNT_REPAIRING",
        REQUEST_DEADLINE_EXCEEDED,
    ):
        return True
    return isinstance(
        err,
        (PolyesterTransportError, PolyesterRateLimitError, PolyesterServerError),
    )


def mutation_outcome_unknown(err: BaseException) -> bool:
    """Return whether the server may have applied a failed mutation.

    True for ambiguous transport and server errors (excluding known admission
    refusals, rate limits and timestamp skew), for any HTTP error with no
    recognised code except a 401 or 403, for a bare 404, for a malformed success
    response, for a refused redirect (:class:`PolyesterRedirectError`: the
    origin that answered with it may have applied the request), and for an
    order or trigger create, cancel, modify or control that was sent but not
    confirmed in time (``ERROR_CODE_*_OUTCOME_UNKNOWN``). Read the order or
    trigger back before retrying.
    """
    return (
        isinstance(
            err,
            (PolyesterResponseContractError, PolyesterRouteNotFoundError, PolyesterRedirectError),
        )
        or _is_outcome_unknown_api_error(err)
        or (
            isinstance(err, (PolyesterTransportError, PolyesterServerError))
            and not isinstance(err, (PolyesterRateLimitError, PolyesterTimestampSkewError))
            and not (
                isinstance(err, PolyesterServerError)
                and err.status_code == 503
                and (
                    _is_known_admission_refusal(err.code)
                    or (
                        err.code == "ERROR_CODE_UNAVAILABLE"
                        and getattr(getattr(err.raw, "DESCRIPTOR", None), "full_name", None)
                        == "orders.v1.ErrorDetail"
                    )
                )
            )
        )
    )


# Explicit orders.v1 admission refusals, not arbitrary 5xx responses.
def _is_known_admission_refusal(code: str | None) -> bool:
    return bool(code) and str(code).removeprefix("ERROR_CODE_") in {
        "FEE_SCHEDULE_UNAVAILABLE",
        "POLICY_UNAVAILABLE",
        "RATE_LIMIT_POLICY_UNAVAILABLE",
        "PAIR_BACKLOGGED",
        "SETTLEMENT_BACKLOGGED",
        "ORDER_MODIFY_IN_PROGRESS",
        "ORDER_PLACEMENT_PENDING",
        "TRIGGER_CONTROLS_BUSY",
        "TRIGGER_CONTROL_IN_PROGRESS",
        "QUICKSWAP_ACCOUNT_OWNER_UNKNOWN",
    }
