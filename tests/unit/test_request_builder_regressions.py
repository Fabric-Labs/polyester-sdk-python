"""Public request builders, exercised only against a local capture server."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
from google.protobuf import json_format

from polyester.catalogs import CatalogManager
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.internal_transfers import AsyncInternalTransfersService
from polyester.services.transfers import AsyncTransfersService
from polyester.services.triggers import AsyncTriggersService
from polyester.services.withdraw import AsyncWithdrawService
from polyester.transport import TransportConfig, TransportFactory
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)


@asynccontextmanager
async def capture_transport():
    requests = []

    async def handler(req: ParsedRequest):
        requests.append(req)
        if req.path.endswith("/CreateInternalTransfer"):
            return connect_proto_response(
                internal_transfer_pb2.CreateInternalTransferResponse(
                    request_id="request-local", transfer_id="transfer-local"
                ).SerializeToString()
            )
        if req.path.endswith("/CreateTradingWithdraw"):
            return connect_proto_response(
                withdraw_pb2.CreateTradingWithdrawResponse(
                    intent_id="intent-local"
                ).SerializeToString()
            )
        if req.path.endswith("/CreateWalletTradingWithdraw"):
            return connect_proto_response(
                withdraw_pb2.CreateWalletTradingWithdrawResponse(
                    intent_id="intent-local"
                ).SerializeToString()
            )
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    transport = TransportFactory(
        TransportConfig(api_url=http.base_url), credentials=make_test_credentials()
    )
    try:
        yield transport, requests
    finally:
        await transport.aclose()
        await http.aclose()


@pytest.mark.parametrize("since", [None, 0, 1_793_922_052_911_123, 2**64 - 1])
async def test_poly_8471_since_is_inclusive_microsecond_lower_bound(since):
    async with capture_transport() as (transport, requests):
        await AsyncTransfersService(transport, None).list(since=since)
    assert len(requests) == 1
    assert requests[0].path.endswith("/ListTransfers")
    request = ledger_read_pb2.ListTransfersRequest.FromString(requests[0].body)
    assert request.ts_min_us == (since or 0)
    # ts_max_us has explicit presence: a sent 0 is an epoch upper bound that
    # answers an empty page. The SDK sets no upper bound, so it is absent.
    assert not request.HasField("ts_max_us")
    assert request.limit == 50


@pytest.mark.parametrize("wire_format", ["binary", "json"])
@pytest.mark.parametrize("since", [None, 0, 1_793_922_052_911_123])
async def test_transfers_list_never_sends_an_upper_time_bound(wire_format, since):
    """An omitted upper bound is unbounded; a sent ``tsMaxUs: 0`` (or a binary
    field 5 holding 0) would ask for an empty, epoch-bounded result."""
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        if wire_format == "json":
            return HttpScript.json(200, {})
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    transport = TransportFactory(
        TransportConfig(api_url=http.base_url, wire_format=wire_format),
        credentials=make_test_credentials(),
    )
    try:
        await AsyncTransfersService(transport, None).list(since=since)
    finally:
        await transport.aclose()
        await http.aclose()

    (sent,) = requests
    if wire_format == "json":
        body = json.loads(sent.body)
        assert "tsMaxUs" not in body
        request = json_format.Parse(sent.body, ledger_read_pb2.ListTransfersRequest())
    else:
        request = ledger_read_pb2.ListTransfersRequest.FromString(sent.body)
    assert not request.HasField("ts_max_us")
    assert request.ts_min_us == (since or 0)


def test_transfers_request_keeps_an_explicit_zero_upper_bound_apart_from_none():
    """The generated request preserves the distinction on both wires: an
    explicit 0 is sent and read back as set, an unset bound is not sent."""
    explicit = ledger_read_pb2.ListTransfersRequest(ts_max_us=0)
    unset = ledger_read_pb2.ListTransfersRequest()
    assert explicit.SerializeToString() == b"\x28\x00"
    assert unset.SerializeToString() == b""
    assert ledger_read_pb2.ListTransfersRequest.FromString(b"\x28\x00").HasField("ts_max_us")
    as_json = json_format.MessageToDict(explicit)
    assert as_json == {"tsMaxUs": "0"}
    assert json_format.ParseDict(as_json, ledger_read_pb2.ListTransfersRequest()).HasField(
        "ts_max_us"
    )
    assert json_format.MessageToDict(unset) == {}


@pytest.mark.parametrize("since", [-1, -(2**100), 2**64, 1.5, "5", True, False])
async def test_poly_8471_invalid_since_is_rejected_before_transport(since):
    async with capture_transport() as (transport, requests):
        with pytest.raises(PolyesterValidationError, match="since"):
            await AsyncTransfersService(transport, None).list(since=since)
        assert not requests


@pytest.mark.parametrize("destination", ["destination_account_id", "destination_subaccount_id"])
@pytest.mark.parametrize("address", [None, "", " \t "])
async def test_poly_8468_python_never_overwrites_a_valid_recipient(destination, address):
    async with capture_transport() as (transport, requests):
        service = AsyncInternalTransfersService(transport, CatalogManager(), None)
        kwargs = {destination: format_id(42), "destination_smart_account_address": address}
        await service.create(asset_id=7, quantity="1", idempotency_key="capture", **kwargs)
        assert len(requests) == 1
        request = internal_transfer_pb2.CreateInternalTransferRequest.FromString(requests[0].body)
        assert request.WhichOneof("destination") == destination
        assert getattr(request, destination) == 42


@pytest.mark.parametrize("address", ["", " \t ", "0xlocal"])
async def test_poly_8468_python_address_only_rejects_blanks(address):
    async with capture_transport() as (transport, requests):
        service = AsyncInternalTransfersService(transport, CatalogManager(), None)
        kwargs = {"destination_smart_account_address": address}
        if not address.strip():
            with pytest.raises(PolyesterValidationError, match="exactly one"):
                await service.create(asset_id=7, quantity="1", idempotency_key="capture", **kwargs)
            assert not requests
        else:
            await service.create(asset_id=7, quantity="1", idempotency_key="capture", **kwargs)
            assert len(requests) == 1
            request = internal_transfer_pb2.CreateInternalTransferRequest.FromString(
                requests[0].body
            )
            assert request.WhichOneof("destination") == "destination_smart_account_address"
            assert request.destination_smart_account_address == address


WITHDRAW_BASE = dict(
    asset_id=7,
    quantity="1",
    payload_signature=b"local-only",
    idempotency_key="capture",
    nonce=42,
    deadline_ts_sec=1_800_000_000,
)


@pytest.mark.parametrize("method", ["create_to_funding", "create_to_external_chain"])
@pytest.mark.parametrize(
    "selectors",
    [
        {"account": "42"},
        {"account": "main"},
        {"account": "active"},
        {"account": {"subaccountId": "42"}},
        {"sub_account_id": "42"},
        {"sub_account_id": ""},
        {"account": "42", "sub_account_id": "43"},
    ],
)
async def test_poly_8474_api_key_withdraw_rejects_explicit_selectors(method, selectors):
    async with capture_transport() as (transport, requests):
        service = AsyncWithdrawService(transport, "42")
        kwargs = dict(WITHDRAW_BASE)
        if method == "create_to_external_chain":
            kwargs.update(destination_chain_id=42161, destination_address="0xlocal")
        with pytest.raises(PolyesterValidationError, match="API.key.*scope"):
            await getattr(service, method)(**kwargs, **selectors)
        assert not requests


@pytest.mark.parametrize("method", ["create_to_funding", "create_to_external_chain"])
@pytest.mark.parametrize("default", [None, "42"])
async def test_poly_8474_omitted_selectors_use_authenticated_key_scope(method, default):
    async with capture_transport() as (transport, requests):
        kwargs = dict(WITHDRAW_BASE)
        if method == "create_to_external_chain":
            kwargs.update(destination_chain_id=42161, destination_address="0xlocal")
        await getattr(AsyncWithdrawService(transport, default), method)(**kwargs)
        assert len(requests) == 1
        assert requests[0].path.endswith("/CreateTradingWithdraw")
        request = withdraw_pb2.CreateTradingWithdrawRequest.FromString(requests[0].body)
        assert request.payload.asset_id == 7
        assert request.payload.nonce.lo == 42
        assert request.payload_signature == b"local-only"
        assert request.payload.action == (
            withdraw_pb2.TO_FUNDING
            if method == "create_to_funding"
            else withdraw_pb2.TO_EXTERNAL_CHAIN
        )
        assert request.payload.destination_chain_id == (
            0 if method == "create_to_funding" else 42161
        )
        assert set(request.DESCRIPTOR.fields_by_name) == {"payload", "payload_signature"}


@pytest.mark.parametrize(
    "selectors, expected",
    [
        ({}, 42),
        ({"sub_account_id": format_id(43)}, 43),
        ({"account": {"subaccountId": format_id(44)}}, 44),
    ],
)
async def test_poly_8474_wallet_withdraw_still_encodes_scope(selectors, expected):
    async with capture_transport() as (transport, requests):
        await AsyncWithdrawService(transport, format_id(42)).create_wallet_trading_withdraw(
            action="to_funding",
            asset_id=7,
            amount="1",
            payload_signature=b"local-only",
            signer_wallet="0xlocal",
            idempotency_key="capture",
            nonce=42,
            deadline_ts_sec=1_800_000_000,
            **selectors,
        )
        assert len(requests) == 1
        request = withdraw_pb2.CreateWalletTradingWithdrawRequest.FromString(requests[0].body)
        assert request.subaccount_id == expected


def triggers(transport):
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return AsyncTriggersService(transport, catalogs, None)


async def trigger_write(service, operation, fields):
    if operation == "modify":
        return await service.modify(trigger_id="5", **fields)
    kwargs = dict(symbol="BTC-USDT", trigger_type=operation, side="sell", qty="0.01")
    if operation == "trailing_stop" and not any(k.startswith("trailing_distance") for k in fields):
        kwargs["trailing_distance_bps"] = 100
    if operation == "stop_loss":
        kwargs["trigger_price"] = "100"
    if operation == "twap":
        kwargs.update(twap_duration_ms=60_000, twap_slice_interval_ms=10_000)
    return await service.create(**kwargs, **fields)


@pytest.mark.parametrize("operation", ["modify", "trailing_stop", "stop_loss", "twap"])
@pytest.mark.parametrize("bps", [50, 0])
async def test_poly_8513_competing_slippage_rejected_before_transport(operation, bps):
    async with capture_transport() as (transport, requests):
        with pytest.raises(PolyesterValidationError, match="at most one of max_slippage"):
            await trigger_write(
                triggers(transport), operation, {"max_slippage_ticks": 5, "max_slippage_bps": bps}
            )
        assert not requests


@pytest.mark.parametrize("operation", ["modify", "trailing_stop"])
async def test_poly_8513_competing_distance_rejected_before_transport(operation):
    async with capture_transport() as (transport, requests):
        with pytest.raises(
            PolyesterValidationError, match="trailing_distance_ticks.*trailing_distance_bps"
        ):
            await trigger_write(
                triggers(transport),
                operation,
                {"trailing_distance_ticks": 5, "trailing_distance_bps": 50},
            )
        assert not requests


@pytest.mark.parametrize("operation", ["modify", "trailing_stop"])
@pytest.mark.parametrize(
    "field, value, oneof",
    [
        ("max_slippage_ticks", 5, "max_slippage"),
        ("max_slippage_bps", 50, "max_slippage"),
        ("max_slippage_ticks", 0, "max_slippage"),
        ("max_slippage_bps", 0, "max_slippage"),
        ("trailing_distance_ticks", 5, "trailing_distance"),
        ("trailing_distance_bps", 50, "trailing_distance"),
    ],
)
async def test_poly_8513_single_fields_round_trip_including_modify_zero(
    operation, field, value, oneof
):
    async with capture_transport() as (transport, requests):
        if operation == "trailing_stop" and value == 0:
            with pytest.raises(PolyesterValidationError):
                await trigger_write(triggers(transport), operation, {field: value})
            assert not requests
            return
        await trigger_write(triggers(transport), operation, {field: value})
        assert len(requests) == 1
        if operation == "modify":
            request = triggers_pb2.ModifyTriggerRequest.FromString(requests[0].body)
        else:
            request = triggers_pb2.CreateTriggerRequest.FromString(
                requests[0].body
            ).trigger.trailing_stop
        assert request.WhichOneof(oneof) == field
        assert getattr(request, field) == value
