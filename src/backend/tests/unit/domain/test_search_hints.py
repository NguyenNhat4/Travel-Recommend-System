"""Query của Agent cho `search_products` (`domain/itinerary/search_hints.py`): bỏ thông tin dạng filter, thêm gợi ý.

Câu nhập lấy nguyên văn từ trace planner thật (LangSmith, gpt-4o-mini và gpt-6-luna, 05–06/10/2026).
"""
import re

import pytest

from src.backend.app.domain.itinerary.search_hints import retrieval_hints, search_query_text

TRACE_QUERIES = [
    ("Khách sạn nghỉ dưỡng thư giãn tại Đà Nẵng cho 2 người lớn, lưu trú ngày 15/10/2026; ưu tiên không gian nghỉ ngơi, "
     "resort hoặc khách sạn tiện nghi", "hotel", "Đà Nẵng",
     "Khách sạn nghỉ dưỡng thư giãn, ưu tiên không gian nghỉ ngơi, resort hoặc khách sạn tiện nghi"),
    ("Khách sạn phù hợp gia đình có trẻ em tại Phú Quốc, cho nhóm 1 người lớn và 24 trẻ em", "hotel", "Phú Quốc",
     "Khách sạn phù hợp gia đình có trẻ em"),
    ("Khách sạn lưu trú phù hợp gia đình có trẻ em tại Hạ Long, cho chuyến đi 2 ngày bắt đầu 2026-10-08", "hotel",
     "Hạ Long", "Khách sạn lưu trú phù hợp gia đình có trẻ em"),
    ("Sân golf và trải nghiệm chơi golf tại Đà Nẵng phù hợp 2 người lớn, chuyến đi ngày 15/10/2026", "golf", "Đà Nẵng",
     "Sân golf và trải nghiệm chơi golf"),
    ("Tour và tham quan, điểm du lịch tại Hà Nội cho chuyến đi 3 ngày", "attraction", "Hà Nội",
     "Tour và tham quan, điểm du lịch"),
]


@pytest.mark.parametrize("query,taxonomy,destination,expected", TRACE_QUERIES)
def test_trace_queries_lose_dates_party_and_destination(query, taxonomy, destination, expected):
    text, removed = search_query_text(query, taxonomy, [], destination)
    assert text == expected
    assert removed > 0
    assert not re.search(r"\d", text)


@pytest.mark.parametrize("query", [
    "khách sạn Nha Trang ngân sách 5 triệu",
    "khách sạn ngân sách khoảng 10tr",
    "resort 4 sao dưới 2tr một đêm",
    "khách sạn 3N2Đ tháng 10",
    "khách sạn 3 ngày 2 đêm cho 2 người lớn 1 trẻ em",
])
def test_budget_stars_duration_and_party_never_reach_the_query(query):
    text, _ = search_query_text(query, "hotel", [], "Nha Trang")
    assert not re.search(r"\d|ngân sách|triệu|người", text, re.I)
    assert text.lower().startswith(("khách sạn", "resort"))


def test_negation_is_cut_because_vectors_ignore_it():
    # Phạm vi phủ định do parser của /search quyết định ("không có hồ bơi, gần biển" phủ cả hai vế).
    text, _ = search_query_text("resort gần biển, không có hồ bơi", "hotel", [], "Nha Trang")
    assert text == "resort gần biển"


def test_empty_query_becomes_the_category_noun_with_hints():
    assert search_query_text("Nha Trang", "hotel", ["hồ bơi"], "Nha Trang") == ("khách sạn, hồ bơi", 1)
    assert search_query_text("Nha Trang", "golf", [], "Nha Trang")[0] == "sân golf"
    # Search không lọc loại: không có danh từ nào đúng cho kết quả hỗn hợp, giữ điểm đến.
    assert search_query_text("Nha Trang", None, [], "Nha Trang")[0] == "Nha Trang"


def test_hints_are_appended_once_and_cleaned_like_the_query():
    text, _ = search_query_text("resort có hồ bơi", "hotel", ["hồ bơi", "biển Nha Trang 2026"], "Nha Trang")
    assert text == "resort có hồ bơi, biển"


def test_city_prefix_of_destination_is_also_removed():
    assert search_query_text("Khách sạn ở Hồ Chí Minh gần trung tâm", "hotel", [], "TP. Hồ Chí Minh")[0] == \
        "Khách sạn gần trung tâm"


def test_words_that_only_look_like_connectors_are_kept():
    assert search_query_text("chợ đêm và nhà khách", "attraction", [], "Nha Trang")[0] == "chợ đêm và nhà khách"


@pytest.mark.parametrize("query,taxonomy,destination,_", TRACE_QUERIES)
def test_sanitizing_twice_changes_nothing(query, taxonomy, destination, _):
    # Plan đã lưu chạy lại qua `validated_plan` phải ra đúng plan cũ (retry dùng lại kết quả theo id).
    hints = ["hồ bơi", "phù hợp gia đình có trẻ nhỏ"]
    once, _ = search_query_text(query, taxonomy, hints, destination)
    assert search_query_text(once, taxonomy, hints, destination) == (once, 0)


def test_query_is_clipped_to_the_contract_limit():
    text, _ = search_query_text("resort " * 200, "hotel", [], "Nha Trang")
    assert len(text) <= 500


def test_hints_follow_catalog_labels_and_skip_filters():
    intent = {"destination": "Nha Trang", "days": 3, "budget": 10_000_000, "startDate": "2026-10-15", "pace": "RELAXED",
              "party": {"type": "FAMILY_WITH_KIDS", "adults": 2, "children": 1}, "interests": ["ẩm thực", "Ẩm Thực"]}
    constraints = {"hotel_attributes": {"pool": True, "oceanView": False, "spa": True}, "star_rating_min": 4,
                   "specific_activity": "VinWonders"}
    assert retrieval_hints(intent, constraints) == {
        "hotel": ["hồ bơi", "spa và massage", "phù hợp gia đình có trẻ nhỏ", "khu vui chơi trẻ em"],
        "attraction": ["VinWonders", "ẩm thực", "gia đình", "trẻ em"],
        "golf": ["VinWonders"],
    }


def test_no_preferences_means_no_hints():
    assert retrieval_hints({"destination": "Huế", "days": 2, "party": {"type": "COUPLE", "adults": 2, "children": 0}},
                           {}) == {}


def test_kids_hint_also_comes_from_constraints():
    assert "hotel" in retrieval_hints({}, {"party_type_hint": "FAMILY_WITH_KIDS"})
    assert "hotel" in retrieval_hints({}, {"children_ages": [5]})
