"""Public contract 1945423c: exact balance history, account flow reads, batch
internal transfers, dust conversion, statement export files, suspended
withdrawal routes, ladder refusal causes and social link cooldowns."""

from __future__ import annotations

import base64
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester, Polyester
from polyester.codecs.decode.balances import balance_history_from_proto
from polyester.codecs.decode.lifecycle import flow_summary_from_proto
from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
from polyester.codecs.scalars import format_id
from polyester.codecs.wire_decode import decode_balance_history
from polyester.errors import (
    AUTH_SOCIAL_CHANGE_LIMIT_REACHED,
    DESTINATION_SWAP_DEPOSIT_ADDRESS,
    ROUTE_SUSPENDED,
    PolyesterApiError,
    PolyesterRateLimitError,
    PolyesterResponseContractError,
    PolyesterValidationError,
    PolyesterWithdrawError,
    is_destination_swap_deposit_address,
    is_retryable_error,
    is_route_suspended,
    mutation_outcome_unknown,
)
from polyester.gen.auth.v1 import auth_pb2, policies_pb2, subaccounts_pb2
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2 as lr
from polyester.gen.chain.lifecycle.v1 import types_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.read.v1 import statement_export_pb2 as export_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.transfer.v1 import dust_conversion_pb2 as dust_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as it_pb2
from polyester.models import InternalTransferLeg
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()
SUB = 9_000_000_001
E18 = 10**18


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


def _u128(value: int) -> u128_pb2.U128:
    return u128_pb2.U128(hi=value >> 64, lo=value & ((1 << 64) - 1))


Answer = Callable[[ParsedRequest], HttpScript]


@asynccontextmanager
async def _client(answer: Answer, *, default_sub_account_id: str | None = None):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return answer(req)

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
        default_sub_account_id=default_sub_account_id,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


def _ok(message: Message) -> Answer:
    return lambda _req: connect_proto_response(message.SerializeToString())


def _connect_error(connect_code: str, detail_type: str, detail: Message, status: int) -> Answer:
    value = base64.b64encode(detail.SerializeToString()).decode()
    body = {
        "code": connect_code,
        "message": "refused",
        "details": [{"type": detail_type, "value": value}],
    }
    return lambda _req: HttpScript.json(status, body)


def _problem(status: int, body: dict[str, Any]) -> Answer:
    return lambda _req: HttpScript.json(status, body)


async def _raised(answer: Answer, call: Callable[[AsyncPolyester], Any]) -> BaseException:
    async with _client(answer) as (client, _requests):
        with pytest.raises(BaseException) as raised:
            await call(client)
    return raised.value


# --- exact balance history -----------------------------------------------------------------------


def _history(*balances: u128_pb2.U128, points: int) -> ledger_read_pb2.GetBalanceHistoryResponse:
    return ledger_read_pb2.GetBalanceHistoryResponse(
        range=ledger_read_pb2.DAY_7,
        points=points,
        series=[ledger_read_pb2.BalanceSeries(asset_id=7, balance=list(balances))],
    )


