"""Parser ràng buộc cứng rút từ câu truy vấn của /search (FR-SRC-03; kiến trúc Phase A — spec tích hợp §2.2, §2.5):
F3 phủ định tiện ích / thương hiệu / loại sản phẩm, F4 taxonomy từ cue ngành dọc, F5 vai trò nơi đi/nơi đến của vé máy bay,
F6 giá/sao, số khách (kiến trúc §6 "Room child: occupancy").

Các parser chạy trên text ĐÃ chuẩn hoá (`QueryNormalizer`: NFC, địa danh đã về tên catalog, "2tr" đã thành "2 triệu"),
khớp trên token đã fold (`lexical.fold`) nhưng trả về span ký tự trên text đầu vào: mỗi parser liệt kê đúng những đoạn
nó đã "tiêu", để tầng gọi cắt chúng khỏi text BM25 (`remove_spans`) — điều kiện đã thành filter thì không được xếp hạng
lần hai qua lexical. Không dùng `lexical.query_tokens` để nhận toán tử: STOPWORDS chứa `tu`/`den`/`co`.

Nguyên tắc chung: không bịa — cụm sau cue phủ định không trỏ tới khoá nào trong `amenities.QUERY_CUES` thì ghi `unresolved`,
"N triệu" không có toán tử thì `unresolved`, không bao giờ suy nơi đi còn thiếu. Mọi hàm thuần, chỉ stdlib.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .amenities import MAX_CUE_TOKENS, QUERY_CUES
from .destination import FLIGHT_CUES
from .lexical import fold

Span = tuple[int, int]

# Token: số có phần lẻ/phân cách nghìn (và hậu tố dính như "2tr", "500k") hoặc `\w+` như `normalize._spans` — token chữ
# ra cùng offset với `NormalizedQuery.destination_spans`.
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*\w*|\w+")
_NUMBER = re.compile(r"^(\d+(?:[.,]\d+)*)([a-z]*)$")


@dataclass(frozen=True)
class _Tok:
    start: int
    end: int
    raw: str
    folded: str


def _toks(text: str) -> list[_Tok]:
    return [_Tok(m.start(), m.end(), m.group(), fold(m.group())) for m in _TOKEN.finditer(text)]


def _gap(text: str, toks: list[_Tok], i: int) -> str:
    """Chuỗi giữa token i-1 và token i (đầu câu nếu i = 0): nơi nằm dấu câu, ký hiệu `<=`, `-`."""
    return text[toks[i - 1].end if i > 0 else 0:toks[i].start]


def _overlaps(span: Span, ranges: Iterable[Span]) -> bool:
    return any(s < span[1] and span[0] < e for s, e in ranges)


def _phrase_before(toks: list[_Tok], i: int, table: Iterable[str], max_n: int = 4) -> tuple[int, str] | None:
    """Cụm dài nhất trong `table` kết thúc ngay trước token i → (chỉ số token đầu, cụm)."""
    for n in range(min(max_n, i), 0, -1):
        key = " ".join(t.folded for t in toks[i - n:i])
        if key in table:
            return i - n, key
    return None


def _phrase_at(toks: list[_Tok], i: int, table: Iterable[str], max_n: int) -> tuple[int, str] | None:
    """Cụm dài nhất trong `table` bắt đầu tại token i → (số token, cụm)."""
    for n in range(min(max_n, len(toks) - i), 0, -1):
        key = " ".join(t.folded for t in toks[i:i + n])
        if key in table:
            return n, key
    return None


def remove_spans(text: str, spans: Iterable[Span]) -> str:
    """Cắt các đoạn ký tự khỏi text (gộp đoạn chồng nhau), gộp khoảng trắng — dựng text BM25 không còn cụm đã thành filter."""
    merged: list[list[int]] = []
    for s, e in sorted((s, e) for s, e in spans if e > s):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    for s, e in reversed(merged):
        text = text[:s] + " " + text[e:]
    text = re.sub(r"\s+([,;.!?])", r"\1", " ".join(text.split()))
    return re.sub(r",(\s*,)+", ",", text).strip(" ,;")


# ====================================================================================== F6: giá và hạng sao
_MONEY_UNITS = {"trieu": 1_000_000, "tr": 1_000_000, "m": 1_000_000, "nghin": 1_000, "ngan": 1_000, "k": 1_000,
                "vnd": 1, "d": 1, "dong": 1}
#: Đơn vị chỉ nhận khi DÍNH vào số ("2m" = 2 triệu); đứng tách ("500 m", "300 m từ biển") là mét → không phải tiền.
_ATTACHED_ONLY_UNITS = frozenset({"m"})
#: Đuôi tiền tệ / đơn vị thời gian nuốt vào span sau số tiền: "2 triệu đồng", "2 triệu/đêm", "2 triệu một đêm".
_CURRENCY_TAIL = frozenset({"dong", "vnd", "d"})
_PER_UNIT_WORDS = frozenset({"dem", "ngay"})
_PER_UNIT_PREFIX = frozenset({"mot", "moi", "1"})
_BARE_VND_MIN = 10_000                  # số trần không đơn vị từ đây coi là VND
_PRICE_MAX_OPS = frozenset({"duoi", "khong qua", "toi da", "toi da la", "khong vuot", "khong vuot qua", "ngan sach",
                            "ngan sach toi da", "ngan sach khong qua", "ngan sach duoi", "gia toi da", "gia khong qua",
                            "gia duoi", "tam", "khoang", "khong den", "chua den", "chua toi", "it hon", "thap hon",
                            "re hon", "max"})
_PRICE_MIN_OPS = frozenset({"tu", "gia tu", "tren", "gia tren", "toi thieu", "it nhat", "hon", "cao hon", "min"})
_RANGE_OPS = frozenset({"tu", "gia tu", "khoang", "tam"})
_SYMBOL_MAX = frozenset({"<=", "<", "=<", "~"})
_SYMBOL_MIN = frozenset({">=", ">", "=>"})
_SYMBOL_TAIL = re.compile(r"(<=|>=|=<|=>|<|>|~)\s*$")
_TRAIL_MAX = ("tro xuong", "tro lai")
_TRAIL_MIN = ("tro len",)
_RANGE_LINKS = frozenset({"den", "toi"})
_STAR_WORDS = frozenset({"sao", "star", "stars"})
_STAR_MIN_OPS = frozenset({"tu", "it nhat", "toi thieu", "khong duoi", "tren", "hang", "chuan", "tieu chuan"})
_STAR_DROP_OPS = frozenset({"khong nhat thiet", "khong nhat thiet phai", "khong can", "khong can phai",
                            "khong bat buoc", "khong yeu cau"})
_STAR_UNRESOLVED_OPS = frozenset({"duoi", "toi da", "khong qua", "khong den"})


@dataclass(frozen=True)
class NumericParse:
    price_min: int | None = None
    price_max: int | None = None
    star_min: float | None = None
    spans: tuple[Span, ...] = ()            # mọi đoạn đã tiêu: toán tử + số + đơn vị (kể cả dropped/unresolved)
    dropped: tuple[str, ...] = ()           # cụm bị người dùng tự nới ("không nhất thiết 5 sao") — không thành filter
    unresolved: tuple[str, ...] = ()        # có số nhưng không biết chiều ("2 triệu", "dưới 4 sao")


def _number(tok: _Tok) -> tuple[str, str] | None:
    """(phần số, hậu tố đơn vị dính liền đã fold) nếu token là số; "2tr" → ("2", "tr")."""
    m = _NUMBER.match(tok.raw.lower())
    return (m.group(1), fold(m.group(2))) if m else None


def _value(num: str, has_unit: bool) -> float | None:
    """"1.5" → 1.5 · "1.500.000" → 1500000 · "500.000" không đơn vị → 500000 · "1.500 triệu" → 1.5."""
    parts = re.split(r"[.,]", num)
    if len(parts) == 1:
        return float(parts[0])
    if all(len(p) == 3 for p in parts[1:]) and (len(parts) >= 3 or not has_unit):
        return float("".join(parts))
    if len(parts) == 2:
        return float(f"{parts[0]}.{parts[1]}")
    return None


def _money_at(toks: list[_Tok], i: int) -> tuple[float, int | None, int] | None:
    """Số tiền bắt đầu tại token i → (giá trị, bội số hoặc None nếu trần không đơn vị, chỉ số token cuối)."""
    num = _number(toks[i])
    if num is None:
        return None
    digits, suffix = num
    # Đơn vị VND ("500.000 đồng", "500.000đ") không đổi thang: dấu chấm vẫn là phân cách nghìn như số trần.
    if suffix in _MONEY_UNITS:
        v = _value(digits, _MONEY_UNITS[suffix] != 1)
        return (v, _MONEY_UNITS[suffix], i) if v else None
    if suffix:
        return None
    if i + 1 < len(toks) and toks[i + 1].folded in _MONEY_UNITS:
        if toks[i + 1].folded in _ATTACHED_ONLY_UNITS:
            return None                             # "500 m" là khoảng cách, không tiêu số
        unit = _MONEY_UNITS[toks[i + 1].folded]
        v = _value(digits, unit != 1)
        return (v, unit, i + 1) if v else None
    v = _value(digits, False)
    return (v, None, i) if v and v >= _BARE_VND_MIN else None


def _absorb_unit_tail(text: str, toks: list[_Tok], end: int) -> int:
    """Nuốt "đồng"/"VND"/"đ" rồi "/đêm" · "một đêm" · "mỗi ngày" đứng ngay sau số tiền → token cuối+1 mới.

    Chạy trước khi xét đuôi "trở xuống"/"trở lên" để "2 triệu đồng trở xuống" vẫn ra trần giá và span không bỏ sót đơn vị.
    """
    if end < len(toks) and toks[end].folded in _CURRENCY_TAIL:
        end += 1
    if end < len(toks) and toks[end].folded in _PER_UNIT_WORDS and "/" in _gap(text, toks, end):
        end += 1
    elif end + 1 < len(toks) and toks[end].folded in _PER_UNIT_PREFIX and toks[end + 1].folded in _PER_UNIT_WORDS:
        end += 2
    return end


def _is_plain_number(toks: list[_Tok], i: int) -> float | None:
    num = _number(toks[i]) if i < len(toks) else None
    if num is None or num[1]:
        return None
    return _value(num[0], False)


def _trail(toks: list[_Tok], j: int, phrases: Iterable[str]) -> int:
    """Số token của cụm đuôi ("trở xuống") bắt đầu tại j, 0 nếu không có."""
    for ph in phrases:
        n = len(ph.split())
        if " ".join(t.folded for t in toks[j:j + n]) == ph:
            return n
    return 0


def _parse_star(text: str, toks: list[_Tok], i: int) -> tuple[dict, int, int] | None:
    """Token i là số, token i+1 là "sao" → (kết quả, token đầu, token cuối+1)."""
    v = _is_plain_number(toks, i)
    if v is None or not 1 <= v <= 5:
        return None
    start, end = i, i + 2
    # "4-5 sao" / "4 đến 5 sao" → lấy mốc dưới
    if i >= 1 and _is_plain_number(toks, i - 1) is not None and any(c in _gap(text, toks, i) for c in "-–"):
        v, start = _is_plain_number(toks, i - 1), i - 1
    elif i >= 2 and toks[i - 1].folded in _RANGE_LINKS and _is_plain_number(toks, i - 2) is not None:
        v, start = _is_plain_number(toks, i - 2), i - 2
    end += _trail(toks, end, _TRAIL_MIN)
    op = _phrase_before(toks, start, _STAR_DROP_OPS | _STAR_UNRESOLVED_OPS | _STAR_MIN_OPS)
    if op is None:
        return {"star_min": v}, start, end
    start, key = op
    if key in _STAR_DROP_OPS:
        return {"dropped": True}, start, end
    if key in _STAR_UNRESOLVED_OPS:
        return {"unresolved": True}, start, end
    return {"star_min": v}, start, end


def _parse_money(text: str, toks: list[_Tok], i: int) -> tuple[dict, int, int] | None:
    """Số tiền (hoặc khoảng A–B) bắt đầu tại token i → ({price_min, price_max} hoặc {unresolved}, token đầu, token cuối+1)."""
    first = _money_at(toks, i)
    lo = _is_plain_number(toks, i)
    # Khoảng "từ A đến B triệu" · "A - B triệu" · "1 triệu đến 2 triệu": A có thể không mang đơn vị, lấy đơn vị của B
    j = _absorb_unit_tail(text, toks, first[2] + 1) if first else i + 1
    link = j < len(toks) and (toks[j].folded in _RANGE_LINKS or any(c in _gap(text, toks, j) for c in "-–~"))
    k = j + 1 if j < len(toks) and toks[j].folded in _RANGE_LINKS else j
    second = _money_at(toks, k) if link and k < len(toks) else None
    if second and second[1] is not None and (first or lo):
        a = (first[0] * (first[1] or 1)) if first and first[1] else (lo or first[0]) * second[1]
        b = second[0] * second[1]
        start = i
        op = _phrase_before(toks, i, _RANGE_OPS | _PRICE_MAX_OPS | _PRICE_MIN_OPS)
        if op:
            start = op[0]
        return {"price_min": int(min(a, b)), "price_max": int(max(a, b))}, start, _absorb_unit_tail(text, toks, second[2] + 1)
    if first is None:
        return None
    amount = int(first[0] * (first[1] or 1))
    start, end = i, _absorb_unit_tail(text, toks, first[2] + 1)
    sym = _gap(text, toks, i).strip()
    op = _phrase_before(toks, i, _PRICE_MAX_OPS | _PRICE_MIN_OPS)
    if op:
        start, key = op
        side = "price_max" if key in _PRICE_MAX_OPS else "price_min"
    elif sym in _SYMBOL_MAX:
        side = "price_max"
    elif sym in _SYMBOL_MIN:
        side = "price_min"
    elif _trail(toks, end, _TRAIL_MAX):
        side = "price_max"
    elif _trail(toks, end, _TRAIL_MIN):
        side = "price_min"
    else:
        return {"unresolved": True}, start, end
    end += _trail(toks, end, _TRAIL_MAX) or _trail(toks, end, _TRAIL_MIN)
    return {side: amount}, start, end


def parse_numeric(text: str) -> NumericParse:
    """F6: trần/sàn giá (VND) và hạng sao tối thiểu. Toán tử nhận trên token fold; "gia re" không ra gì."""
    toks = _toks(text)
    out: dict = {}
    spans, dropped, unresolved = [], [], []
    i = 0
    while i < len(toks):
        hit = None
        if _number(toks[i]) is not None:
            if i + 1 < len(toks) and toks[i + 1].folded in _STAR_WORDS:
                hit = _parse_star(text, toks, i)
            if hit is None:
                hit = _parse_money(text, toks, i)
        if hit is None:
            i += 1
            continue
        res, s, e = hit
        lead = _SYMBOL_TAIL.search(_gap(text, toks, s))      # "<= 500.000": kéo span về tới ký hiệu
        span = (lead.start() + (toks[s - 1].end if s > 0 else 0) if lead else toks[s].start, toks[e - 1].end)
        spans.append(span)
        phrase = text[span[0]:span[1]]
        if res.get("dropped"):
            dropped.append(phrase)
        elif res.get("unresolved"):
            unresolved.append(phrase)
        else:
            for k, v in res.items():
                out.setdefault(k, v)
        i = e
    return NumericParse(out.get("price_min"), out.get("price_max"), out.get("star_min"),
                        tuple(spans), tuple(dropped), tuple(unresolved))


# ====================================================================================== F3: phủ định tiện ích
#: Cue cứng (fold) → tiện ích sau nó bị loại. "khong" và "tru" trần chỉ khi NGAY SAU là cụm tiện ích/thương hiệu
#: ("không gian", "lưu trú" không bao giờ là cue).
_HARD_CUES = frozenset({"khong co", "khong ghi nhan", "khong gom", "khong bao gom", "khong kem", "ngoai tru", "tru",
                        "khong phai", "khong lay", "khong muon", "khong"})
_BARE_CUES = frozenset({"khong", "tru"})
#: Cue mềm: người dùng nới điều kiện ("không cần gần biển") — bỏ điều kiện, không lọc.
_SOFT_CUES = frozenset({"khong can", "khong nhat thiet", "khong bat buoc", "khong yeu cau", "khong can phai",
                        "khong nhat thiet phai"})
_CUE_MAX = max(len(c.split()) for c in _HARD_CUES | _SOFT_CUES)
#: Cue trần phải khớp CHỮ GỐC: "trú"/"trù" fold cũng ra "tru", "khống" ra "khong". Không dấu "tru" đứng sau "lưu"/"cư"
#: ("luu tru", "cu tru") cũng không phải "trừ".
_BARE_RAW = {"khong": frozenset({"không", "khong"}), "tru": frozenset({"trừ", "tru"})}
_TRU_PREV_BLOCK = frozenset({"luu", "cu"})
#: Sau cue mềm có thể đứng "phải"/"có" rồi mới tới tiện ích ("không nhất thiết phải có hồ bơi") — bước qua trước khi thu.
_SOFT_LEAD = ("phai", "co")
#: Sau cue mà gặp từ này thì là so sánh số/khoảng cách ("không quá 2 triệu", "không xa trung tâm"), không phủ định.
_NOT_NEGATION_NEXT = frozenset({"qua", "duoi", "hon", "vuot", "xa", "den", "toi"})
_SCOPE_STOP = frozenset({"nhung", "ma", "co"})
_FILLER_STOP = _SCOPE_STOP | frozenset({"o", "tai", "gan", "cho", "voi", "va", "hoac", "cua", "de", "la"})
_CONNECTORS = frozenset({"va", "hoac", "hay"})
_MAX_FILLER = 2
_SCOPE_WINDOW = 4
#: Thương hiệu có dữ liệu để lọc theo tên (fold → tên hiển thị).
BRAND_CUES: dict[str, str] = {"vinpearl": "Vinpearl"}
#: Loại phần tử trong phạm vi phủ định (`_scope`).
_AMENITY, _BRAND, _VERTICAL = "amenity", "brand", "vertical"
#: Dấu câu giữa cue phủ định và cue loại sản phẩm đứng đầu phạm vi → hai ý khác nhau ("có phòng không, khách sạn ở …").
_VERTICAL_GAP_STOP = ",;.?!"
#: Thành phần combo bị phủ định khi câu có cue combo dương ("combo … không gồm vé máy bay"; kiến trúc §4 `includes_flight=false`).
FLAG_INCLUDES_FLIGHT, FLAG_INCLUDES_HOTEL = "includesFlight", "includesHotel"


@dataclass(frozen=True)
class MustNot:
    key: str                # khoá trong amenities.KEYS
    phrase: str             # chữ gốc trong câu ("hồ bơi")
    span: Span


@dataclass(frozen=True)
class NegationParse:
    must_not: tuple[MustNot, ...] = ()
    must_not_brands: tuple[str, ...] = ()
    soft_dropped: tuple[str, ...] = ()      # "không cần gần biển": bỏ điều kiện, không lọc
    unresolved: tuple[str, ...] = ()        # cụm sau cue cứng không trỏ tới tiện ích nào ("view đẹp")
    spans: tuple[Span, ...] = ()            # cue + phạm vi đã tiêu
    must_not_taxonomies: tuple[str, ...] = ()   # loại sản phẩm bị loại rõ: "không lấy combo", "vé lẻ" → combo (rubric v4 #10)
    must_not_flags: tuple[str, ...] = ()        # thành phần combo bị loại: "combo … không gồm vé máy bay" → includesFlight

    @property
    def must_not_keys(self) -> frozenset[str]:
        return frozenset(m.key for m in self.must_not)


def _gap_has(text: str, toks: list[_Tok], i: int, chars: str) -> bool:
    return any(c in _gap(text, toks, i) for c in chars)


def _scope(text: str, toks: list[_Tok], j: int, protected: tuple[Span, ...], allow_filler: bool):
    """Thu tiện ích/thương hiệu/loại sản phẩm sau cue từ token j → (danh sách (loại, giá trị, token đầu, token cuối+1),
    token cuối+1).

    Loại `amenity` (giá trị = khoá tiện ích), `brand` (tên hiển thị), `vertical` (taxonomy của cue F4: "không lấy combo",
    "không gồm vé máy bay"). Tiện ích khớp trước ("sân golf" là tiện ích, không phải ngành golf). Cue loại sản phẩm chỉ nhận
    khi phạm vi chưa có tiện ích/thương hiệu và không bị dấu câu tách khỏi cue — "không có hồ bơi, phòng rộng" vẫn chỉ là hồ
    bơi. Nối qua `và`/`hoặc`/dấu phẩy/gạch chéo; dừng ở nhưng|mà|có, `;`, `.`, đoạn đã tiêu bởi parser số. Chưa thấy phần tử
    nào thì cho phép tối đa 2 token đệm ("không có sẵn hồ bơi").
    """
    found: list[tuple[str, str, int, int]] = []
    k, filler = j, 0
    while k < len(toks):
        if _overlaps((toks[k].start, toks[k].end), protected) or toks[k].folded in _SCOPE_STOP:
            break
        if k > j and _gap_has(text, toks, k, ";."):
            break
        hit = _phrase_at(toks, k, QUERY_CUES, MAX_CUE_TOKENS)
        vhit = None if hit or toks[k].folded in BRAND_CUES else _phrase_at(toks, k, VERTICAL_CUES, _VERTICAL_MAX)
        if hit:
            found.append((_AMENITY, QUERY_CUES[hit[1]], k, k + hit[0]))
            k += hit[0]
        elif toks[k].folded in BRAND_CUES:
            found.append((_BRAND, BRAND_CUES[toks[k].folded], k, k + 1))
            k += 1
        elif vhit and all(kind == _VERTICAL for kind, *_ in found) \
                and (found or not any(_gap_has(text, toks, m, _VERTICAL_GAP_STOP) for m in range(j, k + 1))):
            found.append((_VERTICAL, VERTICAL_CUES[vhit[1]], k, k + vhit[0]))
            k += vhit[0]
        elif not found and allow_filler and filler < _MAX_FILLER and toks[k].folded not in _FILLER_STOP \
                and _number(toks[k]) is None:
            filler, k = filler + 1, k + 1
            continue
        else:
            break
        # sau một tiện ích: chỉ đi tiếp qua từ nối / dấu phẩy / gạch chéo
        if k < len(toks) and toks[k].folded in _CONNECTORS:
            k += 1
        elif k < len(toks) and _gap_has(text, toks, k, ",/"):
            continue
        else:
            break
    return found, k


def _bare_cue_ok(toks: list[_Tok], i: int, key: str) -> bool:
    """Cue trần "khong"/"tru" tại token i có đúng là từ phủ định không (xem `_BARE_RAW`)."""
    raw = toks[i].raw.lower()
    if raw not in _BARE_RAW[key]:
        return False
    if key == "tru" and raw == "tru" and i > 0 and toks[i - 1].folded in _TRU_PREV_BLOCK:
        return False
    return True


def _soft_scope_start(toks: list[_Tok], j: int) -> int:
    """Token đầu phạm vi của cue mềm: bước qua "phải", "có" dẫn đầu theo đúng thứ tự `_SOFT_LEAD`."""
    for lead in _SOFT_LEAD:
        if j < len(toks) and toks[j].folded == lead:
            j += 1
    return j


def _free_phrase_end(text: str, toks: list[_Tok], j: int, protected: tuple[Span, ...]) -> int:
    """Cụm tự do sau cue (không phải tiện ích): tối đa 4 token, dừng ở từ chức năng, dấu câu, đoạn đã tiêu."""
    end = j
    while end < len(toks) and end - j < _SCOPE_WINDOW and toks[end].folded not in _FILLER_STOP \
            and not _overlaps((toks[end].start, toks[end].end), protected) \
            and not (end > j and _gap_has(text, toks, end, ";.,")):
        end += 1
    return end


def parse_negation(text: str, protected: Iterable[Span] = ()) -> NegationParse:
    """F3: tiện ích bị phủ định → `must_not`; thương hiệu → `must_not_brands`; loại sản phẩm → `must_not_taxonomies` /
    `must_not_flags` (`_vertical_exclusions`); cue mềm → `soft_dropped`; `protected` = đoạn `parse_numeric` đã tiêu."""
    prot = tuple(protected)
    toks = _toks(text)
    must_not: list[MustNot] = []
    brands: list[str] = []
    soft: list[str] = []
    unresolved: list[str] = []
    spans: list[Span] = []
    negated_verticals: list[tuple[str, Span]] = []
    i = 0
    while i < len(toks):
        if _overlaps((toks[i].start, toks[i].end), prot):
            i += 1
            continue
        cue = _phrase_at(toks, i, _HARD_CUES | _SOFT_CUES, _CUE_MAX)
        if cue is None:
            i += 1
            continue
        n, key = cue
        if key in _BARE_CUES and not _bare_cue_ok(toks, i, key):
            i += 1
            continue
        j = i + n
        nxt = toks[j] if j < len(toks) else None
        if nxt is None or nxt.folded in _NOT_NEGATION_NEXT or _number(nxt) is not None \
                or _overlaps((nxt.start, nxt.end), prot):
            i += 1
            continue
        soft_cue = key in _SOFT_CUES
        if soft_cue:
            j = _soft_scope_start(toks, j)       # "không nhất thiết phải có hồ bơi": thu từ "hồ bơi"
            nxt = toks[j] if j < len(toks) else None
            if nxt is None or _number(nxt) is not None or _overlaps((nxt.start, nxt.end), prot):
                i += 1
                continue
        found, end = _scope(text, toks, j, prot, allow_filler=not (key in _BARE_CUES) or soft_cue)
        if key in _BARE_CUES and not (found and found[0][2] == j):
            i += 1                                  # "khong"/"tru" trần: cụm phải đứng ngay sau
            continue
        if soft_cue:
            if not found:                           # "không cần đẹp": lấy tới 4 token hoặc tới từ dừng
                end = _free_phrase_end(text, toks, j, prot)
                if end == j:
                    i += 1
                    continue
            else:
                end = found[-1][3]
            soft.append(text[toks[i].start:toks[end - 1].end])
            spans.append((toks[i].start, toks[end - 1].end))
            i = end
            continue
        if not found:
            # cue cứng nhưng không ra tiện ích: ghi cụm (tới từ dừng / tối đa 4 token), không bịa khoá
            end = _free_phrase_end(text, toks, j, prot)
            if end > j:
                unresolved.append(text[toks[j].start:toks[end - 1].end])
                spans.append((toks[i].start, toks[end - 1].end))
            i = max(end, j)
            continue
        for kind, value, s, e in found:
            phrase, span = text[toks[s].start:toks[e - 1].end], (toks[s].start, toks[e - 1].end)
            if kind == _BRAND:
                brands.append(value)
            elif kind == _AMENITY:
                must_not.append(MustNot(value, phrase, span))
            else:
                negated_verticals.append((value, span))
        end = found[-1][3]
        spans.append((toks[i].start, toks[end - 1].end))
        i = end
    taxonomies, flags = _vertical_exclusions(toks, negated_verticals, spans)
    return NegationParse(tuple(must_not), tuple(dict.fromkeys(brands)), tuple(soft), tuple(unresolved), tuple(spans),
                         must_not_taxonomies=taxonomies, must_not_flags=flags)


def _single_ticket_at(toks: list[_Tok], k: int) -> bool:
    """"vé lẻ" / "ve le" tại token k — khớp chữ gốc: "về lễ" fold cũng ra "ve le"."""
    return k + 1 < len(toks) and toks[k].raw.lower() in ("vé", "ve") and toks[k + 1].raw.lower() in ("lẻ", "le")


def _vertical_exclusions(toks: list[_Tok], negated: list[tuple[str, Span]],
                         neg_spans: list[Span]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(must_not_taxonomies, must_not_flags) theo thứ tự xuất hiện.

    Câu có cue combo DƯƠNG (ngoài mọi phạm vi phủ định) thì vé máy bay / chỗ nghỉ bị phủ định là thành phần của combo →
    cờ `includesFlight` / `includesHotel` ("combo Phú Quốc không gồm vé máy bay"); ngoài ngữ cảnh đó là loại trừ cả loại sản
    phẩm ("khách sạn không phải combo" → combo). "vé lẻ" dương = loại trừ combo rõ ràng (rubric v4 #10, câu c0703).
    """
    composition = {FLIGHT: FLAG_INCLUDES_FLIGHT, HOTEL: FLAG_INCLUDES_HOTEL}
    combo_context = any(tax == COMBO and not _overlaps(span, neg_spans) for tax, span in _vertical_hits(toks))
    out: list[tuple[int, bool, str]] = []          # (offset, là cờ?, giá trị)
    for tax, span in negated:
        if combo_context and tax in composition:
            out.append((span[0], True, composition[tax]))
        else:
            out.append((span[0], False, tax))
    for k in range(len(toks)):
        if _single_ticket_at(toks, k) and not _overlaps((toks[k].start, toks[k + 1].end), neg_spans):
            out.append((toks[k].start, False, COMBO))
    out.sort(key=lambda x: x[0])
    return (tuple(dict.fromkeys(v for _, is_flag, v in out if not is_flag)),
            tuple(dict.fromkeys(v for _, is_flag, v in out if is_flag)))


