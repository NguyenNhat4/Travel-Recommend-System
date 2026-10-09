"""Khoảng tin cậy ghép cặp cho chênh lệch giữa hai cấu hình RecSys (plan WP2.2, `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md`).

Vì sao cần: báo cáo cuối 08/10 (`docs/spec/bench/recsys-bam-so-thich-tong-hop.md` §2.4) chỉ có ước lượng z hai tỷ lệ **độc lập**,
trong khi mọi cấu hình chạy trên **cùng tập khách**. Ước lượng độc lập rộng hơn thực tế, nên "chưa phân biệt được" ở đó có thể là
khác biệt thật. Bootstrap ghép cặp lấy lại khách (cùng một khách rút cho cả hai cấu hình) nên đo đúng phương sai của chênh lệch.

Đầu vào: các file JSONL do `eval_profile.py --per-user-out` ghi, mỗi dòng một khách:
    {"config": "P2_confidence+F7_…", "stratum": "llbo" | "syn_between" | …, "seed": null | 42, "uid": "…",
     "hit@20": 1.0, "ndcg@10": 0.43, "hit@4": 0.0}            # split thật
    {"config": …, "stratum": "syn_noisy_paired", "seed": 42, "uid": "…", "themePrec": 0.75}   # khách giả lập

Chạy:
    python -m src.evaluation.recsys_bench.theme_study.paired_ci --per-user a.jsonl b.jsonl \
        --baseline P0_prod+F0_prod --out ci.json
"""
from __future__ import annotations

import argparse
import collections
import json

import numpy as np

#: Chỉ số đo theo loại stratum. Split thật có target nên đo hit / nDCG; khách giả lập đo tỷ lệ đúng chủ đề.
SPLIT_METRICS = ("hit@20", "ndcg@10", "hit@4", "destHit@20", "mrr@20")   # destHit@20: eval_split có idx (lane A2); mrr@20: eval_oph
#: `tgtHit` / `nextDestHit` chỉ có khi chạy `eval_profile --syn-target`; `index()` tự bỏ chỉ số không có trong dòng.
SYN_METRICS = ("themePrec", "tgtHit@20", "tgtHit@4", "nextDestHit@20", "nextDestHit@4", "xvAtX@4")
BOOT = 2000
#: Seed của bootstrap: cố định để hai lần chạy cùng dữ liệu cho cùng CI (số trong report phải tái sinh được).
BOOT_SEED = 20261008


def load(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    return rows


def index(rows: list[dict]) -> dict:
    """(config, stratum, seed, metric) -> {uid: value}; bỏ giá trị None (khách giả lập không có điểm đến chấm được)."""
    out: dict = collections.defaultdict(dict)
    for r in rows:
        metrics = SYN_METRICS if str(r.get("stratum", "")).startswith("syn_") else SPLIT_METRICS
        for m in metrics:
            v = r.get(m)
            if v is None:
                continue
            out[(r["config"], r["stratum"], r.get("seed"), m)][r["uid"]] = float(v)
    return dict(out)


def paired_ci(a: dict, b: dict, boot: int = BOOT, seed: int = BOOT_SEED, alpha: float = 0.05) -> dict | None:
    """CI bootstrap ghép cặp cho `mean(b) − mean(a)` trên các khách có mặt ở CẢ HAI cấu hình.

    Rút lại theo KHÁCH (không theo quan sát): mỗi lần rút lấy một bộ khách cùng cỡ, và cùng bộ đó dùng cho cả hai cấu hình —
    đó là chỗ phương sai của chênh lệch nhỏ hơn hẳn so với coi hai mẫu độc lập."""
    uids = sorted(set(a) & set(b))
    if not uids:
        return None
    xa = np.array([a[u] for u in uids], dtype=np.float64)
    xb = np.array([b[u] for u in uids], dtype=np.float64)
    d = xb - xa
    n = len(uids)
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, n, size=(boot, n))].mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    n_disc = int(np.count_nonzero(d))
    # p hai phía bootstrap (plan 2026-10-09 §7.4): 2·min(P(mean ≤ 0), P(mean ≥ 0)); hai cấu hình giống hệt → p = 1
    p = 1.0 if n_disc == 0 else min(1.0, 2 * min(float((means <= 0).mean()), float((means >= 0).mean())))
    return {"n": n, "meanA": round(float(xa.mean()), 4), "meanB": round(float(xb.mean()), 4),
            "diff": round(float(d.mean()), 4), "ci_lo": round(float(lo), 4), "ci_hi": round(float(hi), 4),
            # cận dưới CI 90 % một phía — luật giữ bậc superiority (plan §7.5)
            "lo90_1s": round(float(np.percentile(means, 10)), 4),
            "nDiscordant": n_disc, "shareBootGt0": round(float((means > 0).mean()), 4), "p": round(p, 5),
            "significant": bool(lo > 0 or hi < 0)}


