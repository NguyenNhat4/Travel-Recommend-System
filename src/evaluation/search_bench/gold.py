"""Part 5 — gold: drafts → pool → split → (app gán nhãn) → kappa / merge → import → check.

Hợp đồng file giữa các bước nằm ở `gold_schema.py` (không sửa ở đây); luật gán nhãn ở `docs/spec/bench/gold-guide.md`.

- `drafts.txt`: mỗi dòng `query \\t slice [\\t filter_json] [\\t expected_no_result]`; dòng trống / bắt đầu `#` bỏ qua.
  qid = `case_id` của `drafts_raw.tsv` (map qua query + slice, kể cả query đã sửa trong `overrides.tsv`) hoặc `q001…`
  theo thứ tự dòng (`--qid line`, dùng cho fixture).
- `pool`: dense top-`depth` ∪ BM25 top-`depth` trên collection B0, cùng filter **đầy đủ** của draft (`unit_price_min ≤ X`
  là điều kiện cần của "có phòng ≤ X"). Mỗi dòng mang đủ thông tin để app hiển thị mà không cần catalog; filter ghi ra
  tách hai phần: điều kiện cấp parent (`filter_json`) và giá / số khách / ngày ở cấp room (`child_filter_json`).
  → `pool.csv` + `pool.build.json` (snapshot, collection, depth, seed, sha drafts và pool).
- `split`: câu chung phân tầng theo slice (slice có ≥ 2 câu có ≥ 1 câu chung), trong slice lấy mẫu hệ thống theo cỡ
  pool; câu riêng cân theo số **cặp** (mỗi slice lệch ≤ 1 câu, số cặp thường lệch ≤ 1); mỗi người đi các slice theo
  khối liền, B lệch nửa vòng so với A; trong khối câu riêng xáo riêng từng người và câu chung rải đều, nên thứ tự câu
  không cho biết câu nào là câu chung và hai người không gán cùng một câu chung cùng lúc; ứng viên mỗi câu xáo riêng
  từng người → `pool_A.csv`, `pool_B.csv`, `pool_meta.json`.
- `kappa` / `merge` / `import` / `check`: xem từng hàm. Mã thoát của nhóm lệnh `sb gold`: 0 đạt · 1 dữ liệu vi phạm luật
  (`RuleViolation`) · 2 lỗi đầu vào (`GoldError`, `SchemaError`: file thiếu, sai định dạng, sai sha).
"""
from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict

from .gold_schema import (CHILD_FILTER_FIELDS, OUT_OF_CATALOG_SLICE, PARENT_CHILD_SLICE, SLICES, Child, GoldRecord,
                          LabelRow, MergedRow, PoolFile, PoolMeta, PoolRow, SchemaError, atomic_write_text,
                          children_visible, file_sha256, read_labels_csv, read_pool_csv, read_pool_meta,
                          validate_label_against_pool, write_gold_jsonl, write_pool_csv, write_pool_meta)
from .store import filters as F

POOL_BUILD_SUFFIX = ".build.json"
AMENITIES_SHOWN = 12
SNIPPET_WORDS = 40


class GoldError(ValueError):
    """Lỗi đầu vào (file thiếu, sai định dạng, sai sha) → exit 2."""


class RuleViolation(Exception):
    """Dữ liệu vi phạm luật gold (thiếu nhãn, κ thấp, còn needs_discussion…) → exit 1. Gom đủ mọi lỗi rồi mới ném."""

    def __init__(self, title: str, problems: list[str]):
        self.title = title
        self.problems = list(problems)
        super().__init__(f"{title}: {len(self.problems)} lỗi")


def qid_num(qid: str) -> int:
    """Phần số ở cuối qid (`q007` → 7, `c0202` → 202) — dùng cho seed xáo và thứ tự."""
    m = re.search(r"(\d+)$", qid)
    if not m:
        raise GoldError(f"qid {qid!r} không có phần số ở cuối")
    return int(m.group(1))


@dataclass
class Draft:
    qid: str
    query: str
    slice: str
    filter: dict | None           # AST đã resolve (id amenity) — dùng truy vấn Weaviate
    filter_raw: str
    expected_no_result: bool
    line: int
    filter_keys: dict | None = None   # AST gốc (khoá amenity) — ghi ra pool / gold

    def with_qid(self, qid: str) -> "Draft":
        return Draft(qid, self.query, self.slice, self.filter, self.filter_raw, self.expected_no_result, self.line,
                     self.filter_keys)


def parse_drafts(path: Path, slices: list[str], key_to_id: dict[str, int]) -> list[Draft]:
    """drafts.txt → Draft (qid `q001…` theo thứ tự dòng; `case_ids_for` đổi sang case_id)."""
    if not path.exists():
        raise GoldError(f"không thấy {path} — drafts.txt do Người A soạn (checklist ngày 1)")
    out: list[Draft] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = raw.split("\t")
        if not 2 <= len(parts) <= 4:
            raise GoldError(f"{path.name}:{lineno}: cần 2–4 cột phân cách bằng TAB, gặp {len(parts)}")
        query, sl = parts[0].strip(), parts[1].strip()
        if not query:
            raise GoldError(f"{path.name}:{lineno}: query rỗng")
        if sl not in slices:
            raise GoldError(f"{path.name}:{lineno}: slice lạ {sl!r} (có: {', '.join(slices)})")
        fraw = parts[2].strip() if len(parts) > 2 else ""
        try:
            fkeys = F.parse(fraw)
            flt = F.resolve(fkeys, key_to_id) if fkeys else None
            split_filter(fkeys)                                        # tách được parent/child mới nhận
        except (F.FilterError, GoldError) as e:
            raise GoldError(f"{path.name}:{lineno}: {e}") from None
        eno_raw = parts[3].strip().lower() if len(parts) > 3 else ""
        if eno_raw not in ("", "true", "false"):
            raise GoldError(f"{path.name}:{lineno}: expected_no_result phải là true/false, gặp {parts[3]!r}")
        out.append(Draft(qid=f"q{len(out) + 1:03d}", query=query, slice=sl, filter=flt, filter_raw=fraw,
                         expected_no_result=eno_raw == "true", line=lineno, filter_keys=fkeys))
    if not out:
        raise GoldError(f"{path.name}: không có draft nào")
    dup = [q for q, n in Counter((d.query.lower(), d.slice) for d in out).items() if n > 1]
    if dup:
        raise GoldError(f"{path.name}: draft trùng (query, slice): {dup[:3]}")
    return out


def case_ids_for(drafts: list[Draft], raw_cases: list[dict], overrides: dict[str, dict]) -> list[str]:
    """case_id cho từng draft: khớp (query, slice) với `drafts_raw.tsv`, hoặc với `edited_query` của `overrides.tsv`.

    Không khớp / khớp nhiều case → GoldError (dùng `--qid line` nếu drafts không sinh từ drafts_raw.tsv).
    """
    index: dict[tuple[str, str], set[str]] = {}
    for r in raw_cases:
        qs = {r["query"].strip()}
        o = overrides.get(r["case_id"])
        if o and o.get("verdict") == "NEEDS_EDIT" and o.get("edited_query"):
            qs.add(o["edited_query"].strip())
        for q in qs:
            index.setdefault((q.casefold(), r["slice"]), set()).add(r["case_id"])
    out: list[str] = []
    bad: list[str] = []
    for d in drafts:
        cands = sorted(index.get((d.query.casefold(), d.slice), ()))
        if len(cands) != 1:
            bad.append(f"dòng {d.line} {d.query!r} [{d.slice}]: " + ("không khớp case nào" if not cands else f"khớp {cands}"))
        else:
            out.append(cands[0])
    if bad:
        raise GoldError("không map được draft sang case_id (thử `--qid line`; câu sửa chỉ có trong kho nhãn local thì "
                        "chép nó thành dòng NEEDS_EDIT của overrides.tsv — xem `sb gold drafts`):\n  "
                        + "\n  ".join(bad[:20]))
    dup = [c for c, n in Counter(out).items() if n > 1]
    if dup:
        raise GoldError(f"nhiều draft cùng map về một case_id: {dup[:5]}")
    return out


