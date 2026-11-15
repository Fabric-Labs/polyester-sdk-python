"""A reply that must name what it created, changed or read refuses ID 0.

0 (or ``""`` for a string ID) is the proto default of an absent field: the
reply is refused with ``PolyesterResponseContractError`` instead of reporting
the ID ``"0"`` or ``""``, and the same reply with a real ID decodes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from polyester.codecs.decode.address_book import (
    address_book_view_from_proto,
    entry_from_create_proto,
    entry_from_update_proto,
    list_counterparties_from_proto,
    list_destinations_from_proto,
    list_entries_from_proto,
    list_internal_whitelist_from_proto,
    tag_from_create_proto,
    tag_from_update_proto,
)
from polyester.codecs.decode.alerts import price_alerts_page_from_proto
from polyester.codecs.decode.api_keys import api_key_from_get_proto, api_keys_list_from_proto
from polyester.codecs.decode.auth import me_from_proto
from polyester.codecs.decode.changelog import (
    changelog_changes_page_from_proto,
    changelog_deployment_group_from_proto,
    changelog_post_from_proto,
)
from polyester.codecs.decode.lifecycle import (
    flow_from_get_response,
    flows_by_tx_list_from_proto,
    flows_list_from_proto,
)
from polyester.codecs.decode.orders import (
    batch_create_from_proto,
    cancel_all_from_proto,
    get_order_from_proto,
    orders_list_from_proto,
    user_trades_list_from_proto,
)
from polyester.codecs.decode.sub_accounts import (
    get_subaccount_from_proto,
    subaccount_invites_list_from_proto,
    subaccounts_list_from_proto,
)
from polyester.codecs.decode.system import status_events_page_from_proto
from polyester.codecs.decode.transfers import transfers_list_from_proto
from polyester.codecs.decode.triggers import (
    batch_cancel_triggers_from_proto,
    cancel_oco_from_proto,
    create_oco_from_proto,
    get_trigger_from_proto,
    trigger_events_list_from_proto,
    trigger_mutation_from_proto,
    triggers_list_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
from polyester.gen.alerts.v1 import price_alerts_pb2 as alerts
from polyester.gen.auth.v1 import address_book_pb2 as ab
from polyester.gen.auth.v1 import api_keys_pb2 as api_keys
from polyester.gen.auth.v1 import auth_pb2 as auth
from polyester.gen.auth.v1 import mfa_pb2 as mfa
from polyester.gen.auth.v1 import policies_pb2 as policies
from polyester.gen.auth.v1 import subaccounts_pb2 as subaccounts
from polyester.gen.chain.analytics.v1 import analytics_read_pb2 as analytics
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2 as lifecycle
from polyester.gen.changelog.v1 import changelog_pb2 as changelog
from polyester.gen.ledger.read.v1 import ledger_read_pb2 as ledger_read
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.gen.orders.v1 import orders_read_pb2 as orders_read
from polyester.gen.system.v1 import system_pb2 as system
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from polyester.services.chain_analytics import zipped_asset_supply_group_from_proto

ARMED = triggers.TriggerStatus.STATUS_ARMED


def _batch_create(order_id: int) -> orders.BatchCreateOrdersResponse:
    return orders.BatchCreateOrdersResponse(
        results=[
            orders.BatchCreateResultItem(
                client_order_id="c1", accepted=orders.BatchCreateAccepted(order_id=order_id)
            )
        ],
        accepted_count=1,
    )


def _cancel_all_reply(order_id: int) -> orders.CancelAllOrdersResponse:
    return orders.CancelAllOrdersResponse(
        status=orders.CancelAllOrdersResponse.SUBMITTED,
        matched_orders=1,
        submitted_cancels=1,
        total_cancelled=1,
        cancelled_orders=[orders.CancelledOrder(order_id=order_id, client_order_id="c1")],
    )


def _batch_cancel_triggers(trigger_id: int) -> triggers.BatchCancelTriggersResponse:
    return triggers.BatchCancelTriggersResponse(
        results=[
            triggers.BatchCancelTriggersResultItem(
                status=triggers.BatchCancelTriggersResultItem.ACCEPTED, trigger_id=trigger_id
            )
        ],
        accepted_count=1,
    )


def _create_oco(order_list_id: int, tp: int, sl: int) -> triggers.CreateOcoResponse:
    return triggers.CreateOcoResponse(
        order_list_id=order_list_id,
        client_list_id="oco-1",
        take_profit_trigger_id=tp,
        stop_loss_trigger_id=sl,
    )


ZERO_REPLIES: dict[str, Callable[[], Any]] = {
    "CreateTrigger": lambda: trigger_mutation_from_proto(triggers.CreateTriggerResponse()),
    "CancelTrigger": lambda: trigger_mutation_from_proto(
        triggers.CancelTriggerResponse(status=ARMED)
    ),
    "PauseTrigger": lambda: trigger_mutation_from_proto(
        triggers.PauseTriggerResponse(status=ARMED)
    ),
    "ResumeTrigger": lambda: trigger_mutation_from_proto(
        triggers.ResumeTriggerResponse(status=ARMED)
    ),
    "ModifyTrigger": lambda: trigger_mutation_from_proto(
        triggers.ModifyTriggerResponse(status=ARMED)
    ),
    "CreateOco order_list_id": lambda: create_oco_from_proto(_create_oco(0, 2, 3)),
    "CreateOco take_profit_trigger_id": lambda: create_oco_from_proto(_create_oco(1, 0, 3)),
    "CreateOco stop_loss_trigger_id": lambda: create_oco_from_proto(_create_oco(1, 2, 0)),
    "CancelOco": lambda: cancel_oco_from_proto(triggers.CancelOcoResponse()),
    "BatchCancelTriggers item": lambda: batch_cancel_triggers_from_proto(_batch_cancel_triggers(0)),
    "BatchCreateOrders accepted item": lambda: batch_create_from_proto(_batch_create(0)),
    "CancelAllOrders cancelled order": lambda: cancel_all_from_proto(_cancel_all_reply(0)),
    "CreateAddressBookEntry": lambda: entry_from_create_proto(
        ab.CreateAddressBookEntryResponse(entry=ab.AddressBookEntry())
    ),
    "UpdateAddressBookEntry": lambda: entry_from_update_proto(
        ab.UpdateAddressBookEntryResponse(entry=ab.AddressBookEntry())
    ),
    "CreateAddressBookTag": lambda: tag_from_create_proto(
        ab.CreateAddressBookTagResponse(tag=ab.AddressBookTag())
    ),
    "UpdateAddressBookTag": lambda: tag_from_update_proto(
        ab.UpdateAddressBookTagResponse(tag=ab.AddressBookTag())
    ),
}


@pytest.mark.parametrize("name", sorted(ZERO_REPLIES))
def test_reply_with_zero_required_id_is_refused(name: str) -> None:
    with pytest.raises(PolyesterResponseContractError):
        ZERO_REPLIES[name]()


def test_reply_with_real_required_id_decodes() -> None:
    created = trigger_mutation_from_proto(triggers.CreateTriggerResponse(trigger_id=7))
    assert (created.trigger_id, created.status) == (format_id(7), "accepted")
    canceled = trigger_mutation_from_proto(
        triggers.CancelTriggerResponse(trigger_id=7, status=triggers.TriggerStatus.STATUS_CANCELED)
    )
    assert canceled.trigger_id == format_id(7)
    assert create_oco_from_proto(_create_oco(1, 2, 3)).order_list_id == format_id(1)
    assert cancel_oco_from_proto(triggers.CancelOcoResponse(order_list_id=1)).order_list_id == (
        format_id(1)
    )
    assert batch_cancel_triggers_from_proto(_batch_cancel_triggers(7)).results[0].trigger_id == (
        format_id(7)
    )
    assert batch_create_from_proto(_batch_create(9)).results[0].order_id == format_id(9)
    assert cancel_all_from_proto(_cancel_all_reply(9)).cancelled_orders[0].order_id == format_id(9)
    entry = entry_from_create_proto(
        ab.CreateAddressBookEntryResponse(entry=ab.AddressBookEntry(address_book_entry_id=4))
    )
    assert entry.address_book_entry_id == format_id(4)
    tag = tag_from_create_proto(ab.CreateAddressBookTagResponse(tag=ab.AddressBookTag(tag_id=5)))
    assert tag.tag_id == format_id(5)


# Reads: a reply that lists or returns objects refuses one without its ID
# (0, or "" for a string ID). An optional nested message (a lineage, a
# session, a policy, a destination's address-book entry) is checked only when
# present. Each case builds the reply with the given ID and decodes it.
def _order(order_id: int = 7, lineage_id: int | None = None) -> orders_read.Order:
    order = orders_read.Order(order_id=order_id, symbol_id=1)
    if lineage_id is not None:
        order.lineage.CopyFrom(orders_read.OrderLineage(id=lineage_id, generation=1))
    return order


def _trade(lineage_id: int) -> orders_read.UserTrade:
    return orders_read.UserTrade(
        symbol_id=1,
        match_id=1,
        order_id=7,
        lineage=orders_read.OrderLineage(id=lineage_id, generation=1),
    )


def _entry(entry_id: int = 4, tag_id: int = 5) -> ab.AddressBookEntry:
    return ab.AddressBookEntry(
        address_book_entry_id=entry_id, tags=[ab.AddressBookTag(tag_id=tag_id)]
    )


def _invite(invite_id: int = 7, subaccount_id: int = 8) -> subaccounts.SubaccountInvite:
    return subaccounts.SubaccountInvite(id=invite_id, subaccount_id=subaccount_id)


def _change(change_id: int) -> changelog.Change:
    return changelog.Change(id=change_id)


def _post(change_id: int) -> changelog.GetPostResponse:
    return changelog.GetPostResponse(
        post=changelog.Post(
            summary=changelog.PostSummary(slug="post"),
            sections=[changelog.Section(heading="h", changes=[_change(change_id)])],
        )
    )


def _deployment_group(change_id: int) -> changelog.GetDeploymentGroupResponse:
    return changelog.GetDeploymentGroupResponse(
        group=changelog.DeploymentGroup(
            summary=changelog.DeploymentGroupSummary(slug="group"),
            attention=[changelog.DeploymentGroupAttention(change=_change(change_id))],
        )
    )


READ_REPLIES: dict[str, tuple[Callable[[Any], Any], int | str, int | str]] = {
    # A
    "GetTrigger trigger_id": (
        lambda v: get_trigger_from_proto(
            triggers.GetTriggerResponse(trigger=triggers.Trigger(trigger_id=v))
        ),
        0,
        7,
    ),
    # B
    "ListTriggers trigger_id": (
        lambda v: triggers_list_from_proto(
            triggers.ListTriggersResponse(triggers=[triggers.Trigger(trigger_id=v)])
        ),
        0,
        7,
    ),
    # C
    "ListTriggerEvents trigger_id": (
        lambda v: trigger_events_list_from_proto(
            triggers.ListTriggerEventsResponse(events=[triggers.TriggerEvent(trigger_id=v)])
        ),
        0,
        7,
    ),
    # D
    "GetOrder order_id": (
        lambda v: get_order_from_proto(orders_read.GetOrderResponse(order=_order(v))),
        0,
        7,
    ),
    "GetOrder order lineage.id": (
        lambda v: get_order_from_proto(orders_read.GetOrderResponse(order=_order(lineage_id=v))),
        0,
        3,
    ),
    "GetOrder trade lineage.id": (
        lambda v: get_order_from_proto(
            orders_read.GetOrderResponse(order=_order(), trades=[_trade(v)])
        ),
        0,
        3,
    ),
    # E
    "GetOpenOrders order_id": (
        lambda v: orders_list_from_proto(orders_read.GetOpenOrdersResponse(orders=[_order(v)])),
        0,
        7,
    ),
    "GetOpenOrders lineage.id": (
        lambda v: orders_list_from_proto(
            orders_read.GetOpenOrdersResponse(orders=[_order(lineage_id=v)])
        ),
        0,
        3,
    ),
    "GetOrderHistory order_id": (
        lambda v: orders_list_from_proto(orders_read.GetOrderHistoryResponse(orders=[_order(v)])),
        0,
        7,
    ),
    "GetOrderHistory lineage.id": (
        lambda v: orders_list_from_proto(
            orders_read.GetOrderHistoryResponse(orders=[_order(lineage_id=v)])
        ),
        0,
        3,
    ),
    # F
    "GetUserTrades lineage.id": (
        lambda v: user_trades_list_from_proto(
            orders_read.GetUserTradesResponse(trades=[_trade(v)])
        ),
        0,
        3,
    ),
    # G
    "ListAlerts alert_id": (
        lambda v: price_alerts_page_from_proto(
            alerts.ListAlertsResponse(alerts=[alerts.PriceAlert(alert_id=v)]), None
        ),
        0,
        7,
    ),
    # H
    "ListAddressBookEntries address_book_entry_id": (
        lambda v: list_entries_from_proto(
            ab.ListAddressBookEntriesResponse(entries=[_entry(entry_id=v)])
        ),
        0,
        4,
    ),
    "ListAddressBookEntries tag_id": (
        lambda v: list_entries_from_proto(
            ab.ListAddressBookEntriesResponse(entries=[_entry(tag_id=v)])
        ),
        0,
        5,
    ),
    "CreateAddressBookEntry tag_id": (
        lambda v: entry_from_create_proto(
            ab.CreateAddressBookEntryResponse(entry=_entry(tag_id=v))
        ),
        0,
        5,
    ),
    "UpdateAddressBookEntry tag_id": (
        lambda v: entry_from_update_proto(
            ab.UpdateAddressBookEntryResponse(entry=_entry(tag_id=v))
        ),
        0,
        5,
    ),
    # I
    "ListTransferDestinations address_book_entry_id": (
        lambda v: list_destinations_from_proto(
            ab.ListTransferDestinationsResponse(
                destinations=[ab.TransferDestination(address_book_entry=_entry(entry_id=v))]
            )
        ),
        0,
        4,
    ),
    "ListTransferDestinations tag_id": (
        lambda v: list_destinations_from_proto(
            ab.ListTransferDestinationsResponse(
                destinations=[ab.TransferDestination(address_book_entry=_entry(tag_id=v))]
            )
        ),
        0,
        5,
    ),
    # J
    "GetAddressBookView external address_book_entry_id": (
        lambda v: address_book_view_from_proto(
            ab.GetAddressBookViewResponse(
                entries=ab.AddressBookEntriesView(
                    external=[ab.ExternalAddressBookEntry(address_book_entry_id=v)]
                )
            )
        ),
        0,
        4,
    ),
    "GetAddressBookView internal address_book_entry_id": (
        lambda v: address_book_view_from_proto(
            ab.GetAddressBookViewResponse(
                entries=ab.AddressBookEntriesView(
                    internal=[ab.InternalAddressBookEntry(address_book_entry_id=v)]
                )
            )
        ),
        0,
        4,
    ),
    # K
    "ListInternalTransferWhitelistEntries entry_id": (
        lambda v: list_internal_whitelist_from_proto(
            ab.ListInternalTransferWhitelistEntriesResponse(
                entries=[ab.InternalTransferWhitelistEntry(entry_id=v)]
            )
        ),
        0,
        7,
    ),
    # L
    "ListTransferCounterparties counterparty_id": (
        lambda v: list_counterparties_from_proto(
            ab.ListTransferCounterpartiesResponse(
                counterparties=[ab.TransferCounterparty(counterparty_id=v)]
            )
        ),
        0,
        7,
    ),
    # M
    "GetApiKey key_id": (
        lambda v: api_key_from_get_proto(
            api_keys.GetApiKeyResponse(api_key=api_keys.ApiKey(key_id=v))
        ),
        "",
        "key-1",
    ),
    "ListApiKeys key_id": (
        lambda v: api_keys_list_from_proto(
            api_keys.ListApiKeysResponse(api_keys=[api_keys.ApiKey(key_id=v)])
        ),
        "",
        "key-1",
    ),
    "GetSubaccount api_keys key_id": (
        lambda v: get_subaccount_from_proto(
            subaccounts.GetSubaccountResponse(api_keys=[api_keys.ApiKey(key_id=v)])
        ),
        "",
        "key-1",
    ),
    # N
    "Me account_id": (lambda v: me_from_proto(auth.MeResponse(account_id=v)), 0, 7),
    "Me session.session_id": (
        lambda v: me_from_proto(
            auth.MeResponse(account_id=7, session=mfa.SessionInfo(session_id=v))
        ),
        "",
        "session-1",
    ),
    # P
    "GetSubaccount subaccount.id": (
        lambda v: get_subaccount_from_proto(
            subaccounts.GetSubaccountResponse(subaccount=subaccounts.Subaccount(id=v))
        ),
        0,
        7,
    ),
    "ListSubaccounts subaccounts.id": (
        lambda v: subaccounts_list_from_proto(
            subaccounts.ListSubaccountsResponse(subaccounts=[subaccounts.Subaccount(id=v)])
        ),
        0,
        7,
    ),
    # Q
    "GetSubaccount invites.id": (
        lambda v: get_subaccount_from_proto(
            subaccounts.GetSubaccountResponse(invites=[_invite(invite_id=v)])
        ),
        0,
        7,
    ),
    "GetSubaccount invites.subaccount_id": (
        lambda v: get_subaccount_from_proto(
            subaccounts.GetSubaccountResponse(invites=[_invite(subaccount_id=v)])
        ),
        0,
        8,
    ),
    "ListSubaccountInvites invites.id": (
        lambda v: subaccount_invites_list_from_proto(
            subaccounts.ListSubaccountInvitesResponse(invites=[_invite(invite_id=v)])
        ),
        0,
        7,
    ),
    "ListSubaccountInvites invites.subaccount_id": (
        lambda v: subaccount_invites_list_from_proto(
            subaccounts.ListSubaccountInvitesResponse(invites=[_invite(subaccount_id=v)])
        ),
        0,
        8,
    ),
    # R
    "GetSubaccount policy.id": (
        lambda v: get_subaccount_from_proto(
            subaccounts.GetSubaccountResponse(policy=policies.SubaccountPolicyView(id=v))
        ),
        0,
        7,
    ),
    # S
    "GetZippedAssetSupplyGroup group_id": (
        lambda v: zipped_asset_supply_group_from_proto(
            analytics.GetZippedAssetSupplyGroupResponse(group_id=v)
        ),
        "",
        "group-1",
    ),
    # T
    "GetFlowById flow_id": (
        lambda v: flow_from_get_response(
            lifecycle.GetFlowResponse(
                flow=lifecycle.FlowDetailView(summary=lifecycle.FlowSummaryView(flow_id=v))
            )
        ),
        "",
        "flow-1",
    ),
    "ListFlows flow_id": (
        lambda v: flows_list_from_proto(
            lifecycle.ListFlowsResponse(flows=[lifecycle.FlowSummaryView(flow_id=v)])
        ),
        "",
        "flow-1",
    ),
    "ListFlowsByTx flow_id": (
        lambda v: flows_by_tx_list_from_proto(
            lifecycle.ListFlowsByTxResponse(matches=[lifecycle.FlowTxMatchView(flow_id=v)])
        ),
        "",
        "flow-1",
    ),
    # U
    "ListChanges change.id": (
        lambda v: changelog_changes_page_from_proto(
            changelog.ListChangesResponse(changes=[changelog.ChangeEntry(change=_change(v))])
        ),
        0,
        7,
    ),
    "GetPost change.id": (lambda v: changelog_post_from_proto(_post(v)), 0, 7),
    "GetDeploymentGroup change.id": (
        lambda v: changelog_deployment_group_from_proto(_deployment_group(v)),
        0,
        7,
    ),
    # V
    "ListTransfers transfer_id": (
        lambda v: transfers_list_from_proto(
            ledger_read.ListTransfersResponse(transfers=[ledger_read.TransferRow(transfer_id=v)])
        ),
        "",
        "tr-1",
    ),
    # W
    "ListStatusEvents id": (
        lambda v: status_events_page_from_proto(
            system.ListStatusEventsResponse(events=[system.StatusEvent(id=v)])
        ),
        0,
        7,
    ),
}


@pytest.mark.parametrize("name", sorted(READ_REPLIES))
def test_read_reply_without_required_id_is_refused(name: str) -> None:
    decode, missing, _real = READ_REPLIES[name]
    operation = name.split(" ", 1)[0]
    with pytest.raises(PolyesterResponseContractError, match=operation):
        decode(missing)


@pytest.mark.parametrize("name", sorted(READ_REPLIES))
def test_read_reply_with_required_id_decodes(name: str) -> None:
    decode, _missing, real = READ_REPLIES[name]
    decode(real)


def test_absent_optional_nested_messages_are_not_checked() -> None:
    assert get_trigger_from_proto(triggers.GetTriggerResponse()) is None
    assert me_from_proto(auth.MeResponse(account_id=7)).session is None
    assert get_order_from_proto(orders_read.GetOrderResponse(order=_order())).order is not None
    destinations = list_destinations_from_proto(
        ab.ListTransferDestinationsResponse(destinations=[ab.TransferDestination()])
    )
    assert destinations.destinations[0].address_book_entry is None
    subaccount = get_subaccount_from_proto(subaccounts.GetSubaccountResponse())
    assert (subaccount.subaccount, subaccount.policy) == (None, None)