# ====================================================================================== F4: taxonomy từ cue ngành dọc
def vertical_cue_spans(text: str) -> tuple[tuple[str, Span], ...]:
    """Mọi cue loại sản phẩm trong câu → (taxonomy, span), không xét ngữ cảnh — plan 2026-10-13 dùng để tách cue khỏi residual."""
    return tuple(_vertical_hits(_toks(text)))


HOTEL, FLIGHT, ATTRACTION, COMBO, GOLF = "hotel", "flight", "attraction", "combo", "golf"
#: Cụm (fold) → taxonomy (enum `schemas/common.yaml`). Khớp dài nhất trước: "ve may bay" thắng "ve"; "ve" trần không là cue.
VERTICAL_CUES: dict[str, str] = {
    **{c: HOTEL for c in ("khach san", "resort", "khu nghi duong", "khu du lich nghi duong", "nghi duong", "villa",
                          "biet thu", "homestay", "can ho", "nha nghi", "cho nghi", "noi luu tru", "noi o", "phong",
                          "hotel")},
    **{c: FLIGHT for c in (*FLIGHT_CUES, "bay tu", "bay den")},
    **{c: ATTRACTION for c in ("ve tham quan", "ve vao cua", "ve vui choi", "diem tham quan", "tham quan", "vinwonders",
                               "cong vien", "safari", "grand world", "khu vui choi", "diem vui choi")},
    **{c: COMBO for c in ("combo", "tron goi", "goi du lich")},
    **{c: GOLF for c in ("voucher golf", "san golf", "san gon", "golf", "tee time")},
}
_VERTICAL_MAX = max(len(c.split()) for c in VERTICAL_CUES)
STRONG, WEAK = "strong", "weak"
#: Cue YẾU: chữ chung chung hoặc tên điểm vui chơi — hay xuất hiện mà không thật sự giới hạn loại. Cờ
#: `PlanFlags.taxonomy_strong_only` chỉ lọc taxonomy khi câu có ít nhất một cue mạnh. Chốt theo dữ liệu 06/10 (gold_v5 chưa tag,
#: chọn trên dev, kiểm trên test của `devtest@gold_v4`; tỷ lệ item nhãn 2 cùng taxonomy với cue, câu một ngành dọc):
#: danh từ chỗ nghỉ ("cho nghi" dev 100 % / test 100 %, "noi luu tru" 100 %, "noi o" 100 %, "khu nghi duong") → MẠNH;
#: tên điểm vui chơi ("safari" dev 73 %, "vinwonders" test 50 % — combo chứa vé được nhãn 2) → YẾU; "phong", "nghi duong",
#: "tham quan", "cong vien", "khu vui choi", "goi du lich" giữ YẾU (chung chung, n nhỏ).
WEAK_VERTICAL_CUES = frozenset({"nghi duong", "phong", "tham quan", "cong vien", "khu vui choi", "diem vui choi",
                                "goi du lich", "vinwonders", "safari", "grand world"})