def local_only_edits(rows: list[dict], raw_cases: list[dict], overrides: dict[str, dict]) -> list[dict]:
    """Dòng đã chọn mang câu sửa (NEEDS_EDIT) chỉ có trong kho nhãn local (không commit): `drafts_raw.tsv` +
    `overrides.tsv` không tái hiện được câu này, nên `case_ids_for` — tức `sb gold pool --qid case`, máy khác, test
    trên drafts.txt đã commit — không map được sang case_id. So khớp đúng như `case_ids_for` (strip + casefold)."""
    raw_q = {r["case_id"]: r["query"].strip().casefold() for r in raw_cases}
    out = []
    for r in rows:
        q = r["query"].strip().casefold()
        o = overrides.get(r["case_id"]) or {}
        edited = (o.get("edited_query") or "").strip().casefold() if o.get("verdict") == "NEEDS_EDIT" else ""
        if q != raw_q.get(r["case_id"]) and q != edited:
            out.append(r)
    return out


# ------------------------------------------------------------------ filter: tách parent / child, viết thành chữ
CHILD_FIELD_MAP = {"unit_price_min": "unit_price"}      # field của drafts (cấp parent) → field của child_filter
assert set(CHILD_FIELD_MAP.values()) <= CHILD_FILTER_FIELDS
CHILD_OPS = ("eq", "lte", "lt", "gte", "gt")
_LEAF_OPS = ("eq", "in", "contains_all", "contains_any", "lte", "lt", "gte", "gt")


def _fields(node: dict) -> set[str]:
    (op, arg), = node.items()
    if op in ("and", "or"):
        return set().union(*(_fields(ch) for ch in arg))
    if op == "not":
        return _fields(arg)
    return {arg[0]}


def _conj(nodes: list[dict]) -> dict | None:
    return None if not nodes else nodes[0] if len(nodes) == 1 else {"and": nodes}


def split_filter(ast: dict | None) -> tuple[dict | None, dict | None]:
    """Filter của draft → (filter cấp parent, filter cấp room/flight). Chỉ tách conjunct ở mức ngoài cùng."""
    if not ast:
        return None, None
    conj = ast["and"] if next(iter(ast)) == "and" else [ast]
    parent: list[dict] = []
    child: list[dict] = []
    for n in conj:
        (op, arg), = n.items()
        if op in _LEAF_OPS and arg[0] in CHILD_FIELD_MAP:
            child.append({op: [CHILD_FIELD_MAP[arg[0]], arg[1]]})
        elif _fields(n) & set(CHILD_FIELD_MAP):
            raise GoldError(f"{', '.join(sorted(CHILD_FIELD_MAP))} chỉ được là điều kiện AND ở mức ngoài cùng, gặp {n}")
        else:
            parent.append(n)
    return _conj(parent), _conj(child)


def validate_child_filter(ast: dict | None) -> None:
    if ast is None:
        return
    (op, arg), = ast.items()
    if op == "and":
        for ch in arg:
            validate_child_filter(ch)
        return
    if op not in CHILD_OPS or not isinstance(arg, list) or len(arg) != 2 or arg[0] not in CHILD_FILTER_FIELDS:
        raise GoldError(f"child_filter chỉ gồm AND của {'/'.join(CHILD_OPS)} trên {sorted(CHILD_FILTER_FIELDS)}, gặp {ast}")


_SYM = {"eq": "=", "lte": "≤", "lt": "<", "gte": "≥", "gt": ">"}
_FIELD_VI = {"destination": "destination", "taxonomy": "loại", "variant": "loại", "star_rating": "hạng sao",
             "province": "tỉnh", "brand": "thương hiệu", "unit_price_min": "giá thấp nhất",
             "unit_price": "giá", "max_occupancy": "số khách", "departure_date": "ngày bay"}
_CHILD_SUFFIX = {"unit_price": "room", "max_occupancy": "room", "departure_date": "chuyến bay"}


def _num_vi(v: Any) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", ".")
    return str(v).replace(".", ",")


def _amen(xs: list, labels: dict) -> str:
    return ", ".join(str(labels.get(x, x)) for x in xs)


def _text(node: dict, labels: dict, child: bool) -> list[str]:
    (op, arg), = node.items()
    if op == "and":
        return [t for ch in arg for t in _text(ch, labels, child)]
    if op == "or":
        return ["(" + " hoặc ".join(" · ".join(_text(ch, labels, child)) for ch in arg) + ")"]
    if op == "not":
        (cop, carg), = arg.items()
        if cop == "contains_any":
            return [f"không có: {_amen(carg[1], labels)}"]
        return [f"{_FIELD_VI.get(carg[0], carg[0])} ≠ {carg[1]}"]
    f, v = arg
    if op == "contains_all":
        return [f"có tiện ích: {_amen(v, labels)}"]
    if op == "contains_any":
        return [f"có một trong: {_amen(v, labels)}"]
    if op == "in":
        return [f"{_FIELD_VI.get(f, f)} thuộc: {', '.join(map(str, v))}"]
    s = f"{_FIELD_VI.get(f, f)} {_SYM[op]} {_num_vi(v)}"
    if child:
        s += f" (kiểm ở cấp {_CHILD_SUFFIX.get(f, 'room')})"
    return [s]


def render_filter_text(parent: dict | None, child: dict | None, amenity_labels: dict | None = None) -> str:
    """Filter viết thành chữ cho người gán (mẫu c9003 của fixture); `amenity_labels` đổi khoá/id amenity → tên."""
    labels = amenity_labels or {}
    parts = (_text(parent, labels, False) if parent else []) + (_text(child, labels, True) if child else [])
    return " · ".join(parts)


# ------------------------------------------------------------------ pool: làm giàu ứng viên từ catalog của dataset
def _fold(s: str) -> str:
    from ..vector_bench.lexical import fold
    return fold(s)


@dataclass
class PoolView:
    """Những gì pool cần biết về từng search unit, không đọc lại Weaviate."""
    items: dict[str, dict]                       # product_id → name, variant, destination, star_rating, amenity_ids
    snippets: dict[str, str]
    children: dict[str, list[Child]]             # chỉ hotel_property
    amenity_label: dict[int, str]
    amenity_order: dict[int, tuple]              # seed trước raw, rồi tần suất giảm dần
    key_to_id: dict[str, int] = field(default_factory=dict)

    def labels_by_key(self) -> dict:
        out: dict = dict(self.amenity_label)
        out.update({k: self.amenity_label.get(i, k) for k, i in self.key_to_id.items()})
        return out


def snippet_of(text: str, n_words: int = SNIPPET_WORDS) -> str:
    return " ".join((text or "").split()[:n_words])


def load_pool_view(cfg, dataset: str, text_variant: str) -> PoolView:
    from . import catalog, paths
    from .textbuild import load_texts
    items = catalog.read_items(dataset)
    texts, _ = load_texts(cfg, dataset, text_variant)
    vocab = json.loads((paths.data_dir(dataset) / paths.AMENITY_VOCAB).read_text(encoding="utf-8"))
    records = catalog.reload_records(cfg, dataset)
    _, kids, _, _ = catalog.group_children(records, cfg.catalog.search_unit_variants)
    rows: dict[str, dict] = {}
    for r in items[["product_id", "name", "variant", "destination", "star_rating", "amenity_ids"]].to_dict("records"):
        star = r["star_rating"]
        r["star_rating"] = None if star is None or np.isnan(star) else round(float(star), 1)
        r["amenity_ids"] = [int(x) for x in (r["amenity_ids"] if r["amenity_ids"] is not None else [])]
        rows[r["product_id"]] = r
    children = {pid: sorted((Child(id=k["productId"], name=catalog._room_name(k) or k.get("name") or k["productId"])
                             for k in kids.get(pid, [])), key=lambda c: (c.name, c.id))
                for pid, r in rows.items() if r["variant"] == "hotel_property"}
    return PoolView(items=rows, snippets={p: snippet_of(t) for p, t in zip(texts["product_id"], texts["text"])},
                    children=children,
                    amenity_label={int(i): e["label"] for i, e in vocab.items()},
                    amenity_order={int(i): (0 if e.get("source") == "seed" else 1, -int(e.get("freq") or 0), int(i))
                                   for i, e in vocab.items()},
                    key_to_id=F.amenity_key_index(vocab))


def _amenity_ids_in(node: dict | None) -> set[int]:
    if not node:
        return set()
    (op, arg), = node.items()
    if op in ("and", "or"):
        return set().union(*(_amenity_ids_in(ch) for ch in arg))
    if op == "not":
        return _amenity_ids_in(arg)
    if op in ("contains_all", "contains_any"):
        return {x for x in arg[1] if isinstance(x, int)}
    return set()


