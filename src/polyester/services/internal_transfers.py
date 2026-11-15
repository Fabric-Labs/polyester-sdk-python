from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.contract_limits import contract_repeated_items, contract_string_length
from polyester.codecs.decode.internal_transfers import (
    internal_transfer_batch_from_proto,
    internal_transfer_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.scalars import UINT32_MAX, exact_integer, parse_account_id
from polyester.codecs.withdraw import str_to_u128_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.transfer.v1.internal_transfer_connect import InternalTransferServiceClient
from polyester.gen.transfer.v1.internal_transfer_pb2 import (
    BatchCreateInternalTransfersRequest,
    CreateInternalTransferRequest,
    InternalTransferBatchLeg,
)
from polyester.models import (
    InternalTransferBatchResult,
    InternalTransferLeg,
    InternalTransferResult,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.types.money import AssetAmount

# Legs one BatchCreateInternalTransfers request takes, and the length of its
# idempotency key, from the contract's validation rules.
BATCH_MIN_LEGS, BATCH_MAX_LEGS = contract_repeated_items(
    BatchCreateInternalTransfersRequest, "legs"
)
BATCH_IDEMPOTENCY_KEY_MIN_LEN, BATCH_IDEMPOTENCY_KEY_MAX_LEN = contract_string_length(
    BatchCreateInternalTransfersRequest, "idempotency_key"
)


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
        """Submit up to ``BATCH_MAX_LEGS`` (10) Trading to Trading transfers
        authorized by one MFA check (``BatchCreateInternalTransfers``).

        Each leg (an :class:`~polyester.models.InternalTransferLeg`, or a
        mapping of its fields) is checked as ``create`` checks its arguments.
        The server checks every leg before any runs: if one fails, the batch is
        ``"refused"`` and nothing moves. Otherwise legs run in order and
        independently; they are not atomic, so a leg can be refused (for
        example ``"insufficient_funds"``) after earlier legs were accepted.
        Read each leg's ``status``.

        ``idempotency_key`` (1 to 128 characters, sent exactly as given) covers
        the whole batch. Retry with the same key and the same legs in the same
        order: accepted legs answer the same transfers, and legs not yet
        accepted run again. A ``"pending"`` leg's outcome is not known yet:
        retry the batch with the same key to read it. Different legs under the
        key are refused with ``ERROR_CODE_IDEMPOTENCY_CONFLICT``. Each leg counts
        as one internal transfer against the rate limit.
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
        if not BATCH_MIN_LEGS <= len(legs) <= BATCH_MAX_LEGS:
            raise PolyesterValidationError(
                f"batch_create takes {BATCH_MIN_LEGS} to {BATCH_MAX_LEGS} legs; got {len(legs)}"
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
        return await unary_auth_decoded(
            self._transport,
            InternalTransferServiceClient,
            lambda client, req: client.batch_create_internal_transfers(req),
            request,
            lambda msg: internal_transfer_batch_from_proto(msg, leg_count=leg_count),
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


def _leg(raw: object, index: int) -> InternalTransferLeg:
    if isinstance(raw, InternalTransferLeg):
        return raw
    if isinstance(raw, Mapping):
        try:
            return InternalTransferLeg(**raw)
        except TypeError as exc:
            raise PolyesterValidationError(f"legs[{index}]: {exc}") from exc
    raise PolyesterValidationError(f"legs[{index}] must be an InternalTransferLeg")