#: Cue (fold) → "strong" | "weak", phủ mọi khoá của `VERTICAL_CUES` (dựng từ `WEAK_VERTICAL_CUES`).
VERTICAL_CUE_STRENGTH: dict[str, str] = {c: WEAK if c in WEAK_VERTICAL_CUES else STRONG for c in VERTICAL_CUES}
#: Sau cue combo đứng đầu câu, cue loại này là THÀNH PHẦN của combo ("combo vé máy bay và khách sạn Đà Lạt" = combo, c0706).
_COMBO_COMPONENTS = frozenset({HOTEL, FLIGHT, ATTRACTION})
#: Cue đứng ngay sau từ này là tiện ích/điểm lân cận của chỗ nghỉ, không phải ngành dọc ("resort có sân golf").
_ATTACHED_PREV = frozenset({"co", "kem", "gan", "voi", "gom", "canh", "sat"})
#: Tên điểm vui chơi hay đi kèm tên khu/địa điểm: sau cue chỗ nghỉ ("khách sạn Grand World Phú Quốc") nó chỉ định vị,
#: không phải ngành dọc thứ hai — trừ khi có "vé"/từ nối/dấu phẩy đứng trước ("khách sạn gần biển và vé VinWonders").
_POI_BRAND_CUES = frozenset({"vinwonders", "grand world", "safari"})
#: Công khai cho query plan: span của cue này KHÔNG bị cắt khỏi `lexical_text` khi F4 lọc — là tên sản phẩm, BM25 cần nó.
POI_BRAND_CUES = _POI_BRAND_CUES
_POI_SEPARATE_PREV = frozenset({"ve", "va", "hoac", "hay", "cung", "them", "kem"})
SKIPPED_MULTI = "multi"


