"""B6 / B7 / B8 (01/10) — phân khúc, strict vs lenient, 20 ca engine trượt mà baseline trúng. Đọc từ thư mục run
(`per_user.jsonl`) + split tính lại; không cần Weaviate.

- Nhãn mỗi khách tính **một lần** rồi áp cho mọi arm: `strategy` (engine trả), `coldStart` (`eventsUsed < 3`),
  `lifecycleAtAsOf` tính lại từ purchase trong train theo luật seed (`LAST_PURCHASE_DAYS_AGO`: active ≤ 180 ngày, dormant
  ≤ 365, churned > 365, chưa mua = new) — **không** dùng `cdp.profiles.lifecycle_stage` (tính tại as_of DB, có purchase bị
  giấu → rò rỉ), `targetTaxonomy`, `targetTrip` ∈ {open, closed, new} (trip của purchase bị giấu là trip mở / đã đóng /
  chưa có trong train), `activeTripIsSolo` (I-3: trip mở là view lẻ không có `eventGroupId`), `persona`.
- Strict vs lenient: `rank` (unit cha) là metric chính; `rankStrict` (đúng productId đã mua) chỉ có nghĩa với target đã là
  search unit (attraction, combo, golf) — với phòng / chuyến con, mọi arm đều 0 theo cấu trúc.
- 20 ca: engine (`base`) trượt top-20, baseline (`ref`) trúng; nguyên nhân theo thứ tự ưu tiên, chọn tất định xoay vòng.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .ceiling import EngineView
from .events import PERSONA_IDS, parse_ts
from .splits import Split

LIFECYCLE_DAYS = (("active", 180), ("dormant", 365))     # seed/config.py LAST_PURCHASE_DAYS_AGO; hơn 365 = churned
LABELS = ("strategy", "coldStart", "lifecycleAtAsOf", "targetTaxonomy", "targetTrip", "activeTripIsSolo", "persona")
NOISY_BELOW = 20
CASE_REASONS = ("filtered", "wrong_active_trip", "out_of_candidates", "vertical_cap", "pool_miss", "mmr_demoted", "ranked_low")


def lifecycle_at(train: list[dict], as_of: datetime) -> str:
    """Ngày kể từ purchase gần nhất trong train (ngày thập phân, UTC) → active / dormant / churned; chưa mua → new. Seed tính
    theo ngày lịch VN nên có thể lệch ± 1 ngày ở biên 180 / 365 — chỉ là nhãn phân khúc, không phải metric."""
    stamps = [parse_ts(e["timestamp"]) for e in train if e.get("eventName") == "purchase"]
    if not stamps:
        return "new"
    days = (as_of - max(stamps)).total_seconds() / 86400
    for name, limit in LIFECYCLE_DAYS:
        if days <= limit:
            return name
    return "churned"


def target_trip_kind(split: Split, user: str, view: EngineView) -> str:
    """open = trip của purchase bị giấu chính là trip mở engine chọn; closed = có trong train nhưng không phải trip mở (đã
    quá 60 ngày, hoặc bị một view lẻ trẻ hơn che — xem `activeTripIsSolo`); new = chưa có event nào trong train."""
    gid = split.target_events[user].get("eventGroupId")
    if not gid or gid not in view.trips:
        return "new"
    return "open" if gid == view.active_trip else "closed"


def user_labels(split: Split, index: UnitIndex, rows_engine: dict[str, dict], views: dict[str, EngineView]) -> dict[str, dict]:
    out = {}
    for u in sorted(split.targets):
        row, view = rows_engine.get(u, {}), views[u]
        events_used = row.get("eventsUsed")
        out[u] = {"strategy": row.get("strategy") or view.strategy,
                  "coldStart": bool(row.get("coldStart")) if "coldStart" in row else (events_used or view.n_events) < 3,
                  "lifecycleAtAsOf": lifecycle_at(split.train_by_user[u], split.as_of_by_user[u]),
                  "targetTaxonomy": str(index.taxonomy[index.idx[split.targets[u]]]),
                  "targetTrip": target_trip_kind(split, u, view), "activeTripIsSolo": view.active_is_solo,
                  "persona": u in PERSONA_IDS}
    return out


def _hit(row: dict | None, k: int) -> bool:
    return bool(row) and row.get("rank") is not None and row["rank"] <= k


def _ndcg(row: dict | None, k: int) -> float:
    if not row or row.get("rank") is None or row["rank"] > k:
        return 0.0
    return 1.0 / np.log2(row["rank"] + 1)


def segments(rows_by_arm: dict[str, dict[str, dict]], labels: dict[str, dict], *, k: int = 20) -> dict:
    """{label: {value: {n, arms: {arm: {hit@k, ndcg@10, hit@5}}, noisy}}}; giá trị theo thứ tự n giảm dần."""
    out: dict = {}
    users = sorted(labels)
    for label in LABELS:
        groups: dict = defaultdict(list)
        for u in users:
            groups[str(labels[u][label])].append(u)
        out[label] = {}
        for value, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            arms = {}
            for arm, rows in rows_by_arm.items():
                arms[arm] = {f"hit@{k}": float(np.mean([_hit(rows.get(u), k) for u in members])),
                             "ndcg@10": float(np.mean([_ndcg(rows.get(u), 10) for u in members])),
                             "hit@5": float(np.mean([_hit(rows.get(u), 5) for u in members]))}
            out[label][value] = {"n": len(members), "arms": arms, "noisy": len(members) < NOISY_BELOW}
    return out


def segments_markdown(seg: dict, arms: list[str], *, k: int = 20) -> str:
    lines = []
    for label, values in seg.items():
        lines += [f"**{label}**", "", "| Giá trị | n | " + " | ".join(f"{a} hit@{k} / NDCG@10" for a in arms) + " |",
                  "|---|---:|" + "---:|" * len(arms)]
        for value, g in values.items():
            cells = " | ".join(f"{g['arms'][a][f'hit@{k}']:.3f} / {g['arms'][a]['ndcg@10']:.3f}" for a in arms if a in g["arms"])
            lines.append(f"| {value}{' *(ồn, n < 20)*' if g['noisy'] else ''} | {g['n']} | {cells} |")
        lines.append("")
    return "\n".join(lines)


def strict_lenient(rows_by_arm: dict[str, dict[str, dict]], split: Split, index: UnitIndex, *, k: int = 20) -> dict:
    """Theo taxonomy của target: n, số target là con (phòng / chuyến), lenient hit@k và strict hit@k từng arm, strict trên
    tập target cấp unit (nơi strict có nghĩa)."""
    users = sorted(split.targets)
    by_tax: dict[str, list[str]] = defaultdict(list)
    for u in users:
        by_tax[str(index.taxonomy[index.idx[split.targets[u]]])].append(u)
    out = {}
    for tax, members in sorted(by_tax.items()):
        children = [u for u in members if str(split.target_events[u].get("productId") or "") != split.targets[u]]  # như bench.py
        unit_level = [u for u in members if u not in set(children)]
        arms = {}
        for arm, rows in rows_by_arm.items():
            strict_hits = [bool(rows.get(u) and rows[u].get("rankStrict") is not None and rows[u]["rankStrict"] <= k) for u in members]
            arms[arm] = {"lenient": float(np.mean([_hit(rows.get(u), k) for u in members])),
                         "strict": float(np.mean(strict_hits)),
                         "strictUnitLevel": float(np.mean([bool(rows.get(u) and rows[u].get("rankStrict") is not None
                                                                and rows[u]["rankStrict"] <= k) for u in unit_level])) if unit_level else None}
        out[tax] = {"n": len(members), "nChild": len(children), "arms": arms}
    return out


def strict_markdown(sl: dict, arms: list[str], *, k: int = 20) -> str:
    lines = ["| Taxonomy | n | target là con | " + " | ".join(f"{a} lenient / strict" for a in arms) + " |",
             "|---|---:|---:|" + "---:|" * len(arms)]
    for tax, g in sl.items():
        cells = " | ".join(f"{g['arms'][a]['lenient']:.3f} / {g['arms'][a]['strict']:.3f}" for a in arms if a in g["arms"])
        lines.append(f"| {tax} | {g['n']} | {g['nChild']} | {cells} |")
    lines += ["", f"Strict = đúng productId đã mua trong top-{k}; target là phòng / chuyến con thì mọi arm bằng 0 theo cấu trúc "
              "(engine chỉ trả search unit) — chỉ đọc strict ở taxonomy có target cấp unit (attraction, combo, golf), ở đó strict = lenient."]
    return "\n".join(lines)


def case_reason(user: str, rows_by_arm: dict[str, dict[str, dict]], ceiling_per_user: dict, views: dict[str, EngineView],
                split: Split, *, base: str, k: int = 20) -> tuple[str, str]:
    """(nguyên nhân, chi tiết) theo thứ tự ưu tiên của plan Day 3 B8."""
    c = ceiling_per_user.get(user) or {}
    if c.get("unreachable"):
        return "filtered", ",".join(c["unreachable"])
    view = views[user]
    gid = split.target_events[user].get("eventGroupId")
    if view.active_trip and (view.active_is_solo or gid != view.active_trip):
        return "wrong_active_trip", f"trip mở {view.active_trip} · trip target {gid}"
    row = rows_by_arm[base].get(user) or {}
    if base == "engine_prod":
        # prod luôn trả ≤ MAX_PER_VERTICAL × số taxonomy < k=20 → "hết ứng viên" phải đo trên list eval không cap
        ev = (rows_by_arm.get("engine") or {}).get(user) or {}
        if _hit(ev, k):
            return "vertical_cap", f"engine eval hạng {ev.get('rank')}"
        row = ev or row
    if (row.get("returned") or 0) < k:
        return "out_of_candidates", f"trả {row.get('returned')}/{k}"
    pool = (rows_by_arm.get("engine_nommr") or {}).get(user)
    if pool is not None:
        pr = pool.get("rank")
        if pr is None:
            return "pool_miss", "không vào pool score"
        if pr <= k:
            return "mmr_demoted", f"poolRank {pr} ≤ {k}: trong top-{k} theo score, MMR đẩy ra"
        return "ranked_low", f"poolRank {pr} > {k}: trượt kể cả không MMR"
    return "ranked_low", "không có arm engine_nommr để tách pool"


def cases(rows_by_arm: dict[str, dict[str, dict]], ceiling_per_user: dict, views: dict[str, EngineView], split: Split,
          index: UnitIndex, *, base: str = "engine", ref: str = "most_popular_in_destination", n: int = 20, k: int = 20) -> dict:
    base_rows, ref_rows = rows_by_arm[base], rows_by_arm[ref]
    candidates = [u for u in sorted(split.targets) if not _hit(base_rows.get(u), k) and _hit(ref_rows.get(u), k)]
    detail = {}
    for u in candidates:
        reason, why = case_reason(u, rows_by_arm, ceiling_per_user, views, split, base=base, k=k)
        t = split.targets[u]
        detail[u] = {"user": u, "reason": reason, "why": why, "target": t, "targetName": index.units[index.idx[t]].name,
                     "targetTaxonomy": str(index.taxonomy[index.idx[t]]), "targetDestination": str(index.destination[index.idx[t]]),
                     "strategy": (base_rows.get(u) or {}).get("strategy"), "engineDestination": (base_rows.get(u) or {}).get("destination"),
                     f"{base}Rank": (base_rows.get(u) or {}).get("rank"), f"{ref}Rank": (ref_rows.get(u) or {}).get("rank"),
                     "trainEvents": len(split.train_by_user[u]), "activeTrip": views[u].active_trip}
    counts = Counter(d["reason"] for d in detail.values())
    by_reason: dict[str, list[str]] = defaultdict(list)
    for u in candidates:
        by_reason[detail[u]["reason"]].append(u)
    chosen: list[str] = []
    order = [r for r in CASE_REASONS if r in by_reason] + sorted(set(by_reason) - set(CASE_REASONS))
    i = 0
    while len(chosen) < min(n, len(candidates)):
        r = order[i % len(order)]
        if by_reason[r]:
            chosen.append(by_reason[r].pop(0))
        i += 1
    return {"base": base, "ref": ref, "k": k, "nCandidates": len(candidates), "nUsers": len(split.targets),
            "reasons": dict(sorted(counts.items())), "cases": [detail[u] for u in chosen]}


def cases_markdown(c: dict) -> str:
    lines = [f"{c['base']} trượt top-{c['k']} mà {c['ref']} trúng: **{c['nCandidates']}/{c['nUsers']}** khách. Nguyên nhân (toàn tập):",
             "", "| Nguyên nhân | Khách |", "|---|---:|"]
    for r, v in sorted(c["reasons"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{r}` | {v} |")
    lines += ["", f"{len(c['cases'])} ca (xoay vòng theo nguyên nhân, tất định):", "",
              f"| # | Khách | Nguyên nhân | Chi tiết | Target | Loại · điểm đến | strategy · điểm đến engine | hạng {c['base']} / {c['ref']} | event train |",
              "|---:|---|---|---|---|---|---|---|---:|"]
    base_key, ref_key = f"{c['base']}Rank", f"{c['ref']}Rank"
    for i, d in enumerate(c["cases"], 1):
        lines.append(f"| {i} | {d['user']} | `{d['reason']}` | {d['why']} | {d['targetName'][:40]} | {d['targetTaxonomy']} · {d['targetDestination']} | "
                     f"{d['strategy']} · {d['engineDestination']} | {d[base_key]} / {d[ref_key]} | {d['trainEvents']} |")
    return "\n".join(lines)
