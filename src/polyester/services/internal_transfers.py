from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.contract_limits import (
    contract_repeated_items_min,
    contract_string_length,
    contract_string_pattern,
)
from polyester.codecs.decode.internal_transfers import (
    internal_transfer_batch_from_proto,
    internal_transfer_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.proto_helpers import error_code_name
from polyester.codecs.scalars import UINT32_MAX, exact_integer, parse_account_id
from polyester.codecs.withdraw import str_to_u128_proto
from polyester.errors import (
    PolyesterError,
    PolyesterServerError,
    PolyesterValidationError,
)
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from polyester.gen.transfer.v1.internal_transfer_connect import InternalTransferServiceClient
from polyester.gen.transfer.v1.internal_transfer_pb2 import (
    BatchCreateInternalTransfersRequest,
    CreateInternalTransferRequest,
    GetInternalTransferBatchRequest,
    InternalTransferBatchLeg,
)
from polyester.models import (
    InternalTransferBatchResult,
    InternalTransferLeg,
    InternalTransferResult,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._poll import poll_until_final
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.types.money import AssetAmount

# The fewest legs one BatchCreateInternalTransfers request takes, the length
# of its idempotency key, and the form of a batch request ID, from the
# contract's validation rules. The contract sets no rule on the most legs: the
# server refuses a batch over its documented limits.
BATCH_MIN_LEGS = contract_repeated_items_min(BatchCreateInternalTransfersRequest, "legs")
BATCH_IDEMPOTENCY_KEY_MIN_LEN, BATCH_IDEMPOTENCY_KEY_MAX_LEN = contract_string_length(
    BatchCreateInternalTransfersRequest, "idempotency_key"
)
BATCH_REQUEST_ID_MIN_LEN, BATCH_REQUEST_ID_MAX_LEN = contract_string_length(
    GetInternalTransferBatchRequest, "request_id"
)
_BATCH_REQUEST_ID_PATTERN = re.compile(
    contract_string_pattern(GetInternalTransferBatchRequest, "request_id")
)
# Codes a batch answers, with unavailable (HTTP 503), when a service its
# checks depend on is briefly unavailable; nothing was recorded.
_BATCH_PRE_ADMISSION_CODES = frozenset({"SERVICE_UNAVAILABLE", "ACCOUNT_SHARD_UNAVAILABLE"})


def _is_pre_admission_refusal(err: PolyesterError) -> bool:
    """Whether a batch failure is a documented pre-admission refusal: a
    :class:`PolyesterServerError` from an actual HTTP 503 that is either a
    ConnectRPC error whose body names ``unavailable`` itself and carries
    exactly one detail, a ``transfer.v1.ErrorDetail`` with one of its codes,
    or the contract's REST problem for one, served under one
    ``application/problem+json`` field and declaring that code's ``type``.
    A body naming a member twice, a code read from the status, another or an
    extra detail entry (one that cannot be decoded included), a 502 or 504,
    another media type, generic JSON or a code only in a diagnostic field
    is not."""
    if not isinstance(err, PolyesterServerError):
        return False
    if err.status_code != 503 or err._evidence_ambiguous:
        return False
    details = err._connect_details
    if details:
        # The typed proof: the body itself names unavailable (never read from
        # the status), and its one detail is a transfer refusal of an
        # admission code. Any other or extra detail proves nothing.
        # Exactly one entry as sent, not one that survived decoding.
        if (
            err._wire_connect_code != "unavailable"
            or err._raw_detail_count != 1
            or len(details) != 1
        ):
            return False
        detail = details[0]
        detail_type = getattr(getattr(detail, "DESCRIPTOR", None), "full_name", None)
        if detail_type != "transfer.v1.ErrorDetail":
            return False
        code = int(getattr(detail, "code", 0))
        name = error_code_name(transfer_pb2.ErrorCode, code).removeprefix("ERROR_CODE_")
        return name in _BATCH_PRE_ADMISSION_CODES
    problem = err.problem
    return (
        problem is not None
        and problem.media_type == "application/problem+json"
        and problem.code in _BATCH_PRE_ADMISSION_CODES
        and problem.declared_type == problem.type
    )
_BATCH_POLL_INITIAL = 0.25
_BATCH_POLL_MAX = 2.0


class AsyncInternalTransfersService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager,
        default_sub_account_id: str | None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id

    async def create(
        self,
        *,
        asset_id: int,
        quantity: str | AssetAmount,
        idempotency_key: str,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        destination_account_id: str | int | None = None,
        destination_subaccount_id: str | int | None = None,
        destination_smart_account_address: str | None = None,
        quantity_scale: int | None = None,
    ) -> InternalTransferResult:
        request = CreateInternalTransferRequest()
        self._fill_transfer(
            request,
            asset_id=asset_id,
            quantity=quantity,
            quantity_scale=quantity_scale,
            account=account,
            sub_account_id=sub_account_id,
            destination_account_id=destination_account_id,
            destination_subaccount_id=destination_subaccount_id,
            destination_smart_account_address=destination_smart_account_address,
            label="create",
        )
        if not idempotency_key.strip():
            raise PolyesterValidationError(
                "create requires a non-empty idempotency_key reused across retries"
            )
        request.idempotency_key = idempotency_key
        return await unary_auth_decoded(
            self._transport,
            InternalTransferServiceClient,
            lambda client, req: client.create_internal_transfer(req),
            request,
            internal_transfer_from_proto,
        )

    async def batch_create(
        self,
        *,
        legs: Sequence[InternalTransferLeg | Mapping[str, Any]],
        idempotency_key: str,
    ) -> InternalTransferBatchResult:
        """Move Trading to Trading transfers together, authorized by one MFA
        check (``BatchCreateInternalTransfers``): every leg is credited, or
        none moves.

        Each leg (an :class:`~polyester.models.InternalTransferLeg`, or a
        mapping of its fields) is checked as ``create`` checks its arguments.
        The server takes at most 500 legs debiting at most 50 distinct source
        account and asset pairs from at most 10 source accounts, each source,
        destination and asset combination once; it refuses a larger batch
        (``ERROR_CODE_BATCH_TOO_MANY_SOURCES`` for too many source accounts).

        The result's ``status`` is ``"accepted"`` (every leg credited),
        ``"refused"`` (nothing moved, and nothing will under this key; the legs
        that caused it carry ``error_code``) or ``"processing"`` (the outcome
        is not known yet and the batch completes on its own: follow it with
        :meth:`wait_batch` or :meth:`get_batch` by its ``request_id``).

        ``idempotency_key`` (1 to 128 characters, sent exactly as given) covers
        the whole batch. A retry with the same key and the same legs in the
        same order returns the batch's current state; different legs under the
        key are refused with ``ERROR_CODE_IDEMPOTENCY_CONFLICT``. A refused
        batch is final for its key: submit a new batch under a new key. When a
        service the checks depend on is briefly unavailable, the request
        raises a retryable :class:`~polyester.errors.PolyesterServerError`
        (``ERROR_CODE_SERVICE_UNAVAILABLE`` or
        ``ERROR_CODE_ACCOUNT_SHARD_UNAVAILABLE``, HTTP 503) and records
        nothing: send the same key and legs again after its ``retry_after``. A
        ``RATE_LIMIT_EXCEEDED`` refusal without a retry delay means the batch
        outweighs the account's burst: split it instead of retrying.
        """
        if not isinstance(idempotency_key, str) or not (
            BATCH_IDEMPOTENCY_KEY_MIN_LEN <= len(idempotency_key) <= BATCH_IDEMPOTENCY_KEY_MAX_LEN
        ):
            raise PolyesterValidationError(
                f"batch_create requires an idempotency_key of {BATCH_IDEMPOTENCY_KEY_MIN_LEN} "
                f"to {BATCH_IDEMPOTENCY_KEY_MAX_LEN} characters reused across retries"
            )
        if isinstance(legs, str | bytes | Mapping) or not isinstance(legs, Sequence):
            raise PolyesterValidationError("legs must be a sequence of InternalTransferLeg")
        if len(legs) < BATCH_MIN_LEGS:
            raise PolyesterValidationError(
                f"batch_create takes at least {BATCH_MIN_LEGS} leg; got {len(legs)}"
            )
        request = BatchCreateInternalTransfersRequest(idempotency_key=idempotency_key)
        for index, raw in enumerate(legs):
            leg = _leg(raw, index)
            self._fill_transfer(
                request.legs.add(),
                asset_id=leg.asset_id,
                quantity=leg.quantity,
                quantity_scale=leg.quantity_scale,
                account=leg.account,  # type: ignore[arg-type]
                sub_account_id=leg.sub_account_id,
                destination_account_id=leg.destination_account_id,
                destination_subaccount_id=leg.destination_subaccount_id,
                destination_smart_account_address=leg.destination_smart_account_address,
                label=f"legs[{index}]",
            )
        leg_count = len(request.legs)
        try:
            return await unary_auth_decoded(
                self._transport,
                InternalTransferServiceClient,
                lambda client, req: client.batch_create_internal_transfers(req),
                request,
                lambda msg: internal_transfer_batch_from_proto(msg, leg_count=leg_count),
            )
        except PolyesterError as exc:
            # Only the refusals the contract documents as the batch's checks
            # being briefly undecidable are safe to send again under the same
            # key: nothing was recorded. Any other 5xx of the batch may have
            # moved funds, whatever error it maps to (a rate limit or a
            # retryable refusal included). A 4xx keeps its own meaning: a
            # genuine 429 throttle stays retryable.
            if exc.status_code is not None and exc.status_code >= 500:
                exc._outcome_known = _is_pre_admission_refusal(exc)
            raise

    async def get_batch(self, *, request_id: str) -> InternalTransferBatchResult:
        """A batch's current outcome and the state of every leg, by the
        ``request_id`` :meth:`batch_create` returned
        (``GetInternalTransferBatch``), answered as the batch was answered.

        It neither submits nor retries the batch and needs no fresh MFA. The
        caller must be allowed to read the transfers of every source account
        of the batch. ``request_id`` is the decimal string the batch carries:
        1 to 39 ASCII digits without a leading zero.
        """
        checked = _batch_request_id(request_id)
        return await unary_auth_decoded(
            self._transport,
            InternalTransferServiceClient,
            lambda client, req: client.get_internal_transfer_batch(req),
            GetInternalTransferBatchRequest(request_id=checked),
            lambda msg: internal_transfer_batch_from_proto(
                msg, request_id=checked, operation="GetInternalTransferBatch"
            ),
        )

    async def wait_batch(
        self, *, request_id: str, timeout: float | None = None
    ) -> InternalTransferBatchResult:
        """Read the batch with :meth:`get_batch` until it is no longer
        ``"processing"``, and return it: ``"accepted"`` or ``"refused"``.

        Reads start 250 ms apart and back off to 2 s. Errors are raised as
        they come. After ``timeout`` seconds (``None`` waits for as long as
        the batch processes), :class:`~polyester.errors.PolyesterTimeoutError`
        is raised: the batch still completes on its own, so read it again
        later. The timeout bounds each read and wait: a read still in flight
        at the deadline is cancelled, and none is returned after it.
        Cancelling the call cancels the wait.
        """
        checked = _batch_request_id(request_id)
        return await poll_until_final(
            lambda: self.get_batch(request_id=checked),
            lambda batch: batch.status != "processing",
            timeout=timeout,
            initial=_BATCH_POLL_INITIAL,
            maximum=_BATCH_POLL_MAX,
            expired=lambda _last: (
                f"internal transfer batch {checked} is still processing; "
                "it completes on its own, so read it again later"
            ),
        )

    def _fill_transfer(
        self,
        target: CreateInternalTransferRequest | InternalTransferBatchLeg,
        *,
        asset_id: int,
        quantity: str | Decimal | AssetAmount,
        quantity_scale: int | None,
        account: AccountScope | None,
        sub_account_id: str | int | None,
        destination_account_id: str | int | None,
        destination_subaccount_id: str | int | None,
        destination_smart_account_address: str | None,
        label: str,
    ) -> None:
        """Set one transfer's asset, exact amount, source and destination."""
        destination_address = (
            "" if destination_smart_account_address is None else destination_smart_account_address
        )
        has_destination_address = bool(destination_address.strip())
        destination_count = sum(
            (
                destination_account_id is not None,
                destination_subaccount_id is not None,
                has_destination_address,
            )
        )
        if destination_count != 1:
            raise PolyesterValidationError(
                f"{label} requires exactly one of destination_account_id, "
                "destination_subaccount_id, or destination_smart_account_address"
            )
        asset_id = exact_integer(asset_id, "asset_id", min_value=1, max_value=UINT32_MAX)
        target.asset_id = asset_id
        target.amount_e18.CopyFrom(
            str_to_u128_proto(quantity, scale=quantity_scale, asset_id=asset_id)  # type: ignore[arg-type]
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            target.subaccount_id = parsed_sub
        if destination_account_id is not None:
            target.destination_account_id = parse_account_id(
                destination_account_id, "destination_account_id"
            )
        if destination_subaccount_id is not None:
            target.destination_subaccount_id = parse_account_id(
                destination_subaccount_id, "destination_subaccount_id"
            )
        if has_destination_address:
            target.destination_smart_account_address = destination_address


def _batch_request_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not BATCH_REQUEST_ID_MIN_LEN <= len(value) <= BATCH_REQUEST_ID_MAX_LEN
        or _BATCH_REQUEST_ID_PATTERN.fullmatch(value) is None
    ):
        raise PolyesterValidationError(
            f"request_id must be {BATCH_REQUEST_ID_MIN_LEN} to {BATCH_REQUEST_ID_MAX_LEN} "
            "ASCII digits without a leading zero, as batch_create returned it"
        )
    return value


def _leg(raw: object, index: int) -> InternalTransferLeg:
    if isinstance(raw, InternalTransferLeg):
        return raw
    if isinstance(raw, Mapping):
        try:
            return InternalTransferLeg(**raw)
        except TypeError as exc:
            raise PolyesterValidationError(f"legs[{index}]: {exc}") from exc
    raise PolyesterValidationError(f"legs[{index}] must be an InternalTransferLeg")