@dataclass(frozen=True)
class VerticalParse:
    verticals: tuple[str, ...] = ()         # ngành dọc phân biệt, theo thứ tự xuất hiện (kể cả thành phần của combo)
    taxonomy: str | None = None             # đúng một ngành dọc (hoặc combo đứng đầu + thành phần) → lọc theo nó
    skipped: str | None = None              # "multi" khi câu nêu ≥ 2 ngành dọc (gold cross_vertical)
    spans: tuple[Span, ...] = ()            # cue đã tính của `taxonomy` (multi: mọi cue đã tính) — phần cắt khỏi BM25
    strength: str | None = None             # "strong": có cue mạnh của `taxonomy` · "weak": chỉ cue yếu · None: không có taxonomy


def _brand_ranges(toks: list[_Tok], brand_names: Iterable[str]) -> list[tuple[int, int, str]]:
    """Dải token thuộc tên thương hiệu/sản phẩm (khớp dài nhất trên token fold) → (đầu, cuối, tên fold)."""
    names = {fold(b) for b in brand_names if b}
    names.discard("")
    if not names:
        return []
    max_n = max(len(b.split()) for b in names)
    out, i = [], 0
    while i < len(toks):
        hit = _phrase_at(toks, i, names, max_n)
        if hit:
            out.append((i, i + hit[0], hit[1]))
            i += hit[0]
        else:
            i += 1
    return out


