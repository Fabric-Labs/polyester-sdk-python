"""Changelog sections name their product area (0157Z); a cancel of an ended
order reads as already terminal (2343Z)."""

from __future__ import annotations

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester import ORDER_ALREADY_TERMINAL, PolyesterApiError, is_order_already_terminal
from polyester._wire import map_connect_error
from polyester.codecs.decode.changelog import changelog_change_from_proto, changelog_post_from_proto
from polyester.gen.changelog.v1 import changelog_pb2 as pb
from polyester.gen.orders.v1 import orders_pb2
from polyester.services.changelog import _enum_values


def _post(*sections: pb.Section) -> pb.GetPostResponse:
    return pb.GetPostResponse(
        post=pb.Post(summary=pb.PostSummary(slug="2026-11-04"), sections=list(sections))
    )


def test_sections_name_their_product_area() -> None:
    post = changelog_post_from_proto(
        _post(
            pb.Section(heading="Market data", surface=pb.MARKET_DATA),
            pb.Section(heading="QuickSwap", surface=pb.QUICKSWAP),
            pb.Section(heading="Rewards", surface=pb.REWARDS),
            pb.Section(heading="Changes that need your attention"),
        )
    )

    assert [s.surface for s in post.sections] == ["market_data", "quickswap", "rewards", ""]


def test_unknown_surfaces_decode_as_their_number() -> None:
    section = pb.Section(heading="Later")
    section.surface = 42  # type: ignore[assignment]
    post = changelog_post_from_proto(_post(section))
    assert post.sections[0].surface == "42"

    change = pb.Change(id=1, surfaces=[pb.REWARDS])
    change.surfaces.append(43)  # type: ignore[arg-type]
    assert changelog_change_from_proto(change).surfaces == ["rewards", "43"]


def test_new_surfaces_filter_list_changes() -> None:
    assert _enum_values(pb.Surface, ["market_data", "quickswap", "rewards"], "surfaces") == [
        pb.MARKET_DATA,
        pb.QUICKSWAP,
        pb.REWARDS,
    ]


def _order_error(code: int) -> BaseException:
    return map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION, "refused", details=[orders_pb2.ErrorDetail(code=code)]
        )
    )


def test_cancel_of_an_ended_order_reads_already_terminal() -> None:
    ended = _order_error(orders_pb2.ERROR_CODE_ORDER_ALREADY_TERMINAL)

    assert isinstance(ended, PolyesterApiError)
    assert ended.code == ORDER_ALREADY_TERMINAL
    assert is_order_already_terminal(ended)
    assert not is_order_already_terminal(_order_error(orders_pb2.ERROR_CODE_ORDER_UNKNOWN))
    assert not is_order_already_terminal(ValueError("x"))
