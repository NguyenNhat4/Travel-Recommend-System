"""Từ vựng tiện ích có kiểm soát cho filter của /search (FR-SRC-03; kiến trúc Phase A — `must_not` tiện ích).

Hai chiều, cùng một khoá: (1) chuỗi `attributes.amenities` của catalog → khoá (`amenity_keys`), (2) cụm trong câu hỏi → khoá
(`QUERY_CUES`, dùng cho parser phủ định). Khoá trùng tên bảng `docs/spec/data-collection/schema.md` §8.2 khi có (`pool`, `spa`,
`wifi`, `parking`, `shuttle`, `nearBeach`, `privateBeach`, `kidsClub`); khoá thêm (`golf`, `restaurant`, `breakfast`, `bar`, `gym`,
`kitchen`, `balcony`, `terrace`, `bathtub`, `elevator`, `privatePool`, `seaView`, `familyRoom`, `waterPark`, `meetingRoom`,
`petFriendly`, `tennis`) là khoá nội bộ của filter, không đi ra contract `attributes`.

Ngữ nghĩa "có ghi nhận": một unit có khoá k khi ít nhất một chuỗi tiện ích của nó (hoặc của phòng con) khớp cụm của k. Vắng khoá
= không biết, không phải "không có" (spec §2.7 [C2]) — vì vậy filter phủ định chỉ LOẠI unit có khoá, không khẳng định gì về unit
không có khoá (khớp quy ước gán nhãn #3/#7 của `docs/spec/bench/gold-guide.md`).

Cụm đã fold (`lexical.fold`): khớp theo token liên tiếp (" san gon " ⊂ " san gon tai cho nghi "), không khớp substring ("sai gon"
không thành "gon"). Bỏ qua: chuỗi POI quanh khách sạn kèm khoảng cách ("san golf da lat 570 m", "sai gon 880 m"), chuỗi mở đầu
bằng phủ định ("khong co thang may"), và `exclude` riêng từng khoá ("san gon nho" = mini golf, "san gon trong vong 3 km" = gần).
Số đếm trên snapshot 2026-09-23 ghi cạnh từng khoá để người sau biết độ phủ. KHÔNG đụng `catalog/text_builder._FEATURES`:
đổi text catalog là đổi vector toàn bộ. Thuần stdlib.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from .lexical import fold

#: Chuỗi tiện ích thực ra là điểm quanh khách sạn kèm khoảng cách: "… 570 m", "… 1 4 km" (fold đã biến "1.4" thành "1 4").
_POI_DISTANCE = re.compile(r"(?:^|\s)\d+(?:\s\d+)?\s?(?:m|km)$")
#: Chuỗi catalog tự phủ định ("khong co thang may thang may", "khong co wi fi mien phi …") → không tính cho khoá nào.
_NEGATED_PREFIXES = ("khong co ", "khong duoc ", "khong ")


@dataclass(frozen=True)
class Amenity:
    key: str
    catalog: tuple[str, ...]          # cụm (fold) xuất hiện trong chuỗi tiện ích catalog
    query: tuple[str, ...]            # cụm (fold) khách gõ trong câu hỏi
    exclude: tuple[str, ...] = ()     # chuỗi catalog chứa cụm này thì KHÔNG tính cho khoá (dù khớp `catalog`)


AMENITIES: tuple[Amenity, ...] = (
    # hồ bơi: "ho boi ngoai troi" 483 · "be boi" 334 · "be boi ngoai troi" 329 · "nhin ra ho boi" 244 · "ho boi rieng" 111 …
    Amenity("pool", ("ho boi", "be boi", "pool", "swimming"), ("ho boi", "be boi", "pool", "boi"),
            exclude=("boi voi ong tho", "lan bien", "boi loi tang")),
    Amenity("privatePool", ("ho boi rieng", "be boi rieng", "private pool"), ("ho boi rieng", "be boi rieng", "pool rieng")),
    # golf: "san gon tai cho nghi" 128 · "san golf" 1; loại "san gon nho" 31 (mini golf), "san gon trong vong 3 km" 20 (gần)
    Amenity("golf", ("san gon", "san golf", "golf"), ("san golf", "san gon", "golf", "gon"),
            exclude=("san gon nho", "mini golf", "trong vong")),
    Amenity("restaurant", ("nha hang", "restaurant"), ("nha hang", "restaurant")),
    # bữa sáng: "bua sang" 560 · "bua sang tu chon" 365 · … — không phân biệt miễn phí/có phí (khoá `freeBreakfast` của §8.2 cần loại
    # mục có phí; ở đây chỉ nói "có ghi nhận bữa sáng")
    Amenity("breakfast", ("bua sang", "an sang", "breakfast"), ("bua sang", "an sang", "breakfast")),
    Amenity("shuttle", ("dua don san bay", "xe dua don", "dich vu dua don", "shuttle"),
            ("xe dua don san bay", "dua don san bay", "xe dua don", "dua don", "shuttle")),
    Amenity("parking", ("do xe", "dau xe", "parking"), ("cho do xe", "bai do xe", "do xe", "dau xe", "parking")),
    Amenity("spa", ("spa", "massage", "mat xa", "xong hoi", "xong kho", "sauna"),
            ("spa", "massage", "mat xa", "xong hoi", "sauna")),
    Amenity("gym", ("trung tam the duc", "phong gym", "gym", "fitness", "the hinh", "phong tap"),
            ("gym", "phong gym", "phong tap", "the duc", "fitness")),
    Amenity("bar", ("quay bar", "quan bar", "bar", "lounge"), ("quay bar", "quan bar", "bar")),
    Amenity("elevator", ("thang may", "elevator", "lift"), ("thang may", "elevator")),
    Amenity("wifi", ("wifi", "wi fi", "internet"), ("wifi", "wi fi", "internet")),
    # trẻ em: chỉ cơ sở vui chơi ("clb tre em" 12, "khu vui choi tre em" 9), không lấy ghế ăn / nắp ổ cắm
    Amenity("kidsClub", ("clb tre em", "cau lac bo tre em", "khu vui choi tre em", "san choi tre em", "kids club",
                         "co so vat chat cho tre em"),
            ("khu vui choi tre em", "clb tre em", "cau lac bo tre em", "kids club")),
    Amenity("petFriendly", ("thu cung", "vat nuoi", "pet"), ("thu cung", "vat nuoi", "pet")),
    Amenity("waterPark", ("cong vien nuoc", "water park"), ("cong vien nuoc", "water park")),
    Amenity("meetingRoom", ("phong hop", "phong hoi thao", "hoi nghi", "meeting"),
            ("phong hop", "phong hoi nghi", "hoi nghi", "hoi thao", "meeting")),
    # biển: "nhin ra bien" 443 (tầm nhìn) · "giap bien" 400 · "bai bien rieng" 107 · "bai bien" 38
    Amenity("seaView", ("nhin ra bien", "huong bien", "view bien", "ocean view", "sea view"),
            ("view bien", "huong bien", "nhin ra bien", "ocean view", "sea view")),
    Amenity("nearBeach", ("giap bien", "bai bien", "gan bien", "sat bien", "beachfront", "beach"),
            ("gan bien", "sat bien", "giap bien", "bai bien", "beach")),
    Amenity("privateBeach", ("bai bien rieng", "private beach"), ("bai bien rieng", "private beach")),
    # phòng: "ban cong" 1240 · "san hien" 868 · "bon tam" 220 (+ "bon tam hoac voi sen" 496 là tuỳ chọn → loại) · "bep rieng" 433
    Amenity("balcony", ("ban cong", "balcony"), ("ban cong", "balcony")),
    Amenity("terrace", ("san hien", "san thuong", "terrace"), ("san hien", "san thuong", "terrace")),
    Amenity("bathtub", ("bon tam", "bathtub", "jacuzzi"), ("bon tam", "bathtub", "jacuzzi"),
            exclude=("bon tam hoac voi sen",)),
    Amenity("kitchen", ("bep rieng", "nha bep", "bep nho", "bep day du", "bep", "kitchen"),
            ("bep rieng", "nha bep", "bep nho", "bep", "kitchen"),
            exclude=("bep chung", "vat dung nha bep", "dung cu nha bep", "do dung", "bep nuong", "lam bep")),
    Amenity("familyRoom", ("phong gia dinh", "family room"), ("phong gia dinh", "family room")),
    Amenity("tennis", ("san tennis", "tennis"), ("san tennis", "tennis")),
)

KEYS: frozenset[str] = frozenset(a.key for a in AMENITIES)
_BY_KEY = {a.key: a for a in AMENITIES}

#: Cụm trong câu hỏi (fold) → khoá; parser phủ định khớp dài nhất trước. Một cụm chỉ trỏ một khoá (cụm dài — "ho boi rieng" —
#: ưu tiên khoá hẹp hơn vì được khớp trước).
QUERY_CUES: dict[str, str] = {}
for _a in AMENITIES:
    for _cue in _a.query:
        QUERY_CUES.setdefault(_cue, _a.key)
MAX_CUE_TOKENS = max(len(c.split()) for c in QUERY_CUES)


def _contains_phrase(s: str, phrase: str) -> bool:
    return f" {phrase} " in f" {s} "


@lru_cache(maxsize=65536)
def keys_of_string(raw: str) -> frozenset[str]:
    """Khoá của một chuỗi tiện ích catalog (đã hoặc chưa fold). Memo theo chuỗi: catalog thật có ~200k chuỗi nhưng chỉ ~1.900
    chuỗi khác nhau — không memo thì dựng thuộc tính cho 3.183 unit mất ~9 s lúc khởi động."""
    s = fold(raw)
    if not s or _POI_DISTANCE.search(s) or s.startswith(_NEGATED_PREFIXES):
        return frozenset()
    out = set()
    for a in AMENITIES:
        if any(_contains_phrase(s, ex) or ex in s for ex in a.exclude):
            continue
        if any(_contains_phrase(s, ph) for ph in a.catalog):
            out.add(a.key)
    return frozenset(out)


def amenity_keys(strings: Iterable[str | None]) -> frozenset[str]:
    """Hợp khoá của mọi chuỗi tiện ích của một unit (property + phòng con). Chuỗi không khớp gì → bỏ, không báo lỗi."""
    out: set[str] = set()
    for raw in strings:
        if raw:
            out |= keys_of_string(str(raw))
    return frozenset(out)


def amenity(key: str) -> Amenity:
    return _BY_KEY[key]
