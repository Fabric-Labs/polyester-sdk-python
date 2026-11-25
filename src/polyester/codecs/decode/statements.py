from __future__ import annotations

from polyester.codecs.decode.common import require_id
from polyester.codecs.proto_helpers import (
    format_optional_uint64_id,
    format_uint64_id,
    optional_timestamp,
)
from polyester.errors import PolyesterResponseContractError
from polyester.gen.ledger.read.v1 import statement_export_pb2 as export_pb2
from polyester.models.secret import Secret
from polyester.models.statements import (
    StatementExport,
    StatementExportDownloadUrl,
    StatementExportsPage,
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
        type=_label(export_pb2.StatementExportType, int(msg.type), ""),
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
        history_available_from=optional_timestamp(msg, "history_available_from"),
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
        in_progress_exports=int(msg.in_progress_exports),
        max_in_progress_exports=int(msg.max_in_progress_exports),
    )


def canceled_statement_export_from_proto(
    msg: export_pb2.CancelStatementExportResponse,
) -> StatementExport:
    return _required_export(msg, "CancelStatementExport")


def statement_export_download_url_from_proto(
    msg: export_pb2.GetStatementExportDownloadUrlResponse,
) -> StatementExportDownloadUrl:
    operation = "GetStatementExportDownloadUrl"
    expires_at = optional_timestamp(msg, "expires_at")
    if not msg.url:
        raise PolyesterResponseContractError(operation, "missing url")
    if expires_at is None:
        raise PolyesterResponseContractError(operation, "missing expires_at")
    if not msg.filename:
        raise PolyesterResponseContractError(operation, "missing filename")
    return StatementExportDownloadUrl(
        url=Secret(msg.url), expires_at=expires_at, filename=msg.filename
    )