def pooled(idx: dict, config: str, stratum: str, metric: str) -> dict:
    """Gộp mọi seed của một stratum: khách của các seed khác nhau là khách khác nhau nên uid phải mang seed."""
    out = {}
    for (c, s, seed, m), vals in idx.items():
        if c == config and s == stratum and m == metric:
            out.update({f"{seed}/{u}": v for u, v in vals.items()})
    return out


def compare(idx: dict, pairs: list[tuple[str, str]], boot: int = BOOT, seed: int = BOOT_SEED,
            by_seed: bool = False) -> list[dict]:
    strata = sorted({k[1] for k in idx})
    rows = []
    for base, cand in pairs:
        for stratum in strata:
            metrics = SYN_METRICS if stratum.startswith("syn_") else SPLIT_METRICS
            seeds = sorted({k[2] for k in idx if k[1] == stratum}, key=lambda s: (s is None, s))
            groups = [("all", None)] + ([(str(s), s) for s in seeds] if by_seed and len(seeds) > 1 else [])
            for label, only in groups:
                for metric in metrics:
                    if only is None:
                        a, b = pooled(idx, base, stratum, metric), pooled(idx, cand, stratum, metric)
                    else:
                        a = idx.get((base, stratum, only, metric), {})
                        b = idx.get((cand, stratum, only, metric), {})
                    r = paired_ci(a, b, boot, seed)
                    if r:
                        rows.append({"baseline": base, "config": cand, "stratum": stratum, "seed": label,
                                     "metric": metric, **r})
    return rows


def noise_effect(rows: list[dict], boot: int = BOOT, seed: int = BOOT_SEED) -> list[dict]:
    """Nhiễu làm `themePrec` giảm bao nhiêu **trên cùng một khách** (plan WP2.3).

    Ghép `syn_noisy_paired` với `syn_between` qua `baseUid` (khách nhiễu là bản sao của khách `between` cộng 5–8 lượt xem
    lệch chủ đề). So `between` với kịch bản `noisy` cũ không làm được việc này: đó là hai cohort khác nhau, nên chênh lệch
    lẫn cả khác biệt lịch sử nền (báo cáo cuối §2.2)."""
    out = []
    for config in dict.fromkeys(r["config"] for r in rows):
        base = {(r.get("seed"), r["uid"]): r.get("themePrec") for r in rows
                if r["config"] == config and r.get("stratum") == "syn_between"}
        a, b = {}, {}
        for r in rows:
            if r["config"] != config or r.get("stratum") != "syn_noisy_paired" or not r.get("baseUid"):
                continue
            k = (r.get("seed"), r["baseUid"])
            if base.get(k) is None or r.get("themePrec") is None:
                continue
            key = f"{r.get('seed')}/{r['baseUid']}"
            a[key], b[key] = float(base[k]), float(r["themePrec"])
        r = paired_ci(a, b, boot, seed)
        if r:
            out.append({"config": config, "stratum": "syn_between -> syn_noisy_paired", "metric": "themePrec", **r})
    return out


def seed_spread(idx: dict) -> list[dict]:
    """Trung bình ± độ lệch giữa các seed cho từng cấu hình × stratum khách giả lập (plan WP2.4)."""
    out = []
    by: dict = collections.defaultdict(dict)
    for (c, s, seed, m), vals in idx.items():
        if s.startswith("syn_") and seed is not None and vals:
            by[(c, s, m)][seed] = float(np.mean(list(vals.values())))
    for (c, s, m), per in sorted(by.items()):
        v = np.array([per[k] for k in sorted(per)], dtype=np.float64)
        out.append({"config": c, "stratum": s, "metric": m, "seeds": sorted(per),
                    "perSeed": [round(x, 4) for x in v], "mean": round(float(v.mean()), 4),
                    "sd": round(float(v.std(ddof=1)) if len(v) > 1 else 0.0, 4)})
    return out


