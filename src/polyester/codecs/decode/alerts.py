from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.codecs.scalars import timestamp_dict_to_datetime
from polyester.gen.alerts.v1 import price_alerts_pb2 as pb
from polyester.models.alerts import PriceAlert, PriceAlertsPage, PriceAlertUpdate
from polyester.types.money import Price

UNSPECIFIED = "unspecified"

DIRECTION_LABELS = {int(pb.ABOVE): "above", int(pb.BELOW): "below"}
PRICE_SOURCE_LABELS = {int(pb.LAST_PRICE): "last", int(pb.INDEX_PRICE): "index"}
STATUS_LABELS = {
    int(pb.ACTIVE): "active",
    int(pb.TRIGGERED): "triggered",
    int(pb.CANCELLED): "cancelled",
}
CHANNEL_LABELS = {int(pb.IN_APP): "in_app", int(pb.TELEGRAM): "telegram"}
OUTCOME_LABELS = {
    int(pb.APPLIED): "applied",
    int(pb.UNCHANGED): "unchanged",
    int(pb.REPLAYED): "replayed",
}


def _label(labels: dict[int, str], value: int) -> str:
    return labels.get(int(value), UNSPECIFIED)


def _price(ticks: int, symbol: str) -> Price | None:
    if ticks <= 0:
        return None
    return Price.from_ticks(int(ticks), symbol=symbol or None)


def price_alert_from_proto(msg: pb.PriceAlert, catalogs: CatalogManager | None) -> PriceAlert:
    symbol = ""
    if catalogs is not None and msg.symbol_id:
        symbol = catalogs.symbol_for_symbol_id(int(msg.symbol_id)) or ""
    triggered = msg.HasField("triggered_at") or msg.triggered_price_ticks > 0
    return PriceAlert(
        alert_id=format_uint64_id(msg.alert_id),
        symbol_id=int(msg.symbol_id),
        symbol=symbol,
        direction=_label(DIRECTION_LABELS, msg.direction),
        price_source=_label(PRICE_SOURCE_LABELS, msg.price_source),
        price=_price(msg.price_ticks, symbol),
        reference_price=_price(msg.reference_price_ticks, symbol),
        armed=bool(msg.armed),
        status=_label(STATUS_LABELS, msg.status),
        channels=[_label(CHANNEL_LABELS, channel) for channel in msg.channels],
        revision=int(msg.revision),
        created_at=timestamp_dict_to_datetime(msg.created_at)
        if msg.HasField("created_at")
        else None,
        updated_at=timestamp_dict_to_datetime(msg.updated_at)
        if msg.HasField("updated_at")
        else None,
        triggered_at=timestamp_dict_to_datetime(msg.triggered_at)
        if msg.HasField("triggered_at")
        else None,
        triggered_price=_price(msg.triggered_price_ticks, symbol) if triggered else None,
    )


def price_alerts_page_from_proto(
    msg: pb.ListAlertsResponse, catalogs: CatalogManager | None
) -> PriceAlertsPage:
    return PriceAlertsPage(
        alerts=[price_alert_from_proto(alert, catalogs) for alert in msg.alerts],
        next_page_token=msg.next_page_token,
    )


def price_alert_update_from_proto(
    msg: pb.UpdateAlertResponse, catalogs: CatalogManager | None
) -> PriceAlertUpdate:
    return PriceAlertUpdate(
        alert=price_alert_from_proto(msg.alert, catalogs),
        outcome=_label(OUTCOME_LABELS, msg.outcome),
    )
