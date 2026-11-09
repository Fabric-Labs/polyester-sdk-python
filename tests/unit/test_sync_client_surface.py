"""The sync client declares every async member, with the async signature.

``polyester._sync_services`` declares each sync service member so a type
checker sees the async signature. These tests fail when an async service gains,
loses or changes a member that the sync view doesn't follow.
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from collections.abc import Iterator

import pytest

from polyester import AsyncPolyester, Polyester
from polyester._sync_services import SyncMember, _SyncService, _SyncSubscribeService
from polyester.services.orders import AsyncOrdersService

CALLBACKS = ("on_event", "on_error")


@pytest.fixture(scope="module")
def client() -> Iterator[Polyester]:
    with Polyester(api_url="http://127.0.0.1:9", hydrate_catalogs=False) as sync:
        yield sync


def _views(client: Polyester) -> Iterator[tuple[str, _SyncService]]:
    for name, value in vars(client).items():
        if isinstance(value, _SyncService):
            yield name, value
    yield "auth.profile", client.auth.profile


def _kind(member: object) -> str:
    if inspect.isasyncgenfunction(member):
        return "iterate"
    if inspect.iscoroutinefunction(member):
        return "call"
    return "plain"


def _public(cls: type) -> dict[str, object]:
    return {name: member for name, member in inspect.getmembers(cls) if not name.startswith("_")}


def test_every_async_client_service_has_a_typed_sync_view(client: Polyester) -> None:
    async_services = {
        name
        for name, value in vars(client._client).items()
        if not name.startswith("_") and type(value).__name__.startswith("Async")
    }
    views = {name for name, _ in _views(client)}
    assert async_services <= views
    for name, view in _views(client):
        assert type(view) not in (_SyncService, _SyncSubscribeService), name


def test_sync_views_declare_every_async_member_as_its_kind(client: Polyester) -> None:
    checked = 0
    for name, view in _views(client):
        async_cls = type(view._service)
        declared = {
            member_name: member
            for member_name, member in vars(type(view)).items()
            if isinstance(member, SyncMember)
        }
        assert set(declared) == set(_public(async_cls)), name
        for member_name, member in declared.items():
            target = getattr(async_cls, member_name)
            assert member.member is target, f"{name}.{member_name}"
            assert member.kind == _kind(target), f"{name}.{member_name}"
            assert member.name == member_name
            checked += 1
    assert checked > 150


def _normalized(annotation: object) -> object:
    return annotation.replace("builtins.", "") if isinstance(annotation, str) else annotation


def _subscribe_methods(client: Polyester) -> Iterator[tuple[str, _SyncService, str, object]]:
    seen: set[type] = set()
    for name, view in _views(client):
        # ``candles`` is ``market_data``.
        if type(view) in seen:
            continue
        seen.add(type(view))
        for method_name, method in vars(type(view)).items():
            if method_name.startswith("subscribe") and method_name.endswith("_sync"):
                yield f"{name}.{method_name}", view, method_name, method


def test_subscribe_sync_methods_take_the_async_keywords(client: Polyester) -> None:
    declared = list(_subscribe_methods(client))
    assert len(declared) == 21
    for label, view, _method_name, method in declared:
        target_name = method.__sync_subscribes__  # type: ignore[attr-defined]
        target = inspect.signature(getattr(type(view._service), target_name))
        sync = inspect.signature(method)  # type: ignore[arg-type]
        assert sync.return_annotation == "SyncSubscription", label
        sync_params = [p for p in sync.parameters.values() if p.name != "self"]
        assert [p.name for p in sync_params[:2]] == list(CALLBACKS), label
        assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in sync_params), label
        forwarded = [
            (p.name, p.kind, p.default, _normalized(p.annotation))
            for p in sync_params
            if p.name not in CALLBACKS
        ]
        expected = [
            (p.name, p.kind, p.default, _normalized(p.annotation))
            for p in target.parameters.values()
            if p.name != "self" and p.name not in CALLBACKS
        ]
        assert forwarded == expected, label
        event = re.fullmatch(r"AsyncSubscription\[(.+)\]", str(target.return_annotation))
        if event is not None:
            assert sync.parameters["on_event"].annotation == (f"Callable[[{event[1]}], object]"), (
                label
            )


def _overloads(cls: type, name: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == name
            and any(ast.unparse(d) == "overload" for d in node.decorator_list)
        ):
            found.append(f"{ast.unparse(node.args)} -> {ast.unparse(node.returns)}")  # type: ignore[arg-type]
    return found


@pytest.mark.parametrize("name", ["create", "preview_order"])
def test_overloaded_order_methods_keep_the_async_overloads(name: str) -> None:
    from polyester._sync_services import SyncOrdersService

    expected = _overloads(AsyncOrdersService, name)
    assert len(expected) == 2
    assert _overloads(SyncOrdersService, name) == expected


def test_sync_constructor_takes_the_async_parameters() -> None:
    sync = inspect.signature(Polyester.__init__)
    asynchronous = inspect.signature(AsyncPolyester.__init__)
    assert list(sync.parameters.values()) == list(asynchronous.parameters.values())


def test_declared_members_forward_to_the_async_service(client: Polyester) -> None:
    keypair = client.api_keys.generate_keypair()
    assert len(keypair.public_key) == 32
    assert client.orders.subscribe_sync.__sync_subscribes__ == "subscribe"  # type: ignore[attr-defined]
    with pytest.raises(TypeError, match="unexpected keyword argument 'acount_id'"):
        client.balances.subscribe_sync(on_event=print, acount_id=42)  # type: ignore[call-arg]