def pick_amenities(ids: list[int], view: PoolView, *, must: set[int], query: str, k: int = AMENITIES_SHOWN) -> list[str]:
    """Tối đa k tên tiện ích: có trong filter → khớp nguyên từ trong câu hỏi (bỏ dấu) → seed → raw (tần suất giảm)."""
    q = f" {_fold(query)} "

    def key(i: int) -> tuple:
        lab = view.amenity_label.get(i, "")
        in_query = bool(lab) and f" {_fold(lab)} " in q
        return (0 if i in must else 1 if in_query else 2, *view.amenity_order.get(i, (2, 0, i)))

    return [view.amenity_label[i] for i in sorted(set(ids), key=key) if i in view.amenity_label][:k]


def pool_rows(draft: Draft, dense: list, lexical: list, view: PoolView) -> list[PoolRow]:
    """Hợp dense ∪ BM25 của một draft thành các dòng pool (sắp theo product_id; `split` xáo riêng cho từng người)."""
    ranks: dict[str, dict[str, int | None]] = {}
    for kind, hits in (("dense", dense), ("lexical", lexical)):
        for h in hits:
            ranks.setdefault(h.product_id, {"dense": None, "lexical": None})[kind] = h.rank
    parent, child = split_filter(draft.filter_keys)
    ftext = render_filter_text(parent, child, view.labels_by_key())
    must = _amenity_ids_in(draft.filter)
    out: list[PoolRow] = []
    for pid in sorted(ranks):
        it = view.items.get(pid)
        if it is None:
            raise GoldError(f"{pid} có trong collection nhưng không có trong items.parquet — collection và catalog lệch nhau")
        rd, rl = ranks[pid]["dense"], ranks[pid]["lexical"]
        out.append(PoolRow(
            qid=draft.qid, query=draft.query, slice=draft.slice, filter_text=ftext, filter_json=parent,
            child_filter_json=child, expected_no_result=draft.expected_no_result, product_id=pid, name=it["name"],
            taxonomy=it["variant"], destination=it["destination"] or "", star_rating=it["star_rating"],
            amenities=pick_amenities(it["amenity_ids"], view, must=must, query=draft.query),
            snippet=view.snippets.get(pid, ""), children=view.children.get(pid, []),
            source="both" if rd and rl else ("dense" if rd else "lexical"), rank_dense=rd, rank_lex=rl))
    return out


def build_pool(drafts: list[Draft], *, store: Any, embedder: Any, physical: str, fold_mode: str, depth: int,
               query_input_type: str, view: PoolView) -> list[PoolRow]:
    qvecs = embedder.embed([d.query for d in drafts], query_input_type)       # một lượt gom, qua cache
    rows: list[PoolRow] = []
    for d, qv in zip(drafts, qvecs):
        flt = F.to_weaviate(d.filter)
        dense = store.dense(physical, qv, depth, filters=flt)
        lexical = store.bm25(physical, d.query, depth, fold_mode=fold_mode, filters=flt)
        rows += pool_rows(d, dense, lexical, view)
    return rows


def empty_queries(drafts: list[Draft], rows: list[PoolRow]) -> list[str]:
    have = {r.qid for r in rows}
    return [d.qid for d in drafts if d.qid not in have]


def pool_summary(drafts: list[Draft], rows: list[PoolRow]) -> dict:
    per_q = Counter(r.qid for r in rows)
    n = sorted(per_q.values())
    return {"n_queries": len(drafts), "n_rows": len(rows),
            "docs_per_query": {"p50": float(np.median(n)) if n else 0.0, "max": max(n) if n else 0},
            "from": dict(Counter(r.source for r in rows)), "empty_queries": empty_queries(drafts, rows),
            "by_slice": dict(Counter(d.slice for d in drafts))}


class PoolBuild(BaseModel):
    """`pool.build.json` cạnh `pool.csv`: những gì `split` cần chép vào `pool_meta.json`."""
    model_config = ConfigDict(extra="forbid")

    snapshot: str
    collection: str
    depth: int
    seed: int
    qid_mode: str
    drafts_sha256: Optional[str] = None
    pool_sha256: str
    qids: list[str]
    empty_qids: list[str]
    slice_filter: Optional[str] = None
    created_at: datetime


def pool_build_path(pool_csv: Path) -> Path:
    return pool_csv.with_name(pool_csv.stem + POOL_BUILD_SUFFIX)


def write_pool_build(b: PoolBuild, path: Path) -> None:
    atomic_write_text(path, b.model_dump_json(indent=2) + "\n")


def read_pool_build(path: Path) -> PoolBuild:
    if not path.exists():
        raise GoldError(f"không thấy {path} — chạy lại `sb gold pool` (bản mới ghi kèm file này)")
    try:
        return PoolBuild.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise GoldError(f"{path}: {e}") from None


def snapshot_of(stats: dict, dataset: str) -> str:
    m = re.search(r"snapshots[\\/](\d{4}-\d{2}-\d{2})", str(stats.get("path", "")))
    return m.group(1) if m else dataset


