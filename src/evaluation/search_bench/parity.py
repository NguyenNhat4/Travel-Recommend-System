"""Part 9 (30/09) — `sb parity`: cùng 20 câu cố định (`config/parity_queries.yaml`) trên hai nguồn `/search`, so top-1
và overlap@k từng câu; cổng M4 của lịch 10 ngày (top-1 trùng ≥ 18/20, overlap@10 ≥ 8/10 ở mọi câu).

- mode `http`: A = `/search` Cloud, B = `/search` local — chẩn đoán deployment (catalog hai bên có thể khác).
- mode `weaviate`: cùng `SearchProducts` in-process (cổng APP) trên catalog VM; A = collection `Product` trên Weaviate
  Cloud, B = collection `ProductVM` trên Weaviate bench dựng từ vector kéo về từ Cloud → đo đúng "index Cloud = index
  local" trên cùng vector, cùng text (`app_adapter.parity_contexts`).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from . import paths
from .latency import canonical, search_once

REQUIRED_TEXTS = ("VinWonders", "KS biển tại NT", "Vinpeal Resort Nha Trang giá tốt")


class ParityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParityQuery:
    text: str
    slice: str
    qid: str | None = None


def load_parity_queries(path: Path) -> list[ParityQuery]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out = [ParityQuery(text=canonical(str(q["text"])), slice=str(q["slice"]), qid=q.get("qid")) for q in raw.get("queries") or []]
    if not out:
        raise ParityError(f"{path}: không có câu nào")
    if len({q.text for q in out}) != len(out):
        raise ParityError(f"{path}: câu trùng nhau")
    return out


@dataclass
class ParityRow:
    text: str
    slice: str
    a_ids: list[str]
    b_ids: list[str]
    a_diag: dict = field(default_factory=dict)
    b_diag: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def top1_same(self) -> bool:
        return bool(self.a_ids) and bool(self.b_ids) and self.a_ids[0] == self.b_ids[0] or (not self.a_ids and not self.b_ids)

    def overlap(self, k: int) -> int:
        return len(set(self.a_ids[:k]) & set(self.b_ids[:k]))

    def overlap_need(self, k: int, overlap_min: int) -> int:
        """Ngưỡng overlap của câu này: `overlap_min` khi cả hai bên có ≥ overlap_min kết quả; câu ngắn hơn (out_of_catalog,
        tên riêng hiếm) thì hai bên phải trùng hết phần ngắn — 0 kết quả cả hai bên là trùng."""
        return min(overlap_min, len(self.a_ids[:k]), len(self.b_ids[:k]))

    def overlap_ok(self, k: int, overlap_min: int) -> bool:
        return self.overlap(k) >= self.overlap_need(k, overlap_min) and (
            min(len(self.a_ids[:k]), len(self.b_ids[:k])) >= overlap_min or len(self.a_ids[:k]) == len(self.b_ids[:k]))


def verdict(rows: list[ParityRow], *, k: int, top1_min: int, overlap_min: int) -> dict:
    """Cổng: top-1 trùng ≥ top1_min câu và overlap@k ≥ overlap_min ở mọi câu đủ dài (câu ngắn hơn: hai bên cùng số kết quả
    và trùng hết — xem `overlap_need`); câu lỗi tính là lệch."""
    good = [r for r in rows if r.error is None]
    top1 = sum(1 for r in good if r.top1_same)
    overlaps = [r.overlap(k) for r in good]
    full = [r.overlap(k) for r in good if min(len(r.a_ids[:k]), len(r.b_ids[:k])) >= overlap_min]
    worst = sorted(good, key=lambda r: (r.overlap(k) - r.overlap_need(k, overlap_min), r.top1_same))[:5]
    ok = top1 >= top1_min and all(r.overlap_ok(k, overlap_min) for r in good) and len(good) == len(rows)
    return {"n": len(rows), "n_error": len(rows) - len(good), "top1_same": top1, "top1_min": top1_min,
            "overlap_min_seen": min(overlaps) if overlaps else None,
            "overlap_min_full": min(full) if full else None, "n_full": len(full), "overlap_min": overlap_min, "k": k, "pass": ok,
            "mismatch": [{"text": r.text, "slice": r.slice, "top1_same": r.top1_same, "overlap": r.overlap(k),
                          "need": r.overlap_need(k, overlap_min), "a_top3": r.a_ids[:3], "b_top3": r.b_ids[:3]} for r in worst
                         if not r.top1_same or not r.overlap_ok(k, overlap_min)]
                        + [{"text": r.text, "slice": r.slice, "error": r.error} for r in rows if r.error]}


def _diag(body: dict | None) -> dict:
    d = (body or {}).get("diagnostics") or {}
    return {k: d.get(k) for k in ("searchMode", "latencyMs", "lexicalCandidates", "normalizedQuery", "embedCache") if k in d}


def parity_http(base_a: str, base_b: str, queries: list[ParityQuery], *, k: int, timeout_s: float,
                client: Any = None) -> list[ParityRow]:
    import httpx
    own = client is None
    client = client or httpx.Client(timeout=timeout_s, follow_redirects=True)
    rows = []
    try:
        for q in queries:
            sa, ba, _, ea = search_once(client, base_a, q.text, limit=k)
            sb, bb, _, eb = search_once(client, base_b, q.text, limit=k)
            err = " | ".join(x for x in (ea and f"A: {ea}", eb and f"B: {eb}") if x) or None
            rows.append(ParityRow(text=q.text, slice=q.slice, a_ids=[str(r["productId"]) for r in ((ba or {}).get("results") or [])],
                                  b_ids=[str(r["productId"]) for r in ((bb or {}).get("results") or [])],
                                  a_diag=_diag(ba), b_diag=_diag(bb), error=err))
    finally:
        if own:
            client.close()
    return rows


def parity_engines(search_a: Callable[[str], tuple[list[str], list[float], dict]],
                   search_b: Callable[[str], tuple[list[str], list[float], dict]],
                   queries: list[ParityQuery]) -> list[ParityRow]:
    """Mode weaviate: hai `AppSearch.search` (cùng engine, khác kho vector) — mọi lỗi của một câu ghi vào `error`."""
    rows = []
    for q in queries:
        try:
            a_ids, _, a_diag = search_a(q.text)
            b_ids, _, b_diag = search_b(q.text)
            rows.append(ParityRow(text=q.text, slice=q.slice, a_ids=a_ids, b_ids=b_ids, a_diag=a_diag, b_diag=b_diag))
        except Exception as e:  # noqa: BLE001 — một câu hỏng không chặn 19 câu còn lại; verdict tính là lệch
            rows.append(ParityRow(text=q.text, slice=q.slice, a_ids=[], b_ids=[], error=f"{type(e).__name__}: {e}"))
    return rows


def write_parity(run_id: str, *, mode: str, rows: list[ParityRow], result: dict, meta: dict | None = None) -> Path:
    p = paths.run_dir(run_id) / f"parity-{mode}.json"
    p.write_text(json.dumps({"run_id": run_id, "mode": mode, **(meta or {}), "verdict": result,
                             "rows": [{**asdict(r), "top1_same": r.top1_same, "overlap": r.overlap(result["k"])} for r in rows]},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    return p
