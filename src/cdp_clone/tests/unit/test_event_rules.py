from datetime import date, datetime, timezone
from itertools import count

import pytest

from src.cdp_clone.app.domain.events import EventDraft, EventRuleError, prepare_events

NOW = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
PRODUCT = "5febedf3-74ba-5200-a5ec-2a6ab5162acb"


def ids():
    counter = count(1)
    return lambda: f"gen-{next(counter)}"


def purchase(**overrides):
    fields = dict(cdp_user_id="VP0092381", event_name="purchase", event_id="purchase:bi-01",
                  timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc), product_id=PRODUCT, taxonomy="attraction",
                  event_group_id="OFF20260916001", quantity=2, unit_price=1050000, using_date=date(2026, 10, 3))
    return EventDraft(**(fields | overrides))


def test_keeps_given_timestamp_and_event_id():
    [event] = prepare_events([purchase()], NOW, ids())
    assert (event.timestamp, event.event_id, event.cancelled_at) == (datetime(2026, 9, 1, tzinfo=timezone.utc),
                                                                    "purchase:bi-01", None)


def test_fills_missing_timestamp_and_event_id():
    [event] = prepare_events([EventDraft(cdp_user_id="VP1", event_name="search", search_query="Hạ Long")], NOW, ids())
    assert (event.timestamp, event.event_id) == (NOW, "gen-1")


@pytest.mark.parametrize("draft, missing", [
    (EventDraft(cdp_user_id="VP1", event_name="search"), ["searchQuery"]),
    (EventDraft(cdp_user_id="VP1", event_name="product_view", product_id=PRODUCT), ["taxonomy"]),
    (EventDraft(cdp_user_id="VP1", event_name="add_to_cart", product_id=PRODUCT, taxonomy="hotel"), ["quantity"]),
])
def test_required_fields_per_event_name(draft, missing):
    with pytest.raises(EventRuleError) as exc:
        prepare_events([draft], NOW, ids())
    assert exc.value.details["fields"] == missing


def test_purchase_requires_idempotency_key_and_trip_group():
    with pytest.raises(EventRuleError) as exc:
        prepare_events([purchase(event_id=None, event_group_id=None)], NOW, ids())
    assert exc.value.details["fields"] == ["eventId", "eventGroupId"]


def test_reports_position_of_bad_event():
    good = EventDraft(cdp_user_id="VP1", event_name="search", search_query="Phú Quốc")
    with pytest.raises(EventRuleError) as exc:
        prepare_events([good, EventDraft(cdp_user_id="VP1", event_name="search")], NOW, ids())
    assert exc.value.details["eventIndex"] == 1


def test_duplicate_event_id_for_same_user_in_batch_rejected_but_other_user_allowed():
    draft = EventDraft(cdp_user_id="VP1", event_name="search", search_query="Đà Nẵng", event_id="e1")
    with pytest.raises(EventRuleError):
        prepare_events([draft, draft], NOW, ids())
    other = EventDraft(cdp_user_id="VP2", event_name="search", search_query="Đà Nẵng", event_id="e1")
    assert len(prepare_events([draft, other], NOW, ids())) == 2
