from polyester.gen.marketoverview.v1.marketoverview_pb2 import ListMarketOverviewRequest


def test_market_overview_list_request_uses_page_token_not_page() -> None:
    request = ListMarketOverviewRequest(
        limit=25,
        page_token="abc",
        include_sparklines=False,
    )
    request.symbols.extend(["BTC-USDT"])
    assert request.page_token == "abc"
    assert request.limit == 25
    assert list(request.symbols) == ["BTC-USDT"]
