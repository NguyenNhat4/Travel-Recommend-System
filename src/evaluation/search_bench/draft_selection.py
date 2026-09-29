"""Bộ câu đã chọn (drafts.txt), thêm / thay / loại từng câu — chế độ "Bộ câu đã chọn" của app Streamlit.

Luật từ 28/09 (người dùng chốt): drafts.txt = **mọi** câu người soát đã chọn (KEEP / NEEDS_EDIT trong app hoặc
`overrides.tsv`), không cắt theo quota, không tự lấp — mỗi slice cần ≥ `gold.min_per_slice` (3) câu; quota `gold.slices`
chỉ là mục tiêu tham khảo. Tính giống `sb gold drafts` (mặc định). Câu mà `--fill` sẽ lấp chỉ hiện như **gợi ý**.
Mọi quyết định ghi vào `overrides.tsv` (commit được, thắng nhãn của app):
- thêm câu chưa chọn: KEEP (giữ NEEDS_EDIT nếu câu đó đang có);
- thay bằng cách nói khác / ý định khác: REJECT câu hiện tại + KEEP câu được chọn;
- viết lại: NEEDS_EDIT (cùng ý định) hoặc case mới + REJECT (ý định mới);
- loại: REJECT (slice bớt một câu).
Không import streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import gold
from .gold_schema import atomic_write_text
from .labeling import JsonlLabelStore

SOURCE_HUMAN = "người soát"
SOURCE_OVERRIDE = "overrides.tsv"
SOURCE_FILL = "--fill"
KIND_PHRASING = "cách nói khác"
KIND_INTENT = "ý định khác"


@dataclass
class Selection:
    cases: list[dict]
    by_id: dict[str, dict]
    decisions: dict[str, dict]
    overrides: dict[str, dict]
    conflicts: list[str]
    rows: list[dict]                 # kết quả select_drafts (thứ tự case_id) — đúng nội dung drafts.txt sẽ ghi
    report: dict
    quota: dict[str, int]
    n_events: int
    suggested: dict[str, str] | None = None      # case_id → lý do: câu `--fill` sẽ lấp (gợi ý thêm vào bộ)

    @property
    def filled_ids(self) -> dict[str, str]:
        return {f["case_id"]: f["kind"] for f in self.report["filled"]}

    def selected_ids(self) -> set[str]:
        return {r["case_id"] for r in self.rows}


@dataclass
class Alternative:
    case_id: str
    query: str
    kind: str
    status: str
    blocked: bool                    # từng bị loại vì lỗi thật / overrides — vẫn chọn được nhưng cần cân nhắc

    def label(self) -> str:
        return f"{self.kind}: {self.case_id} · {self.query} — {self.status}{' ⚠' if self.blocked else ''}"


def compute(gold_dir: Path, labels_path: Path | None, quota: dict[str, int], items=None, *, fill: bool = False,
            cap: bool = False) -> Selection:
    """Mặc định theo luật 28/09 (`fill=False, cap=False`). `items` (items.parquet) bật hàng rào grounding cho phần gợi ý."""
    cases = gold.read_draft_cases(gold_dir / "drafts_raw.tsv")
    events = JsonlLabelStore(labels_path).load_events() if labels_path and labels_path.exists() else []
    decisions, conflicts = gold.resolve_decisions(events)
    overrides = gold.read_overrides(gold_dir / "overrides.tsv", {r["case_id"] for r in cases})
    decisions, conflicts = gold.apply_overrides(decisions, conflicts, overrides)
    guard = gold.make_fill_guard(items) if items is not None else None
    rows, report = gold.select_drafts(cases, decisions, dict(quota), fill=fill, fill_guard=guard, cap=cap)
    _, sug = gold.select_drafts(cases, decisions, dict(quota), fill=True, fill_guard=guard, cap=cap)
    chosen = {r["case_id"] for r in rows}
    suggested = {f["case_id"]: f["kind"] for f in sug["filled"] if f["case_id"] not in chosen}
    return Selection(cases=cases, by_id={r["case_id"]: r for r in cases}, decisions=decisions, overrides=overrides,
                     conflicts=conflicts, rows=rows, report=report, quota=dict(quota), n_events=len(events),
                     suggested=suggested)


def slice_status(sel: Selection, min_per_slice: int) -> list[dict]:
    """Mỗi slice: số câu đã chọn, đạt tối thiểu chưa, mục tiêu tham khảo, số câu chưa chọn có thể thêm, số gợi ý."""
    chosen: dict[str, int] = {}
    for r in sel.rows:
        chosen[r["slice"]] = chosen.get(r["slice"], 0) + 1
    out = []
    for sl, target in sel.quota.items():
        cands = candidates(sel, sl)
        n = chosen.get(sl, 0)
        out.append({"slice": sl, "đã chọn": n, "tối thiểu": min_per_slice, "đạt": n >= min_per_slice,
                    "mục tiêu": target, "có thể thêm": len(cands),
                    "gợi ý --fill": sum(c.case_id in (sel.suggested or {}) for c in cands)})
    return out


def source_of(sel: Selection, row: dict) -> tuple[str, str]:
    """(nguồn, chi tiết) của một câu trong bộ đã chọn."""
    if row.get("verdict") == "AUTO_FILL":
        return SOURCE_FILL, sel.filled_ids.get(row["case_id"], "tự lấp")
    if row.get("annotator") == "override":
        o = sel.overrides.get(row["case_id"], {})
        return SOURCE_OVERRIDE, f"{row['verdict']} · {o.get('note', '')}"
    return SOURCE_HUMAN, f"{row['verdict']} · {row.get('annotator') or ''}"


def selected_table(sel: Selection) -> list[dict]:
    out = []
    for i, r in enumerate(sel.rows, 1):
        src, detail = source_of(sel, r)
        out.append({"#": i, "case_id": r["case_id"], "slice": r["slice"], "query": r["query"], "nguồn": src,
                    "chi tiết": detail, "ý định": r.get("review_note") or ""})
    return out


def diff_with_file(sel: Selection, path: Path) -> tuple[list[str], list[str]]:
    """(dòng drafts.txt hiện tại sẽ bị bỏ, dòng mới sẽ thêm) nếu ghi lại từ lựa chọn hiện tại."""
    new = gold.drafts_lines(sel.rows)
    old = path.read_bytes().decode("utf-8").splitlines() if path.exists() else []
    old_set, new_set = set(old), set(new)
    return [x for x in old if x not in new_set], [x for x in new if x not in old_set]


def write_drafts(sel: Selection, path: Path) -> None:
    gold.write_drafts(path, sel.rows)


def _decision_text(sel: Selection, cid: str) -> tuple[str, bool]:
    d = sel.decisions.get(cid)
    if not d:
        return "chưa gán", False
    reason = d.get("rejection_reason") or ""
    who = "overrides" if d.get("annotator") == "override" else d.get("annotator") or ""
    if d["verdict"] == "REJECT":
        blocked = who == "overrides" or (reason or "other") not in gold.PHRASING_REASONS
        return f"REJECT ({reason or 'other'}) · {who}", blocked
    return f"{d['verdict']} · {who}", False


def _query_of(sel: Selection, cid: str) -> str:
    d = sel.decisions.get(cid)
    if d and d.get("verdict") == "NEEDS_EDIT" and d.get("edited_query"):
        return d["edited_query"]
    return sel.by_id[cid]["query"]


KIND_ADD = "chưa chọn"


def _unchosen(sel: Selection, sl: str, *, skip_key=None, skip_notes: set[str] = frozenset()) -> list[Alternative]:
    """Ý định cùng slice chưa có trong bộ, mỗi ý định lấy cách nói đầu tiên chưa bị loại (câu gợi ý --fill ưu tiên)."""
    chosen_keys = {gold.intent_key(c, sel.by_id[c]["slice"]) for c in sel.selected_ids()}
    groups: dict[tuple, list[dict]] = {}
    for r in sel.cases:
        if r["slice"] == sl:
            groups.setdefault(gold.intent_key(r["case_id"], sl), []).append(r)
    sug = sel.suggested or {}
    out: list[Alternative] = []
    for k, rs in sorted(groups.items(), key=lambda kv: gold.qid_num(kv[1][0]["case_id"])):
        if k == skip_key or k in chosen_keys:
            continue
        if (rs[0].get("review_note") or "").strip() in skip_notes:
            continue
        texts = [(r, *_decision_text(sel, r["case_id"])) for r in rs]
        pick = next((t for t in texts if t[0]["case_id"] in sug), None) or next((t for t in texts if not t[2]), texts[0])
        r, st, blocked = pick
        if r["case_id"] in sug:
            st = f"⭐ gợi ý --fill · {st}"
        out.append(Alternative(r["case_id"], _query_of(sel, r["case_id"]), KIND_INTENT, st, blocked))
    return out


def candidates(sel: Selection, sl: str) -> list[Alternative]:
    """Câu chưa chọn có thể thêm vào slice: gợi ý --fill trước, rồi câu chưa từng bị loại, rồi câu ⚠. Ở dest_type /
    out_of_catalog bỏ ý định trùng khoá (review_note) với câu đang chọn."""
    notes = {(sel.by_id[c].get("review_note") or "").strip() for c in sel.selected_ids()
             if sel.by_id[c]["slice"] == sl} if sl in gold.NOTE_IS_INTENT_KEY else set()
    out = [Alternative(a.case_id, a.query, KIND_ADD, a.status, a.blocked) for a in _unchosen(sel, sl, skip_notes=notes)]
    sug = sel.suggested or {}
    out.sort(key=lambda a: (a.case_id not in sug, a.blocked))
    return out


def alternatives(sel: Selection, case_id: str) -> list[Alternative]:
    """Ứng viên thay thế cho một câu đã chọn: cách nói khác của cùng ý định, rồi các ý định khác cùng slice chưa có
    trong bộ (mỗi ý định lấy cách nói đầu tiên chưa bị loại). Ở dest_type / out_of_catalog bỏ ý định trùng khoá
    (review_note) với một câu khác đang được chọn."""
    cur = sel.by_id[case_id]
    sl = cur["slice"]
    key = gold.intent_key(case_id, sl)
    other_notes = {(sel.by_id[c].get("review_note") or "").strip() for c in sel.selected_ids()
                   if c != case_id and sel.by_id[c]["slice"] == sl} if sl in gold.NOTE_IS_INTENT_KEY else set()
    out: list[Alternative] = []
    for r in sel.cases:
        if r["slice"] == sl and gold.intent_key(r["case_id"], sl) == key and r["case_id"] != case_id:
            st, blocked = _decision_text(sel, r["case_id"])
            out.append(Alternative(r["case_id"], _query_of(sel, r["case_id"]), KIND_PHRASING, st, blocked))
    out += _unchosen(sel, sl, skip_key=key, skip_notes=other_notes)
    out.sort(key=lambda a: (a.kind != KIND_PHRASING, a.blocked))      # sort ổn định: giữ thứ tự case_id trong nhóm
    return out


# ------------------------------------------------------------------ ghi quyết định vào overrides.tsv
def _clean(v: str) -> str:
    return " ".join(str(v or "").replace("\t", " ").split())


def upsert_overrides(path: Path, rows: list[dict], case_ids: set[str]) -> None:
    """Thêm / thay dòng theo case_id trong overrides.tsv; các dòng khác giữ nguyên từng byte. Kiểm lại cả file trước
    khi ghi (qua `gold.read_overrides`; `case_ids` = mọi case của drafts_raw.tsv)."""
    text = path.read_bytes().decode("utf-8") if path.exists() else "\t".join(gold.OVERRIDE_COLUMNS) + "\n"
    lines = text.splitlines()
    pos = {ln.split("\t", 1)[0]: i for i, ln in enumerate(lines) if i and ln.strip()}
    for r in rows:
        line = "\t".join(_clean(r.get(c, "")) for c in gold.OVERRIDE_COLUMNS)
        if r["case_id"] in pos:
            lines[pos[r["case_id"]]] = line
        else:
            pos[r["case_id"]] = len(lines)
            lines.append(line)
    new = "\n".join(lines) + "\n"
    tmp = path.with_name(path.name + ".check")
    try:
        tmp.write_bytes(new.encode("utf-8"))
        gold.read_overrides(tmp, case_ids)                                   # ném GoldError nếu dòng mới sai luật
    finally:
        tmp.unlink(missing_ok=True)
    atomic_write_text(path, new)


def check_rewrite(sel: Selection, case_id: str, query: str) -> list[str]:
    """Lỗi của câu viết lại cùng ý định (NEEDS_EDIT): rỗng, chứa TAB / xuống dòng, hoặc trùng câu đã có trong slice."""
    q = (query or "").strip()
    if not q:
        return ["nhập câu thay thế"]
    errors = []
    if "\t" in q or "\n" in q:
        errors.append("câu thay thế chứa TAB / xuống dòng")
    sl = sel.by_id[case_id]["slice"]
    existing = {r["query"].strip().casefold() for r in sel.cases if r["slice"] == sl}
    existing |= {_query_of(sel, r["case_id"]).strip().casefold() for r in sel.cases if r["slice"] == sl}
    if q.casefold() in existing:
        errors.append(f"câu {q!r} đã có trong slice {sl}")
    return errors


def decision_rows(sel: Selection, case_id: str, action: str, *, chosen: str | None = None, author: str = "",
                  note: str = "", edited: str = "", today: date | None = None) -> list[dict]:
    """Dòng overrides cho một thao tác: `add` (thêm câu chưa chọn) · `replace` (cần chosen) · `keep` · `drop` ·
    `rewrite` (cần edited: câu viết lại cùng ý định → NEEDS_EDIT) · `replace_new` (cần chosen = case vừa thêm bằng
    `draft_authoring.append_intent`) · `copy_local` (chép nguyên câu NEEDS_EDIT chỉ có trong kho nhãn local sang
    overrides.tsv — `gold.local_only_edits` — để drafts.txt map được case_id từ file commit)."""
    when = (today or date.today()).isoformat()
    who = author or "không ghi"
    extra = f": {note.strip()}" if note and note.strip() else ""
    if action == "copy_local":
        d = sel.decisions.get(case_id) or {}
        if d.get("verdict") != "NEEDS_EDIT" or not d.get("edited_query"):
            raise ValueError(f"{case_id} không có câu NEEDS_EDIT trong kho nhãn")
        return [{"case_id": case_id, "verdict": "NEEDS_EDIT", "edited_query": d["edited_query"].strip(),
                 "note": f"chép nguyên NEEDS_EDIT của {d.get('annotator') or 'không rõ'} từ kho nhãn local ngày {when} "
                         f"qua app ({who}) — để drafts.txt map được case_id từ file commit{extra}"}]
    if action == "rewrite":
        if not edited.strip():
            raise ValueError("rewrite cần câu thay thế")
        return [{"case_id": case_id, "verdict": "NEEDS_EDIT", "edited_query": edited.strip(),
                 "note": f"viết lại {when} qua app ({who}) — cùng ý định, thay câu “{sel.by_id[case_id]['query']}”{extra}"}]
    if action == "replace_new":
        if not chosen:
            raise ValueError("replace_new cần case mới")
        return [{"case_id": case_id, "verdict": "REJECT", "reason": "other",
                 "note": f"thay bằng câu viết mới {chosen} ngày {when} qua app ({who}){extra}"}]
    if action == "keep":
        return [{"case_id": case_id, "verdict": "KEEP",
                 "note": f"đã soát {when} qua app ({who}) — giữ câu{' do --fill lấp' if case_id in sel.filled_ids else ''}{extra}"}]
    if action == "drop":
        return [{"case_id": case_id, "verdict": "REJECT", "reason": "other",
                 "note": f"loại khỏi bộ {when} qua app ({who}){extra}"}]
    if action == "add":
        d = sel.decisions.get(case_id) or {}
        hint = " — gợi ý --fill" if case_id in (sel.suggested or {}) else ""
        row = {"case_id": case_id, "verdict": "KEEP", "note": f"thêm vào bộ {when} qua app ({who}){hint}{extra}"}
        if d.get("verdict") == "NEEDS_EDIT" and d.get("edited_query"):
            row.update(verdict="NEEDS_EDIT", edited_query=d["edited_query"])
        return [row]
    if action != "replace" or not chosen:
        raise ValueError(f"thao tác lạ {action!r}")
    same = gold.intent_key(chosen, sel.by_id[chosen]["slice"]) == gold.intent_key(case_id, sel.by_id[case_id]["slice"])
    d = sel.decisions.get(chosen) or {}
    new = {"case_id": chosen, "verdict": "KEEP", "note": f"thay cho {case_id} ngày {when} qua app ({who}){extra}"}
    if d.get("verdict") == "NEEDS_EDIT" and d.get("edited_query"):
        new.update(verdict="NEEDS_EDIT", edited_query=d["edited_query"])
    return [{"case_id": case_id, "verdict": "REJECT", "reason": "duplicate" if same else "other",
             "note": f"thay bằng {chosen} ({'cùng ý định' if same else 'ý định khác'}) ngày {when} qua app ({who}){extra}"},
            new]
