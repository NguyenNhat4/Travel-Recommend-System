"""Bước chuẩn hoá truy vấn của /search (trước FILTER, spec §2.2): viết tắt → sửa chính tả tên riêng theo từ vựng
catalog → tên điểm đến về đúng giá trị catalog → kiểu đi về nhãn `audience` mà text catalog dùng.

Bốn lượt trên CHUỖI GỐC: mỗi lượt tách token bằng `\\w+` (sau NFC), khớp trên dạng đã fold, thay theo span từ phải
sang trái — từ không đụng tới giữ nguyên dấu, hoa thường và dấu câu. Các bảng ở đây chỉ chứa CÁCH VIẾT: alias điểm
đến trỏ tới nơi catalog không có thì bị bỏ lúc dựng, từ vựng sửa chính tả dựng từ tên sản phẩm + điểm đến — tính hợp
lệ vẫn đến từ catalog (cùng nguyên tắc `history/2026-09-20-resolve-destination-from-catalog.md`; Agent vẫn để LLM
chọn điểm đến, thanh tìm kiếm không có LLM nên cần bảng tất định). Thuần stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .lexical import STOPWORDS, fold, tokens

_WORD = re.compile(r"\w+")          # NFC trước: dấu tổ hợp (Mn) không thuộc \w nên NFD sẽ tách token sai
_PRICE = re.compile(r"^(\d+)tr$")   # "2tr" → "2 triệu": chỉ mở rộng chữ, nghĩa giá là bước 2
# Âm tiết tiếng Việt đã fold: phụ âm đầu? + 1–3 nguyên âm + phụ âm cuối?. Token khớp mẫu là từ thường (kể cả gõ sai
# mà vẫn hợp lệ) → KHÔNG bao giờ sửa chính tả; chỉ token "không phải tiếng Việt" (Trnag, Vinpeal) mới là ứng viên.
# Đây là chốt chặn thay cho từ điển tiếng Việt (repo không có).
_VN_SYLLABLE = re.compile(
    r"^(?:ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnpqrstvx])?[aeiouy]{1,3}(?:ch|ng|nh|[cmnpt])?$")

#: Viết tắt thông dụng (khoá đã fold) → cụm đầy đủ. `kdl` lấy cả hai nghĩa (người dùng chốt 25/09).
ALIASES: dict[str, str] = {"ks": "khách sạn", "kdl": "khu du lịch nghỉ dưỡng", "gd": "gia đình", "vw": "VinWonders"}

#: Cách viết khác của điểm đến → đúng giá trị catalog. Chỉ biến thể chính tả (theo `data_collection/collectors/geo.py`),
#: không lấy địa danh con (ba na, cam ranh) vì đổi nghĩa truy vấn. "dn" = Đà Nẵng (catalog không có Đồng Nai);
#: bỏ "qn" (Quy Nhơn / Quảng Ninh / Quảng Nam) và "vp".
DESTINATION_ALIASES: dict[str, str] = {
    "nt": "Nha Trang", "pq": "Phú Quốc", "dn": "Đà Nẵng", "hn": "Hà Nội", "hl": "Hạ Long",
    "sg": "TP. Hồ Chí Minh", "hcm": "TP. Hồ Chí Minh", "tphcm": "TP. Hồ Chí Minh", "hcmc": "TP. Hồ Chí Minh",
    "tp hcm": "TP. Hồ Chí Minh", "sai gon": "TP. Hồ Chí Minh", "saigon": "TP. Hồ Chí Minh",
    "ho chi minh": "TP. Hồ Chí Minh", "hanoi": "Hà Nội", "danang": "Đà Nẵng", "halong": "Hạ Long",
    "dalat": "Đà Lạt", "sapa": "Sa Pa",
}

#: Kiểu đi: cụm (đã fold) → (nhãn, cụm thay). Cụm thay là chữ mà text catalog dùng (`audience`: Gia đình · Nhóm bạn ·
#: Cặp đôi · Doanh nhân; mô tả: "cặp đôi", "một mình", "nhóm bạn", "công tác"). `None` = giữ nguyên chữ (cụm đã tự
#: nhiên hoặc mang thêm nghĩa như "có trẻ nhỏ", "nhóm 4 người"). Chỉ khớp chữ, không suy từ số người (bước 2).
PARTY_PHRASES: dict[str, tuple[str, str | None]] = {
    "mot minh": ("SOLO", "một mình"), "1 minh": ("SOLO", "một mình"), "solo": ("SOLO", "một mình"),
    "mot nguoi": ("SOLO", "một mình"),
    "cap doi": ("COUPLE", "cặp đôi"), "ban trai": ("COUPLE", "cặp đôi"), "ban gai": ("COUPLE", "cặp đôi"),
    "nguoi yeu": ("COUPLE", "cặp đôi"), "vo chong": ("COUPLE", "cặp đôi"), "honeymoon": ("COUPLE", "cặp đôi"),
    "tuan trang mat": ("COUPLE", "cặp đôi"), "couple": ("COUPLE", "cặp đôi"),
    "gia dinh": ("FAMILY", "gia đình"), "ca nha": ("FAMILY", "gia đình"), "co tre nho": ("FAMILY", None),
    "co con nho": ("FAMILY", None), "tre em": ("FAMILY", None),
    "nhom ban": ("FRIENDS", "nhóm bạn"), "hoi ban": ("FRIENDS", "nhóm bạn"), "ban be": ("FRIENDS", "nhóm bạn"),
    "nhom": ("FRIENDS", None), "di nhom": ("FRIENDS", None), "team": ("FRIENDS", "nhóm bạn"),
    "cong ty": ("BUSINESS", "công tác"), "dong nghiep": ("BUSINESS", "công tác"), "cong tac": ("BUSINESS", "công tác"),
    "doanh nhan": ("BUSINESS", None), "team building": ("BUSINESS", "công tác"), "hoi nghi": ("BUSINESS", None),
    "di lam": ("BUSINESS", "công tác"),
}


@dataclass(frozen=True)
class NormalizedQuery:
    text: str
    applied_aliases: tuple[tuple[str, str], ...] = ()   # (gốc, thay): viết tắt, tên điểm đến, kiểu đi có đổi chữ
    corrections: tuple[tuple[str, str], ...] = ()       # (token gốc, token đã sửa)
    destinations: tuple[str, ...] = ()                  # tên chuẩn xuất hiện trong câu — dành cho bước 2
    party: str | None = None                            # SOLO | COUPLE | FAMILY | FRIENDS | BUSINESS
    #: (bắt đầu, kết thúc, tên chuẩn) của từng địa danh TRÊN `text` cuối — offset hợp lệ với chuỗi trả về, để parser
    #: ràng buộc (`constraints.py`) cắt cụm ra khỏi text BM25. `destinations` giữ nguyên (không lặp, theo thứ tự).
    destination_spans: tuple[tuple[int, int, str], ...] = ()


def _spans(text: str) -> list[tuple[int, int, str, str]]:
    """[(bắt đầu, kết thúc, chữ gốc, dạng fold)] cho từng token `\\w+`."""
    return [(m.start(), m.end(), m.group(), fold(m.group())) for m in _WORD.finditer(text)]


def _find(spans, has: Callable[[str], bool], max_n: int) -> list[tuple[int, int, str]]:
    """Khớp dài nhất trước trên chuỗi token đã fold → (chỉ số token đầu, số token, khoá đã fold), không chồng nhau."""
    out, i = [], 0
    while i < len(spans):
        for n in range(min(max_n, len(spans) - i), 0, -1):
            key = " ".join(s[3] for s in spans[i:i + n])
            if has(key):
                out.append((i, n, key))
                i += n
                break
        else:
            i += 1
    return out


def _apply(text: str, spans, hits, rep_of: Callable[[str], str | None]) -> tuple[str, list[tuple[str, str]]]:
    """Thay các cụm đã khớp (từ phải sang trái để offset còn đúng); chỉ ghi nhận cụm thực sự đổi chữ."""
    edits, log = [], []
    for i, n, key in hits:
        rep = rep_of(key)
        start, end = spans[i][0], spans[i + n - 1][1]
        orig = text[start:end]
        if rep is not None and orig != rep:
            edits.append((start, end, rep))
            log.append((orig, rep))
    for start, end, rep in sorted(edits, reverse=True):
        text = text[:start] + rep + text[end:]
    return text, log


def _price(key: str) -> str | None:
    m = _PRICE.match(key)
    return f"{m.group(1)} triệu" if m else None


def _osa(a: str, b: str) -> int:
    """Khoảng cách Damerau–Levenshtein (optimal string alignment): thêm, bớt, thay, hoán vị hai ký tự kề."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