def split_rows(rows: list[dict], fields: list[str]) -> list[dict]:
    """Thêm bản sao của mỗi dòng với stratum `<stratum>|<field>=<value>` (vd `temporal|ctx0=booked`) để có CI theo tầng."""
    out = list(rows)
    for f in fields:
        out += [{**r, "stratum": f"{r['stratum']}|{f}={r.get(f)}"} for r in rows if f in r]
    return out


def holm(rows: list[dict], family: list[dict], alpha: float = 0.05) -> list[dict]:
    """Holm–Bonferroni trên họ chỉ số chính (khai trước, plan §7.4). `family`: danh sách {baseline, config, stratum, metric}."""
    keys = [(f["baseline"], f["config"], f["stratum"], f["metric"]) for f in family]
    found = {(r["baseline"], r["config"], r["stratum"], r["metric"]): r for r in rows if r.get("seed") == "all"}
    fam = [(k, found[k]["p"]) for k in keys if k in found]
    missing = [k for k in keys if k not in found]
    m = len(fam)
    out, running, stop = [], 0.0, False
    for rank, (k, p) in enumerate(sorted(fam, key=lambda kp: kp[1])):
        adj = min(1.0, (m - rank) * p)
        running = max(running, adj)
        reject = not stop and p <= alpha / (m - rank)
        stop = stop or not reject
        out.append({"baseline": k[0], "config": k[1], "stratum": k[2], "metric": k[3], "p": p, "pHolm": round(running, 5),
                    "reject": reject})
    return out + [{"baseline": k[0], "config": k[1], "stratum": k[2], "metric": k[3], "missing": True} for k in missing]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-user", nargs="+", required=True, help="một hoặc nhiều file JSONL của --per-user-out")
    ap.add_argument("--baseline", default=None, help="cấu hình làm mốc; mặc định cấu hình xuất hiện đầu tiên")
    ap.add_argument("--compare", default="", help="cặp tường minh, vd 'A:B,C:D' hoặc 'A>B' — ghi đè --baseline")
    ap.add_argument("--boot", type=int, default=BOOT)
    ap.add_argument("--seed", type=int, default=BOOT_SEED)
    ap.add_argument("--by-seed", action="store_true", help="thêm dòng CI riêng cho từng seed khách giả lập")
    ap.add_argument("--split-by", default="", help="trường per-user để tách tầng, vd 'ctx0,segment' (dòng eval_oph)")
    ap.add_argument("--family", default=None, help="file JSON danh sách {baseline, config, stratum, metric} → Holm")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = load(a.per_user)
    if a.split_by:
        rows = split_rows(rows, [f for f in a.split_by.split(",") if f])
    idx = index(rows)
    configs = list(dict.fromkeys(r["config"] for r in rows))
    if a.compare:
        # 'A>B' khi tên cấu hình chứa ':' (vd `B2+popH:90:1>B2+popH:90:1+dormHL:3`); 'A:B' như cũ
        pairs = [tuple(p.split(">", 1)) if ">" in p else tuple(p.split(":", 1)) for p in a.compare.split(",") if p]
    else:
        base = a.baseline or configs[0]
        if base not in configs:
            raise SystemExit(f"--baseline {base!r} không có trong dữ liệu: {configs}")
        pairs = [(base, c) for c in configs if c != base]
    out = {"boot": a.boot, "bootSeed": a.seed, "configs": configs,
           "rows": compare(idx, pairs, a.boot, a.seed, a.by_seed), "seedSpread": seed_spread(idx),
           "noiseEffect": noise_effect(rows, a.boot, a.seed)}
    if a.family:
        out["holm"] = holm(out["rows"], json.load(open(a.family, encoding="utf-8")))
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in out["rows"]:
        flag = "*" if r["significant"] else " "
        print(f"{flag} {r['stratum']:<20} {r['metric']:<9} seed={r['seed']:<5} {r['baseline']} -> {r['config']}: "
              f"{r['meanA']:.4f} -> {r['meanB']:.4f}  diff {r['diff']:+.4f} "
              f"[{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}] n={r['n']}", flush=True)


if __name__ == "__main__":
    main()
