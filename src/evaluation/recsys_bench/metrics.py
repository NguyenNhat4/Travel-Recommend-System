"""Chỉ số của harness (test-plan §2.5, handbook §12), một target mỗi khách.

Phần lõi port từ `origin/khoa/recsys-research@6b9b0af` (`src/evaluation/benchmark.py`: `score_recommendations`,
`_purchased_taxonomies`), giữ nguyên tên khoá. Bổ sung: `recall@5` (test-plan §2.5), `vertical_diversity@10`,
`returned_mean` (engine có thể trả ít hơn k vì MMR giới hạn 2 món mỗi taxonomy), `users`, `p50_runtime_ms`;
`ndcg@5` (01/10, B4) vì list production chỉ 5 món — NDCG@10 không phản ánh thứ hạng khách thật sự thấy.
Không có MRR: một target mỗi khách thì NDCG@10 đã phản ánh thứ hạng.

Day 4 R2 (01/10) — đủ cột handbook §12:
- `exposure_gini`: Gini của số lần xuất hiện trong top-20 trên **mọi** unit `recommendable` (unit không được gợi lần nào
  đếm 0) — cùng tập với mẫu số của `catalog_coverage`. 0 = mọi unit được hiển thị đều nhau; gần 1 = vài unit chiếm hết.
- `cross_category_open_trip` (handbook §12 "danh mục chưa được đặt **trong chuyến đi này**"): chỉ khách có **chuyến mở**
  tại `as_of` theo đúng luật engine (`ceiling.engine_view` → `trip_is_open`, FR-REC-02); tỉ lệ item top-20 có taxonomy ∉
  taxonomy đã mua trong chuyến mở đó. Chuyến mở chỉ có view (không purchase) có tập đã mua rỗng → mọi item đều "cross"
  (1,0 tầm thường), nên báo thêm `cross_category_open_trip_bought`: chỉ khách có chuyến mở **đã mua ≥ 1 món**. Mẫu số
  (số khách) ở `users_open_trip` / `users_open_trip_bought`; không có khách nào → 0,0 / 0 (không None, để `bench.aggregate`
  không ra nan).
- `cross_category_rate` cũ giữ nguyên nghĩa: taxonomy của trip purchase **gần nhất** trong train (mở hay đã đóng), mọi khách.
- `paired_bootstrap`: chép từ `src/evaluation/search_bench/metrics.py` (01/10) — không import chéo vì module đó kéo pandas
  và gốc package `evaluation.*` (chỉ chạy khi `src/` nằm trên sys.path).
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .events import parse_ts

#: Khoá hai biến thể cross-category theo chuyến mở — luôn có trong hàng chỉ số (0,0 / 0 khi không có khách phù hợp).
OPEN_TRIP_EMPTY = {"cross_category_open_trip": 0.0, "users_open_trip": 0,
                   "cross_category_open_trip_bought": 0.0, "users_open_trip_bought": 0}


def gini(counts: Iterable[float] | np.ndarray) -> float:
    """Hệ số Gini của một vector số đếm (0 = đều, →1 = tập trung); rỗng hoặc tổng 0 → 0,0. Chuyển từ `sanity.py` (01/10)."""
    x = np.sort(np.asarray(counts if isinstance(counts, np.ndarray) else list(counts), dtype=float))
    if x.size == 0 or x.sum() == 0:
        return 0.0
    i = np.arange(1, x.size + 1)
    return float((2 * np.sum(i * x) / (x.size * x.sum())) - (x.size + 1) / x.size)


def purchased_taxonomies(train_events: Iterable[dict], index: UnitIndex) -> set[str]:
    """Taxonomy đã mua trong trip gần nhất của khách (trong train) — mẫu số của cross-category rate."""
    purchases = [e for e in train_events if e.get("eventName") == "purchase"]
    if not purchases:
        return set()
    latest_group = max(purchases, key=lambda e: parse_ts(e["timestamp"])).get("eventGroupId")
    relevant = [e for e in purchases if e.get("eventGroupId") == latest_group] if latest_group else purchases
    out = set()
    for e in relevant:
        unit = index.resolve(str(e.get("productId") or ""))
        if unit is not None:
            out.add(str(index.taxonomy[unit]))
    return out


def score(recommendations: dict[str, list[str]], targets: dict[str, str], bought: dict[str, set[str]],
          index: UnitIndex, latencies_ms: list[float] | None = None, *,
          open_trip: dict[str, set[str] | None] | None = None) -> dict[str, float]:
    """`open_trip`: khách → taxonomy đã mua trong chuyến mở tại as_of (∅ nếu chuyến mở chưa mua gì); None hoặc thiếu khoá =
    không có chuyến mở (xem `bench.open_trip_taxonomies`). Không truyền → hai cột cross-cat chuyến mở = 0,0 / 0."""
    users = [u for u in targets if u in recommendations]
    open_trip = open_trip or {}
    latencies = np.asarray(latencies_ms or [], dtype=np.float64)
    runtime = {f"p{q}_runtime_ms": float(np.percentile(latencies, q)) if latencies.size else 0.0 for q in (50, 95, 99)}
    if not users:
        return {"users": 0, "recall@5": 0.0, "recall@10": 0.0, "recall@20": 0.0, "ndcg@5": 0.0, "ndcg@10": 0.0,
                "cross_category_rate": 0.0, "availability_precision": 0.0, "catalog_coverage": 0.0,
                "vertical_diversity@10": 0.0, "returned_mean": 0.0, "exposure_gini": 0.0, **OPEN_TRIP_EMPTY, **runtime}
    recommendable_mask = np.asarray(index.recommendable, dtype=bool)
    n_taxonomies = max(1, len(set(map(str, index.taxonomy[recommendable_mask]))))
    exposure = np.zeros(recommendable_mask.size, dtype=np.int64)          # số lần mỗi unit vào top-20 (mọi khách)
    r5, r10, r20, ndcg5, ndcg, diversity, returned = [], [], [], [], [], [], []
    cross = items = available = 0
    cross_open = items_open = users_open = 0
    cross_bought = items_bought = users_bought = 0
    seen: set[str] = set()
    for user in users:
        ids, target = list(recommendations[user]), targets[user]
        excluded = open_trip.get(user)
        has_open, has_bought = excluded is not None, bool(excluded)
        users_open += has_open
        users_bought += has_bought
        returned.append(len(ids))
        r5.append(float(target in ids[:5]))
        r10.append(float(target in ids[:10]))
        r20.append(float(target in ids[:20]))
        ndcg5.append(1.0 / np.log2(ids[:5].index(target) + 2) if target in ids[:5] else 0.0)
        ndcg.append(1.0 / np.log2(ids[:10].index(target) + 2) if target in ids[:10] else 0.0)
        top10 = [str(index.taxonomy[index.idx[p]]) for p in ids[:10] if p in index.idx]
        diversity.append(len(set(top10)) / min(len(top10), n_taxonomies) if top10 else 0.0)
        for product_id in ids[:20]:
            i = index.idx.get(product_id)
            if i is None:
                continue
            seen.add(product_id)
            items += 1
            available += int(bool(index.available[i]))
            taxonomy = str(index.taxonomy[i])
            cross += int(taxonomy not in bought.get(user, set()))
            exposure[i] += 1
            if has_open:
                is_cross = int(taxonomy not in excluded)
                items_open += 1
                cross_open += is_cross
                if has_bought:
                    items_bought += 1
                    cross_bought += is_cross
    recommendable = max(int(recommendable_mask.sum()), 1)
    return {
        "users": len(users),
        "recall@5": float(np.mean(r5)), "recall@10": float(np.mean(r10)), "recall@20": float(np.mean(r20)),
        "ndcg@5": float(np.mean(ndcg5)), "ndcg@10": float(np.mean(ndcg)),
        "cross_category_rate": cross / items if items else 0.0,
        "availability_precision": available / items if items else 0.0,
        "catalog_coverage": len(seen) / recommendable,
        "vertical_diversity@10": float(np.mean(diversity)),
        "returned_mean": float(np.mean(returned)),
        "exposure_gini": gini(exposure[recommendable_mask]),
        "cross_category_open_trip": cross_open / items_open if items_open else 0.0, "users_open_trip": users_open,
        "cross_category_open_trip_bought": cross_bought / items_bought if items_bought else 0.0,
        "users_open_trip_bought": users_bought,
        **runtime,
    }


def rank_of(target: str, ids: list[str]) -> int | None:
    return ids.index(target) + 1 if target in ids else None


def paired_bootstrap(a: dict[str, float | None], b: dict[str, float | None], *, n_boot: int = 10_000, seed: int = 42) -> dict:
    """Δ = (b − a)·100 (điểm phần trăm) trên khoá có ở cả hai và xác định. Trả mean, CI95 percentile, p một phía (mid-p,
    H1: b > a), n cặp, n bị loại. Chép nguyên công thức `search_bench.metrics.paired_bootstrap` để hai bench đọc số cùng cách."""
    def defined(v) -> bool:
        return v is not None and not (isinstance(v, float) and v != v)

    common = sorted(set(a) & set(b))
    pairs = [(a[q], b[q]) for q in common if defined(a[q]) and defined(b[q])]
    dropped = len(set(a) | set(b)) - len(pairs)
    if not pairs:
        return {"delta": None, "ci95": [None, None], "p_one_sided": None, "n": 0, "n_dropped": dropped}
    d = np.array([(y - x) * 100.0 for x, y in pairs])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(axis=1)
    p = float((means < 0).mean() + 0.5 * (means == 0).mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"delta": float(d.mean()), "ci95": [float(lo), float(hi)], "p_one_sided": p, "n": len(d), "n_dropped": dropped}
