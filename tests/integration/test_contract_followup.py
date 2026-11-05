import pytest

from polyester import is_not_found


@pytest.mark.integration
async def test_fee_reserves_and_unknown_trigger(live_client):
    fees = await live_client.fees.get_spot_fee_rates()
    assert fees.fee_rates, "fee response must exercise at least one market"
    for row in fees.fee_rates:
        assert row.reserve_fee_rate_percent != ""
        assert row.post_only_reserve_fee_rate_percent != ""
        assert row.breakdown is not None
        assert isinstance(row.breakdown.account_discounts, list)
    print(f"reserve fields and breakdown returned for {len(fees.fee_rates)} markets")
    trigger_id = str(2**64 - 102)
    with pytest.raises(Exception) as get:
        await live_client.triggers.get(trigger_id=trigger_id)
    with pytest.raises(type(get.value)) as events:
        await live_client.triggers.list_events(trigger_id=trigger_id)
    assert is_not_found(get.value)
    assert is_not_found(events.value)
    print("GetTrigger and ListTriggerEvents both returned not_found")