#: Tên công khai cho module khác trong `domain/search` (parser ràng buộc dùng chung cách tách token và khớp cụm).
spans = _spans
find_phrases = _find


class QueryNormalizer:
    """Dựng một lần từ catalog (`destinations`, `names`), gọi cho từng truy vấn. Idempotent: chạy hai lần như một."""

    def __init__(self, destinations: Iterable[str], names: Iterable[str], *,
                 min_len: int = 5, min_df: int = 3, spelling: bool = True):
        dests = {str(d) for d in destinations if d}
        self._alias = {**ALIASES, **{k: v for k, v in DESTINATION_ALIASES.items() if v in dests}}
        self._gazetteer = {fold(d): d for d in dests}
        self._party = dict(PARTY_PHRASES)
        self._max_n = max((len(k.split()) for k in (*self._alias, *self._gazetteer, *self._party)), default=1)
        self._min_len, self._min_df, self._spelling = min_len, min_df, spelling

        # Từ vựng sửa chính tả: DF theo tên (mỗi tên một lần) + cách viết phổ biến nhất của mỗi token (để trả về đúng
        # hoa thường/dấu của catalog: "vinpearl" → "Vinpearl"). Token của tên điểm đến luôn đủ điều kiện ứng viên.
        df: Counter[str] = Counter()
        surface: defaultdict[str, Counter[str]] = defaultdict(Counter)
        for name in names:
            name = unicodedata.normalize("NFC", str(name))
            df.update(set(tokens(name)))
            for raw in _WORD.findall(name):
                surface[fold(raw)][raw] += 1
        for d in dests:
            for raw in _WORD.findall(unicodedata.normalize("NFC", d)):
                t = fold(raw)
                df[t] = max(df[t], min_df)
                surface[t].setdefault(raw, 0)
        self._df = df
        self._surface = {t: c.most_common(1)[0][0] for t, c in surface.items() if c}
        self._buckets: defaultdict[tuple[str, int], list[str]] = defaultdict(list)
        for t, n in df.items():
            if n >= min_df and t:
                self._buckets[(t[0], len(t))].append(t)

    # ------------------------------------------------------------------ sửa chính tả
    def _correct_token(self, t: str) -> str | None:
        if (len(t) < self._min_len or t in self._df or t in STOPWORDS or t in self._alias
                or any(c.isdigit() for c in t) or _VN_SYLLABLE.match(t)):
            return None
        max_d = 2 if len(t) >= 8 else 1
        best: tuple[int, int, str] | None = None   # (khoảng cách, -DF, token): hoà thì DF cao, rồi a→z
        for length in range(len(t) - max_d, len(t) + max_d + 1):
            for c in self._buckets.get((t[0], length), ()):
                d = _osa(t, c)
                if d <= max_d and (best is None or (d, -self._df[c], c) < best):
                    best = (d, -self._df[c], c)
        return best[2] if best else None

    def _correct(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        edits, log = [], []
        for start, end, raw, folded in _spans(text):
            fixed = self._correct_token(folded)
            if fixed:
                rep = self._surface.get(fixed, fixed)
                edits.append((start, end, rep))
                log.append((raw, rep))
        for start, end, rep in sorted(edits, reverse=True):
            text = text[:start] + rep + text[end:]
        return text, log

    # ------------------------------------------------------------------ điểm vào
    def __call__(self, q: str) -> NormalizedQuery:
        text = unicodedata.normalize("NFC", q)

        # Lượt alias tra cả gazetteer để "khớp dài nhất" đúng: "tp ho chi minh" (4 token, đã chuẩn) thắng alias
        # "ho chi minh" (3 token) — nếu không, chạy lần hai sẽ thành "TP. TP. Hồ Chí Minh".
        spans = _spans(text)
        hits = _find(spans, lambda k: k in self._alias or k in self._gazetteer or _price(k) is not None, self._max_n)
        text, aliases = _apply(text, spans, hits, lambda k: self._alias.get(k) or self._gazetteer.get(k) or _price(k))

        corrections: list[tuple[str, str]] = []
        if self._spelling:
            text, corrections = self._correct(text)

        spans = _spans(text)
        hits = _find(spans, self._gazetteer.__contains__, self._max_n)
        text, places = _apply(text, spans, hits, self._gazetteer.get)
        destinations = tuple(dict.fromkeys(self._gazetteer[k] for _, _, k in hits))

        spans = _spans(text)
        hits = _find(spans, self._party.__contains__, self._max_n)
        text, party_edits = _apply(text, spans, hits, lambda k: self._party[k][1])
        party = self._party[hits[0][2]][0] if hits else None   # nhắc nhiều kiểu thì lấy kiểu nhắc trước

        # Quét gazetteer lần cuối trên text ĐÃ xong để offset địa danh đúng với chuỗi trả về.
        spans = _spans(text)
        hits = _find(spans, self._gazetteer.__contains__, self._max_n)
        destination_spans = tuple((spans[i][0], spans[i + n - 1][1], self._gazetteer[k]) for i, n, k in hits)

        return NormalizedQuery(text, tuple(aliases + places + party_edits), tuple(corrections), destinations, party,
                               destination_spans)
