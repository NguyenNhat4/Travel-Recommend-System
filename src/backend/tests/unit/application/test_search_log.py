"""Log tìm kiếm (SEARCH_LOG_QUERIES, kiến trúc search §11): dựng dòng `app.search_logs` từ response /search và ghi nền qua
hàng đợi có trần — không chặn, không ném lỗi, đầy thì bỏ và đếm."""
import threading

from src.backend.app.application.ports.search_logs import SearchLogEntry
from src.backend.app.application.search.search_log import SearchLogRecorder, search_log_entry

RESPONSE = {
    "results": [{"productId": "11111111-1111-4111-8111-111111111111"}, {"productId": "H2"}],
    "total": 7,
    "appliedFilters": {"hard": {"priceMax": 2000000, "priceSource": "param", "minOccupancy": 3, "partySource": "param"},
                       "soft": {"starRatingMin": 4}},
    "diagnostics": {"modelVersion": "embed-multilingual-v3.0:t5", "latencyMs": 42,
                    "queryPlan": {"confidence": 0.75, "fallbackReasons": ["weak_taxonomy_cue"]}},
}


def test_entry_takes_hard_filters_confidence_and_request_filters():
    e = search_log_entry("resort Nha Trang", RESPONSE, request_filters={"taxonomy": "hotel", "destination": None},
                         cdp_user_id="cdp-1", session_id="s-1")
    assert e == SearchLogEntry(
        query="resort Nha Trang", result_count=7, model_version="embed-multilingual-v3.0:t5",
        result_product_ids=("11111111-1111-4111-8111-111111111111", "H2"),
        filters={"taxonomy": "hotel", "priceMax": 2000000, "priceSource": "param", "minOccupancy": 3,
                 "partySource": "param", "confidence": 0.75},
        latency_ms=42, cdp_user_id="cdp-1", session_id="s-1")


def test_entry_without_any_filter_is_null_filters():
    e = search_log_entry("biển", {"results": [], "total": 0, "diagnostics": {"modelVersion": "m"}})
    assert e.filters is None and e.result_product_ids == () and e.latency_ms is None and e.cdp_user_id is None
    assert search_log_entry("biển", {"results": [], "total": 0, "diagnostics": {}}).model_version == "none"


class _Writer:
    def __init__(self, *, fail=False, gate: threading.Event | None = None):
        self.rows, self.fail, self.gate = [], fail, gate

    def write(self, entry):
        if self.gate is not None:
            self.gate.wait(5)
        if self.fail:
            raise RuntimeError("db down: Key (cdp_user_id)=(cdp-1)")
        self.rows.append(entry)


def _entry(q="q"):
    return SearchLogEntry(query=q, result_count=0, model_version="m")


def test_recorder_writes_in_background():
    w = _Writer()
    rec = SearchLogRecorder(w)
    assert rec.record(_entry("a")) and rec.record(_entry("b"))
    rec.close(wait=True)
    assert [r.query for r in w.rows] == ["a", "b"] and rec.stats() == {"written": 2, "failed": 0, "dropped": 0}


def test_recorder_swallows_writer_errors():
    rec = SearchLogRecorder(_Writer(fail=True))
    assert rec.record(_entry()) is True
    rec.close(wait=True)
    assert rec.stats() == {"written": 0, "failed": 1, "dropped": 0}


def test_recorder_drops_when_queue_is_full_or_closed():
    gate = threading.Event()
    w = _Writer(gate=gate)
    rec = SearchLogRecorder(w, max_pending=1)
    assert rec.record(_entry("first")) is True
    assert rec.record(_entry("second")) is False          # một dòng đang chờ ghi → dòng sau bị bỏ, không chặn request
    gate.set()
    rec.close(wait=True)
    assert [r.query for r in w.rows] == ["first"] and rec.stats()["dropped"] == 1
    assert rec.record(_entry("late")) is False and rec.stats()["dropped"] == 2
