"""Every field of the requests and replies public contracts 1945423c and 5c2119f
added or changed is classified.

``testdata/contract_field_inventory.tsv`` lists each field of those messages,
and of the messages nested in their new replies, as ``covered`` (naming the
SDK argument or model attribute that carries it) or ``omitted`` with a reason.
A field the contract adds, a listed field that is gone, or a covered model
attribute the SDK no longer has fails this test.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from google.protobuf import descriptor_pool

import polyester.errors
import polyester.gen.auth.v1.auth_pb2  # noqa: F401
import polyester.gen.chain.lifecycle.v1.lifecycle_read_pb2  # noqa: F401
import polyester.gen.ledger.read.v1.ledger_read_pb2  # noqa: F401
import polyester.gen.ledger.read.v1.statement_export_pb2  # noqa: F401
import polyester.gen.orderbook.v1.orderbook_pb2  # noqa: F401
import polyester.gen.orders.v1.orders_pb2  # noqa: F401
import polyester.gen.transfer.v1.dust_conversion_pb2  # noqa: F401
import polyester.gen.transfer.v1.internal_transfer_pb2  # noqa: F401
import polyester.models
from polyester.services.dust_conversions import AsyncDustConversionsService
from polyester.services.internal_transfers import AsyncInternalTransfersService
from polyester.services.lifecycle import AsyncLifecycleService
from polyester.services.orderbook import AsyncOrderbookService
from polyester.services.statements import AsyncStatementsService

INVENTORY = Path(__file__).parents[2] / "testdata" / "contract_field_inventory.tsv"

MESSAGES = [
    "auth.v1.AuthErrorDetail",
    "chain.lifecycle.v1.GetAccountFlowRequest",
    "chain.lifecycle.v1.GetAccountFlowResponse",
    "chain.lifecycle.v1.ListAccountFlowsRequest",
    "chain.lifecycle.v1.ListAccountFlowsResponse",
    "ledger.read.v1.BalanceSeries",
    "ledger.read.v1.GetBalanceHistoryResponse",
    "ledger.read.v1.CreateStatementExportRequest",
    "ledger.read.v1.CreateStatementExportResponse",
    "ledger.read.v1.GetStatementExportRequest",
    "ledger.read.v1.GetStatementExportResponse",
    "ledger.read.v1.ListStatementExportsRequest",
    "ledger.read.v1.ListStatementExportsResponse",
    "ledger.read.v1.StatementExport",
    "orderbook.v1.GetOrderBookRequest",
    "orderbook.v1.GetOrderBookResponse",
    "orders.v1.ErrorDetail",
    "transfer.v1.BatchCreateInternalTransfersRequest",
    "transfer.v1.InternalTransferBatchLeg",
    "transfer.v1.BatchCreateInternalTransfersResponse",
    "transfer.v1.InternalTransferBatchLegResult",
    "transfer.v1.ResolvedDestination",
    "transfer.v1.ListDustBalancesRequest",
    "transfer.v1.ListDustBalancesResponse",
    "transfer.v1.QuoteDustConversionRequest",
    "transfer.v1.QuoteDustConversionResponse",
    "transfer.v1.CreateDustConversionRequest",
    "transfer.v1.CreateDustConversionResponse",
    "transfer.v1.GetDustConversionRequest",
    "transfer.v1.GetDustConversionResponse",
    "transfer.v1.ListDustConversionsRequest",
    "transfer.v1.ListDustConversionsResponse",
    "transfer.v1.DustBalance",
    "transfer.v1.DustAssetPrice",
    "transfer.v1.DustSource",
    "transfer.v1.DustConversion",
    # Public contract 0.93.5.
    "auth.v1.TimestampWindow",
    "chain.withdraw.v1.GetWalletBalancesResponse",
    "chain.withdraw.v1.UnavailableWalletAsset",
    "chain.zipper.v1.ZippedAssetSupplyUpdate",
    "ledger.read.v1.CancelStatementExportRequest",
    "ledger.read.v1.CancelStatementExportResponse",
    "ledger.read.v1.GetStatementExportDownloadUrlRequest",
    "ledger.read.v1.GetStatementExportDownloadUrlResponse",
    "marketdata.v1.AssetMarketFlag",
    "marketdata.v1.AssetMarketStats",
    "marketdata.v1.AssetMarketValue",
    "system.v1.GetTimeResponse",
    "transfer.v1.GetInternalTransferBatchRequest",
    "transfer.v1.GetInternalTransferBatchResponse",
    "triggers.v1.LadderDetails",
]

METHODS = {
    "lifecycle.list_account_flows": AsyncLifecycleService.list_account_flows,
    "lifecycle.get_account_flow": AsyncLifecycleService.get_account_flow,
    "statements.create_export": AsyncStatementsService.create_export,
    "statements.get_export": AsyncStatementsService.get_export,
    "statements.list_exports": AsyncStatementsService.list_exports,
    "statements.cancel_export": AsyncStatementsService.cancel_export,
    "statements.get_export_download_url": AsyncStatementsService.get_export_download_url,
    "internal_transfers.get_batch": AsyncInternalTransfersService.get_batch,
    "dust_conversions.list_balances": AsyncDustConversionsService.list_balances,
    "dust_conversions.quote": AsyncDustConversionsService.quote,
    "dust_conversions.convert": AsyncDustConversionsService.convert,
    "dust_conversions.get": AsyncDustConversionsService.get,
    "dust_conversions.list": AsyncDustConversionsService.list,
    "internal_transfers.batch_create": AsyncInternalTransfersService.batch_create,
    "orderbook.get": AsyncOrderbookService.get,
}


def _inventory() -> dict[str, tuple[str, str]]:
    listed: dict[str, tuple[str, str]] = {}
    for line in INVENTORY.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        field, kind, name = line.split("\t")
        assert kind in ("covered", "omitted"), line
        assert name, f"{field} needs a name or a reason"
        assert field not in listed, f"{field} is listed twice"
        listed[field] = (kind, name)
    return listed


def _check_covered(field: str, name: str) -> list[str]:
    """Each comma-separated name must exist: ``Model.attr`` (or a bare
    ``attr`` of the previous model), ``service.method arg`` (or a bare ``arg``
    of the previous method), or a whole ``Model``."""
    problems: list[str] = []
    owner: object | None = None
    params: set[str] | None = None
    for part in re.sub(r"\s*\(.*?\)", "", name).split(","):
        words = part.strip().split(" ")
        if words[0] in METHODS:
            params = set(inspect.signature(METHODS[words[0]]).parameters)
            owner = None
            words = words[1:]
        elif "." in words[0]:
            model_name, attr = words[0].rsplit(".", 1)
            owner = getattr(polyester.models, model_name, None) or getattr(
                polyester.errors, model_name, None
            )
            params = None
            if owner is None:
                problems.append(f"{field}: no model {model_name}")
                continue
            words = [attr]
        elif getattr(polyester.models, words[0], None) is not None and len(words) == 1:
            continue
        for word in words:
            if params is not None:
                if word not in params:
                    problems.append(f"{field}: no argument {word}")
            elif owner is not None:
                attrs = set(getattr(owner, "__struct_fields__", ())) or set(
                    inspect.signature(owner.__init__).parameters  # type: ignore[misc]
                )
                if word not in attrs:
                    problems.append(f"{field}: {owner.__name__} has no {word}")  # type: ignore[attr-defined]
            else:
                problems.append(f"{field}: cannot resolve {word!r}")
    return problems


def test_contract_field_inventory_covers_every_new_field() -> None:
    listed = _inventory()
    pool = descriptor_pool.Default()
    present = {
        f"{name}.{field.name}"
        for name in MESSAGES
        for field in pool.FindMessageTypeByName(name).fields
    }
    unlisted = sorted(present - set(listed))
    gone = sorted(set(listed) - present)
    assert not unlisted and not gone, f"unlisted: {unlisted}; listed but gone: {gone}"
    problems = [
        problem
        for field, (kind, name) in listed.items()
        if kind == "covered"
        for problem in _check_covered(field, name)
    ]
    assert not problems, problems
