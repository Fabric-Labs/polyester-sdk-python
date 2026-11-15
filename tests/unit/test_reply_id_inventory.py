"""Every ID field of every reply in the contract is classified.

``testdata/reply_id_inventory.tsv``, shared with the Go and Rust SDKs, lists each
non-repeated scalar field named ``id`` or ending in ``_id`` of every RPC reply,
recursively, as ``required`` (its decoder refuses 0 or an empty string) or
``not_required`` with a reason. A new ID field in the contract fails this test
until it is listed.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from google.protobuf.descriptor import Descriptor, FieldDescriptor

import polyester.gen

INVENTORY = Path(__file__).parents[2] / "testdata" / "reply_id_inventory.tsv"


def _reply_id_fields() -> set[str]:
    files = []
    for module in pkgutil.walk_packages(polyester.gen.__path__, "polyester.gen."):
        if module.name.endswith("_pb2"):
            files.append(importlib.import_module(module.name).DESCRIPTOR)
    out: set[str] = set()
    seen: set[str] = set()

    def walk(message: Descriptor) -> None:
        if message.full_name in seen or message.full_name.startswith("google."):
            return
        seen.add(message.full_name)
        for field in message.fields:
            if field.type in (FieldDescriptor.TYPE_MESSAGE, FieldDescriptor.TYPE_GROUP):
                walk(field.message_type)
                continue
            repeated = getattr(field, "is_repeated", None)
            if repeated is None:
                repeated = field.label == FieldDescriptor.LABEL_REPEATED
            if not repeated and (field.name == "id" or field.name.endswith("_id")):
                out.add(f"{message.full_name}.{field.name}")

    for file in files:
        for service in file.services_by_name.values():
            for method in service.methods:
                walk(method.output_type)
    return out


def _inventory() -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in INVENTORY.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        field, kind, reason = line.split("\t")
        assert kind in ("required", "not_required"), line
        assert kind == "required" or reason, f"{field} needs a reason"
        assert field not in listed, f"{field} is listed twice"
        listed[field] = kind
    return listed


def test_inventory_lists_every_reply_id_field() -> None:
    walked = _reply_id_fields()
    listed = set(_inventory())
    assert sorted(walked - listed) == [], "unlisted reply ID fields"
    assert sorted(listed - walked) == [], "listed fields no reply has"