def _vertical_hits(toks: list[_Tok]) -> list[tuple[str, Span]]:
    """Mọi cue loại sản phẩm (khớp dài nhất, không chồng) → (taxonomy, span); không xét ngữ cảnh."""
    out, i = [], 0
    while i < len(toks):
        hit = _phrase_at(toks, i, VERTICAL_CUES, _VERTICAL_MAX)
        if hit is None:
            i += 1
            continue
        out.append((VERTICAL_CUES[hit[1]], (toks[i].start, toks[i + hit[0] - 1].end)))
        i += hit[0]
    return out


def _combo_head(text: str, toks: list[_Tok], counted: list[tuple[str, str, Span, int]]) -> bool:
    """Cue đã tính đầu tiên là combo, mọi cue khác là thành phần (chỗ nghỉ / vé máy bay / vé tham quan), và cue combo không
    đứng thành một mục của danh sách — "trọn gói và vé máy bay Đà Lạt" (ngay sau là từ nối / dấu phẩy) vẫn là multi."""
    tax, _, _, after = counted[0]
    if tax != COMBO or any(t != COMBO and t not in _COMBO_COMPONENTS for t, *_ in counted):
        return False
    return not (after < len(toks) and (toks[after].folded in _CONNECTORS or _gap_has(text, toks, after, ",/;")))


