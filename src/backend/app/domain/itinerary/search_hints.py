"""Query của `search_products` do Agent lập: chỉ mang phần ngữ nghĩa, không mang thông tin dạng filter. Thuần Python.

Text query của /search được dùng hai lần: embed/BM25 để xếp hạng, và query plan đọc ra filter ("ngân sách 5 triệu" →
trần giá **từng sản phẩm**, "2 người lớn" → sức chứa). Document đem embed không có giá, ngày hay số người
(`domain/catalog/text_builder.py`), nên các cụm đó chỉ làm nhiễu xếp hạng; còn khi cờ filter-từ-câu bật thì ngân sách
cả chuyến thành trần giá từng sản phẩm — đúng điều `_validated_args` tránh khi xoá `priceMax`. Thông tin dạng filter đi
qua tham số tool hoặc hậu kiểm ở `application/itinerary/retrieval.py`.

Ngược lại, sở thích (tiện ích khách sạn, gia đình có trẻ nhỏ, hoạt động yêu thích, tên sản phẩm bắt buộc) chỉ được hậu
kiểm trên top-K, nên phải có trong query để kéo đúng sản phẩm vào top-K. Gợi ý dùng đúng nhãn text_builder ghi vào document.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from ..search.constraints import parse_negation, parse_numeric, parse_party, remove_spans
from . import preferences
from .normalization import fold

#: Danh từ loại sản phẩm: query rỗng sau khi làm sạch thì dùng nó (kèm gợi ý) thay vì tên điểm đến.
TAXONOMY_NOUNS = {"hotel": "khách sạn", "attraction": "điểm tham quan", "golf": "sân golf", "combo": "combo",
                  "flight": "vé máy bay"}
MAX_QUERY_CHARS = 500  # SearchRequest.query maxLength

#: `constraints.hotel_attributes` → nhãn trong text embed (`text_builder._FEATURES`/`enrich`). Chỉ giá trị true:
#: false là phủ định, đã hậu kiểm, và vector không hiểu phủ định.
_HOTEL_ATTRIBUTE_LABELS = (
    ("pool", "hồ bơi"), ("kidsPool", "hồ bơi"), ("oceanView", "hướng biển"), ("nearBeach", "gần bãi biển"),
    ("privateBeach", "bãi biển riêng"), ("spa", "spa và massage"), ("kidsClub", "khu vui chơi trẻ em"),
    ("familyFriendly", "phù hợp gia đình có trẻ nhỏ"),
)
_HOTEL_KIDS = ("phù hợp gia đình có trẻ nhỏ", "khu vui chơi trẻ em")
_ATTRACTION_KIDS = ("gia đình", "trẻ em")

_CUE = r"(?:(?:lưu trú|khởi hành|bắt đầu|xuất phát|đi|từ|vào|trong|cho)\s+)?"
_DATE = re.compile(
    rf"\b{_CUE}(?:ngày\s+)?(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?"
    r"|(?:ngày\s+\d{1,2}\s+)?tháng\s+\d{1,2}(?:\s+năm\s+\d{4}|[/-]\d{4})?|ngày\s+\d{1,2}(?![\d/-]))", re.I)
_DURATION = re.compile(
    r"\b(?:(?:cho\s+)?(?:chuyến đi|kỳ nghỉ|lịch trình|chuyến)\s+)?(?:trong\s+)?"
    r"\d+\s*(?:ngày|đêm|n|đ)(?:\s*\d+\s*(?:đêm|đ))?\b", re.I)
_MONEY = re.compile(r"\b(?:ngân sách|chi phí|tổng)?\s*(?:khoảng|tầm|tối đa|dưới|là)?\s*"
                    r"\d[\d.,]*\s*(?:triệu|tr|nghìn|ngàn|k|đồng|vnđ|vnd)\b", re.I)
_BUDGET_WORD = re.compile(r"\bngân sách\b(?:\s+(?:khoảng|tầm|tối đa|là|dưới|không quá))?", re.I)
_DIGITS = re.compile(r"(?<!\w)\d[\d.,/:-]*\w*")
#: Từ nối còn treo ở cuối một vế sau khi cắt ("cho" của "cho 2 người lớn", "tại" của "tại Đà Nẵng"). So sánh trên fold.
_DANGLING = tuple(sorted({fold(w) for w in (
    "cho", "cho nhóm", "nhóm", "tại", "ở", "vào", "trong", "với", "và", "hoặc", "phù hợp", "dành cho", "lưu trú",
    "chuyến đi", "chuyến", "bắt đầu", "khởi hành", "xuất phát", "từ", "đến", "khoảng", "ngân sách", "đi", "của", "là",
    "gồm", "dịp", "kỳ nghỉ", "gần", "khu vực")}, key=lambda w: -len(w.split())))


def _has_kids(intent: Mapping[str, Any], constraints: Mapping[str, Any]) -> bool:
    party = intent.get("party") or {}
    return (party.get("type") == "FAMILY_WITH_KIDS" or (party.get("children") or 0) > 0
            or constraints.get("party_type_hint") == "FAMILY_WITH_KIDS" or bool(constraints.get("children_ages")))


def _unique(values) -> list[str]:
    seen: set[str] = set()
    out = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and fold(text) not in seen:
            seen.add(fold(text))
            out.append(text)
    return out


def retrieval_hints(intent: Mapping[str, Any], constraints: Mapping[str, Any]) -> dict[str, list[str]]:
    """Cụm ngữ nghĩa nên có trong query theo taxonomy; taxonomy không có gợi ý thì không có khoá.

    Không đưa vào: số (ngân sách, ngày, số người, sao), điểm đến, phủ định và `pace` (chỉ ảnh hưởng mật độ lịch).
    """
    kids = _has_kids(intent, constraints)
    attributes = constraints.get("hotel_attributes") or {}
    activity = constraints.get("specific_activity")
    interests = [value for value in intent.get("interests") or [] if isinstance(value, str)]
    hints = {
        # Sở thích khách sạn trong `interests` (FR-AGT-06) là ưu tiên: chỉ kéo khách sạn hợp vào top-K, không lọc.
        "hotel": _unique([constraints.get("specific_hotel"),
                          *(label for key, label in _HOTEL_ATTRIBUTE_LABELS if attributes.get(key) is True),
                          *preferences.hints(preferences.from_interests(interests)),
                          *(_HOTEL_KIDS if kids else ())]),
        "attraction": _unique([activity, *(value for value in interests if not preferences.is_preference(value)),
                               *(_ATTRACTION_KIDS if kids else ())]),
        # Hậu kiểm bắt tên `specific_activity` cả ở golf (`retrieval.py`), nên golf cũng tìm theo tên đó.
        "golf": _unique([activity]),
    }
    return {taxonomy: values for taxonomy, values in hints.items() if values}


def _destination_pattern(destination: str | None) -> re.Pattern | None:
    if not destination:
        return None
    names = {destination, re.sub(r"^(?:TP\.?|Thành phố)\s*", "", destination, flags=re.I)}
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True) if name)
    return re.compile(rf"(?:\b(?:tại|ở|gần|đến|đi|khu vực|thành phố)\s+)?(?<!\w)(?:{alternatives})(?!\w)", re.I)


def _trim(clause: str) -> str:
    words = clause.split()
    changed = True
    while words and changed:
        changed = False
        for phrase in _DANGLING:
            size = len(phrase.split())
            if len(words) >= size and fold(" ".join(words[-size:])) == phrase:
                del words[-size:]
                changed = True
                break
    return " ".join(words)


def _strip(text: str, destination: str | None) -> tuple[str, int]:
    """(text đã bỏ mọi cụm dạng filter, số đoạn đã cắt)."""
    numeric = parse_numeric(text)
    party = parse_party(text, numeric.spans)
    negation = parse_negation(text, (*numeric.spans, *party.spans))
    spans = [*numeric.spans, *party.spans, *negation.spans]
    patterns = [_DATE, _DURATION, _MONEY, _BUDGET_WORD, _DIGITS]
    place = _destination_pattern(destination)
    if place is not None:
        patterns.append(place)
    for pattern in patterns:
        spans.extend(match.span() for match in pattern.finditer(text) if match.group().strip())
    cleaned = remove_spans(text, spans)
    clauses = [_trim(clause.strip(" .!?-–:")) for clause in re.split(r"[,;]", cleaned)]
    return ", ".join(clause for clause in clauses if clause), len(spans)


def _clip(text: str) -> str:
    if len(text) <= MAX_QUERY_CHARS:
        return text
    cut = text[:MAX_QUERY_CHARS]
    return cut[:cut.rfind(" ")] if " " in cut else cut


def search_query_text(query: str, taxonomy: str | None, hints: list[str] | None = None,
                      destination: str | None = None) -> tuple[str, int]:
    """Query đã làm sạch cho một lời gọi `search_products`, và số đoạn dạng filter đã cắt khỏi query gốc.

    Bỏ giá/ngân sách, sao, số người, phủ định (tái dùng parser của /search), ngày, số ngày/đêm, mọi số còn sót và tên
    điểm đến (đã có tham số `destination`); thêm gợi ý của taxonomy chưa có trong query. Rỗng thì dùng danh từ loại kèm
    gợi ý; search không lọc loại thì dùng điểm đến. Lũy đẳng: chạy lại trên kết quả cho ra đúng kết quả đó, để plan đã
    lưu chạy lại vẫn là plan cũ.
    """
    text, removed = _strip(query, destination)
    extras = []
    for hint in hints or []:
        cleaned, _ = _strip(hint, destination)
        if cleaned and fold(cleaned) not in fold(", ".join([text, *extras])):
            extras.append(cleaned)
    if not text and taxonomy in TAXONOMY_NOUNS:
        text = TAXONOMY_NOUNS[taxonomy]
    text = ", ".join(part for part in (text, *extras) if part)
    if not text:
        text = destination or " ".join(query.split())
    return _clip(text), removed
