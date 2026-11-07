"""ApiKeyCredentials must not expose the private key when rendered or serialized."""

from __future__ import annotations

import base64
import copy
import dataclasses
import io
import json
import logging
import pickle
import pprint

import pytest

from polyester.auth import ApiKeyCredentials, load_api_key_credentials

# An obviously fake Ed25519 seed (0xa0, 0xa1, ...).
SYNTHETIC_SEED = bytes(range(0xA0, 0xC0))


def _credentials() -> ApiKeyCredentials:
    creds = load_api_key_credentials(
        api_key_id="key_redaction", api_private_key=SYNTHETIC_SEED.hex(), from_env=False
    )
    assert creds is not None
    return creds


def _assert_no_key_material(path: str, rendered: str | bytes) -> None:
    text = rendered.decode("latin-1") if isinstance(rendered, bytes) else rendered
    markers = {
        "hex": SYNTHETIC_SEED[:8].hex(),
        "bytes repr": repr(SYNTHETIC_SEED[:8])[2:-1],
        "base64": base64.b64encode(SYNTHETIC_SEED[:12]).decode(),
        "decimal": "160, 161, 162, 163",
    }
    for name, marker in markers.items():
        assert marker.lower() not in text.lower(), f"{path} leaked the private key ({name})"
    if isinstance(rendered, bytes):
        assert SYNTHETIC_SEED[:8] not in rendered, f"{path} leaked raw private key bytes"


@dataclasses.dataclass
class AppConfig:
    name: str
    credentials: ApiKeyCredentials


def test_text_rendering_redacts_private_key() -> None:
    creds = _credentials()
    nested = AppConfig(name="app", credentials=creds)
    for path, rendered in {
        "repr": repr(creds),
        "str": str(creds),
        "format": f"{creds}",
        "format !r": f"{creds!r}",
        "percent": "%s %r" % (creds, creds),  # noqa: UP031 - the path under test
        "pprint": pprint.pformat(creds),
        "nested repr": repr(nested),
        "nested pprint": pprint.pformat(nested),
        "list": str([creds]),
        "dict": str({"credentials": creds}),
        "json default=str": json.dumps({"credentials": creds}, default=str),
    }.items():
        _assert_no_key_material(path, rendered)
    assert "key_redaction" in repr(creds)
    assert "[REDACTED]" in repr(creds)


def test_logging_redacts_private_key() -> None:
    creds = _credentials()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s %(credentials)s"))
    logger = logging.getLogger("polyester.tests.secret_rendering")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.info("configured %s %r", creds, creds, extra={"credentials": creds})
        logger.info("nested %s", AppConfig(name="app", credentials=creds), extra={"credentials": 1})
    finally:
        logger.removeHandler(handler)
    _assert_no_key_material("logging", stream.getvalue())
    assert "key_redaction" in stream.getvalue()


def test_json_without_a_default_refuses_credentials() -> None:
    with pytest.raises(TypeError) as captured:
        json.dumps({"credentials": _credentials()})
    _assert_no_key_material("json error", str(captured.value))


@pytest.mark.parametrize(
    "convert",
    [dataclasses.asdict, dataclasses.astuple],
    ids=["asdict", "astuple"],
)
def test_dataclass_conversion_refuses_credentials(convert) -> None:
    creds = _credentials()
    for subject in (creds, AppConfig(name="app", credentials=creds)):
        with pytest.raises(TypeError) as captured:
            convert(subject)
        _assert_no_key_material("dataclass conversion error", str(captured.value))


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_pickle_refuses_credentials(protocol: int) -> None:
    creds = _credentials()
    for subject in (creds, AppConfig(name="app", credentials=creds), [creds]):
        with pytest.raises((TypeError, pickle.PicklingError)) as captured:
            pickle.dumps(subject, protocol=protocol)
        _assert_no_key_material("pickle error", str(captured.value))


def test_copies_keep_working_without_exposing_the_key() -> None:
    creds = _credentials()
    assert copy.copy(creds) == creds
    replaced = dataclasses.replace(creds, key_id="key_other")
    assert replaced.key_id == "key_other"
    assert replaced.private_key == creds.private_key
    _assert_no_key_material("replace repr", repr(replaced))