def parse_vertical(text: str, excluded: Iterable[Span] = (), brand_names: Iterable[str] = (),
                   brand_taxonomy: Mapping[str, str] | None = None) -> VerticalParse:
    """F4: `excluded` = phạm vi phủ định (cue trong đó không tính); `brand_names` = tên có chứa cue ("Golf Valley Hotel").
    `brand_taxonomy` (tên fold → taxonomy của unit): cue NẰM TRONG tên chỉ tính khi đúng loại của chính unit đó
    ("tìm Vinpearl Resort & Golf Nam Hội An" → "resort" tính là hotel, "golf" bỏ); không có bảng → mọi cue trong tên bỏ.
    "có <cue> nào" là câu hỏi tồn tại ("Quy Nhơn có nơi lưu trú nào…") — không coi cue là tiện ích gắn sau "có".

    Một loại → lọc theo nó; nhiều loại → multi, trừ khi combo đứng đầu và các loại sau là thành phần (`_combo_head`)."""
    excl = tuple(excluded)
    toks = _toks(text)
    brands = _brand_ranges(toks, brand_names)
    counted: list[tuple[str, str, Span, int]] = []      # (taxonomy, cue, span, token ngay sau cue)
    i = 0
    while i < len(toks):
        hit = _phrase_at(toks, i, VERTICAL_CUES, _VERTICAL_MAX)
        if hit is None:
            i += 1
            continue
        n, key = hit
        span = (toks[i].start, toks[i + n - 1].end)
        attached = i > 0 and toks[i - 1].folded in _ATTACHED_PREV             and not (toks[i - 1].folded == "co" and i + n < len(toks) and toks[i + n].folded == "nao")
        own = next(((brand_taxonomy or {}).get(nm) for s_, e_, nm in brands if s_ <= i < e_), None)
        in_brand = any(s_ <= i < e_ for s_, e_, _ in brands) and own != VERTICAL_CUES[key]
        poi_modifier = key in _POI_BRAND_CUES and bool(counted) and counted[0][0] == HOTEL and i > 0 \
            and toks[i - 1].folded not in _POI_SEPARATE_PREV and not _gap_has(text, toks, i, ",/;")
        if not (attached or in_brand or poi_modifier or _overlaps(span, excl)):
            counted.append((VERTICAL_CUES[key], key, span, i + n))
        i += n
    distinct = tuple(dict.fromkeys(tax for tax, *_ in counted))
    if len(distinct) == 1:
        chosen = distinct[0]
    elif len(distinct) > 1 and _combo_head(text, toks, counted):
        chosen = COMBO
    else:
        return VerticalParse(distinct, None, SKIPPED_MULTI if len(distinct) > 1 else None, tuple(c[2] for c in counted))
    mine = [c for c in counted if c[0] == chosen]
    strength = STRONG if any(VERTICAL_CUE_STRENGTH[c[1]] == STRONG for c in mine) else WEAK
    return VerticalParse(distinct, chosen, None, tuple(c[2] for c in mine), strength)


# ====================================================================================== F5: nơi đi → nơi đến
_TO_OPS = frozenset({"di", "den", "toi", "vao", "ra", "ve", "sang", "qua"})
_DEST_ONLY_OPS = frozenset({"den", "toi", "ve", "vao", "di"})
#: "ra"/"sang" (và "ve" không dấu — trùng "vé") chỉ là toán tử đích khi đứng sau động từ di chuyển: "bay ra Hà Nội".
_DEST_AFTER_VERB_OPS = frozenset({"ra", "sang"})
_MOVE_VERBS = frozenset({"bay", "di", "tro"})
_FROM_OPS = frozenset({"tu"})
_FROM_PREFIX = ("khoi hanh", "xuat phat")      # không lấy "bay": nó thuộc "vé máy bay"
_MAX_ROUTE_FILLER = 2                           # "từ Hà Nội bay thẳng tới Đà Nẵng": tối đa 2 token đệm trước toán tử đích
_ARROWS = "-–—→>/"
EXPLICIT, DESTINATION_ONLY, ORIGIN_ONLY, AMBIGUOUS = "explicit", "destination_only", "origin_only", "ambiguous"
_IATA = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class FlightRoles:
    origin: str | None = None
    destination: str | None = None
    direction: str | None = None            # explicit | destination_only | origin_only | None
    skipped: str | None = None              # "ambiguous": hai địa danh nhưng không rõ vai
    spans: tuple[Span, ...] = ()


def _uppercase_codes(raw_text: str | None) -> set[str] | None:
    """Mã IATA viết HOA đứng riêng trong câu gốc; None = không có câu gốc để đối chiếu."""
    if raw_text is None:
        return None
    return {m.group() for m in re.finditer(r"\b[A-Z]{3}\b", raw_text)}


def _mentions(text: str, toks: list[_Tok], places: Iterable[tuple[int, int, str]], iata: Mapping[str, str],
              raw_text: str | None) -> list[tuple[int, int, str]]:
    out = sorted((int(s), int(e), str(n)) for s, e, n in places)
    allowed = _uppercase_codes(raw_text)
    for t in toks:
        if _IATA.match(t.raw) and t.raw in iata and (allowed is None or t.raw in allowed) \
                and not _overlaps((t.start, t.end), [(s, e) for s, e, _ in out]):
            out.append((t.start, t.end, iata[t.raw]))
    return sorted(out)


def _tok_range(toks: list[_Tok], span: Span) -> tuple[int, int]:
    """(token đầu, token cuối+1) nằm trong span địa danh."""
    idx = [k for k, t in enumerate(toks) if t.start >= span[0] and t.end <= span[1]]
    return (idx[0], idx[-1] + 1) if idx else (0, 0)


