"""So `ids[:k]` theo khách giữa hai arm (cùng run hoặc hai run) — cổng regression R4 (spec `recsys-algos-v1.md` §9 G1/G2) và
`expect_equal_to` của yaml. Không cần DB / Weaviate: đọc `per_user.jsonl`."""
from __future__ import annotations


def ids_by_arm(per_user: list[dict]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for r in per_user:
        out.setdefault(r["arm"], {})[r["user"]] = r
    return out


def compare_ids(base: dict[str, dict], ref: dict[str, dict], *, k: int = 20, tie_tolerant: bool = False, max_examples: int = 10) -> dict:
    """`base[user]` / `ref[user]` là hàng per_user (có `ids`). Khớp = `ids[:k]` bằng nhau theo thứ tự (hoặc theo tập khi
    `tie_tolerant`). Trả {n, equal, equalSet, mismatches[≤ max_examples], onlyBase, onlyRef}."""
    users = sorted(set(base) & set(ref))
    equal = equal_set = 0
    mismatches = []
    for u in users:
        a, b = list(base[u].get("ids") or [])[:k], list(ref[u].get("ids") or [])[:k]
        same_set = set(a) == set(b)
        same = a == b
        equal += same
        equal_set += same_set
        ok = same_set if tie_tolerant else same
        if not ok and len(mismatches) < max_examples:
            mismatches.append({"user": u, "strategy": base[u].get("strategy"), "poolTruncated": base[u].get("poolTruncated"),
                               "base": a[:6], "ref": b[:6], "sameSet": same_set})
    n = len(users)
    return {"n": n, "equal": equal, "equalSet": equal_set, "k": k, "tieTolerant": tie_tolerant,
            "pass": n > 0 and (equal_set if tie_tolerant else equal) == n,
            "mismatches": mismatches, "onlyBase": len(set(base) - set(ref)), "onlyRef": len(set(ref) - set(base))}


def markdown(result: dict, base: str, ref: str) -> str:
    lines = [f"`{base}` vs `{ref}` · k = {result['k']} · khớp thứ tự **{result['equal']}/{result['n']}** · khớp tập {result['equalSet']}/{result['n']}"
             + (" · chế độ bỏ qua hoà" if result["tieTolerant"] else "")
             + (f" · chỉ ở base {result['onlyBase']} / chỉ ở ref {result['onlyRef']}" if result["onlyBase"] or result["onlyRef"] else "")
             + f" → {'PASS' if result['pass'] else 'FAIL'}"]
    if result["mismatches"]:
        lines += ["", "| Khách | strategy | pool cắt | base[:6] | ref[:6] | cùng tập |", "|---|---|---:|---|---|---|"]
        for m in result["mismatches"]:
            lines.append(f"| {m['user']} | {m['strategy']} | {m['poolTruncated']} | {m['base']} | {m['ref']} | {m['sameSet']} |")
    return "\n".join(lines)
