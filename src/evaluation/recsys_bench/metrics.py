"""Chỉ số của harness (test-plan §2.5, handbook §12), một target mỗi khách.

Phần lõi port từ `origin/khoa/recsys-research@6b9b0af` (`src/evaluation/benchmark.py`: `score_recommendations`,
`_purchased_taxonomies`), giữ nguyên tên khoá. Bổ sung: `recall@5` (test-plan §2.5), `vertical_diversity@10`,
`returned_mean` (engine có thể trả ít hơn k vì MMR giới hạn 2 món mỗi taxonomy), `users`, `p50_runtime_ms`.
Không có MRR: một target mỗi khách thì NDCG@10 đã phản ánh thứ hạng.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .events import parse_ts


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
          index: UnitIndex, latencies_ms: list[float] | None = None) -> dict[str, float]:
    users = [u for u in targets if u in recommendations]
    latencies = np.asarray(latencies_ms or [], dtype=np.float64)
    runtime = {f"p{q}_runtime_ms": float(np.percentile(latencies, q)) if latencies.size else 0.0 for q in (50, 95, 99)}
    if not users:
        return {"users": 0, "recall@5": 0.0, "recall@10": 0.0, "recall@20": 0.0, "ndcg@10": 0.0,
                "cross_category_rate": 0.0, "availability_precision": 0.0, "catalog_coverage": 0.0,
                "vertical_diversity@10": 0.0, "returned_mean": 0.0, **runtime}
    n_taxonomies = max(1, len(set(map(str, index.taxonomy[np.asarray(index.recommendable, dtype=bool)]))))
    r5, r10, r20, ndcg, diversity, returned = [], [], [], [], [], []
    cross = items = available = 0
    seen: set[str] = set()
    for user in users:
        ids, target = list(recommendations[user]), targets[user]
        returned.append(len(ids))
        r5.append(float(target in ids[:5]))
        r10.append(float(target in ids[:10]))
        r20.append(float(target in ids[:20]))
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
            cross += int(str(index.taxonomy[i]) not in bought.get(user, set()))
    recommendable = max(int(np.asarray(index.recommendable, dtype=bool).sum()), 1)
    return {
        "users": len(users),
        "recall@5": float(np.mean(r5)), "recall@10": float(np.mean(r10)), "recall@20": float(np.mean(r20)),
        "ndcg@10": float(np.mean(ndcg)),
        "cross_category_rate": cross / items if items else 0.0,
        "availability_precision": available / items if items else 0.0,
        "catalog_coverage": len(seen) / recommendable,
        "vertical_diversity@10": float(np.mean(diversity)),
        "returned_mean": float(np.mean(returned)),
        **runtime,
    }


def rank_of(target: str, ids: list[str]) -> int | None:
    return ids.index(target) + 1 if target in ids else None
