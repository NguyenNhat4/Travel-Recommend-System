"""Bằng chứng theo cụm và phần câu catalog không giải thích được (plan `docs/plan/2026-10-13-search-evidence-gate-no-answer.md`
§2.1, §2.6; FR-SRC-04 chốt 13/10).

Hai việc, cùng một cách so chữ:

- **Bằng chứng theo cụm** cho nhánh lexical: khớp phải là cặp âm tiết LIỀN NHAU, ĐÚNG THỨ TỰ, và GIỮ DẤU khi câu có dấu.
  `fold` làm "Trần" = "trấn", "Văn" = "Vận", nên "Trần Thị Mai" từng khớp "Thị trấn Hoàng Hôn"; ở đây không còn.
- **Residual không giải thích được**: phần câu còn lại sau khi tách điều kiện (giá, thời lượng, điểm đến, cue loại…) mà không
  cặp âm tiết nào có trong catalog. Cụm dạng tên riêng chiếm toàn bộ residual → câu không có đáp án; cụm lạ khác → bỏ khỏi
  truy vấn, tìm tiếp.

Token giữ dấu được đưa về MỘT kiểu đặt dấu thanh (`tone.TONE_OLD`) để "hoà" = "hòa". Token không dấu trong câu (người dùng gõ
"Da Lat", hoặc chữ vốn không dấu "resort") so ở dạng fold. Thuần stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from .lexical import STOPWORDS, fold, strip_accents
from .tone import TONE_OLD, normalize_tone

_WORD = re.compile(r"\w+")
#: `lexical.STOPWORDS` ở dạng giữ dấu: token có dấu so với tập này — "chợ" (fold "cho") là nội dung, "cho" mới là từ chức năng.
TONE_STOPWORDS = frozenset({"ở", "và", "của", "cho", "tại", "gần", "đến", "từ", "có", "là", "những", "các", "một",
                            "the", "and", "of", "in", "at"})

#: Họ người Việt (giữ dấu, kiểu dấu cũ) — âm tiết đầu của cụm dạng tên riêng.
SURNAMES = frozenset({
    "nguyễn", "trần", "lê", "phạm", "hoàng", "huỳnh", "phan", "vũ", "võ", "đặng", "bùi", "đỗ", "hồ", "ngô", "dương",
    "lý", "đinh", "trương", "lâm", "trịnh", "lưu", "quách", "vương", "kiều", "đoàn", "lương", "triệu", "phùng", "hứa",
    "đào", "đàm", "mạc", "châu", "tạ", "thái", "khúc", "tôn", "doãn", "giang", "mai", "hà", "tô", "lại",
})
#: Họ khi câu KHÔNG dấu: chỉ những dạng fold không trùng từ thường hay gặp ("le", "ho", "do", "ha", "mai", "to", "cao"…).
SURNAMES_FOLDED = frozenset({
    "nguyen", "tran", "pham", "hoang", "huynh", "phan", "dang", "bui", "ngo", "duong", "dinh", "truong", "trinh",
    "luu", "quach", "vuong", "kieu", "doan", "luong", "trieu", "phung",
})


@lru_cache(maxsize=200_000)
def tone_form(word: str) -> str:
    """Chữ thường NFC, dấu thanh đặt theo kiểu cũ — khoá so khớp giữ dấu."""
    return normalize_tone(unicodedata.normalize("NFC", word).lower(), TONE_OLD)[0]


@dataclass(frozen=True)
class Tok:
    start: int
    end: int
    raw: str
    tone: str        # `tone_form(raw)`
    folded: str      # `fold(raw)`

    @property
    def accented(self) -> bool:
        return strip_accents(self.tone) != self.tone

    @property
    def is_content(self) -> bool:
        if self.folded.isdigit():
            return False
        return self.tone not in TONE_STOPWORDS if self.accented else self.folded not in STOPWORDS


def toks(text: str) -> list[Tok]:
    out = []
    for m in _WORD.finditer(unicodedata.normalize("NFC", text)):
        raw = m.group()
        f = fold(raw)
        if f:
            out.append(Tok(m.start(), m.end(), raw, tone_form(raw), f))
    return out


def _overlaps(t: Tok, spans: Iterable[tuple[int, int]]) -> bool:
    return any(s < t.end and t.start < e for s, e in spans)


@dataclass(frozen=True)
class Grams:
    """Unigram và bigram của một hoặc nhiều đoạn văn, ở cả dạng giữ dấu và dạng fold."""
    tone_uni: frozenset[str] = frozenset()
    fold_uni: frozenset[str] = frozenset()
    tone_bi: frozenset[str] = frozenset()
    fold_bi: frozenset[str] = frozenset()

    @classmethod
    def build(cls, texts: Iterable[str]) -> Grams:
        tu: set[str] = set()
        fu: set[str] = set()
        tb: set[str] = set()
        fb: set[str] = set()
        for text in texts:
            seq = toks(text or "")
            for t in seq:
                tu.add(t.tone)
                fu.add(t.folded)
            for a, b in zip(seq, seq[1:]):
                tb.add(f"{a.tone} {b.tone}")
                fb.add(f"{a.folded} {b.folded}")
        return cls(frozenset(tu), frozenset(fu), frozenset(tb), frozenset(fb))

    def has_uni(self, t: Tok) -> bool:
        return t.tone in self.tone_uni if t.accented else t.folded in self.fold_uni

    def has_bi(self, a: Tok, b: Tok) -> bool:
        """Cả hai có dấu → so giữ dấu; còn lại (người dùng bỏ dấu một phần) → so fold, chấp nhận lỏng."""
        if a.accented and b.accented:
            return f"{a.tone} {b.tone}" in self.tone_bi
        return f"{a.folded} {b.folded}" in self.fold_bi


def content(seq: Sequence[Tok], drop_folded: Iterable[str] = ()) -> list[Tok]:
    """Token mang nội dung (bỏ từ chức năng, số, và token fold thuộc `drop_folded` — vd điểm đến đã thành filter);
    bỏ hết thì giữ danh sách trước khi bỏ `drop_folded` (như `coverage` của use case)."""
    base = [t for t in seq if t.is_content]
    drop = frozenset(drop_folded)
    kept = [t for t in base if t.folded not in drop]
    return kept or base


def phrase_hit(q: Sequence[Tok], grams: Grams) -> bool:
    """1 token → có trong `grams`; ≥ 2 token → ít nhất một cặp kề nhau (đúng thứ tự) có trong `grams`."""
    if not q:
        return False
    if len(q) == 1:
        return grams.has_uni(q[0])
    return any(grams.has_bi(a, b) for a, b in zip(q, q[1:]))


def token_hit(q: Sequence[Tok], grams: Grams) -> bool:
    """Ít nhất một token nội dung có trong `grams` (giữ dấu khi câu có dấu) — mức bằng chứng của phần cộng RRF."""
    return any(grams.has_uni(t) for t in q)


def name_evidence(q: Sequence[Tok], name: Grams, min_coverage: float) -> bool:
    """Bằng chứng TÊN (vớt unit chỉ có ở BM25): khớp cụm trong tên và tên phủ ≥ `min_coverage` token của câu (giữ dấu)."""
    if not q:
        return False
    cov = sum(name.has_uni(t) for t in q) / len(q)
    return cov >= min_coverage and phrase_hit(q, name)


# ---------------------------------------------------------------------------------------------- residual
@dataclass(frozen=True)
class Residual:
    unexplained: tuple[str, ...] = ()                # có → câu không có đáp án (emptyReason `unexplained`)
    unparsed: tuple[str, ...] = ()                   # cụm lạ bỏ khỏi truy vấn
    unparsed_spans: tuple[tuple[int, int], ...] = field(default=())
    has_content: bool = False                        # còn token nội dung sau khi bỏ điều kiện + cụm lạ

    @property
    def empty(self) -> bool:
        return bool(self.unexplained)


def _name_like(run: Sequence[Tok]) -> bool:
    if len(run) < 2:
        return False
    first = run[0]
    if first.accented and first.tone in SURNAMES:
        return True
    if not first.accented and first.folded in SURNAMES_FOLDED:
        return True
    return all(t.raw[:1].isupper() for t in run)


#: Từ chung chung (fold) không tự nói người dùng muốn gì: không tính là nội dung khi xét "còn gì để tìm" (chỉ-filter, câu chỉ
#: còn chữ chung sau khi bỏ cụm lạ). Không phải cue loại sản phẩm (`constraints.VERTICAL_CUES` không đổi).
GENERIC_WORDS = frozenset({"tour", "du", "lich", "thong", "tin", "dich", "vu", "san", "pham", "gia", "re", "tot", "dep", "nhat"})


def _segments(text: str, removed: tuple[tuple[int, int], ...]) -> list[list[Tok]]:
    """Token nội dung theo đoạn liền nhau: từ chức năng, số, span đã tách (`removed`) cắt đoạn — hai token hai bên chỗ cắt
    không được ghép cặp ("Nguyễn Khắc Tiệp gần biển": "tiệp biển" không phải một cặp)."""
    out: list[list[Tok]] = [[]]
    for t in toks(text):
        if t.is_content and not _overlaps(t, removed):
            out[-1].append(t)
        elif out[-1]:
            out.append([])
    return [seg for seg in out if seg]


def explain_residual(text: str, removed: Iterable[tuple[int, int]], vocab: Grams, *, has_filters: bool) -> Residual:
    """Phần câu ngoài `removed` (span điều kiện, điểm đến, cue loại…) có được catalog giải thích không.

    Trong mỗi đoạn liền nhau (§`_segments`), token được giải thích khi tạo với token kề bên một cặp có trong `vocab`; đoạn một
    token thì xét unigram. Chuỗi liên tiếp token không giải thích được:
    - mọi chuỗi đều dạng tên riêng (≥ 2 âm tiết, mở đầu bằng họ hoặc viết hoa mọi âm tiết) và phủ TOÀN BỘ residual
      → `unexplained`;
    - câu không có filter nào và sau khi bỏ chuỗi lạ không còn gì ngoài chữ chung (`GENERIC_WORDS`), hoặc mọi token đều không
      có trong `vocab` → `unexplained` (câu vô nghĩa / chỉ có tên nơi lạ: "combo du lịch Cà Mau", "xkcd qwzt");
    - còn lại: chuỗi dạng tên hoặc chứa token lạ hẳn (unigram ∉ vocab) → `unparsed` (bỏ khỏi truy vấn); chuỗi toàn chữ quen
      thì giữ (dense vẫn hiểu được)."""
    segs = _segments(text, tuple(removed))
    seq = [t for seg in segs for t in seg]
    if not seq:
        return Residual()
    runs: list[list[Tok]] = []
    for seg in segs:
        if len(seg) == 1:
            explained = [vocab.has_uni(seg[0])]
        else:
            pair = [vocab.has_bi(a, b) for a, b in zip(seg, seg[1:])]
            explained = [(i > 0 and pair[i - 1]) or (i < len(pair) and pair[i]) for i in range(len(seg))]
        cur: list[Tok] = []
        for t, ok in zip(seg, explained):
            if ok:
                if cur:
                    runs.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            runs.append(cur)

    def phrase(r: Sequence[Tok]) -> str:
        return text[r[0].start:r[-1].end]

    covered = sum(len(r) for r in runs)
    if runs and covered == len(seq) and all(_name_like(r) for r in runs):
        return Residual(unexplained=tuple(phrase(r) for r in runs))
    if not has_filters and all(not vocab.has_uni(t) for t in seq):
        return Residual(unexplained=(text[seq[0].start:seq[-1].end],))
    drop = [r for r in runs if _name_like(r) or any(not vocab.has_uni(t) for t in r)]
    dropped = {id(t) for r in drop for t in r}
    left = [t for t in seq if id(t) not in dropped]
    if drop and not has_filters and all(t.folded in GENERIC_WORDS for t in left):
        return Residual(unexplained=tuple(phrase(r) for r in drop))
    return Residual(unparsed=tuple(phrase(r) for r in drop),
                    unparsed_spans=tuple((r[0].start, r[-1].end) for r in drop),
                    has_content=any(t.folded not in GENERIC_WORDS for t in left))


def has_content(text: str, removed: Iterable[tuple[int, int]]) -> bool:
    """Còn token nội dung (không phải từ chức năng / số / chữ chung `GENERIC_WORDS`) ngoài các span `removed` không."""
    spans = tuple(removed)
    return any(t.is_content and t.folded not in GENERIC_WORDS and not _overlaps(t, spans) for t in toks(text))
