from __future__ import annotations

from polyester.codecs.decode.common import require_id
from polyester.codecs.proto_helpers import (
    format_optional_uint64_id,
    format_uint64_id,
    optional_timestamp,
)
from polyester.errors import PolyesterResponseContractError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.read.v1 import statement_export_pb2 as export_pb2
from polyester.models.statements import StatementExport, StatementExportsPage, StatementPage


def statement_page_from_proto(msg: ledger_read_pb2.ExportStatementResponse) -> StatementPage:
    return StatementPage(
        csv=msg.csv,
        next_page_token=msg.next_page_token,
        complete_through=optional_timestamp(msg, "complete_through"),
    )


def _label(enum, value: int, prefix: str) -> str:
    if value == 0:
        return ""
    try:
        name: str = enum.Name(value)
    except ValueError:
        return f"UNKNOWN({value})"
    return name.removeprefix(prefix).lower()


def statement_export_from_proto(msg: export_pb2.StatementExport, operation: str) -> StatementExport:
    require_id(operation, "export_id", msg.export_id)
    return StatementExport(
        export_id=format_uint64_id(int(msg.export_id)),
        subaccount_id=(
            format_optional_uint64_id(int(msg.subaccount_id))
            if msg.HasField("subaccount_id")
            else ""
        ),
        start_time=optional_timestamp(msg, "start_time"),
        end_time=optional_timestamp(msg, "end_time"),
        asset_id=int(msg.asset_id),
        idempotency_key=msg.idempotency_key,
        status=_label(
            export_pb2.StatementExportStatus, int(msg.status), "STATEMENT_EXPORT_STATUS_"
        ),
        complete_through=optional_timestamp(msg, "complete_through"),
        movements=int(msg.movements),
        bytes=int(msg.bytes),
        created_at=optional_timestamp(msg, "created_at"),
        ready_at=optional_timestamp(msg, "ready_at"),
        expires_at=optional_timestamp(msg, "expires_at"),
        failure_reason=_label(
            export_pb2.StatementExportFailureReason,
            int(msg.failure_reason),
            "STATEMENT_EXPORT_FAILURE_REASON_",
        ),
    )


def _required_export(msg, operation: str) -> StatementExport:
    if not msg.HasField("export"):
        raise PolyesterResponseContractError(operation, "missing export")
    return statement_export_from_proto(msg.export, operation)


def created_statement_export_from_proto(
    msg: export_pb2.CreateStatementExportResponse,
) -> StatementExport:
    return _required_export(msg, "CreateStatementExport")


def statement_export_from_get_response(
    msg: export_pb2.GetStatementExportResponse,
) -> StatementExport:
    return _required_export(msg, "GetStatementExport")


def statement_exports_page_from_proto(
    msg: export_pb2.ListStatementExportsResponse,
) -> StatementExportsPage:
    return StatementExportsPage(
        exports=[statement_export_from_proto(item, "ListStatementExports") for item in msg.exports],
        next_page_token=msg.next_page_token,
    )