def _is_op(tok: _Tok, ops: frozenset[str]) -> bool:
    """Toán tử hướng: "về" (verb) chứ không phải "vé"; "từ" chứ không phải "tư"/"tự". Không dấu thì chấp nhận."""
    low = tok.raw.lower()
    if tok.folded not in ops:
        return False
    if tok.folded == "ve":
        return low in ("về", "ve")
    if tok.folded == "tu":
        return low in ("từ", "tu")
    return True


def _from_start(toks: list[_Tok], k: int) -> int:
    """Token "tu" ở k; lùi thêm "khởi hành"/"xuất phát" nếu có."""
    for pre in _FROM_PREFIX:
        n = len(pre.split())
        if k - n >= 0 and " ".join(t.folded for t in toks[k - n:k]) == pre:
            return k - n
    return k


def _dest_only_before(toks: list[_Tok], a0: int) -> bool:
    """Token ngay trước địa danh (bắt đầu tại a0) là toán tử "đến" một chiều: "đến"/"tới"/"vào"/"đi"/"về", hoặc
    "ra"/"sang"/"ve" không dấu khi có động từ di chuyển đứng trước nữa ("bay ra", "đi sang", "trở về")."""
    if a0 == 0:
        return False
    prev = toks[a0 - 1]
    after_verb = a0 >= 2 and toks[a0 - 2].folded in _MOVE_VERBS
    if _is_op(prev, _DEST_AFTER_VERB_OPS):
        return after_verb
    if not _is_op(prev, _DEST_ONLY_OPS):
        return False
    if prev.folded == "ve" and prev.raw.lower() == "ve":
        return after_verb
    return True


def _route_fillers_ok(between: list[_Tok]) -> bool:
    """Giữa A và B (A có "từ"): rỗng, hoặc ≤ 2 token đệm (bay, thẳng, khứ hồi…) rồi một toán tử đích; không có "từ" thứ hai."""
    if not between:
        return True
    return len(between) <= _MAX_ROUTE_FILLER + 1 and _is_op(between[-1], _TO_OPS) \
        and not any(t.folded in _FROM_OPS for t in between[:-1])


def parse_flight_roles(text: str, places: Iterable[tuple[int, int, str]], iata: Mapping[str, str] = {},
                       raw_text: str | None = None) -> FlightRoles:
    """F5: `places` = `NormalizedQuery.destination_spans` trên `text`; `iata` = mã HOA → tên thành phố chuẩn."""
    toks = _toks(text)
    ms = _mentions(text, toks, places, iata, raw_text)
    if not ms:
        return FlightRoles()
    if len(ms) > 2:
        return FlightRoles(skipped=AMBIGUOUS)
    a = ms[0]
    a0, a1 = _tok_range(toks, (a[0], a[1]))
    prev_a = toks[a0 - 1] if a0 > 0 else None
    if len(ms) == 1:
        if prev_a is not None and _is_op(prev_a, _FROM_OPS):
            s = _from_start(toks, a0 - 1)
            return FlightRoles(origin=a[2], direction=ORIGIN_ONLY, spans=((toks[s].start, a[1]),))
        if _dest_only_before(toks, a0):
            return FlightRoles(destination=a[2], direction=DESTINATION_ONLY, spans=((prev_a.start, a[1]),))
        return FlightRoles()
    b = ms[1]
    b0, b1 = _tok_range(toks, (b[0], b[1]))
    between = toks[a1:b0]
    gap = text[a[1]:b[0]]
    from_a = prev_a is not None and _is_op(prev_a, _FROM_OPS)
    start = toks[_from_start(toks, a0 - 1)].start if from_a else a[0]
    if from_a and _route_fillers_ok(between):
        return FlightRoles(a[2], b[2], EXPLICIT, spans=((start, b[1]),))
    if len(between) == 1 and _is_op(between[0], _TO_OPS - {"qua"}):
        return FlightRoles(a[2], b[2], EXPLICIT, spans=((start, b[1]),))
    if not between and (gap.strip() == "" or any(c in gap for c in _ARROWS)):
        return FlightRoles(a[2], b[2], EXPLICIT, spans=((start, b[1]),))
    prev_b = toks[b0 - 1] if b0 > 0 else None
    if prev_a is not None and _is_op(prev_a, _DEST_ONLY_OPS) and prev_b is not None and _is_op(prev_b, _FROM_OPS):
        s = toks[_from_start(toks, b0 - 1)].start           # "đến B từ A"
        return FlightRoles(b[2], a[2], EXPLICIT, spans=((prev_a.start, a[1]), (s, b[1])))
    return FlightRoles(skipped=AMBIGUOUS)


# ====================================================================================== Số khách (party)
#: Kiến trúc §6 "Room child: occupancy"; contract `SearchRequest.travelContext.guests {adults, children}`. Chỉ số viết bằng
#: chữ số 1–30 ngay trước đơn vị; số viết bằng chữ ("bốn người") không nhận — "ba", "năm" trùng từ thường.
_PARTY_MIN, _PARTY_MAX = 1, 30
_INT = re.compile(r"^\d+$")
#: Từ nối giữa hai cụm số khách ("2 người lớn và 1 trẻ em") — gộp thành một span để BM25 không còn "và" lẻ loi.
_PARTY_LINKS = frozenset({"va", "voi", "cung", "kem"})
ADULTS, CHILDREN, TOTAL = "adults", "children", "total"


@dataclass(frozen=True)
class PartyParse:
    adults: int | None = None               # "N người lớn"
    children: int | None = None             # "M trẻ em / trẻ nhỏ / bé / con / em bé"
    total: int | None = None                # người lớn + trẻ em, hoặc "N người / N khách / nhóm N người"; None khi chỉ biết trẻ em
    spans: tuple[Span, ...] = ()            # số + đơn vị (gộp qua từ nối) — phần cắt khỏi BM25 khi filter áp


def _party_unit(toks: list[_Tok], k: int) -> tuple[str, int] | None:
    """(loại, số token) của đơn vị số khách bắt đầu tại token k. Khớp chữ gốc ở chỗ fold trùng: "bé" ≠ "bể" (bể bơi), "con"
    ≠ "còn"/"Côn"; "khách sạn" không phải "khách"."""
    if k >= len(toks):
        return None
    f, raw = toks[k].folded, toks[k].raw.lower()
    nxt = toks[k + 1] if k + 1 < len(toks) else None
    nf = nxt.folded if nxt else None
    if f == "nguoi":
        return (ADULTS, 2) if nf == "lon" else (TOTAL, 1)
    if f == "khach":
        return None if nf == "san" else (TOTAL, 1)
    if f == "tre" and nf in ("em", "nho"):
        return CHILDREN, 2
    if f == "em" and nxt is not None and nxt.raw.lower() in ("bé", "be"):
        return CHILDREN, 2
    if raw in ("bé", "be") and nf != "boi":
        return CHILDREN, 1
    if raw == "con":
        return CHILDREN, 1
    return None


