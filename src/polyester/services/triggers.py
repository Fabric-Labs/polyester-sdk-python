from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.triggers import (
    get_trigger_from_proto,
    trigger_events_list_from_proto,
    trigger_mutation_from_proto,
    triggers_list_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_trigger_bytes, decode_trigger_event_bytes
from polyester.codecs.scalars import id_to_int, parse_required_uint64_decimal
from polyester.codecs.triggers import (
    create_trigger_to_proto,
    modify_trigger_to_proto,
    quantity_scale_for_symbol,
)
from polyester.gen.triggers.v1.triggers_connect import TriggersServiceClient
from polyester.gen.triggers.v1.triggers_pb2 import (
    CancelTriggerRequest,
    GetTriggerRequest,
    ListTriggerEventsRequest,
    ListTriggersRequest,
    PauseTriggerRequest,
    ResumeTriggerRequest,
)
from polyester.models import (
    Trigger,
    TriggerEvent,
    TriggerEventsList,
    TriggerMutationResult,
    TriggersList,
)
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import resolve_sub_account_id


class AsyncTriggersService(BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager,
        default_sub_account_id: str | None,
        *,
        default_account_id: str | int | None = None,
        realtime: AsyncRealtimeClient | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime

    async def list(
        self,
        *,
        sub_account_id: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> TriggersList:
        request = ListTriggersRequest(limit=limit)
        if page_token:
            request.page_token = page_token
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if symbol:
            request.symbol = symbol
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.list_triggers(req),
            request,
            triggers_list_from_proto,
        )

    async def get(
        self,
        *,
        trigger_id: str | int,
        sub_account_id: str | None = None,
    ) -> Trigger | None:
        request = GetTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.get_trigger(req),
            request,
            get_trigger_from_proto,
        )

    async def create(
        self,
        *,
        symbol: str,
        trigger_type: str,
        trigger_price: str,
        side: str,
        qty: str,
        order_type: str = "market",
        limit_price: str | None = None,
        trigger_price_source: str = "last",
        tif: str = "gtc",
        sub_account_id: str | None = None,
        client_trigger_id: str | None = None,
        post_only: bool = False,
    ) -> TriggerMutationResult:
        scale = quantity_scale_for_symbol(self._catalogs, symbol)
        request = create_trigger_to_proto(
            symbol=symbol,
            trigger_type=trigger_type,
            trigger_price=trigger_price,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            trigger_price_source=trigger_price_source,
            tif=tif,
            sub_account_id=self._resolve_sub_account_id(sub_account_id),
            client_trigger_id=client_trigger_id,
            post_only=post_only,
            quantity_scale=scale,
        )
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.create_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def cancel(
        self,
        *,
        trigger_id: str | int,
        sub_account_id: str | None = None,
    ) -> TriggerMutationResult:
        request = CancelTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.cancel_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def modify(
        self,
        *,
        trigger_id: str | int,
        sub_account_id: str | None = None,
        trigger_price: str | None = None,
        limit_price: str | None = None,
        trailing_distance_ticks: int | None = None,
        trailing_distance_bps: int | None = None,
        activation_price: str | None = None,
        max_slippage_ticks: int | None = None,
        max_slippage_bps: int | None = None,
    ) -> TriggerMutationResult:
        request = modify_trigger_to_proto(
            trigger_id=trigger_id,
            sub_account_id=self._resolve_sub_account_id(sub_account_id),
            trigger_price=trigger_price,
            limit_price=limit_price,
            trailing_distance_ticks=trailing_distance_ticks,
            trailing_distance_bps=trailing_distance_bps,
            activation_price=activation_price,
            max_slippage_ticks=max_slippage_ticks,
            max_slippage_bps=max_slippage_bps,
        )
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.modify_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def pause(
        self,
        *,
        trigger_id: str | int,
        sub_account_id: str | None = None,
    ) -> TriggerMutationResult:
        request = PauseTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.pause_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def resume(
        self,
        *,
        trigger_id: str | int,
        sub_account_id: str | None = None,
    ) -> TriggerMutationResult:
        request = ResumeTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.resume_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def list_events(
        self,
        *,
        trigger_id: str | int,
        sub_account_id: str | None = None,
        limit: int = 50,
        before_ts_ns: str | int | None = None,
    ) -> TriggerEventsList:
        request = ListTriggerEventsRequest(
            trigger_id=id_to_int(trigger_id, "trigger_id"),
            limit=limit,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if before_ts_ns is not None:
            if isinstance(before_ts_ns, str):
                request.before_ts_ns = parse_required_uint64_decimal(
                    before_ts_ns, "before_ts_ns"
                )
            else:
                request.before_ts_ns = int(before_ts_ns)
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.list_trigger_events(req),
            request,
            trigger_events_list_from_proto,
        )

    async def subscribe(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[Trigger]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:spot:triggers:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_trigger_bytes,
        )

    async def subscribe_events(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[TriggerEvent]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:spot:triggers:events:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_trigger_event_bytes,
        )

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