def load_key_index(amenity_vocab_path: Path) -> dict[str, int]:
    if not amenity_vocab_path.exists():
        raise GoldError(f"chưa có {amenity_vocab_path} — chạy `sb catalog build` trước")
    return F.amenity_key_index(json.loads(amenity_vocab_path.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ split → pool_A / pool_B / pool_meta
def overlap_quota(slice_counts: dict[str, int], overlap: int) -> dict[str, int]:
    """Số câu chung mỗi slice, không vượt số câu của slice. Slice có ≥ 2 câu được ít nhất 1 câu chung khi `overlap` ≥ số
    slice đó (κ phủ mọi slice); phần còn lại chia theo tỷ lệ — largest remainder, hoà → tên slice. Chỉ số nguyên."""
    total = sum(slice_counts.values())
    names = sorted(slice_counts)
    eligible = [s for s in names if slice_counts[s] >= 2]
    floor = overlap >= len(eligible)
    quota = {s: int(floor and slice_counts[s] >= 2) for s in names}
    for _ in range(overlap - sum(quota.values())):
        open_ = [s for s in names if quota[s] < slice_counts[s]]
        if not open_:
            break
        # max giữ slice đầu tiên khi hoà → tên slice nhỏ hơn thắng
        s = max(open_, key=lambda s: overlap * slice_counts[s] - quota[s] * total)
        quota[s] += 1
    return quota


LABELER_INDEX = {"A": 0, "B": 1}
TAG_PICK = 1_000_001        # nhãn luồng RNG (qid_num < 10^5 nên không trùng luồng xáo ứng viên [seed, qid_num, người])
TAG_POS = 1_000_002


def _pick_shared(by_slice: dict[str, list[str]], size: dict[str, int], quota: dict[str, int],
                 seed: int) -> dict[str, bool]:
    """Câu chung trong mỗi slice: mẫu hệ thống, điểm đầu ngẫu nhiên, trên các câu xếp theo (cỡ pool, qid) → câu chung
    trải từ pool nhỏ tới pool lớn; mỗi câu có xác suất vào đúng quota/n. Mỗi slice một luồng RNG riêng."""
    shared: dict[str, bool] = {}
    for s, qs in by_slice.items():
        k = quota[s]
        if not k:
            continue
        cand = sorted(qs, key=lambda q: (size[q], qid_num(q), q))
        u = np.random.default_rng([seed, TAG_PICK, SLICES.index(s)]).random()
        for i in range(k):
            shared[cand[int((i + u) * len(cand) / k)]] = True
    return shared


def _assign_private(by_slice: dict[str, list[str]], size: dict[str, int], shared: dict[str, bool]) -> dict[str, str]:
    """Câu riêng → "A" / "B", cân theo số cặp (thời gian gán tỷ lệ với số ứng viên, không với số câu).

    Trong mỗi slice xếp câu theo cỡ giảm dần, chia từng cặp (lớn, nhỏ): câu lớn cho bên đang ít cặp hơn; câu lẻ cho bên
    đang ít câu hơn → mỗi slice và tổng lệch ≤ 1 câu. Sau đó đổi chéo A↔B trong cùng slice (giữ nguyên số câu) chừng nào
    còn thu hẹp được độ lệch số cặp. Không ngẫu nhiên, không dựa vào nội dung câu."""
    side: dict[str, str] = {}
    cnt = {"A": [0, 0], "B": [0, 0]}                      # [số cặp, số câu]

    def give(q: str, x: str) -> None:
        side[q] = x
        cnt[x][0] += size[q]
        cnt[x][1] += 1

    for qs in by_slice.values():
        priv = sorted((q for q in qs if q not in shared), key=lambda q: (-size[q], qid_num(q), q))
        for j in range(0, len(priv) - 1, 2):
            first = "A" if tuple(cnt["A"]) <= tuple(cnt["B"]) else "B"
            give(priv[j], first)
            give(priv[j + 1], "B" if first == "A" else "A")
        if len(priv) % 2:
            give(priv[-1], "A" if (cnt["A"][1], cnt["A"][0]) <= (cnt["B"][1], cnt["B"][0]) else "B")
    while True:
        delta = cnt["A"][0] - cnt["B"][0]
        best = None
        for si, qs in enumerate(by_slice.values()):
            qa = [q for q in qs if side.get(q) == "A"]
            qb = [q for q in qs if side.get(q) == "B"]
            for a in qa:
                for b in qb:
                    nd = abs(delta - 2 * (size[a] - size[b]))
                    key = (nd, si, qid_num(a), qid_num(b))
                    if nd < abs(delta) and (best is None or key < best[0]):
                        best = (key, a, b)
        if best is None:                                  # |delta| giảm ngặt mỗi vòng → vòng lặp dừng
            return side
        _, a, b = best
        cnt["A"][0] += size[b] - size[a]
        cnt["B"][0] += size[a] - size[b]
        side[a], side[b] = "B", "A"


def _rotation(slice_seq: list[str], counts: dict[str, int]) -> int:
    """Chỉ số r để tổng số câu của slice_seq[:r] gần một nửa nhất (hoà → r nhỏ hơn): B bắt đầu từ slice này."""
    total = sum(counts[s] for s in slice_seq)
    best, best_r, cum = None, 0, 0
    for r, s in enumerate(slice_seq):
        d = abs(2 * cum - total)
        if best is None or d < best:
            best, best_r = d, r
        cum += counts[s]
    return best_r


def _queue(labeler: str, slices: list[str], by_slice: dict[str, list[str]], side: dict[str, str],
           shared: dict[str, bool], seed: int) -> list[str]:
    """Thứ tự câu của một người: từng slice là một khối liền (luật riêng của slice gán liền mạch); trong khối, câu riêng
    xáo riêng từng người — giữ thứ tự pool (case_id tăng dần) thì câu chung chen vào sẽ lộ vì lệch thứ tự — câu chung đặt
    cách đều với điểm lệch ngẫu nhiên riêng từng người; tránh hai câu chung liền nhau qua ranh giới khối khi được."""
    out: list[str] = []
    for s in slices:
        # thứ tự rút cố định (câu riêng → câu chung → điểm lệch) để tất định
        rng = np.random.default_rng([seed, TAG_POS, SLICES.index(s), LABELER_INDEX[labeler]])
        priv = [q for q in by_slice[s] if side.get(q) == labeler]
        priv = [priv[i] for i in rng.permutation(len(priv))]
        sh = [q for q in by_slice[s] if q in shared]
        if not sh:
            out += priv
            continue
        sh = [sh[i] for i in rng.permutation(len(sh))]
        m, k = len(priv) + len(sh), len(sh)
        u = rng.random()
        pos = [int((i + u) * m / k) for i in range(k)]
        if out and out[-1] in shared and pos[0] == 0 and pos[-1] + 1 < m:
            pos = [p + 1 for p in pos]
        it_p, it_s = iter(priv), iter(sh)
        out += [next(it_s) if p in pos else next(it_p) for p in range(m)]
    return out


def split_pool(rows: list[PoolRow], overlap: int, seed: int) -> tuple[list[PoolRow], list[PoolRow], list[str]]:
    """(dòng của A, dòng của B, qid chung theo thứ tự pool).

    - Câu chung: `overlap_quota` theo slice (slice có ≥ 2 câu có ≥ 1 câu chung), trong slice lấy mẫu hệ thống theo cỡ pool.
    - Câu riêng: cân theo số cặp — mỗi slice và tổng lệch ≤ 1 câu, rồi đổi chéo trong slice tới khi không một lần đổi nào
      thu hẹp được |cặp A − cặp B| (thường ≤ 1; không bảo đảm, vd. mỗi slice chỉ một câu riêng thì không đổi được).
    - Thứ tự câu: khối slice liền; A đi các slice theo thứ tự pool, B bắt đầu từ slice ở khoảng giữa (lệch nửa vòng) → mỗi
      câu chung được hai người gán ở hai thời điểm xa nhau, không cùng lúc — cần không slice nào chiếm quá nửa số câu
      (một slice duy nhất thì A và B cùng bắt đầu, chỉ khác thứ tự trong khối). Trong khối câu riêng xáo riêng từng
      người, câu chung rải đều → thứ tự câu không cho biết câu nào là câu chung.
    - Ứng viên trong một câu: xếp theo product_id rồi xáo bằng rng([seed, qid_num, người gán]) — mỗi người một thứ tự.
    Tất định theo `seed`: không dùng `hash()`, không lặp theo thứ tự của set."""
    order: list[str] = []
    slice_of: dict[str, str] = {}
    by_q: dict[str, list[PoolRow]] = {}
    for r in rows:
        if r.qid not in by_q:
            order.append(r.qid)
            slice_of[r.qid] = r.slice
            by_q[r.qid] = []
        by_q[r.qid].append(r)
    n = len(order)
    if not 0 <= overlap < n:
        raise GoldError(f"overlap {overlap} phải trong [0, {n}) (số query của pool)")
    size = {q: len(by_q[q]) for q in order}
    by_slice: dict[str, list[str]] = {}                   # slice theo thứ tự xuất hiện trong pool, câu theo thứ tự pool
    for q in order:
        by_slice.setdefault(slice_of[q], []).append(q)
    slices = list(by_slice)
    counts = {s: len(qs) for s, qs in by_slice.items()}
    shared = _pick_shared(by_slice, size, overlap_quota(counts, overlap), seed)
    side = _assign_private(by_slice, size, shared)
    r0 = _rotation(slices, counts)
    queues = {"A": _queue("A", slices, by_slice, side, shared, seed),
              "B": _queue("B", slices[r0:] + slices[:r0], by_slice, side, shared, seed)}

    def rows_for(labeler: str) -> list[PoolRow]:
        out: list[PoolRow] = []
        for q in queues[labeler]:
            rs = sorted(by_q[q], key=lambda r: r.product_id)
            perm = np.random.default_rng([seed, qid_num(q), LABELER_INDEX[labeler]]).permutation(len(rs))
            out += [rs[i].model_copy(update={"is_overlap": q in shared}) for i in perm]
        return out

    return rows_for("A"), rows_for("B"), [q for q in order if q in shared]


def split_report(rows_a: list[PoolRow], rows_b: list[PoolRow], shared: list[str]) -> dict:
    """Số liệu để in sau `split` (không có qid câu chung): câu chung theo slice (k/n), số cặp chung, lệch số cặp, slice
    đầu của mỗi người, và `apart` — hai người có bắt đầu ở slice khác nhau và không slice nào chiếm quá nửa số câu (điều
    kiện để mỗi câu chung được gán ở hai thời điểm xa nhau)."""
    n_slice: dict[str, set] = {}
    for r in (*rows_a, *rows_b):
        n_slice.setdefault(r.slice, set()).add(r.qid)
    shared_set = set(shared)
    per = {s: f"{sum(q in shared_set for q in qs)}/{len(qs)}" for s, qs in n_slice.items()}
    first = {"A": rows_a[0].slice if rows_a else None, "B": rows_b[0].slice if rows_b else None}
    total = sum(len(qs) for qs in n_slice.values())
    return {"overlap_by_slice": per,
            "overlap_pairs": sum(r.is_overlap for r in rows_a),
            "delta_pairs": len(rows_a) - len(rows_b),
            "first_slice": first,
            "apart": first["A"] != first["B"] and all(2 * len(qs) <= total for qs in n_slice.values())}


def write_split(rows_a: list[PoolRow], rows_b: list[PoolRow], shared: list[str], build: PoolBuild, out_dir: Path, *,
                force: bool = False) -> PoolMeta:
    meta_p = out_dir / "pool_meta.json"
    labels = sorted((out_dir / "labels").glob("*.csv")) if (out_dir / "labels").exists() else []
    if meta_p.exists() and labels and not force:
        raise GoldError(f"{out_dir / 'labels'} đã có nhãn ({', '.join(p.name for p in labels)}) gắn với pool hiện tại — "
                        "chia lại sẽ làm lệch sha; thêm --force nếu thật sự muốn bỏ")
    files = {}
    for x, rs in (("A", rows_a), ("B", rows_b)):
        p = out_dir / f"pool_{x}.csv"
        write_pool_csv(rs, p)
        files[x] = PoolFile(path=p.name, sha256=file_sha256(p), labeler=x, n_queries=len({r.qid for r in rs}),
                            n_pairs=len(rs))
    meta = PoolMeta(snapshot=build.snapshot, collection=build.collection, depth=build.depth, seed=build.seed,
                    drafts_sha256=build.drafts_sha256, overlap_qids=shared, files=files,
                    created_at=datetime.now().astimezone().replace(microsecond=0))
    write_pool_meta(meta, meta_p)
    return meta


# ------------------------------------------------------------------ Part 5 (ngày 1): drafts_raw.tsv + nhãn app → drafts.txt

DRAFT_RAW_COLUMNS = ("case_id", "query", "slice", "filter_json", "expected_no_result", "source_refs", "review_note")
PHRASINGS_PER_INTENT = 3        # mỗi ý định sinh 3 cách nói liền nhau (gold-draft-prompt.md rule 10)
PER_ROW_INTENT_SLICES = ("out_of_catalog",)   # ở slice này 3 dòng là 3 taxonomy khác nhau → 3 ý định


def read_draft_cases(path: Path) -> list[dict]:
    """drafts_raw.tsv → list dict theo thứ tự file; kiểm đủ cột."""
    import csv as _csv

    if not path.exists():
        raise GoldError(f"không thấy {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(_csv.DictReader(fh, delimiter="\t"))
    if not rows:
        raise GoldError(f"{path.name}: không có dòng nào")
    missing = [c for c in DRAFT_RAW_COLUMNS if c not in rows[0]]
    if missing:
        raise GoldError(f"{path.name} thiếu cột {missing}")
    return rows


def intent_key(case_id: str, slice_: str) -> tuple[str, int]:
    """Ý định của một case. Mặc định 3 dòng liền nhau = 1 ý định; `out_of_catalog` thì mỗi dòng một ý định."""
    n = int(case_id.lstrip("c"))
    return (slice_, n) if slice_ in PER_ROW_INTENT_SLICES else (slice_, (n - 1) // PHRASINGS_PER_INTENT)


def resolve_decisions(events: list) -> tuple[dict[str, dict], list[str]]:
    """Nhãn mới nhất theo (case_id, annotator) → một quyết định cho mỗi case.

    Nhiều annotator cho cùng case mà khác verdict → bất đồng: trả về ở danh sách thứ hai và KHÔNG chọn case đó.
    """
    from .labeling import latest_by_annotator

    per_case: dict[str, list] = {}
    for (case_id, _ann), ev in latest_by_annotator(events).items():
        per_case.setdefault(case_id, []).append(ev)
    decisions: dict[str, dict] = {}
    conflicts: list[str] = []
    for case_id, evs in per_case.items():
        if len({e.verdict for e in evs}) > 1:
            conflicts.append(case_id)
            continue
        newest = max(evs, key=lambda e: (e.updated_at, e.event_id))
        decisions[case_id] = {"verdict": newest.verdict, "edited_query": newest.edited_query,
                              "rejection_reason": newest.rejection_reason, "annotator": newest.annotator}
    return decisions, sorted(conflicts)


# `review_note` chỉ là khoá ý định đầy đủ ở hai slice này (loại x dia danh / dia danh vang);
# o cac slice khac no chi mo ta khuon rang buoc (vi du multi_constraint: "star=3;price<=1000000"),
# hai y dinh khac diem den van dung chung note nen KHONG duoc coi la trung.
NOTE_IS_INTENT_KEY = ("dest_type", "out_of_catalog")
PHRASING_REASONS = ("duplicate", "unnatural")   # lỗi của cách nói, không phải của ý định → ý định vẫn dùng được


def select_drafts(cases: list[dict], decisions: dict[str, dict], quota: dict[str, int], *,
                  fill: bool = False, fill_guard=None, cap: bool = True) -> tuple[list[dict], dict]:
    """Chọn bộ draft cuối: giữ 1 cách nói cho mỗi ý định, cắt theo quota từng slice.

    `cap=False` (luật từ 28/09): lấy **mọi** ý định người soát đã chọn, không cắt theo quota — quota chỉ là mục tiêu
    tham khảo; `fill` (nếu bật) chỉ lấp slice còn dưới mục tiêu.

    Trả về (rows, report). `rows` giữ thứ tự case_id; mỗi row có query đã áp NEEDS_EDIT.
    """
    kept_by_intent: dict[tuple[str, int], dict] = {}
    dropped_duplicate: list[str] = []
    reasons: Counter = Counter()
    ungraded: Counter = Counter()
    for row in cases:
        case_id, sl = row["case_id"], row["slice"]
        if sl not in quota:
            raise GoldError(f"{case_id}: slice {sl!r} không có trong gold.slices")
        d = decisions.get(case_id)
        if d is None:
            ungraded[sl] += 1
            continue
        if d["verdict"] == "REJECT":
            reasons[d["rejection_reason"] or "other"] += 1
            continue
        query = d["edited_query"] if d["verdict"] == "NEEDS_EDIT" else row["query"]
        if not query.strip():
            raise GoldError(f"{case_id}: NEEDS_EDIT nhưng edited_query rỗng")
        key = intent_key(case_id, sl)
        if key in kept_by_intent:
            dropped_duplicate.append(case_id)     # giữ cách nói có case_id nhỏ nhất (dạng câu gốc)
            continue
        kept_by_intent[key] = {**row, "query": query.strip(), "verdict": d["verdict"], "annotator": d["annotator"]}

    by_intent_rows: dict[tuple[str, int], list[dict]] = {}
    for row in cases:
        by_intent_rows.setdefault(intent_key(row["case_id"], row["slice"]), []).append(row)

    filled: list[dict] = []
    skipped_fill: list[dict] = []
    selected: list[dict] = []
    over_quota: dict[str, list[str]] = {}
    per_slice: dict[str, dict] = {}
    for sl, q in quota.items():
        avail = sorted((r for r in kept_by_intent.values() if r["slice"] == sl), key=lambda r: r["case_id"])
        take, rest = (avail[:q], avail[q:]) if cap else (list(avail), [])
        if fill and len(take) < q:
            covered = {(r.get("review_note") or "").strip() for r in take} if sl in NOTE_IS_INTENT_KEY else set()
            # Ở slice mà note là khoá ý định, lỗi thật trên MỘT dòng (vd. out_of_catalog: điểm đến có sản phẩm trùng tên)
            # áp cho mọi dòng cùng note — không lấp lại "vé tham quan X" khi "resort ở X" đã bị loại vì X có trong catalog.
            dead_notes = set()
            if sl in NOTE_IS_INTENT_KEY:
                for r in cases:
                    v = decisions.get(r["case_id"])
                    if r["slice"] == sl and v and v["verdict"] == "REJECT" and (
                            (v["rejection_reason"] or "other") not in PHRASING_REASONS or v.get("annotator") == "override"):
                        dead_notes.add((r.get("review_note") or "").strip())
                dead_notes.discard("")
            for key, rows_ in sorted(by_intent_rows.items(), key=lambda kv: kv[1][0]["case_id"]):
                if len(take) >= q or key[0] != sl or key in kept_by_intent:
                    continue
                verdicts = [decisions.get(r["case_id"]) for r in rows_]
                graded = [v for v in verdicts if v is not None]
                # Lỗi của ý định (bịa thực thể, sai slice, grounding…) hay một REJECT trong overrides.tsv áp cho mọi cách
                # nói → loại cả ý định, kể cả khi còn dòng chưa gán. Chỉ duplicate/unnatural là lỗi của riêng một câu.
                bad = sorted({v["rejection_reason"] or "other" for v in graded if v["verdict"] == "REJECT"
                              and ((v["rejection_reason"] or "other") not in PHRASING_REASONS
                                   or v.get("annotator") == "override")})
                if bad:
                    skipped_fill.append({"case_id": rows_[0]["case_id"], "slice": sl,
                                         "why": "loại vì lỗi thật: " + ", ".join(bad)})
                    continue
                if len(graded) < len(verdicts):
                    kind = "chưa gán"
                else:
                    kind = "loại vì cách nói (" + ", ".join(sorted({v["rejection_reason"] for v in graded})) + ")"
                # Cách nói còn dùng được: chưa gán, hoặc chỉ bị loại vì trùng; bỏ câu người soát đã đánh `unnatural`.
                usable = [r for r, v in zip(rows_, verdicts) if v is None or v["rejection_reason"] == "duplicate"]
                if not usable:
                    skipped_fill.append({"case_id": rows_[0]["case_id"], "slice": sl,
                                         "why": "mọi cách nói đều bị đánh unnatural"})
                    continue
                cand = usable[0]                                  # cách nói gốc nhất còn dùng được
                note = (cand.get("review_note") or "").strip() if sl in NOTE_IS_INTENT_KEY else ""
                if note and note in dead_notes:
                    skipped_fill.append({"case_id": cand["case_id"], "slice": sl,
                                         "why": f"khoá ý định đã bị loại vì lỗi thật ở dòng khác ({note})"})
                    continue
                if note and note in covered:
                    skipped_fill.append({"case_id": cand["case_id"], "slice": sl,
                                         "why": f"trùng khoá ý định đã có ({note})"})
                    continue
                why = fill_guard(cand) if fill_guard else None
                if why:
                    skipped_fill.append({"case_id": cand["case_id"], "slice": sl, "why": why})
                    continue
                row = {**cand, "verdict": "AUTO_FILL", "annotator": "auto"}
                take.append(row)
                filled.append({"case_id": cand["case_id"], "slice": sl, "kind": kind, "query": cand["query"]})
                covered.add(note)
            take.sort(key=lambda r: r["case_id"])
        selected += take
        if rest:
            over_quota[sl] = [r["case_id"] for r in rest]
        per_slice[sl] = {"quota": q, "available_intents": len(avail), "selected": len(take),
                         "shortfall": max(0, q - len(take)), "ungraded_rows": ungraded[sl]}
    selected.sort(key=lambda r: r["case_id"])

    seen: dict[tuple[str, str], str] = {}
    for r in selected:
        k = (r["query"].casefold(), r["slice"])
        if k in seen:
            raise GoldError(f"{r['case_id']} trùng (query, slice) với {seen[k]} — parse_drafts sẽ từ chối")
        seen[k] = r["case_id"]

    report = {"per_slice": per_slice, "selected": len(selected), "target": sum(quota.values()),
              "dropped_duplicate": dropped_duplicate, "over_quota": over_quota,
              "reject_reasons": dict(reasons), "ungraded_total": sum(ungraded.values()),
              "filled": filled, "skipped_fill": skipped_fill}
    return selected, report


def make_fill_guard(items):
    """Hàng rào grounding của `--fill` (items.parquet của dataset): bỏ ý định mà mọi `source_refs` đã biến mất khỏi
    catalog, hoặc `filter_json` khớp 0 sản phẩm. Dùng chung cho CLI `gold drafts` và app Streamlit."""
    alive = set(items["product_id"])

    def guard(row: dict) -> Optional[str]:
        refs = [r for r in (row.get("source_refs") or "").split("|") if r.strip()]
        if refs and not any(r.strip() in alive for r in refs):
            return "mọi source_refs đã biến mất khỏi catalog"
        flt = (row.get("filter_json") or "").strip()
        if flt:
            try:
                n = int(F.mask(json.loads(flt), items).sum())
            except Exception as e:                                  # filter hỏng → để người soát xử lý
                return f"filter không đánh giá được ({e})"
            if n == 0:
                return "filter khớp 0 sản phẩm trong catalog hiện hành"
        return None

    return guard


def write_drafts(path: Path, rows: list[dict]) -> None:
    """Ghi `query \t slice [\t filter_json] [\t expected_no_result]` — đúng định dạng parse_drafts đọc."""
    out = drafts_lines(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(out) + "\n").encode("utf-8"))      # LF cả trên Windows (write_text sẽ ghi CRLF)


def drafts_lines(rows: list[dict]) -> list[str]:
    """Các dòng drafts.txt của bộ câu đã chọn (không ghi file) — app dùng để so với drafts.txt hiện tại."""
    out: list[str] = []
    for r in rows:
        flt = (r.get("filter_json") or "").strip()
        eno = (r.get("expected_no_result") or "").strip().lower()
        parts = [r["query"], r["slice"]]
        if eno in ("true", "false"):
            parts += [flt, eno]
        elif flt:
            parts.append(flt)
        if any("\t" in p for p in parts):
            raise GoldError(f"{r['case_id']}: giá trị chứa TAB, không ghi được")
        out.append("\t".join(parts))
    return out


def render_drafts_report(report: dict, min_per_slice: int | None = None) -> str:
    """Bảng theo slice. Có `min_per_slice` (luật 28/09): thêm cột tối thiểu và "đạt"; quota là mục tiêu tham khảo."""
    if min_per_slice is not None:
        lines = [f"| {'slice':22} | {'chọn':>5} | {'tối thiểu':>9} | {'đạt':>4} | {'mục tiêu':>8} | {'ý định có':>9} | "
                 f"{'chưa gán':>8} |",
                 f"|{'-' * 24}|{'-' * 7}|{'-' * 11}|{'-' * 6}|{'-' * 10}|{'-' * 11}|{'-' * 10}|"]
        for sl, s in report["per_slice"].items():
            ok = "✔" if s["selected"] >= min_per_slice else "✖"
            lines.append(f"| {sl:22} | {s['selected']:>5} | {min_per_slice:>9} | {ok:>4} | {s['quota']:>8} | "
                         f"{s['available_intents']:>9} | {s['ungraded_rows']:>8} |")
        lines.append(f"| {'TỔNG':22} | {report['selected']:>5} | {'':>9} | {'':>4} | {report['target']:>8} | {'':>9} | "
                     f"{report['ungraded_total']:>8} |")
        return "\n".join(lines)
    lines = [f"| {'slice':22} | {'chọn':>5} | {'quota':>5} | {'ý định có':>9} | {'thiếu':>5} | {'chưa gán':>8} |",
             f"|{'-' * 24}|{'-' * 7}|{'-' * 7}|{'-' * 11}|{'-' * 7}|{'-' * 10}|"]
    for sl, s in report["per_slice"].items():
        lines.append(f"| {sl:22} | {s['selected']:>5} | {s['quota']:>5} | {s['available_intents']:>9} | "
                     f"{s['shortfall']:>5} | {s['ungraded_rows']:>8} |")
    lines.append(f"| {'TỔNG':22} | {report['selected']:>5} | {report['target']:>5} | {'':>9} | "
                 f"{report['target'] - report['selected']:>5} | {report['ungraded_total']:>8} |")
    return "\n".join(lines)


def slices_below_min(report: dict, min_per_slice: int) -> list[str]:
    """Slice có ít hơn `min_per_slice` câu được chọn (kể cả slice 0 câu)."""
    return [sl for sl, s in report["per_slice"].items() if s["selected"] < min_per_slice]


OVERRIDE_COLUMNS = ("case_id", "verdict", "edited_query", "reason", "note")
OVERRIDE_VERDICTS = ("KEEP", "REJECT", "NEEDS_EDIT")


def read_overrides(path: Path, case_ids: set[str]) -> dict[str, dict]:
    """`gold/overrides.tsv`: quyết định ghi đè nhãn của app, có commit để truy được ai mở lại cái gì, vì sao.

    Dùng khi người dùng chốt sửa một quyết định mà không muốn ghi event giả mạo tên annotator vào kho nhãn.
    """
    import csv as _csv

    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in _csv.DictReader(fh, delimiter="\t") if (r.get("case_id") or "").strip()]
    out: dict[str, dict] = {}
    for i, r in enumerate(rows, 2):
        cid, verdict = r["case_id"].strip(), (r.get("verdict") or "").strip().upper()
        if cid not in case_ids:
            raise GoldError(f"{path.name}:{i}: case {cid} không có trong drafts_raw.tsv")
        if verdict not in OVERRIDE_VERDICTS:
            raise GoldError(f"{path.name}:{i}: verdict phải thuộc {OVERRIDE_VERDICTS}, gặp {verdict!r}")
        edited = (r.get("edited_query") or "").strip()
        if (verdict == "NEEDS_EDIT") != bool(edited):
            raise GoldError(f"{path.name}:{i}: edited_query chỉ có và bắt buộc có khi verdict = NEEDS_EDIT")
        if not (r.get("note") or "").strip():
            raise GoldError(f"{path.name}:{i}: cần ghi note lý do ghi đè")
        if cid in out:
            raise GoldError(f"{path.name}:{i}: case {cid} ghi đè hai lần")
        out[cid] = {"verdict": verdict, "edited_query": edited, "rejection_reason": (r.get("reason") or "").strip(),
                    "annotator": "override", "note": r["note"].strip()}
    return out


def apply_overrides(decisions: dict[str, dict], conflicts: list[str],
                    overrides: dict[str, dict]) -> tuple[dict[str, dict], list[str]]:
    """Ghi đè thắng mọi nhãn của app cho case đó, kể cả khi các annotator đang bất đồng."""
    merged = {**decisions, **overrides}
    return merged, [c for c in conflicts if c not in overrides]


# ------------------------------------------------------------------ Part 5 (ngày 3–4): kappa · merge · import · check
@dataclass
class PoolSet:
    """pool_meta.json + hai file pool đã kiểm sha, số dòng và câu chung."""
    meta: PoolMeta
    meta_path: Path
    rows: dict[str, list[PoolRow]]
    by_key: dict[str, dict[tuple[str, str], PoolRow]]

    def keys(self, labeler: str) -> set[tuple[str, str]]:
        return set(self.by_key[labeler])

    def all_keys(self) -> set[tuple[str, str]]:
        return self.keys("A") | self.keys("B")

    def row(self, key: tuple[str, str]) -> PoolRow:
        return self.by_key["A"].get(key) or self.by_key["B"][key]

    def overlap_keys(self) -> list[tuple[str, str]]:
        ov = set(self.meta.overlap_qids)
        return sorted(k for k in self.by_key["A"] if k[0] in ov)


_QUERY_FIELDS = ("query", "slice", "filter_json", "child_filter_json", "expected_no_result")


def load_pool_set(meta_path: Path) -> PoolSet:
    if not meta_path.exists():
        raise GoldError(f"không thấy {meta_path} — chạy `sb gold split` trước")
    try:
        meta = read_pool_meta(meta_path)
    except ValueError as e:
        raise GoldError(f"{meta_path}: {e}") from None
    rows: dict[str, list[PoolRow]] = {}
    by_key: dict[str, dict[tuple[str, str], PoolRow]] = {}
    for x in ("A", "B"):
        pf = meta.files.get(x)
        if pf is None:
            raise GoldError(f"{meta_path.name} thiếu files.{x}")
        p = Path(pf.path)
        p = p if p.is_absolute() else meta_path.parent / p
        if not p.exists():
            raise GoldError(f"không thấy {p} (files.{x} trong {meta_path.name})")
        sha = file_sha256(p)
        if sha != pf.sha256:
            raise GoldError(f"{p.name}: sha {sha[:12]}… khác meta {pf.sha256[:12]}… — pool đã bị sửa, hoặc git đổi ký tự "
                            "xuống dòng (xem .gitattributes)")
        try:
            rows[x] = read_pool_csv(p)
        except SchemaError as e:
            raise GoldError(str(e)) from None
        by_key[x] = {r.key: r for r in rows[x]}
        nq = len({r.qid for r in rows[x]})
        if (len(rows[x]), nq) != (pf.n_pairs, pf.n_queries):
            raise GoldError(f"{p.name}: {len(rows[x])} cặp / {nq} câu, meta ghi {pf.n_pairs} / {pf.n_queries}")
    ov = set(meta.overlap_qids)
    qa, qb = {k[0] for k in by_key["A"]}, {k[0] for k in by_key["B"]}
    problems = [f"{q}: câu chung nhưng không có trong pool_{x}" for q in sorted(ov)
                for x, qs in (("A", qa), ("B", qb)) if q not in qs]
    problems += [f"{q}: có trong cả hai pool nhưng không phải câu chung" for q in sorted((qa & qb) - ov)]
    for x in ("A", "B"):
        problems += [f"pool_{x} {r.qid}/{r.product_id}: is_overlap={r.is_overlap} lệch overlap_qids" for r in rows[x]
                     if r.is_overlap != (r.qid in ov)]
    for q in sorted(ov & qa & qb):
        pa = {k[1] for k in by_key["A"] if k[0] == q}
        pb = {k[1] for k in by_key["B"] if k[0] == q}
        if pa != pb:
            problems.append(f"{q}: hai pool có tập ứng viên khác nhau")
        ha = next(r for r in rows["A"] if r.qid == q)
        hb = next(r for r in rows["B"] if r.qid == q)
        diff = [f for f in _QUERY_FIELDS if getattr(ha, f) != getattr(hb, f)]
        if diff:
            problems.append(f"{q}: hai pool ghi khác nhau ở {diff}")
    if problems:
        raise GoldError(f"{meta_path.name}: pool A/B không nhất quán:\n  " + "\n  ".join(problems[:20]))
    return PoolSet(meta=meta, meta_path=meta_path, rows=rows, by_key=by_key)


def load_labels(path: Path, labeler: str, pools: PoolSet) -> list[LabelRow]:
    """labels_<X>.csv của đúng người gán X, gắn với đúng pool_<X> trong meta."""
    if not path.exists():
        raise GoldError(f"không thấy {path}")
    try:
        rows = read_labels_csv(path)
    except SchemaError as e:
        raise GoldError(str(e)) from None
    other = sorted({r.labeler for r in rows} - {labeler})
    if other:
        raise GoldError(f"{path.name} là nhãn của người gán {other[0]}, được đưa vào vị trí {labeler} — đảo thứ tự A/B?")
    want = pools.meta.files[labeler].sha256
    stale = Counter(r.pool_sha[:12] for r in rows if r.pool_sha != want)
    if stale:
        raise GoldError(f"{path.name}: {sum(stale.values())} nhãn gắn với pool khác (sha {dict(stale)}), meta hiện tại "
                        f"{want[:12]}… — nhãn gán trên pool cũ")
    return rows


@dataclass
class KappaResult:
    n: int
    confusion: list[list[int]]
    unweighted: float | None
    linear: float | None
    quadratic: float | None


def cohen_kappa(pairs: list[tuple[int, int]], k: int = 3) -> KappaResult:
    """κ Cohen cho nhãn 0..k-1; trọng số bất đồng: không trọng số, linear |i-j|/(k-1), quadratic. Không xác định → None."""
    conf = [[0] * k for _ in range(k)]
    for a, b in pairs:
        conf[a][b] += 1
    n = len(pairs)
    rows = [sum(r) for r in conf]
    cols = [sum(conf[i][j] for i in range(k)) for j in range(k)]

    def weighted(w) -> float | None:
        if n == 0:
            return None
        obs = sum(w(i, j) * conf[i][j] for i in range(k) for j in range(k))
        exp = sum(w(i, j) * rows[i] * cols[j] / n for i in range(k) for j in range(k))
        return None if exp == 0 else round(1 - obs / exp, 6)

    return KappaResult(n=n, confusion=conf, unweighted=weighted(lambda i, j: 0 if i == j else 1),
                       linear=weighted(lambda i, j: abs(i - j) / (k - 1)),
                       quadratic=weighted(lambda i, j: ((i - j) / (k - 1)) ** 2))


def overlap_pairs(pools: PoolSet, la: list[LabelRow], lb: list[LabelRow]
                  ) -> tuple[list[tuple[tuple[str, str], int, int]], list[str]]:
    """(các cặp chung đủ hai nhãn, danh sách cặp chung còn thiếu nhãn)."""
    a = {r.key: r.label for r in la}
    b = {r.key: r.label for r in lb}
    pairs, missing = [], []
    for key in pools.overlap_keys():
        lack = [x for x, m in (("A", a), ("B", b)) if key not in m]
        if lack:
            missing.append(f"{key[0]}/{key[1]} thiếu nhãn của {' và '.join(lack)}")
        else:
            pairs.append((key, a[key], b[key]))
    return pairs, missing


NOTE_GAP1 = "lệch 1 bậc: lấy nhãn thấp hơn"
NOTE_GAP2 = "lệch 2 bậc: cần thảo luận"
NOTE_NO_COMMON_CHILD = "cả hai gán 2 nhưng không tick chung hạng phòng nào"


def merge_pair(a: LabelRow | None, b: LabelRow | None, row: PoolRow) -> MergedRow:
    """Hoà nhãn một cặp theo luật may1 / gold-guide; note của người gán nối sau dạng ` | A: …`."""
    notes: list[str] = []
    if a and b:
        source = "both"
        if a.label == b.label:
            label, nd = a.label, False
            children = sorted(set(a.children_ok) & set(b.children_ok)) if a.label == 2 else []
            if a.label == 2 and children_visible(row) and not children:
                label, nd = None, True
                notes.append(f"{NOTE_NO_COMMON_CHILD} (A: {';'.join(a.children_ok)} · B: {';'.join(b.children_ok)})")
        elif abs(a.label - b.label) == 1:
            label, nd, children = min(a.label, b.label), False, []
            notes.append(NOTE_GAP1)
        else:
            label, nd, children = None, True, []
            notes.append(NOTE_GAP2)
    else:
        one = a or b
        source, label, nd, children = ("A" if a else "B"), one.label, False, list(one.children_ok)
    notes += [f"{x}: {r.note.strip()}" for x, r in (("A", a), ("B", b)) if r and r.note.strip()]
    return MergedRow(qid=row.qid, product_id=row.product_id, label=label, label_A=a.label if a else None,
                     label_B=b.label if b else None, children_ok=children, needs_discussion=nd, source=source,
                     note=" | ".join(notes))


def merge_labels(pools: PoolSet, la: list[LabelRow], lb: list[LabelRow]) -> list[MergedRow]:
    """Mọi cặp của pool phải có nhãn của người được giao; nhãn phải hợp lệ với dòng pool."""
    problems: list[str] = []
    by = {"A": {r.key: r for r in la}, "B": {r.key: r for r in lb}}
    for x in ("A", "B"):
        pool = pools.by_key[x]
        for key, r in sorted(by[x].items()):
            if key not in pool:
                problems.append(f"labels_{x}: {key[0]}/{key[1]} không có trong pool_{x}")
            else:
                problems += [f"labels_{x} {key[0]}/{key[1]}: {e}" for e in validate_label_against_pool(r, pool[key])]
        problems += [f"labels_{x}: {k[0]}/{k[1]} chưa gán" for k in sorted(set(pool) - set(by[x]))]
    if problems:
        raise RuleViolation("merge", problems)
    out = []
    for key in sorted(pools.all_keys()):
        a = by["A"].get(key) if key in pools.by_key["A"] else None
        b = by["B"].get(key) if key in pools.by_key["B"] else None
        out.append(merge_pair(a, b, pools.row(key)))
    return out


def read_catalog_parents(path: Path) -> dict[str, str | None]:
    """products.jsonl (snapshot) hoặc catalog giả → {productId: parentProductId | None}."""
    if not path.exists():
        raise GoldError(f"không thấy catalog {path}")
    out: dict[str, str | None] = {}
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                pid = r["productId"]
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                raise GoldError(f"{path.name}:{n}: {e}") from None
            out[pid] = r.get("parentProductId") or (r.get("attributes") or {}).get("parentProductId")
    return out


def build_gold(pools: PoolSet, merged: list, parents: dict[str, str | None], provenance: str) -> list[GoldRecord]:
    """merged.csv (đã hoà, đã thảo luận) → GoldRecord mỗi câu. Gom mọi lỗi rồi mới từ chối."""
    problems: list[str] = []
    by_key = {m.key: m for m in merged}
    want = pools.all_keys()
    problems += [f"{k[0]}/{k[1]}: còn needs_discussion — sửa trong merged.csv trước" for k, m in sorted(by_key.items())
                 if m.needs_discussion]
    problems += [f"{k[0]}/{k[1]}: thiếu trong merged.csv" for k in sorted(want - set(by_key))]
    problems += [f"{k[0]}/{k[1]}: không có trong pool" for k in sorted(set(by_key) - want)]
    stamp = datetime.now().astimezone()
    for key, m in sorted(by_key.items()):
        if key not in want or m.needs_discussion:
            continue
        pid = m.product_id
        if pid not in parents:
            problems.append(f"{key[0]}/{pid}: không có trong catalog snapshot")
        elif parents[pid]:
            problems.append(f"{key[0]}/{pid}: là sản phẩm con (của {parents[pid]}), nhãn phải ở cấp parent")
        for c in m.children_ok:
            if parents.get(c, "∅") != pid:
                problems.append(f"{key[0]}/{pid}: hạng phòng {c} không phải con của {pid} trong catalog")
        stand = LabelRow(qid=m.qid, product_id=pid, label=m.label, children_ok=m.children_ok, labeler="A",
                         labeled_at=stamp, pool_sha="")
        problems += [f"{key[0]}/{pid}: {e}" for e in validate_label_against_pool(stand, pools.row(key))]
    if problems:
        raise RuleViolation("import", problems)
    heads: dict[str, PoolRow] = {}
    for r in pools.rows["A"] + pools.rows["B"]:
        heads.setdefault(r.qid, r)
    records = []
    for qid in sorted(heads):
        ms = [m for k, m in sorted(by_key.items()) if k[0] == qid]
        h = heads[qid]
        records.append(GoldRecord(
            qid=qid, text=h.query, slice=h.slice, filter=h.filter_json, child_filter=h.child_filter_json,
            expected_no_result=h.expected_no_result, judgments={m.product_id: m.label for m in ms},
            provenance={m.product_id: provenance for m in ms},
            expected_children={m.product_id: m.children_ok for m in ms if m.children_ok}))
    return records


def write_gold_checked(records: list[GoldRecord], out: Path, *, overwrite: bool = False) -> bool:
    """Ghi gold.jsonl (qua `write_gold_jsonl`); file đã có mà khác nội dung → GoldError trừ khi overwrite (Part 11:
    gold chỉ thêm). Trả về True nếu nội dung đổi."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "gold.jsonl"
        write_gold_jsonl(records, tmp)
        new = tmp.read_bytes()
    if out.exists():
        if out.read_bytes() == new:
            return False
        if not overwrite:
            raise GoldError(f"{out} đã có và khác nội dung mới — gold chỉ được thêm (spec Part 11); "
                            "thêm --overwrite nếu chưa tag gold_v1")
    atomic_write_text(out, new.decode("utf-8"))
    return True


@dataclass
class CheckReport:
    per_slice: dict[str, Counter]
    n_queries: dict[str, int]
    problems: list[str]
    warnings: list[str]


def check_gold(records: list[GoldRecord], min_per_slice: int, configured_slices: list[str]) -> CheckReport:
    """Luật `sb gold check` trên các câu active; slice chỉ xét các slice có mặt (slice cấu hình mà vắng → cảnh báo)."""
    problems: list[str] = []
    warnings: list[str] = []
    dup = [q for q, n in Counter(r.qid for r in records).items() if n > 1]
    problems += [f"{q}: qid trùng" for q in dup]
    active = [r for r in records if r.status == "active"]
    per_slice: dict[str, Counter] = {}
    n_q: Counter = Counter()
    for r in active:
        labels = list(r.judgments.values())
        if not labels:
            problems.append(f"{r.qid}: không có nhãn")
        n_q[r.slice] += 1
        per_slice.setdefault(r.slice, Counter()).update(labels)
        if r.slice not in SLICES:
            problems.append(f"{r.qid}: slice lạ {r.slice!r}")
        if r.slice == OUT_OF_CATALOG_SLICE:
            if 2 in labels:
                problems.append(f"{r.qid}: out_of_catalog nhưng có nhãn 2 ({[p for p, v in r.judgments.items() if v == 2]})")
            if not r.expected_no_result:
                problems.append(f"{r.qid}: out_of_catalog thiếu expected_no_result")
        else:
            if 2 not in labels:
                problems.append(f"{r.qid} [{r.slice}]: không có nhãn 2")
            if r.expected_no_result:
                warnings.append(f"{r.qid} [{r.slice}]: expected_no_result=true ngoài out_of_catalog")
        if r.slice == PARENT_CHILD_SLICE:
            problems += [f"{r.qid}/{p}: nhãn 2 ở parent_child thiếu expected_children" for p, v in r.judgments.items()
                         if v == 2 and not r.expected_children.get(p)]
    problems += [f"slice {s}: {n} câu < {min_per_slice}" for s, n in sorted(n_q.items()) if n < min_per_slice]
    absent = [s for s in configured_slices if s not in n_q]
    if absent:
        warnings.append(f"slice trong config chưa có câu active nào: {', '.join(absent)}")
    return CheckReport(per_slice=per_slice, n_queries=dict(n_q), problems=problems, warnings=warnings)
