"""Part 5 (phần Người B chạy ngày 2) — `sb gold pool` và `sb gold split`.

- `drafts.txt`: mỗi dòng `query \\t slice [\\t filter_json] [\\t expected_no_result]`; dòng trống / bắt đầu `#` bỏ qua;
  qid `q001…` theo thứ tự dòng. Slice phải thuộc `gold.slices`; filter kiểm và đổi khoá amenity → id (`store/filters.py`).
- `pool`: với mỗi draft, dense top-`depth` (collection của B0, embed query theo arm) ∪ BM25 top-`depth`, cùng filter →
  `pool.csv` đúng cột spec, **xáo thứ tự trong mỗi qid** (seed cố định) để người gán không thấy rank.
- `split`: 25 qid chung chọn stratified theo slice; phần còn lại qid lẻ → `pool_A.csv`, chẵn → `pool_B.csv`.
`kappa`, `merge`, `import`, `check` thuộc ngày 3–4 (Người A) — chưa cài ở đây.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .store import filters as F

POOL_COLUMNS = ["qid", "query", "slice", "product_id", "name", "variant", "destination", "from", "rank_dense", "rank_lex", "label"]
CSV_ENCODING = "utf-8-sig"      # Excel mở đúng tiếng Việt


class GoldError(ValueError):
    pass


@dataclass
class Draft:
    qid: str
    query: str
    slice: str
    filter: dict | None           # AST đã resolve (id amenity)
    filter_raw: str
    expected_no_result: bool
    line: int


def parse_drafts(path: Path, slices: list[str], key_to_id: dict[str, int]) -> list[Draft]:
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
            flt = F.parse(fraw)
            flt = F.resolve(flt, key_to_id) if flt else None
        except F.FilterError as e:
            raise GoldError(f"{path.name}:{lineno}: {e}") from None
        eno_raw = parts[3].strip().lower() if len(parts) > 3 else ""
        if eno_raw not in ("", "true", "false"):
            raise GoldError(f"{path.name}:{lineno}: expected_no_result phải là true/false, gặp {parts[3]!r}")
        out.append(Draft(qid=f"q{len(out) + 1:03d}", query=query, slice=sl, filter=flt, filter_raw=fraw,
                         expected_no_result=eno_raw == "true", line=lineno))
    if not out:
        raise GoldError(f"{path.name}: không có draft nào")
    dup = [q for q, n in Counter((d.query.lower(), d.slice) for d in out).items() if n > 1]
    if dup:
        raise GoldError(f"{path.name}: draft trùng (query, slice): {dup[:3]}")
    return out


def _qnum(qid: str) -> int:
    return int(qid.lstrip("q"))


def pool_rows(draft: Draft, dense: list, lexical: list, seed: int) -> list[dict]:
    """Hợp dense ∪ BM25 cho một draft, ghi rank ở từng kênh, xáo thứ tự dòng (seed cố định theo qid)."""
    rows: dict[str, dict] = {}
    for kind, hits in (("dense", dense), ("lexical", lexical)):
        for h in hits:
            r = rows.setdefault(h.product_id, {"qid": draft.qid, "query": draft.query, "slice": draft.slice,
                                               "product_id": h.product_id, "name": h.name, "variant": h.variant,
                                               "destination": h.destination, "rank_dense": None, "rank_lex": None, "label": ""})
            r["rank_dense" if kind == "dense" else "rank_lex"] = h.rank
    for r in rows.values():
        r["from"] = "both" if r["rank_dense"] and r["rank_lex"] else ("dense" if r["rank_dense"] else "lexical")
    ordered = sorted(rows.values(), key=lambda r: r["product_id"])
    perm = np.random.default_rng([seed, _qnum(draft.qid)]).permutation(len(ordered))
    return [ordered[i] for i in perm]


def build_pool(drafts: list[Draft], *, store: Any, embedder: Any, physical: str, fold_mode: str, depth: int,
               query_input_type: str, seed: int) -> pd.DataFrame:
    qvecs = embedder.embed([d.query for d in drafts], query_input_type)       # một lượt gom, qua cache
    rows: list[dict] = []
    for d, qv in zip(drafts, qvecs):
        flt = F.to_weaviate(d.filter)
        dense = store.dense(physical, qv, depth, filters=flt)
        lexical = store.bm25(physical, d.query, depth, fold_mode=fold_mode, filters=flt)
        rows += pool_rows(d, dense, lexical, seed)
    df = pd.DataFrame(rows, columns=POOL_COLUMNS)
    for c in ("rank_dense", "rank_lex"):
        df[c] = df[c].astype("Int64")
    return df


def pool_summary(drafts: list[Draft], df: pd.DataFrame) -> dict:
    per_q = df.groupby("qid").size() if len(df) else pd.Series(dtype=int)
    empty = [d.qid for d in drafts if d.qid not in per_q.index]
    return {"n_queries": len(drafts), "n_rows": int(len(df)),
            "docs_per_query": {"p50": float(per_q.median()) if len(per_q) else 0.0, "max": int(per_q.max()) if len(per_q) else 0},
            "from": dict(Counter(df["from"])), "empty_queries": empty,
            "by_slice": dict(Counter(d.slice for d in drafts))}


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=CSV_ENCODING)


def read_pool(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise GoldError(f"không thấy {path} — chạy `sb gold pool` trước")
    df = pd.read_csv(path, encoding=CSV_ENCODING, dtype={"qid": str, "product_id": str, "label": str}, keep_default_na=False)
    missing = [c for c in POOL_COLUMNS if c not in df.columns]
    if missing:
        raise GoldError(f"{path.name} thiếu cột {missing}")
    return df


def overlap_quota(slice_counts: dict[str, int], overlap: int) -> dict[str, int]:
    """Chia `overlap` theo tỷ lệ slice (largest remainder; hoà → tên slice), không vượt số query của slice."""
    total = sum(slice_counts.values())
    raw = {s: overlap * n / total for s, n in slice_counts.items()}
    quota = {s: min(int(np.floor(v)), slice_counts[s]) for s, v in raw.items()}
    rest = overlap - sum(quota.values())
    for s in sorted(raw, key=lambda s: (-(raw[s] - np.floor(raw[s])), s)):
        if rest <= 0:
            break
        if quota[s] < slice_counts[s]:
            quota[s] += 1
            rest -= 1
    for s in sorted(slice_counts):              # còn dư (slice nhỏ đã đầy) → dồn sang slice còn chỗ
        while rest > 0 and quota[s] < slice_counts[s]:
            quota[s] += 1
            rest -= 1
    return quota


def split_pool(df: pd.DataFrame, overlap: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    q = df.drop_duplicates("qid")[["qid", "slice"]]
    n = len(q)
    if not 0 <= overlap < n:
        raise GoldError(f"overlap {overlap} phải trong [0, {n}) (số query của pool)")
    by_slice = {s: sorted(g["qid"], key=_qnum) for s, g in q.groupby("slice")}
    quota = overlap_quota({s: len(v) for s, v in by_slice.items()}, overlap)
    rng = np.random.default_rng(seed)
    shared: list[str] = []
    for s in sorted(by_slice):
        if quota[s]:
            shared += [str(x) for x in rng.choice(by_slice[s], size=quota[s], replace=False)]
    shared_set = set(shared)
    rest = [x for x in q["qid"] if x not in shared_set]
    a = shared_set | {x for x in rest if _qnum(x) % 2 == 1}
    b = shared_set | {x for x in rest if _qnum(x) % 2 == 0}
    return df[df["qid"].isin(a)].copy(), df[df["qid"].isin(b)].copy(), sorted(shared, key=_qnum)


def load_key_index(amenity_vocab_path: Path) -> dict[str, int]:
    if not amenity_vocab_path.exists():
        raise GoldError(f"chưa có {amenity_vocab_path} — chạy `sb catalog build` trước")
    return F.amenity_key_index(json.loads(amenity_vocab_path.read_text(encoding="utf-8")))


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
                  fill: bool = False, fill_guard=None) -> tuple[list[dict], dict]:
    """Chọn bộ draft cuối: giữ 1 cách nói cho mỗi ý định, cắt theo quota từng slice.

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
        take, rest = avail[:q], avail[q:]
        if fill and len(take) < q:
            covered = {(r.get("review_note") or "").strip() for r in take} if sl in NOTE_IS_INTENT_KEY else set()
            for key, rows_ in sorted(by_intent_rows.items(), key=lambda kv: kv[1][0]["case_id"]):
                if len(take) >= q or key[0] != sl or key in kept_by_intent:
                    continue
                verdicts = [decisions.get(r["case_id"]) for r in rows_]
                if any(v is None for v in verdicts):
                    kind = "chưa gán"
                elif all((v["rejection_reason"] or "other") in PHRASING_REASONS for v in verdicts):
                    kind = "loại vì cách nói (" + ", ".join(sorted({v["rejection_reason"] for v in verdicts})) + ")"
                else:
                    bad = sorted({v["rejection_reason"] for v in verdicts} - set(PHRASING_REASONS))
                    skipped_fill.append({"case_id": rows_[0]["case_id"], "slice": sl,
                                         "why": "loại vì lỗi thật: " + ", ".join(bad)})
                    continue
                cand = rows_[0]                                   # cách nói gốc: case_id nhỏ nhất của ý định
                note = (cand.get("review_note") or "").strip() if sl in NOTE_IS_INTENT_KEY else ""
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


def write_drafts(path: Path, rows: list[dict]) -> None:
    """Ghi `query \t slice [\t filter_json] [\t expected_no_result]` — đúng định dạng parse_drafts đọc."""
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def render_drafts_report(report: dict) -> str:
    lines = [f"| {'slice':22} | {'chọn':>5} | {'quota':>5} | {'ý định có':>9} | {'thiếu':>5} | {'chưa gán':>8} |",
             f"|{'-' * 24}|{'-' * 7}|{'-' * 7}|{'-' * 11}|{'-' * 7}|{'-' * 10}|"]
    for sl, s in report["per_slice"].items():
        lines.append(f"| {sl:22} | {s['selected']:>5} | {s['quota']:>5} | {s['available_intents']:>9} | "
                     f"{s['shortfall']:>5} | {s['ungraded_rows']:>8} |")
    lines.append(f"| {'TỔNG':22} | {report['selected']:>5} | {report['target']:>5} | {'':>9} | "
                 f"{report['target'] - report['selected']:>5} | {report['ungraded_total']:>8} |")
    return "\n".join(lines)


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
