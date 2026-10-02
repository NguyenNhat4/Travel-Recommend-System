"""So cặp arm trên **cùng run** (Day 4 R6, 01/10): paired bootstrap Δ hit@k / NDCG@k theo khách từ `per_user.jsonl`.

Δ = `base` − `ref` tính theo điểm phần trăm (×100), CI95 percentile, p một phía (H1: base > ref) — cùng công thức `sb compare`
của search_bench (`metrics.paired_bootstrap`). Cùng quy ước `analyze`: `base` là arm bị xét (vd `engine`), `ref` là baseline
đối chiếu (vd `most_popular_in_destination`). Hai arm phải thuộc cùng run (cùng split / configHash / modelVersion) —
`run --run-id` đã bảo đảm điều đó. hit@k và NDCG@k lấy từ `rank` (lenient, unit cha) qua `analysis._hit` / `_ndcg`.
Arm random có khoá theo seed (`random-s42`), không có khoá `random`.
"""
from __future__ import annotations

import numpy as np

from .analysis import _hit, _ndcg
from .metrics import paired_bootstrap

#: (tên, k, hàm theo khách) — @5 vì list production là 5 món; @20 là k của harness.
METRICS = (("hit@5", 5, _hit), ("hit@10", 10, _hit), ("hit@20", 20, _hit), ("ndcg@5", 5, _ndcg), ("ndcg@10", 10, _ndcg))


class CompareError(ValueError):
    """Thiếu arm trong run."""


def compare_arms(rows_by_arm: dict[str, dict[str, dict]], base: str, ref: str, *, n_boot: int = 10_000, seed: int = 42) -> dict:
    """`rows_by_arm[arm][user]` = hàng `per_user` → Δ (base − ref) từng chỉ số với CI95 bootstrap theo cặp khách."""
    for arm in (base, ref):
        if arm not in rows_by_arm:
            raise CompareError(f"run không có arm {arm!r} (có: {sorted(rows_by_arm)})")
    users = sorted(set(rows_by_arm[base]) & set(rows_by_arm[ref]))
    only_one = len(set(rows_by_arm[base]) ^ set(rows_by_arm[ref]))
    out = {"base": base, "ref": ref, "n": len(users), "usersOnlyOneArm": only_one, "nBoot": n_boot, "seed": seed, "metrics": {}}
    for name, k, fn in METRICS:
        a = {u: float(fn(rows_by_arm[ref][u], k)) for u in users}
        b = {u: float(fn(rows_by_arm[base][u], k)) for u in users}
        boot = paired_bootstrap(a, b, n_boot=n_boot, seed=seed)
        out["metrics"][name] = {"base": float(np.mean(list(b.values()))) if b else 0.0,
                                "ref": float(np.mean(list(a.values()))) if a else 0.0, **boot}
    return out


def compare_markdown(c: dict) -> str:
    lines = [f"Δ = `{c['base']}` − `{c['ref']}` (điểm phần trăm) · paired bootstrap {c['nBoot']:,} lượt, seed {c['seed']} · "
             f"n = {c['n']} khách" + (f" · {c['usersOnlyOneArm']} khách chỉ có ở một arm (bỏ)" if c["usersOnlyOneArm"] else ""),
             "", "| Chỉ số | base | ref | Δ | CI95 | p một phía (base ≤ ref) |", "|---|---:|---:|---:|---|---:|"]
    for name, m in c["metrics"].items():
        if m["delta"] is None:
            lines.append(f"| {name} | {m['base']:.4f} | {m['ref']:.4f} | — | — | — |")
            continue
        lines.append(f"| {name} | {m['base']:.4f} | {m['ref']:.4f} | {m['delta']:+.2f} | "
                     f"[{m['ci95'][0]:+.2f}; {m['ci95'][1]:+.2f}] | {m['p_one_sided']:.4f} |")
    return "\n".join(lines)
