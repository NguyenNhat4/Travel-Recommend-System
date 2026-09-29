"""Bổ sung câu hỏi gold bằng tay (app Streamlit, chế độ "Bổ sung câu hỏi").

Ý định mới đi đúng luồng sẵn có, không tạo file mới:
    drafts_raw.tsv  (thêm dòng c0673…, mỗi ý định một khối 3 mã — `gold.intent_key` coi 3 mã liền nhau là 1 ý định)
    overrides.tsv   (tuỳ chọn: KEEP cho các dòng vừa thêm, vì người thêm chính là người quyết định)
    → `sb gold drafts --fill` chọn vào drafts.txt khi slice còn chỗ trong quota `gold.slices`.
Luật kiểm tra lấy từ các đợt bổ sung 24/09 (drafts_manifest.json → supplements) và `docs/spec/bench/gold-guide.md`.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import gold
from .gold_schema import atomic_write_text
from .store import filters as F

RAW_FILE = "drafts_raw.tsv"
OVERRIDES_FILE = "overrides.tsv"
DRAFTS_FILE = "drafts.txt"
OOC = "out_of_catalog"
MULTI = "multi_constraint"
MULTI_MATCH_RANGE = (5, 40)           # filter multi_constraint lý tưởng khớp 5–40 sản phẩm (phản biện 24/09)
OOC_NOTE_PREFIX = "absent destination:"

STATUS_IN = "trong drafts.txt"
STATUS_REJECTED = "đã loại (overrides)"
STATUS_SAME_KEY = "cùng khoá với ý định đã chọn"
STATUS_DEAD_KEY = "khoá đã bị loại"
STATUS_UNUSED = "chưa dùng"


@dataclass
class AuthoringState:
    gold_dir: Path
    raw: list[dict]
    overrides: dict[str, dict]
    selected: set[str]                  # case_id đang có trong drafts.txt
    quota: dict[str, int]
    drafts_error: str | None = None     # drafts.txt không map được sang case_id (vd sửa tay)


@dataclass
class IntentView:
    slice: str
    case_ids: list[str]
    queries: list[str]
    review_note: str
    filter_json: str
    source_refs: str
    status: str


@dataclass
class NewIntent:
    slice: str
    phrasings: list[str]
    review_note: str = ""
    filter_json: str = ""
    source_refs: list[str] = field(default_factory=list)
    place: str = ""                     # chỉ out_of_catalog: điểm đến không có trong catalog

    def clean_phrasings(self) -> list[str]:
        return [p.strip() for p in self.phrasings if p and p.strip()]

    def note(self) -> str:
        if self.slice == OOC and self.place.strip():
            return OOC_NOTE_PREFIX + self.place.strip()
        return self.review_note.strip()


def drafts_case_ids(path: Path, raw: list[dict], overrides: dict[str, dict]) -> list[str]:
    """case_id của từng dòng drafts.txt (không cần parse filter — chỉ khớp query + slice như `gold.case_ids_for`)."""
    ds = []
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        ds.append(gold.Draft(qid=f"q{n}", query=parts[0].strip(), slice=parts[1].strip() if len(parts) > 1 else "",
                             filter=None, filter_raw="", expected_no_result=False, line=n))
    return gold.case_ids_for(ds, raw, overrides)


def load_state(gold_dir: Path, quota: dict[str, int]) -> AuthoringState:
    raw = gold.read_draft_cases(gold_dir / RAW_FILE)
    overrides = gold.read_overrides(gold_dir / OVERRIDES_FILE, {r["case_id"] for r in raw})
    selected: set[str] = set()
    err = None
    p = gold_dir / DRAFTS_FILE
    if p.exists():
        try:
            selected = set(drafts_case_ids(p, raw, overrides))
        except gold.GoldError as e:
            err = str(e)
    return AuthoringState(gold_dir=gold_dir, raw=raw, overrides=overrides, selected=selected, quota=dict(quota),
                          drafts_error=err)


def intents(state: AuthoringState, slice_: str) -> list[IntentView]:
    groups: dict[tuple, list[dict]] = {}
    for r in state.raw:
        if r["slice"] == slice_:
            groups.setdefault(gold.intent_key(r["case_id"], r["slice"]), []).append(r)
    ordered = sorted(groups.values(), key=lambda rs: gold.qid_num(rs[0]["case_id"]))
    keyed = slice_ in gold.NOTE_IS_INTENT_KEY            # dest_type / out_of_catalog: review_note là khoá ý định

    def note_of(rs: list[dict]) -> str:
        return (rs[0].get("review_note") or "").strip()

    def rejected(rs: list[dict]) -> bool:
        return any(state.overrides.get(r["case_id"], {}).get("verdict") == "REJECT" for r in rs)

    covered = {note_of(rs) for rs in ordered if any(r["case_id"] in state.selected for r in rs)} if keyed else set()
    dead = {note_of(rs) for rs in ordered if rejected(rs)} if keyed else set()
    out = []
    for rows in ordered:
        ids = [r["case_id"] for r in rows]
        if any(c in state.selected for c in ids):
            status = STATUS_IN
        elif rejected(rows):
            status = STATUS_REJECTED
        elif note_of(rows) in covered:
            status = STATUS_SAME_KEY
        elif note_of(rows) in dead:
            status = STATUS_DEAD_KEY
        else:
            status = STATUS_UNUSED
        queries = []
        for r in rows:
            o = state.overrides.get(r["case_id"])
            queries.append(o["edited_query"] if o and o.get("verdict") == "NEEDS_EDIT" else r["query"])
        out.append(IntentView(slice=slice_, case_ids=ids, queries=queries, review_note=rows[0].get("review_note") or "",
                              filter_json=rows[0].get("filter_json") or "", source_refs=rows[0].get("source_refs") or "",
                              status=status))
    return out


def slice_summary(state: AuthoringState, min_per_slice: int) -> list[dict]:
    """Mỗi slice: mục tiêu (quota, tham khảo), số ý định trong drafts.txt, số ý định còn dùng được. `dưới tối thiểu` =
    drafts.txt có ít hơn `min_per_slice` câu của slice (luật 28/09: mỗi slice ≥ 3 câu, không cần đủ mục tiêu)."""
    out = []
    for sl, q in state.quota.items():
        its = intents(state, sl)
        n_in = sum(i.status == STATUS_IN for i in its)
        spare = sum(i.status == STATUS_UNUSED for i in its)
        out.append({"slice": sl, "mục tiêu": q, "trong drafts.txt": n_in, "ý định có": len(its), "chưa dùng": spare,
                    "dưới tối thiểu": n_in < min_per_slice})
    return out


def next_block_start(raw: list[dict]) -> int:
    """Số case đầu tiên sau mã lớn nhất, căn theo khối 3 (`(n - 1) % 3 == 0`)."""
    n = max((gold.qid_num(r["case_id"]) for r in raw), default=0) + 1
    while (n - 1) % gold.PHRASINGS_PER_INTENT:
        n += 1
    return n


def _existing_queries(state: AuthoringState) -> set[tuple[str, str]]:
    out = {(r["query"].strip().casefold(), r["slice"]) for r in state.raw}
    by_id = {r["case_id"]: r for r in state.raw}
    for cid, o in state.overrides.items():
        if o.get("edited_query") and cid in by_id:
            out.add((o["edited_query"].strip().casefold(), by_id[cid]["slice"]))
    return out


def validate(state: AuthoringState, new: NewIntent, cat=None) -> tuple[list[str], list[str]]:
    """(lỗi chặn lưu, cảnh báo). `cat` = `catalog_lookup.Catalog` để kiểm grounding; None thì bỏ các phép kiểm đó."""
    from .catalog_lookup import filter_mask, known_refs, place_hits

    errors: list[str] = []
    warns: list[str] = []
    if new.slice not in state.quota:
        return [f"slice lạ {new.slice!r}"], warns
    phr = new.clean_phrasings()
    if not phr:
        errors.append("cần ít nhất một cách nói")
    if len(phr) > gold.PHRASINGS_PER_INTENT:
        errors.append(f"tối đa {gold.PHRASINGS_PER_INTENT} cách nói cho một ý định")
    seen = _existing_queries(state)
    for p in phr:
        if "\t" in p or "\n" in p:
            errors.append(f"câu {p!r} chứa TAB / xuống dòng")
        k = (p.casefold(), new.slice)
        if k in seen:
            errors.append(f"câu {p!r} đã có trong slice {new.slice}")
        seen.add(k)
    note = new.note()
    if not note:
        errors.append("cần review_note (mô tả ý định, như các dòng cùng slice)" if new.slice != OOC
                      else "nhập điểm đến không có trong catalog")
    if note and new.slice in gold.NOTE_IS_INTENT_KEY:
        same = [i for i in intents(state, new.slice) if i.review_note.strip() == note]
        if same:
            errors.append(f"khoá ý định {note!r} đã có ở {', '.join(same[0].case_ids)} ({same[0].status})")
    refs = [r.strip() for r in new.source_refs if r and r.strip()]
    flt = None
    if new.filter_json.strip():
        try:
            flt = F.parse(new.filter_json.strip())
            gold.split_filter(flt)
        except (F.FilterError, gold.GoldError) as e:
            errors.append(f"filter_json: {e}")
    if new.slice == OOC:
        if flt is not None or refs:
            errors.append("out_of_catalog không có filter_json / source_refs")
        if cat is not None and new.place.strip():
            hits = place_hits(cat, new.place)
            if len(hits):
                ex = "; ".join(f"{n} ({v}, {d})" for n, v, d in hits[["name", "variant", "destination"]].head(3).itertuples(index=False))
                errors.append(f"catalog có {len(hits)} sản phẩm nhắc tới {new.place.strip()!r} (vd {ex}) — câu không còn "
                              "ngoài catalog")
    else:
        if new.slice == MULTI and flt is None:
            errors.append("multi_constraint cần filter_json (dựng ở chế độ Tra cứu catalog → Tìm sản phẩm)")
        if not refs:
            errors.append("cần ít nhất một source_refs: sản phẩm thoả câu hỏi (chọn ở chế độ Tra cứu catalog)")
        if cat is not None and refs:
            _, bad = known_refs(cat, refs)
            if bad:
                errors.append(f"source_refs không phải search unit trong catalog: {bad}")
        if cat is not None and flt is not None:
            try:
                m = filter_mask(cat, flt)
                n = int(m.sum())
                if n == 0:
                    errors.append("filter khớp 0 sản phẩm trong catalog")
                elif new.slice == MULTI and not MULTI_MATCH_RANGE[0] <= n <= MULTI_MATCH_RANGE[1]:
                    warns.append(f"filter khớp {n} sản phẩm (nên {MULTI_MATCH_RANGE[0]}–{MULTI_MATCH_RANGE[1]})")
                ok = set(cat.items.index[m])
                miss = [r for r in refs if r in cat.items.index and r not in ok]
                if miss:
                    warns.append(f"source_refs không thoả filter: {miss}")
            except F.FilterError as e:
                errors.append(f"filter_json: {e}")
    return errors, warns


def _tsv_line(values: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter="\t", lineterminator="\n").writerow(values)
    return buf.getvalue()


def _append(path: Path, text: str) -> None:
    old = path.read_bytes().decode("utf-8") if path.exists() else ""
    if old and not old.endswith("\n"):
        old += "\n"
    atomic_write_text(path, old + text)


def append_intent(state: AuthoringState, new: NewIntent, *, author: str, keep: bool = True,
                  today: date | None = None) -> list[str]:
    """Ghi ý định vào drafts_raw.tsv (+ KEEP vào overrides.tsv nếu `keep`). Gọi `validate` trước; trả về case_id mới."""
    phr = new.clean_phrasings()
    start = next_block_start(state.raw)
    ids = [f"c{start + i:04d}" for i in range(len(phr))]
    flt = F.parse(new.filter_json.strip()) if new.filter_json.strip() else None
    fjson = json.dumps(flt, ensure_ascii=False, separators=(",", ":")) if flt is not None else ""
    eno = "true" if new.slice == OOC else ""
    refs = "|".join(r.strip() for r in new.source_refs if r and r.strip())
    note = new.note()
    _append(state.gold_dir / RAW_FILE,
            "".join(_tsv_line([cid, q, new.slice, fjson, eno, refs, note]) for cid, q in zip(ids, phr)))
    if keep:
        when = (today or date.today()).isoformat()
        why = f"tự thêm {when} qua app (người thêm: {author or 'không ghi'}): {note}"
        _append(state.gold_dir / OVERRIDES_FILE, "".join(_tsv_line([cid, "KEEP", "", "", why]) for cid in ids))
    return ids
