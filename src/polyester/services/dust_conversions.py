from __future__ import annotations

import re
from collections.abc import AsyncIterator

from polyester.codecs.contract_limits import (
    contract_string_length,
    contract_string_pattern,
    contract_uint32_max,
)
from polyester.codecs.decode.dust import (
    created_dust_conversion_from_proto,
    dust_balances_from_proto,
    dust_conversion_from_get_response,
    dust_conversions_page_from_proto,
    dust_quote_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.scalars import UINT32_MAX, exact_integer
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.transfer.v1 import dust_conversion_pb2 as dust_pb2
from polyester.gen.transfer.v1.dust_conversion_connect import DustConversionServiceClient
from polyester.models.dust import (
    DustBalances,
    DustConversion,
    DustConversionsPage,
    DustQuote,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import AccountScope, ScopedSubAccountMixin

# Request limits, from the contract's validation rules.
QUOTE_ID_MIN_LEN, QUOTE_ID_MAX_LEN = contract_string_length(
    dust_pb2.CreateDustConversionRequest, "quote_id"
)
IDEMPOTENCY_KEY_MIN_LEN, IDEMPOTENCY_KEY_MAX_LEN = contract_string_length(
    dust_pb2.CreateDustConversionRequest, "idempotency_key"
)
CONVERSION_ID_MIN_LEN, CONVERSION_ID_MAX_LEN = contract_string_length(
    dust_pb2.GetDustConversionRequest, "conversion_id"
)
_CONVERSION_ID_PATTERN = re.compile(
    contract_string_pattern(dust_pb2.GetDustConversionRequest, "conversion_id")
)
LIST_CONVERSIONS_MAX_LIMIT = contract_uint32_max(dust_pb2.ListDustConversionsRequest, "limit")
_PAGE_TOKEN_MAX_LEN = contract_string_length(dust_pb2.ListDustConversionsRequest, "page_token")[1]


def _bounded_text(value: object, name: str, low: int, high: int) -> str:
    if not isinstance(value, str) or not low <= len(value) <= high:
        raise PolyesterValidationError(f"{name} must be a string of {low} to {high} characters")
    return value


class AsyncDustConversionsService(ScopedSubAccountMixin, BaseService):
    """Dust conversion (``transfer.v1.DustConversionService``): turn Trading
    balances too small to trade into one target asset at index prices, less a
    disclosed fee. One conversion moves every source and credits the payout
    atomically, or moves nothing.

    A balance is dust when no open market accepts an order for it and it is
    worth at most 10 USD; one conversion takes at most 20 balances worth at
    most 200 USD together; an account converts once every 6 hours (refused
    conversions excepted), and each target has a daily limit.

    Every call is signed. Listing balances needs ``READ_BALANCES``; quoting,
    converting and reading conversions need ``CONVERT_DUST``, which no
    existing API-key or sub-account policy includes until its owner adds it.
    No step-up is required. Each call covers one account, resolved as
    ``transfers.list`` resolves it: with neither ``account`` nor
    ``sub_account_id``, the client's default sub-account, else the account the
    key is scoped to.

    Refusals raise :class:`~polyester.errors.PolyesterApiError` with the
    ``transfer.v1`` code: ``ERROR_CODE_DUST_WINDOW_ACTIVE`` and
    ``ERROR_CODE_DUST_DAILY_LIMIT`` mean try later (hours, so they are not
    retryable); ``ERROR_CODE_DUST_BUSY`` is a retryable
    :class:`~polyester.errors.PolyesterRateLimitError`;
    ``ERROR_CODE_DUST_QUOTE_EXPIRED``, ``ERROR_CODE_DUST_PRICE_MOVED``,
    ``ERROR_CODE_DUST_BALANCE_CHANGED``, ``ERROR_CODE_DUST_NOT_ELIGIBLE`` and
    ``ERROR_CODE_DUST_CONVERSION_FAILED`` mean quote again.
    """

    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    def _subaccount(self, account: AccountScope | None, sub_account_id: str | int | None) -> int:
        parsed = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        return 0 if parsed is None else parsed

    async def list_balances(
        self,
        *,
        target_asset_id: int = 0,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> DustBalances:
        """Every nonzero available Trading balance with its eligibility and the
        payout the eligible ones would bring now in ``target_asset_id`` (one of
        the returned ``targets``; 0, the default, means the first). Reserves
        nothing."""
        request = dust_pb2.ListDustBalancesRequest(
            target_asset_id=exact_integer(
                target_asset_id, "target_asset_id", min_value=0, max_value=UINT32_MAX
            ),
            subaccount_id=self._subaccount(account, sub_account_id),
        )
        return await unary_auth_decoded(
            self._transport,
            DustConversionServiceClient,
            lambda client, req: client.list_dust_balances(req),
            request,
            dust_balances_from_proto,
        )

    async def quote(
        self,
        *,
        target_asset_id: int,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> DustQuote:
        """Price the account's dust into ``target_asset_id``, one of
        ``list_balances``'s targets. The quote is valid for 30 seconds and
        reserves nothing; its ``quote_id`` is "" when nothing converts."""
        request = dust_pb2.QuoteDustConversionRequest(
            target_asset_id=exact_integer(
                target_asset_id, "target_asset_id", min_value=1, max_value=UINT32_MAX
            ),
            subaccount_id=self._subaccount(account, sub_account_id),
        )
        return await unary_auth_decoded(
            self._transport,
            DustConversionServiceClient,
            lambda client, req: client.quote_dust_conversion(req),
            request,
            dust_quote_from_proto,
        )

    async def convert(
        self,
        *,
        quote_id: str,
        idempotency_key: str,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> DustConversion:
        """Convert a quote at current index prices. Every source must still be
        the whole balance the quote showed; a payout more than 1% below the
        quote is refused. A quote converts once.

        The conversion is ``"completed"``, or ``"processing"`` when its outcome
        is not known yet: poll ``get`` with its ``conversion_id``.
        Retrying with the same ``idempotency_key`` (sent exactly as given)
        returns the same conversion. The account must be the quote's.
        """
        request = dust_pb2.CreateDustConversionRequest(
            quote_id=_bounded_text(quote_id, "quote_id", QUOTE_ID_MIN_LEN, QUOTE_ID_MAX_LEN),
            idempotency_key=_bounded_text(
                idempotency_key,
                "idempotency_key",
                IDEMPOTENCY_KEY_MIN_LEN,
                IDEMPOTENCY_KEY_MAX_LEN,
            ),
            subaccount_id=self._subaccount(account, sub_account_id),
        )
        return await unary_auth_decoded(
            self._transport,
            DustConversionServiceClient,
            lambda client, req: client.create_dust_conversion(req),
            request,
            created_dust_conversion_from_proto,
        )

    async def get(
        self,
        *,
        conversion_id: str,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> DustConversion:
        """One of the account's conversions, by the ``conversion_id`` it was
        created with (a decimal number)."""
        _bounded_text(conversion_id, "conversion_id", CONVERSION_ID_MIN_LEN, CONVERSION_ID_MAX_LEN)
        if _CONVERSION_ID_PATTERN.fullmatch(conversion_id) is None:
            raise PolyesterValidationError(
                "conversion_id must be the decimal number a conversion was created with"
            )
        request = dust_pb2.GetDustConversionRequest(
            conversion_id=conversion_id,
            subaccount_id=self._subaccount(account, sub_account_id),
        )
        return await unary_auth_decoded(
            self._transport,
            DustConversionServiceClient,
            lambda client, req: client.get_dust_conversion(req),
            request,
            dust_conversion_from_get_response,
        )

    async def list(
        self,
        *,
        limit: int = 0,
        page_token: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> DustConversionsPage:
        """One page of the account's conversions, newest first. ``limit`` is 0
        (the server's 20) to ``LIST_CONVERSIONS_MAX_LIMIT`` (100); pass
        ``next_page_token`` back as ``page_token``."""
        request = dust_pb2.ListDustConversionsRequest(
            limit=exact_integer(limit, "limit", min_value=0, max_value=LIST_CONVERSIONS_MAX_LIMIT),
            page_token=_bounded_text(page_token or "", "page_token", 0, _PAGE_TOKEN_MAX_LEN),
            subaccount_id=self._subaccount(account, sub_account_id),
        )
        return await unary_auth_decoded(
            self._transport,
            DustConversionServiceClient,
            lambda client, req: client.list_dust_conversions(req),
            request,
            dust_conversions_page_from_proto,
        )

    async def iter_conversions(
        self,
        *,
        limit: int = 0,
        page_token: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> AsyncIterator[DustConversion]:
        """Every conversion of the account, newest first, fetching pages as
        needed with the same arguments."""
        requested: set[str] = set()
        token = page_token
        while True:
            if token:
                requested.add(token)
            page = await self.list(
                limit=limit, page_token=token, account=account, sub_account_id=sub_account_id
            )
            for conversion in page.conversions:
                yield conversion
            if not page.next_page_token:
                return
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ListDustConversions", "next_page_token repeats an earlier page token"
                )
            token = page.next_page_token
