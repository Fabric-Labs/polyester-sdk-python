"""Results that carry private keys must not expose them when rendered or serialized."""

from __future__ import annotations

import base64
import copy
import dataclasses
import io
import json
import logging
import pickle
import pprint
from typing import Any

import msgspec
import pytest

from polyester.codecs.decode.guard_signer import export_wallet_from_proto
from polyester.gen.chain.guard.v1 import guard_signer_pb2
from polyester.models.auth import Ed25519Keypair
from polyester.models.guard_signer import ExportGuardSignerWalletResult
from polyester.models.secret import Secret

# Obviously fake key material.
FAKE_EXPORTED_KEY = "fake-exported-guard-key-marker"
FAKE_SEED = bytes(range(0xA0, 0xC0))


def _secret(value: Any) -> Any:
    return Secret(value)


def _reveal(value: Any) -> Any:
    return value.reveal()


def _export_result() -> ExportGuardSignerWalletResult:
    msg = guard_signer_pb2.ExportGuardSignerWalletResponse(private_key=FAKE_EXPORTED_KEY)
    return export_wallet_from_proto(msg)


def _keypair() -> Ed25519Keypair:
    return Ed25519Keypair(
        public_key_hex="ab" * 32,
        public_key=b"\x02" * 32,
        secret_key_hex=_secret(FAKE_SEED.hex()),
        secret_key=_secret(FAKE_SEED),
    )


def _assert_no_key_material(path: str, rendered: str | bytes) -> None:
    text = rendered.decode("latin-1") if isinstance(rendered, bytes) else rendered
    markers = {
        "export marker": FAKE_EXPORTED_KEY,
        "hex": FAKE_SEED[:8].hex(),
        "bytes repr": repr(FAKE_SEED[:8])[2:-1],
        "base64": base64.b64encode(FAKE_SEED[:12]).decode(),
        "decimal": "160, 161, 162, 163",
    }
    for name, marker in markers.items():
        assert marker.lower() not in text.lower(), f"{path} leaked key material ({name})"
    if isinstance(rendered, bytes):
        assert FAKE_SEED[:8] not in rendered, f"{path} leaked raw key bytes"


@dataclasses.dataclass
class Holder:
    name: str
    value: Any


SUBJECTS = {
    "export result": _export_result,
    "keypair": _keypair,
}


@pytest.mark.parametrize("name", SUBJECTS)
def test_accessor_still_reads_the_key(name: str) -> None:
    subject = SUBJECTS[name]()
    if isinstance(subject, ExportGuardSignerWalletResult):
        assert _reveal(subject.private_key) == FAKE_EXPORTED_KEY
    else:
        assert _reveal(subject.secret_key_hex) == FAKE_SEED.hex()
        assert _reveal(subject.secret_key) == FAKE_SEED


@pytest.mark.parametrize("name", SUBJECTS)
def test_text_rendering_redacts_key(name: str) -> None:
    subject = SUBJECTS[name]()
    nested = Holder(name="app", value=subject)
    rich_fields = list(subject.__rich_repr__()) if hasattr(subject, "__rich_repr__") else []
    for path, rendered in {
        "repr": repr(subject),
        "str": str(subject),
        "format": f"{subject}",
        "pprint": pprint.pformat(subject),
        "rich repr protocol": repr(rich_fields),
        "nested repr": repr(nested),
        "list": str([subject]),
        "json default=str": json.dumps({"value": subject}, default=str),
    }.items():
        _assert_no_key_material(f"{name} {path}", rendered)


@pytest.mark.parametrize("name", SUBJECTS)
def test_rich_rendering_redacts_key(name: str) -> None:
    rich_console = pytest.importorskip("rich.console")
    rich_pretty = pytest.importorskip("rich.pretty")
    subject = SUBJECTS[name]()
    console = rich_console.Console(record=True, width=200)
    console.print(subject)
    console.print(Holder(name="app", value=subject))
    _assert_no_key_material(f"{name} rich Console.print", console.export_text())
    _assert_no_key_material(f"{name} rich pretty_repr", rich_pretty.pretty_repr(subject))


@pytest.mark.parametrize("name", SUBJECTS)
def test_logging_redacts_key(name: str) -> None:
    subject = SUBJECTS[name]()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s %(value)s"))
    logger = logging.getLogger("polyester.tests.secret_redaction")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.info("result %r %s", subject, subject, extra={"value": subject})
    finally:
        logger.removeHandler(handler)
    _assert_no_key_material(f"{name} logging", stream.getvalue())


@pytest.mark.parametrize("name", SUBJECTS)
def test_conversion_and_serialization_never_carry_key(name: str) -> None:
    subject = SUBJECTS[name]()
    converters = {
        "msgspec asdict": lambda: repr(msgspec.structs.asdict(subject)),
        "msgspec astuple": lambda: repr(msgspec.structs.astuple(subject)),
        "dataclasses asdict": lambda: repr(dataclasses.asdict(Holder(name="app", value=subject))),
        "deepcopy": lambda: repr(copy.deepcopy(subject)),
        "msgspec to_builtins": lambda: repr(msgspec.to_builtins(subject)),
        "msgspec json": lambda: msgspec.json.encode(subject),
        "msgspec msgpack": lambda: msgspec.msgpack.encode(subject),
        "pickle": lambda: pickle.dumps(subject),
        "nested pickle": lambda: pickle.dumps(Holder(name="app", value=subject)),
    }
    for path, convert in converters.items():
        try:
            rendered = convert()
        except TypeError as exc:
            _assert_no_key_material(f"{name} {path} error", str(exc))
            continue
        _assert_no_key_material(f"{name} {path}", rendered)