def test_balance_history_reads_exact_18_decimal_balances_above_the_old_limit() -> None:
    big = 1_844_674_407_370_955_161_549_999_999_999_999  # > 2**64 at 1e18, > old 1e7 cap
    result = balance_history_from_proto(_history(_u128(big), _u128(E18 // 2), points=2))
    first, second = result.series[0].balance
    assert first.scaled == big
    assert first.as_decimal() == Decimal("1844674407370955.161549999999999999")
    assert second.as_decimal() == Decimal("0.5")
    assert (first.scale, first.domain.value, first.asset_id) == (18, "ledger_e18", 7)
    assert not hasattr(result.series[0], "balance_q")


@pytest.mark.parametrize("points", [0, 1, 3])
def test_balance_history_refuses_a_series_not_aligned_with_its_points(points: int) -> None:
    # An older server's balance_q decodes as an empty balance list: refused, not
    # shown as a history without balances.
    with pytest.raises(PolyesterResponseContractError, match="balances"):
        balance_history_from_proto(_history(_u128(1), _u128(2), points=points))


def test_balance_history_json_decodes_exact_u128_and_checks_points() -> None:
    data = {
        "range": "DAY_1",
        "points": 2,
        "series": [{"assetId": 3, "balance": [{"hi": "1", "lo": "5"}, {"lo": "7"}]}],
    }
    result = decode_balance_history(data)
    assert [b.scaled for b in result.series[0].balance] == [(1 << 64) + 5, 7]
    data["points"] = 3
    with pytest.raises(PolyesterResponseContractError):
        decode_balance_history(data)
    with pytest.raises(PolyesterResponseContractError):
        decode_balance_history(
            {"points": 1, "series": [{"assetId": 3, "balance": [{"lo": "1.5"}]}]}
        )


# --- lifecycle -----------------------------------------------------------------------------------


def test_wallet_delivered_deposit_reads_its_reason_by_name() -> None:
    flow = flow_summary_from_proto(
        lr.FlowSummaryView(
            flow_id="flow_a",
            is_terminal=True,
            lifecycle_reason=types_pb2.ZIPPER_DEPOSIT_DELIVERED_TO_WALLET,
        )
    )
    assert types_pb2.ZIPPER_DEPOSIT_DELIVERED_TO_WALLET == 106
    assert flow.lifecycle_reason == "zipper_deposit_delivered_to_wallet"


async def test_list_flows_no_longer_selects_an_owner_account() -> None:
    async with _client(_ok(lr.ListFlowsResponse())) as (client, requests):
        with pytest.raises(TypeError):
            await client.lifecycle.list_flows(owner_account_id="8")  # type: ignore[call-arg]
    assert requests == []


async def test_list_account_flows_is_signed_and_scoped_to_the_default_sub_account() -> None:
    page = lr.ListAccountFlowsResponse(
        flows=[lr.FlowSummaryView(flow_id="flow_1", participation=lr.PARTICIPATION_RECIPIENT)],
        next_page_token="next",
    )
    async with _client(_ok(page), default_sub_account_id=format_id(SUB)) as (client, requests):
        result = await client.lifecycle.list_account_flows(
            participation="recipient", scope="open_only", limit=500
        )
        await client.lifecycle.list_account_flows(account="main")
    first, second = (lr.ListAccountFlowsRequest.FromString(r.body) for r in requests)
    assert requests[0].path == "/chain.lifecycle.v1.LifecycleReadService/ListAccountFlows"
    assert requests[0].headers.get("x-api-key-id") == "ak_test"
    assert first.subaccount_id == SUB and first.limit == 500
    assert first.participation == lr.PARTICIPATION_RECIPIENT
    assert first.scope == lr.LIST_OPEN_ONLY and first.sort == lr.SORT_NEWEST
    assert not second.HasField("subaccount_id")
    assert result.flows[0].participation == "recipient"
    assert result.next_page_token == "next"


@pytest.mark.parametrize("limit", [501, -1, 1.0, True])
async def test_list_account_flows_refuses_a_limit_outside_the_contract(limit) -> None:
    async with _client(_ok(lr.ListAccountFlowsResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.lifecycle.list_account_flows(limit=limit)
    assert requests == []


async def test_list_account_flows_refuses_a_flow_without_its_id() -> None:
    page = lr.ListAccountFlowsResponse(flows=[lr.FlowSummaryView()])
    async with _client(_ok(page)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            await client.lifecycle.list_account_flows()


async def test_get_account_flow_reads_one_flow_and_refuses_a_reply_without_it() -> None:
    detail = lr.GetAccountFlowResponse(
        flow=lr.FlowDetailView(
            summary=lr.FlowSummaryView(flow_id="flow_9", participation=lr.PARTICIPATION_OWNER)
        )
    )
    async with _client(_ok(detail)) as (client, requests):
        flow = await client.lifecycle.get_account_flow(flow_id="flow_9", sub_account_id=SUB)
    sent = lr.GetAccountFlowRequest.FromString(requests[0].body)
    assert (sent.flow_id, sent.subaccount_id) == ("flow_9", SUB)
    assert (flow.intent_id, flow.participation) == ("flow_9", "owner")
    for reply in (
        lr.GetAccountFlowResponse(),
        lr.GetAccountFlowResponse(flow=lr.FlowDetailView()),
        lr.GetAccountFlowResponse(flow=lr.FlowDetailView(summary=lr.FlowSummaryView())),
    ):
        async with _client(_ok(reply)) as (client, _requests):
            with pytest.raises(PolyesterResponseContractError):
                await client.lifecycle.get_account_flow(flow_id="flow_9")


async def test_get_account_flow_requires_a_flow_id() -> None:
    async with _client(_ok(lr.GetAccountFlowResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.lifecycle.get_account_flow(flow_id="")
    assert requests == []


# --- batch internal transfers --------------------------------------------------------------------

_ADDRESS = "0x2222222222222222222222222222222222222222"


def _legs(count: int) -> list[InternalTransferLeg]:
    return [
        InternalTransferLeg(asset_id=1, quantity="0.5", destination_smart_account_address=_ADDRESS)
        for _ in range(count)
    ]


def _credited(index: int, **overrides) -> it_pb2.InternalTransferBatchLegResult:
    fields = dict(
        leg_index=index,
        status=it_pb2.LEG_CREDITED,
        transfer_id=f"t{index}",
        flow_id=f"flow_{index}",
        credited_at_ts_ns=1_763_000_000_123_456_789,
        asset_id=1,
        asset_code="USDT",
        amount_e18=_u128(E18 // 2),
    )
    fields.update(overrides)
    return it_pb2.InternalTransferBatchLegResult(**fields)


async def test_batch_create_sends_every_leg_exactly_and_reads_each_outcome() -> None:
    reply = it_pb2.BatchCreateInternalTransfersResponse(
        request_id="1234",
        status=it_pb2.BATCH_ACCEPTED,
        legs=[_credited(0), _credited(1, asset_id=3), _credited(2, asset_id=4)],
    )
    async with _client(_ok(reply), default_sub_account_id=format_id(SUB)) as (client, requests):
        result = await client.internal_transfers.batch_create(
            idempotency_key="rebalance-1",
            legs=[
                InternalTransferLeg(
                    asset_id=1, quantity="0.5", destination_smart_account_address=_ADDRESS
                ),
                {
                    "asset_id": 3,
                    "quantity": Decimal("1844674407370.955161549999999999"),
                    "destination_account_id": format_id(42),
                    "account": "main",
                },
                InternalTransferLeg(
                    asset_id=4,
                    quantity="1.234567",
                    quantity_scale=6,
                    destination_subaccount_id=77,
                    sub_account_id=format_id(SUB + 1),
                ),
            ],
        )
    (request,) = requests
    assert request.path == "/transfer.v1.InternalTransferService/BatchCreateInternalTransfers"
    assert request.headers.get("x-api-signature")
    sent = it_pb2.BatchCreateInternalTransfersRequest.FromString(request.body)
    assert sent.idempotency_key == "rebalance-1"
    first, second, third = sent.legs
    assert first.subaccount_id == SUB  # the default sub-account, as create resolves it
    assert first.destination_smart_account_address == _ADDRESS
    assert (first.amount_e18.hi << 64) | first.amount_e18.lo == E18 // 2
    assert second.subaccount_id == 0 and second.destination_account_id == 42
    assert (second.amount_e18.hi << 64) | second.amount_e18.lo == (
        1_844_674_407_370_955_161_549_999_999_999
    )
    assert third.subaccount_id == SUB + 1 and third.destination_subaccount_id == 77
    assert (third.amount_e18.hi << 64) | third.amount_e18.lo == 1_234_567 * 10**12
    assert (result.request_id, result.status) == ("1234", "accepted")
    credited = result.legs[0]
    assert credited.status == "credited" and credited.transfer_id == "t0"
    assert credited.flow_id == "flow_0"
    assert credited.credited_at_ts_ns == 1_763_000_000_123_456_789
    assert credited.quantity is not None and credited.quantity.as_decimal() == Decimal("0.5")
    assert [leg.status for leg in result.legs] == ["credited"] * 3


async def test_batch_create_reads_a_processing_batch() -> None:
    reply = it_pb2.BatchCreateInternalTransfersResponse(
        request_id="1234",
        status=it_pb2.BATCH_PROCESSING,
        legs=[
            it_pb2.InternalTransferBatchLegResult(
                leg_index=i, status=it_pb2.LEG_PROCESSING, transfer_id=f"t{i}"
            )
            for i in range(2)
        ],
    )
    async with _client(_ok(reply)) as (client, _requests):
        result = await client.internal_transfers.batch_create(idempotency_key="k", legs=_legs(2))
    assert (result.request_id, result.status) == ("1234", "processing")
    assert [(leg.status, leg.transfer_id) for leg in result.legs] == [
        ("processing", "t0"),
        ("processing", "t1"),
    ]
    assert result.legs[0].credited_at_ts_ns is None


async def test_batch_create_reads_a_refused_batch() -> None:
    reply = it_pb2.BatchCreateInternalTransfersResponse(
        status=it_pb2.BATCH_REFUSED,
        legs=[
            it_pb2.InternalTransferBatchLegResult(
                leg_index=0,
                status=it_pb2.LEG_NOT_MOVED,
                error_code=it_pb2.ERROR_CODE_DUST_BUSY + 100,
            ),
            it_pb2.InternalTransferBatchLegResult(leg_index=1, status=it_pb2.LEG_NOT_MOVED),
            it_pb2.InternalTransferBatchLegResult(
                leg_index=2,
                status=it_pb2.LEG_NOT_MOVED,
                error_code=it_pb2.ERROR_CODE_BATCH_TOO_MANY_SOURCES,
            ),
        ],
    )
    async with _client(_ok(reply)) as (client, _requests):
        result = await client.internal_transfers.batch_create(idempotency_key="k", legs=_legs(3))
    assert (result.request_id, result.status) == ("", "refused")
    assert [leg.status for leg in result.legs] == ["not_moved"] * 3
    assert result.legs[0].error_code == f"UNKNOWN_ERROR_CODE({it_pb2.ERROR_CODE_DUST_BUSY + 100})"
    assert result.legs[1].error_code == ""
    assert result.legs[2].error_code == "batch_too_many_sources"


def _not_moved(index: int) -> it_pb2.InternalTransferBatchLegResult:
    return it_pb2.InternalTransferBatchLegResult(leg_index=index, status=it_pb2.LEG_NOT_MOVED)


def _processing(index: int, **overrides) -> it_pb2.InternalTransferBatchLegResult:
    fields = dict(leg_index=index, status=it_pb2.LEG_PROCESSING, transfer_id=f"t{index}")
    fields.update(overrides)
    return it_pb2.InternalTransferBatchLegResult(**fields)


@pytest.mark.parametrize(
    "reply",
    [
        # No batch status.
        it_pb2.BatchCreateInternalTransfersResponse(request_id="1", legs=[_credited(0)]),
        # An accepted or processing batch without its request ID.
        it_pb2.BatchCreateInternalTransfersResponse(
            status=it_pb2.BATCH_ACCEPTED, legs=[_credited(0)]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            status=it_pb2.BATCH_PROCESSING, legs=[_processing(0)]
        ),
        # Another leg count or order than requested.
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_credited(0), _credited(1)]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_credited(1)]
        ),
        # A credited or processing leg without its transfer ID.
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_credited(0, transfer_id="")]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_PROCESSING, legs=[_processing(0, transfer_id="")]
        ),
        # A credited leg without the flow or credit time the contract sets on it.
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_credited(0, flow_id="")]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_credited(0, credited_at_ts_ns=0)]
        ),
        # A leg without a known status.
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1",
            status=it_pb2.BATCH_ACCEPTED,
            legs=[it_pb2.InternalTransferBatchLegResult(status=it_pb2.LEG_STATUS_UNSPECIFIED)],
        ),
        # A leg whose status its batch's status does not admit.
        it_pb2.BatchCreateInternalTransfersResponse(
            status=it_pb2.BATCH_REFUSED, legs=[_credited(0)]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_processing(0)]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_PROCESSING, legs=[_not_moved(0)]
        ),
        it_pb2.BatchCreateInternalTransfersResponse(
            request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_not_moved(0)]
        ),
    ],
)
async def test_batch_create_refuses_a_reply_that_breaks_the_contract(reply) -> None:
    async with _client(_ok(reply)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            await client.internal_transfers.batch_create(idempotency_key="k", legs=_legs(1))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"idempotency_key": "k", "legs": []},
        {"idempotency_key": "", "legs": _legs(1)},
        {"idempotency_key": "k" * 129, "legs": _legs(1)},
        {"idempotency_key": "k", "legs": _legs(1)[0]},
        {
            "idempotency_key": "k",
            "legs": [InternalTransferLeg(asset_id=1, quantity=0.5, destination_account_id=42)],
        },
        {
            "idempotency_key": "k",
            "legs": [InternalTransferLeg(asset_id=1.0, quantity="1", destination_account_id=42)],
        },
        {"idempotency_key": "k", "legs": [InternalTransferLeg(asset_id=1, quantity="1")]},
        {
            "idempotency_key": "k",
            "legs": [
                InternalTransferLeg(
                    asset_id=1,
                    quantity="1",
                    destination_account_id=42,
                    destination_smart_account_address=_ADDRESS,
                )
            ],
        },
        {"idempotency_key": "k", "legs": [{"asset_id": 1, "amount": "1"}]},
    ],
)
async def test_batch_create_refuses_what_it_cannot_send_before_sending(kwargs) -> None:
    async with _client(_ok(it_pb2.BatchCreateInternalTransfersResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.internal_transfers.batch_create(**kwargs)
    assert requests == []


async def test_batch_create_sends_more_than_ten_legs_and_leaves_the_limit_to_the_server() -> None:
    # The contract sets no rule on the most legs; the server takes up to 500.
    reply = it_pb2.BatchCreateInternalTransfersResponse(
        request_id="1", status=it_pb2.BATCH_ACCEPTED, legs=[_credited(i) for i in range(501)]
    )
    async with _client(_ok(reply)) as (client, requests):
        result = await client.internal_transfers.batch_create(idempotency_key="k", legs=_legs(501))
    assert len(result.legs) == 501
    assert len(it_pb2.BatchCreateInternalTransfersRequest.FromString(requests[0].body).legs) == 501


# --- dust conversion -----------------------------------------------------------------------------

_NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)


def _conversion(**overrides) -> dust_pb2.DustConversion:
    fields = dict(
        conversion_id="123",
        quote_id="dq_1",
        state=dust_pb2.DUST_CONVERSION_STATE_COMPLETED,
        target_asset_id=3,
        sources=[dust_pb2.DustSource(asset_id=10, amount_e18=_u128(5 * E18))],
        payout_e18=_u128(5_390_000_000_000_000_000),
        quoted_payout_e18=_u128(5_390_000_000_000_000_001),
        fee_e18=_u128(110_000_000_000_000_000),
        fee_bps=200,
        created_at=_ts(_NOW),
        completed_at=_ts(_NOW + timedelta(seconds=1)),
    )
    fields.update(overrides)
    return dust_pb2.DustConversion(**fields)


async def test_dust_list_balances_reads_exact_values_and_labels() -> None:
    reply = dust_pb2.ListDustBalancesResponse(
        target_asset_id=3,
        targets=[3, 1],
        fee_bps=200,
        balances=[
            dust_pb2.DustBalance(
                asset_id=10,
                amount_e18=_u128(5 * E18),
                eligibility=dust_pb2.DUST_ASSET_ELIGIBILITY_ELIGIBLE,
                usd_value_e18=_u128(2_500_000_000_000_000_001),
            ),
            dust_pb2.DustBalance(
                asset_id=11,
                amount_e18=_u128(1),
                eligibility=dust_pb2.DUST_ASSET_ELIGIBILITY_NO_PRICE,
            ),
            dust_pb2.DustBalance(asset_id=12, eligibility=99),
        ],
        gross_usd_e18=_u128(2_500_000_000_000_000_001),
        payout_e18=_u128(2_450_000_000_000_000_000),
        target_available=True,
    )
    async with _client(_ok(reply), default_sub_account_id=format_id(SUB)) as (client, requests):
        result = await client.dust_conversions.list_balances()
    sent = dust_pb2.ListDustBalancesRequest.FromString(requests[0].body)
    assert requests[0].path == "/transfer.v1.DustConversionService/ListDustBalances"
    assert (sent.target_asset_id, sent.subaccount_id) == (0, SUB)
    assert result.targets == [3, 1] and result.fee_bps == 200 and result.target_available
    eligible, no_price, future = result.balances
    assert eligible.eligibility == "eligible"
    assert eligible.usd_value == Decimal("2.500000000000000001")
    assert eligible.quantity is not None and eligible.quantity.as_decimal() == Decimal(5)
    assert (no_price.eligibility, no_price.usd_value) == ("no_price", None)
    assert future.eligibility == "UNKNOWN(99)"
    assert result.gross_usd == Decimal("2.500000000000000001")
    assert result.payout is not None and result.payout.asset_id == 3
    assert result.payout.as_decimal() == Decimal("2.45")


async def test_dust_quote_reads_exact_prices() -> None:
    reply = dust_pb2.QuoteDustConversionResponse(
        quote_id="dq_1",
        expires_at=_ts(_NOW),
        target_asset_id=3,
        prices=[
            dust_pb2.DustAssetPrice(
                asset_id=10, price_ticks=500_000_000, price_scale=9, as_of=_ts(_NOW)
            ),
            dust_pb2.DustAssetPrice(asset_id=11, price_ticks=1, price_scale=40),
        ],
    )
    async with _client(_ok(reply)) as (client, requests):
        quote = await client.dust_conversions.quote(target_asset_id=3, account="main")
    sent = dust_pb2.QuoteDustConversionRequest.FromString(requests[0].body)
    assert (sent.target_asset_id, sent.subaccount_id) == (3, 0)
    assert (quote.quote_id, quote.expires_at) == ("dq_1", _NOW)
    assert quote.prices[0].price == Decimal("0.5") and quote.prices[0].as_of == _NOW
    assert quote.prices[1].price == Decimal("1E-40") and quote.prices[1].as_of is None


@pytest.mark.parametrize("target", [0, -1, 2**32, 3.0, True, "3"])
async def test_dust_quote_requires_a_target_in_the_contract_range(target) -> None:
    async with _client(_ok(dust_pb2.QuoteDustConversionResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.dust_conversions.quote(target_asset_id=target)
    assert requests == []


async def test_dust_create_conversion_sends_the_quote_and_reads_the_conversion() -> None:
    reply = dust_pb2.CreateDustConversionResponse(conversion=_conversion())
    async with _client(_ok(reply)) as (client, requests):
        conversion = await client.dust_conversions.convert(
            quote_id="dq_1", idempotency_key=" dust-1 "
        )
    sent = dust_pb2.CreateDustConversionRequest.FromString(requests[0].body)
    assert (sent.quote_id, sent.idempotency_key) == ("dq_1", " dust-1 ")
    assert conversion.state == "completed" and conversion.refusal_code == ""
    assert conversion.sources[0].quantity is not None
    assert conversion.sources[0].quantity.as_decimal() == Decimal(5)
    assert conversion.payout is not None and conversion.payout.as_decimal() == Decimal("5.39")
    assert conversion.quoted_payout is not None
    assert conversion.quoted_payout.scaled == 5_390_000_000_000_000_001
    assert conversion.fee is not None and conversion.fee.as_decimal() == Decimal("0.11")
    assert conversion.completed_at == _NOW + timedelta(seconds=1)


async def test_dust_conversion_reads_a_refusal_code_as_a_label() -> None:
    reply = dust_pb2.GetDustConversionResponse(
        conversion=_conversion(
            state=dust_pb2.DUST_CONVERSION_STATE_REFUSED,
            refusal_code=it_pb2.ERROR_CODE_DUST_PRICE_MOVED,
            completed_at=None,
        )
    )
    async with _client(_ok(reply)) as (client, requests):
        conversion = await client.dust_conversions.get(conversion_id="123")
    assert dust_pb2.GetDustConversionRequest.FromString(requests[0].body).conversion_id == "123"
    assert (conversion.state, conversion.refusal_code) == ("refused", "dust_price_moved")
    assert conversion.completed_at is None


@pytest.mark.parametrize(
    "reply",
    [
        dust_pb2.CreateDustConversionResponse(),
        dust_pb2.CreateDustConversionResponse(conversion=_conversion(conversion_id="")),
    ],
)
async def test_dust_create_refuses_a_reply_without_its_conversion(reply) -> None:
    async with _client(_ok(reply)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            await client.dust_conversions.convert(quote_id="dq_1", idempotency_key="k")


async def test_dust_list_conversions_pages_and_refuses_a_conversion_without_its_id() -> None:
    pages = {
        "": dust_pb2.ListDustConversionsResponse(
            conversions=[_conversion(conversion_id="2")], next_page_token="p2"
        ),
        "p2": dust_pb2.ListDustConversionsResponse(conversions=[_conversion(conversion_id="1")]),
    }

    def answer(req: ParsedRequest) -> HttpScript:
        sent = dust_pb2.ListDustConversionsRequest.FromString(req.body)
        return connect_proto_response(pages[sent.page_token].SerializeToString())

    async with _client(answer) as (client, requests):
        ids = [c.conversion_id async for c in client.dust_conversions.iter_conversions(limit=100)]
    assert ids == ["2", "1"]
    assert [dust_pb2.ListDustConversionsRequest.FromString(r.body).limit for r in requests] == [
        100,
        100,
    ]
    bad = dust_pb2.ListDustConversionsResponse(conversions=[_conversion(conversion_id="")])
    async with _client(_ok(bad)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            await client.dust_conversions.list()


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.dust_conversions.convert(quote_id="", idempotency_key="k"),
        lambda c: c.dust_conversions.convert(quote_id="q" * 65, idempotency_key="k"),
        lambda c: c.dust_conversions.convert(quote_id="q", idempotency_key=""),
        lambda c: c.dust_conversions.convert(quote_id="q", idempotency_key="k" * 129),
        lambda c: c.dust_conversions.get(conversion_id="0123"),
        lambda c: c.dust_conversions.get(conversion_id="12a"),
        lambda c: c.dust_conversions.get(conversion_id="1" * 40),
        lambda c: c.dust_conversions.list(limit=101),
        lambda c: c.dust_conversions.list(page_token="t" * 257),
        lambda c: c.dust_conversions.list_balances(target_asset_id=-1),
    ],
)
async def test_dust_refuses_what_the_contract_refuses_before_sending(call) -> None:
    async with _client(_ok(dust_pb2.ListDustConversionsResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await call(client)
    assert requests == []


# --- statement exports ---------------------------------------------------------------------------

_START = datetime(2026, 1, 1, tzinfo=UTC)
_END = datetime(2027, 1, 1, tzinfo=UTC)


def _export(**overrides) -> export_pb2.StatementExport:
    fields = dict(
        export_id=(1 << 63) + 9,
        start_time=_ts(_START),
        end_time=_ts(_END),
        idempotency_key="statement-2026",
        status=export_pb2.STATEMENT_EXPORT_STATUS_READY,
        complete_through=_ts(_END),
        movements=2**40,
        bytes=2**41,
        created_at=_ts(_START),
        ready_at=_ts(_END),
        expires_at=_ts(_END + timedelta(days=7)),
    )
    fields.update(overrides)
    return export_pb2.StatementExport(**fields)


async def test_create_export_sends_the_period_and_reads_the_export() -> None:
    reply = export_pb2.CreateStatementExportResponse(export=_export(subaccount_id=SUB))
    async with _client(_ok(reply), default_sub_account_id=format_id(SUB)) as (client, requests):
        export = await client.statements.create_export(
            start_time=_START, end_time=_END, idempotency_key="statement-2026", asset_id=7
        )
    (request,) = requests
    assert request.path == "/ledger.read.v1.StatementExportService/CreateStatementExport"
    assert request.headers.get("x-api-signature")
    sent = export_pb2.CreateStatementExportRequest.FromString(request.body)
    assert (sent.start_time, sent.end_time) == (_ts(_START), _ts(_END))
    assert (sent.idempotency_key, sent.asset_id, sent.subaccount_id) == ("statement-2026", 7, SUB)
    assert export.export_id == format_id((1 << 63) + 9)
    assert export.subaccount_id == format_id(SUB)
    assert (export.status, export.failure_reason) == ("ready", "")
    assert (export.movements, export.bytes) == (2**40, 2**41)
    assert export.expires_at == _END + timedelta(days=7)


async def test_get_export_reads_a_failed_export() -> None:
    reply = export_pb2.GetStatementExportResponse(
        export=_export(
            status=export_pb2.STATEMENT_EXPORT_STATUS_FAILED,
            failure_reason=export_pb2.STATEMENT_EXPORT_FAILURE_REASON_TOO_LARGE,
            ready_at=None,
            expires_at=None,
        )
    )
    async with _client(_ok(reply)) as (client, requests):
        export = await client.statements.get_export(export_id=format_id(5))
    assert export_pb2.GetStatementExportRequest.FromString(requests[0].body).export_id == 5
    assert (export.status, export.failure_reason) == ("failed", "too_large")
    assert (export.subaccount_id, export.ready_at, export.expires_at) == ("", None, None)


@pytest.mark.parametrize(
    "reply",
    [
        export_pb2.GetStatementExportResponse(),
        export_pb2.GetStatementExportResponse(export=_export(export_id=0)),
    ],
)
async def test_get_export_refuses_a_reply_without_its_export(reply) -> None:
    async with _client(_ok(reply)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            await client.statements.get_export(export_id=format_id(5))


async def test_iter_exports_follows_pages() -> None:
    pages = {
        "": export_pb2.ListStatementExportsResponse(
            exports=[_export(export_id=2)], next_page_token="p2"
        ),
        "p2": export_pb2.ListStatementExportsResponse(exports=[_export(export_id=3)]),
    }

    def answer(req: ParsedRequest) -> HttpScript:
        sent = export_pb2.ListStatementExportsRequest.FromString(req.body)
        return connect_proto_response(pages[sent.page_token].SerializeToString())

    async with _client(answer) as (client, requests):
        ids = [e.export_id async for e in client.statements.iter_exports(limit=100)]
    assert ids == [format_id(2), format_id(3)]
    assert all(
        export_pb2.ListStatementExportsRequest.FromString(r.body).limit == 100 for r in requests
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.statements.create_export(
            start_time=_START, end_time=_START, idempotency_key="k"
        ),
        lambda c: c.statements.create_export(
            start_time=_START,
            end_time=_START + timedelta(days=366, microseconds=1),
            idempotency_key="k",
        ),
        lambda c: c.statements.create_export(
            start_time=_START, end_time=_START.replace(tzinfo=None), idempotency_key="k"
        ),
        lambda c: c.statements.create_export(start_time=_START, end_time=_END, idempotency_key=""),
        lambda c: c.statements.create_export(
            start_time=_START, end_time=_END, idempotency_key="k" * 65
        ),
        lambda c: c.statements.create_export(
            start_time=_START, end_time=_END, idempotency_key="has space"
        ),
        lambda c: c.statements.create_export(
            start_time=_START, end_time=_END, idempotency_key="k/1"
        ),
        lambda c: c.statements.create_export(
            start_time=_START, end_time=_END, idempotency_key="k", asset_id=True
        ),
        lambda c: c.statements.get_export(export_id="1"),
        lambda c: c.statements.list_exports(limit=101),
        lambda c: c.statements.list_exports(page_token="t" * 513),
    ],
)
async def test_statement_exports_refuse_what_the_contract_refuses_before_sending(call) -> None:
    async with _client(_ok(export_pb2.ListStatementExportsResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await call(client)
    assert requests == []


async def test_create_export_takes_a_366_day_period() -> None:
    reply = export_pb2.CreateStatementExportResponse(export=_export())
    async with _client(_ok(reply)) as (client, requests):
        await client.statements.create_export(
            start_time=_START, end_time=_START + timedelta(days=366), idempotency_key="a.b_c:d-1"
        )
    assert len(requests) == 1


# --- error codes and retry classification --------------------------------------------------------

_TRANSFER = "transfer.v1.ErrorDetail"
_LEDGER = "ledger.read.v1.ErrorDetail"


async def test_route_suspended_withdrawal_is_final_and_safe_to_resubmit_later() -> None:
    answer = _connect_error(
        "failed_precondition",
        "chain.withdraw.v1.ErrorDetail",
        withdraw_pb2.ErrorDetail(code=withdraw_pb2.ERROR_CODE_ROUTE_SUSPENDED),
        400,
    )
    err = await _raised(answer, lambda c: c.dust_conversions.list_balances())
    assert withdraw_pb2.ERROR_CODE_ROUTE_SUSPENDED == 50
    assert isinstance(err, PolyesterWithdrawError) and err.code == ROUTE_SUSPENDED
    assert is_route_suspended(err)
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


async def test_route_suspended_rest_problem_reads_the_same_code() -> None:
    err = await _raised(
        _problem(400, {"code": "ROUTE_SUSPENDED", "status": 400, "detail": "suspended"}),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert is_route_suspended(err)
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


@pytest.mark.parametrize("status", ["failed_precondition", "invalid_argument"])
async def test_swap_deposit_address_destination_is_final(status: str) -> None:
    answer = _connect_error(
        status,
        "chain.withdraw.v1.ErrorDetail",
        withdraw_pb2.ErrorDetail(
            code=withdraw_pb2.ERROR_CODE_DESTINATION_SWAP_DEPOSIT_ADDRESS,
            field_path="destinations[0]",
        ),
        400,
    )
    err = await _raised(answer, lambda c: c.dust_conversions.list_balances())
    assert withdraw_pb2.ERROR_CODE_DESTINATION_SWAP_DEPOSIT_ADDRESS == 51
    assert isinstance(err, PolyesterWithdrawError)
    assert err.code == DESTINATION_SWAP_DEPOSIT_ADDRESS
    assert err.field_path == "destinations[0]"
    assert is_destination_swap_deposit_address(err) and not is_route_suspended(err)
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


async def test_swap_deposit_address_rest_problem_reads_the_same_code() -> None:
    err = await _raised(
        _problem(
            400,
            {"code": "DESTINATION_SWAP_DEPOSIT_ADDRESS", "status": 400, "detail": "swap deposit"},
        ),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert isinstance(err, PolyesterApiError) and err.code == DESTINATION_SWAP_DEPOSIT_ADDRESS
    assert is_destination_swap_deposit_address(err)
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


def test_other_destination_refusals_are_not_a_swap_deposit_address() -> None:
    err = PolyesterWithdrawError("invalid", code="ERROR_CODE_DESTINATION_INVALID")
    assert not is_destination_swap_deposit_address(err)


async def test_dust_busy_is_a_retryable_rate_limit() -> None:
    answer = _connect_error(
        "resource_exhausted", _TRANSFER, it_pb2.ErrorDetail(code=it_pb2.ERROR_CODE_DUST_BUSY), 429
    )
    err = await _raised(
        answer, lambda c: c.dust_conversions.convert(quote_id="q", idempotency_key="k")
    )
    assert isinstance(err, PolyesterRateLimitError) and err.code == "ERROR_CODE_DUST_BUSY"
    assert is_retryable_error(err)
    rest = await _raised(
        _problem(429, {"code": "DUST_BUSY", "status": 429}),
        lambda c: c.dust_conversions.convert(quote_id="q", idempotency_key="k"),
    )
    assert isinstance(rest, PolyesterRateLimitError) and is_retryable_error(rest)


@pytest.mark.parametrize(
    ("detail_type", "detail"),
    [
        (_TRANSFER, it_pb2.ErrorDetail(code=it_pb2.ERROR_CODE_DUST_WINDOW_ACTIVE)),
        (_TRANSFER, it_pb2.ErrorDetail(code=it_pb2.ERROR_CODE_DUST_DAILY_LIMIT)),
        (
            _LEDGER,
            ledger_read_pb2.ErrorDetail(
                code=ledger_read_pb2.ERROR_CODE_STATEMENT_EXPORT_LIMIT_REACHED
            ),
        ),
    ],
)
async def test_hours_long_resource_limits_are_final_not_rate_limits(detail_type, detail) -> None:
    err = await _raised(
        _connect_error("resource_exhausted", detail_type, detail, 429),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert type(err) is PolyesterApiError
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


@pytest.mark.parametrize(
    "code",
    ["DUST_WINDOW_ACTIVE", "DUST_DAILY_LIMIT", "STATEMENT_EXPORT_LIMIT_REACHED"],
)
async def test_hours_long_resource_limit_problems_are_final(code) -> None:
    err = await _raised(
        _problem(429, {"code": code, "status": 429}), lambda c: c.dust_conversions.list_balances()
    )
    assert isinstance(err, PolyesterApiError) and err.code == f"ERROR_CODE_{code}"
    assert not is_retryable_error(err)


@pytest.mark.parametrize(
    ("detail_type", "detail"),
    [
        *(
            (_TRANSFER, it_pb2.ErrorDetail(code=code))
            for code in (
                it_pb2.ERROR_CODE_DUST_QUOTE_EXPIRED,
                it_pb2.ERROR_CODE_DUST_PRICE_MOVED,
                it_pb2.ERROR_CODE_DUST_BALANCE_CHANGED,
                it_pb2.ERROR_CODE_DUST_NOT_ELIGIBLE,
                it_pb2.ERROR_CODE_DUST_CONVERSION_FAILED,
                it_pb2.ERROR_CODE_DUST_TARGET_UNAVAILABLE,
            )
        ),
        (
            _LEDGER,
            ledger_read_pb2.ErrorDetail(code=ledger_read_pb2.ERROR_CODE_IDEMPOTENCY_KEY_REUSED),
        ),
        (
            _LEDGER,
            ledger_read_pb2.ErrorDetail(code=ledger_read_pb2.ERROR_CODE_STATEMENT_EXPORT_NOT_READY),
        ),
    ],
)
async def test_quote_again_and_reused_key_refusals_are_final(detail_type, detail) -> None:
    err = await _raised(
        _connect_error("failed_precondition", detail_type, detail, 400),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert type(err) is PolyesterApiError and err.code.startswith("ERROR_CODE_")
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


# --- ladder refusal cause ------------------------------------------------------------------------


@pytest.mark.parametrize(("level", "expected"), [(0, 0), (3, 3), (None, None)])
async def test_ladder_refusal_carries_its_cause_and_level(level, expected) -> None:
    detail = orders_pb2.ErrorDetail(
        code=orders_pb2.ERROR_CODE_LADDER_LEVEL_REJECTED,
        cause_code=orders_pb2.ERROR_CODE_MAX_OPEN_ORDERS_PER_PAIR,
    )
    if level is not None:
        detail.level_index = level
    err = await _raised(
        _connect_error("invalid_argument", "orders.v1.ErrorDetail", detail, 400),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert isinstance(err, PolyesterApiError)
    assert err.code == "ERROR_CODE_LADDER_LEVEL_REJECTED"
    assert err.cause_code == "ERROR_CODE_MAX_OPEN_ORDERS_PER_PAIR"
    assert err.level_index == expected


async def test_other_order_refusals_have_no_cause() -> None:
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_INSUFFICIENT_FUNDS)
    err = await _raised(
        _connect_error("failed_precondition", "orders.v1.ErrorDetail", detail, 400),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert isinstance(err, PolyesterApiError)
    assert (err.cause_code, err.level_index) == (None, None)


async def test_ladder_refusal_problem_carries_its_cause_and_level() -> None:
    body = {
        "code": "LADDER_LEVEL_REJECTED",
        "status": 400,
        "causeCode": "MAX_OPEN_ORDERS_PER_PAIR",
        "levelIndex": 0,
        "violations": [
            {"fieldPath": "trigger.ladder.levels[0]", "ruleId": "MAX_OPEN_ORDERS_PER_PAIR"}
        ],
    }
    err = await _raised(_problem(400, body), lambda c: c.dust_conversions.list_balances())
    assert isinstance(err, PolyesterApiError)
    assert err.code == "ERROR_CODE_LADDER_LEVEL_REJECTED"
    assert (err.cause_code, err.level_index) == ("ERROR_CODE_MAX_OPEN_ORDERS_PER_PAIR", 0)


# --- social link cooldowns -----------------------------------------------------------------------


async def test_social_change_limit_carries_retry_at() -> None:
    when = datetime(2026, 12, 14, 17, 20, tzinfo=UTC)
    detail = auth_pb2.AuthErrorDetail(
        code=auth_pb2.AUTH_SOCIAL_CHANGE_LIMIT_REACHED, retry_after=_ts(when)
    )
    err = await _raised(
        _connect_error("failed_precondition", "auth.v1.AuthErrorDetail", detail, 412),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert isinstance(err, PolyesterApiError)
    assert err.code == AUTH_SOCIAL_CHANGE_LIMIT_REACHED and err.retry_at == when
    assert not is_retryable_error(err)


# --- permissions ---------------------------------------------------------------------------------


def test_dust_and_funding_flow_permissions_read_by_name() -> None:
    assert (policies_pb2.CONVERT_DUST, policies_pb2.READ_FUNDING_FLOWS) == (39, 40)
    assert subaccounts_pb2.SUBACCOUNT_PERMISSION_CONVERT_DUST == 30
    assert subaccounts_pb2.SUBACCOUNT_PERMISSION_READ_FUNDING_FLOWS == 31
    actions = [policies_pb2.CONVERT_DUST, policies_pb2.READ_FUNDING_FLOWS]
    api = api_policy_from_proto(policies_pb2.ApiPolicyView(id=1, actions=actions))
    sub = subaccount_policy_from_proto(policies_pb2.SubaccountPolicyView(id=1, actions=actions))
    assert api.actions == sub.actions == ["convert_dust", "read_funding_flows"]


def test_sync_client_exposes_the_new_calls() -> None:
    with Polyester(api_url="http://127.0.0.1:9", hydrate_catalogs=False) as client:
        for name in (
            "list_balances",
            "quote",
            "convert",
            "get",
            "list",
            "iter_conversions",
        ):
            assert callable(getattr(client.dust_conversions, name))
        for name in ("create_export", "get_export", "list_exports", "iter_exports"):
            assert callable(getattr(client.statements, name))
        assert callable(client.internal_transfers.batch_create)
        assert callable(client.lifecycle.list_account_flows)
        assert callable(client.lifecycle.get_account_flow)


async def test_iter_account_flows_follows_pages_with_the_same_request() -> None:
    pages = {
        "": lr.ListAccountFlowsResponse(
            flows=[lr.FlowSummaryView(flow_id="flow_1")], next_page_token="p2"
        ),
        "p2": lr.ListAccountFlowsResponse(flows=[lr.FlowSummaryView(flow_id="flow_2")]),
    }

    def answer(req: ParsedRequest) -> HttpScript:
        sent = lr.ListAccountFlowsRequest.FromString(req.body)
        return connect_proto_response(pages[sent.page_token].SerializeToString())

    async with _client(answer) as (client, requests):
        ids = [
            f.intent_id
            async for f in client.lifecycle.iter_account_flows(participation="owner", limit=10)
        ]
    assert ids == ["flow_1", "flow_2"]
    sent = [lr.ListAccountFlowsRequest.FromString(r.body) for r in requests]
    assert [s.page_token for s in sent] == ["", "p2"]
    assert all(s.participation == lr.PARTICIPATION_OWNER and s.limit == 10 for s in sent)


@pytest.mark.parametrize("level", [0, 2])
async def test_ladder_refused_for_request_quota_keeps_its_cause_on_the_rate_limit(level) -> None:
    detail = orders_pb2.ErrorDetail(
        code=orders_pb2.ERROR_CODE_LADDER_LEVEL_REJECTED,
        cause_code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED,
        level_index=level,
    )
    detail.rate_limit.retry_after_ms = 1500
    err = await _raised(
        _connect_error("resource_exhausted", "orders.v1.ErrorDetail", detail, 429),
        lambda c: c.dust_conversions.list_balances(),
    )
    assert isinstance(err, PolyesterRateLimitError)
    assert err.code == "ERROR_CODE_LADDER_LEVEL_REJECTED"
    assert (err.cause_code, err.level_index) == ("ERROR_CODE_RATE_LIMIT_EXCEEDED", level)
    assert err.retry_after == 1.5


async def test_batch_create_reads_each_legs_resolved_destination() -> None:
    destination = it_pb2.ResolvedDestination(
        root_account_public_id="AAo8yKqygTg",
        subaccount_public_id="AAo8yKqygTh",
        smart_account_address=_ADDRESS,
    )
    reply = it_pb2.BatchCreateInternalTransfersResponse(
        request_id="1",
        status=it_pb2.BATCH_ACCEPTED,
        legs=[_credited(0, destination=destination), _credited(1)],
    )
    async with _client(_ok(reply)) as (client, _requests):
        result = await client.internal_transfers.batch_create(legs=_legs(2), idempotency_key="k")
    got = result.legs[0].destination
    assert got is not None
    assert got.root_account_public_id == "AAo8yKqygTg"
    assert got.subaccount_public_id == "AAo8yKqygTh"
    assert got.smart_account_address == _ADDRESS
    assert result.legs[1].destination is None


async def test_list_account_flows_sends_every_filter() -> None:
    async with _client(_ok(lr.ListAccountFlowsResponse())) as (client, requests):
        await client.lifecycle.list_account_flows(
            flow_kind="withdraw",
            flow_state="PENDING_LEDGER",
            order_by="started_at",
            tx_ref="0xabc",
            polyester_chain_ids=[7],
            zipped_asset_ids=[3, 4],
            unified_asset_ids=list(range(1, 101)),
        )
    sent = lr.ListAccountFlowsRequest.FromString(requests[0].body)
    assert sent.flow_kind == types_pb2.KIND_WITHDRAW
    assert sent.flow_state == types_pb2.STATE_PENDING_LEDGER
    assert sent.order_by == lr.ORDER_BY_STARTED_AT
    assert sent.tx_ref == "0xabc"
    assert list(sent.polyester_chain_ids) == [7]
    assert list(sent.zipped_asset_ids) == [3, 4]
    assert list(sent.unified_asset_ids) == list(range(1, 101))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"flow_kind": "sideways"},
        {"flow_kind": "unspecified"},
        {"flow_state": "sideways"},
        {"order_by": "sideways"},
        {"polyester_chain_ids": [0]},
        {"zipped_asset_ids": [3, 3]},
        {"unified_asset_ids": list(range(1, 102))},
        {"unified_asset_ids": [1.0]},
        {"polyester_chain_ids": [True]},
        {"tx_ref": 5},
    ],
)
async def test_list_account_flows_refuses_out_of_contract_filters_before_sending(kwargs) -> None:
    async with _client(_ok(lr.ListAccountFlowsResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.lifecycle.list_account_flows(**kwargs)
    assert requests == []
