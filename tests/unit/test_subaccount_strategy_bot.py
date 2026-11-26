"""``Subaccount.strategy_bot``: a sub-account a strategy bot has held, on reads
and on realtime updates."""

from __future__ import annotations

from google.protobuf.json_format import Parse

from polyester.codecs.decode.sub_accounts import subaccount_from_proto
from polyester.codecs.realtime_decode import decode_subaccount_bytes
from polyester.gen.auth.v1 import subaccounts_pb2


def test_strategy_bot_reads_on_replies_and_realtime_updates() -> None:
    msg = subaccounts_pb2.Subaccount(id=7, label="Weekly DCA", strategy_bot=True)
    assert subaccount_from_proto(msg).strategy_bot is True
    assert decode_subaccount_bytes(msg.SerializeToString()).strategy_bot is True


def test_strategy_bot_defaults_to_false_when_json_omits_it() -> None:
    parsed = Parse('{"id": "7", "label": "desk"}', subaccounts_pb2.Subaccount())
    assert subaccount_from_proto(parsed).strategy_bot is False
    parsed = Parse('{"id": "7", "strategyBot": true}', subaccounts_pb2.Subaccount())
    assert subaccount_from_proto(parsed).strategy_bot is True