def parse_party(text: str, protected: Iterable[Span] = ()) -> PartyParse:
    """Số khách trong câu: "N người lớn" · "M trẻ em" · "N người" / "N khách" (cả "nhóm / gia đình / đoàn N người", tên hạng
    phòng "Phòng 4 Người"). `protected` = đoạn `parse_numeric` đã tiêu (giá, sao) — số trong đó không bao giờ là số khách.
    Nêu nhiều lần thì lấy lần đầu mỗi loại; tổng = người lớn + trẻ em (hoặc tổng nêu thẳng nếu lớn hơn)."""
    prot = tuple(protected)
    toks = _toks(text)
    found: list[tuple[str, int, int, int]] = []          # (loại, số, token đầu, token cuối+1)
    i = 0
    while i < len(toks):
        t = toks[i]
        unit = None
        if _INT.match(t.raw) and _PARTY_MIN <= int(t.raw) <= _PARTY_MAX and not _overlaps((t.start, t.end), prot):
            unit = _party_unit(toks, i + 1)
        if unit is None or _overlaps((toks[i + 1].start, toks[i + unit[1]].end), prot):
            i += 1
            continue
        kind, n = unit
        found.append((kind, int(t.raw), i, i + 1 + n))
        i += 1 + n
    if not found:
        return PartyParse()
    first = {}
    for kind, v, _, _ in found:
        first.setdefault(kind, v)
    adults, children, stated = first.get(ADULTS), first.get(CHILDREN), first.get(TOTAL)
    if adults is not None:
        total = adults + (children or 0)
        if stated is not None and stated > total:
            total = stated
    else:
        total = stated
    spans: list[Span] = []
    prev_end = None
    for _, _, s, e in found:
        joined = prev_end is not None and not _gap_has(text, toks, s, ";.") and (
            s == prev_end or (s == prev_end + 1 and toks[prev_end].folded in _PARTY_LINKS))
        if joined:
            spans[-1] = (spans[-1][0], toks[e - 1].end)
        else:
            spans.append((toks[s].start, toks[e - 1].end))
        prev_end = e
    return PartyParse(adults, children, total, tuple(spans))


# ====================================================================================== F7: thời lượng chuyến đi
#: "N ngày M đêm" · "3N2Đ" · "N ngày" · "M đêm" · "N days M nights" (spec tích hợp §2.2, contract 1.18.0 `queryPlan.duration`).
#: Như số khách: chỉ chữ số 1–30 đứng NGAY TRƯỚC đơn vị (fold) — "ngày 15/10" (đơn vị đứng trước số), "45 ngày", "0 đêm",
#: "3 tiếng", "qua đêm" / "ban đêm" / "chợ đêm" / "ngay trung tâm" (không có số trước) đều không nhận. Giá theo đêm ("2 triệu/đêm",
#: "1.5 triệu một đêm") đã nằm trọn trong span của `parse_numeric` (`_absorb_unit_tail`) → tầng gọi truyền `protected`.
_DAY_UNITS = frozenset({"ngay", "day", "days"})
_NIGHT_UNITS = frozenset({"dem", "night", "nights"})
#: Dạng viết tắt là MỘT token của `_TOKEN` ("3N2Đ" → `\d+\w*`), fold ra "3n2d".
_COMPACT_DURATION = re.compile(r"^(\d{1,2})n(\d{1,2})d$")
_DURATION_MIN, _DURATION_MAX = 1, 30
#: Từ nối giữa hai cụm ("3 ngày và 2 đêm") — gộp thành một span như `_PARTY_LINKS`; dấu `,` `-` `/` gộp qua khoảng trống.
_DURATION_LINKS = frozenset({"va"})
_DURATION_GAP_CHARS = frozenset(" \t,-/")
_DAYS, _NIGHTS = "days", "nights"


@dataclass(frozen=True)
class DurationParse:
    days: int | None = None                 # "N ngày" / "N days" / nửa đầu "3N2Đ"
    nights: int | None = None               # "M đêm" / "M nights" / nửa sau "3N2Đ"; không suy nửa thiếu
    spans: tuple[Span, ...] = ()            # số + đơn vị (gộp cụm kề qua từ nối / dấu) — phần cắt khỏi BM25


def _duration_at(toks: list[_Tok], i: int, prot: tuple[Span, ...]) -> tuple[dict[str, int], int] | None:
    """Cụm thời lượng bắt đầu tại token i → ({days?, nights?}, token cuối+1); None nếu không phải."""
    t = toks[i]
    if _overlaps((t.start, t.end), prot):
        return None
    m = _COMPACT_DURATION.match(t.folded)
    if m:
        d, n = int(m.group(1)), int(m.group(2))
        if _DURATION_MIN <= d <= _DURATION_MAX and _DURATION_MIN <= n <= _DURATION_MAX:
            return {_DAYS: d, _NIGHTS: n}, i + 1
        return None
    if not _INT.match(t.raw) or not _DURATION_MIN <= int(t.raw) <= _DURATION_MAX or i + 1 >= len(toks):
        return None
    unit = toks[i + 1]
    if _overlaps((unit.start, unit.end), prot):
        return None
    if unit.folded in _DAY_UNITS:
        return {_DAYS: int(t.raw)}, i + 2
    if unit.folded in _NIGHT_UNITS:
        return {_NIGHTS: int(t.raw)}, i + 2
    return None


def _plain_gap(text: str, toks: list[_Tok], i: int) -> bool:
    """Khoảng trước token i chỉ gồm khoảng trắng / `,` `-` `/` — hai cụm thời lượng kề nhau được gộp qua nó."""
    return set(_gap(text, toks, i)) <= _DURATION_GAP_CHARS


def parse_duration(text: str, protected: Iterable[Span] = ()) -> DurationParse:
    """F7: số ngày / số đêm trong câu. `protected` = đoạn `parse_numeric` + `parse_party` đã tiêu — số trong đó (giá theo đêm,
    số khách) không bao giờ là thời lượng. Nêu nhiều lần thì lấy lần đầu mỗi loại nhưng mọi cụm khớp đều bị tiêu."""
    prot = tuple(protected)
    toks = _toks(text)
    found: list[tuple[dict[str, int], int, int]] = []        # (giá trị, token đầu, token cuối+1)
    i = 0
    while i < len(toks):
        hit = _duration_at(toks, i, prot)
        if hit is None:
            i += 1
            continue
        found.append((hit[0], i, hit[1]))
        i = hit[1]
    if not found:
        return DurationParse()
    first: dict[str, int] = {}
    for values, _, _ in found:
        for k, v in values.items():
            first.setdefault(k, v)
    spans: list[Span] = []
    prev_end = None
    for _, s, e in found:
        joined = prev_end is not None and (
            (s == prev_end and _plain_gap(text, toks, s))
            or (s == prev_end + 1 and toks[prev_end].folded in _DURATION_LINKS
                and _plain_gap(text, toks, prev_end) and _plain_gap(text, toks, s)))
        if joined:
            spans[-1] = (spans[-1][0], toks[e - 1].end)
        else:
            spans.append((toks[s].start, toks[e - 1].end))
        prev_end = e
    return DurationParse(first.get(_DAYS), first.get(_NIGHTS), tuple(spans))
