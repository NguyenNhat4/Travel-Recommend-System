"""Dựng bảng Markdown từ file kết quả của `eval_profile.py` / `paired_ci.py` — số trong report sinh thẳng từ JSON, không chép tay.

Thêm 08/10/2026 (plan WP0.4 / WP2): bàn giao trước dùng script dùng-một-lần không commit, nên không ai tái sinh được bảng.

    python -m src.evaluation.recsys_bench.theme_study.tables metrics run_a.json run_b.json
    python -m src.evaluation.recsys_bench.theme_study.tables metrics new.json --baseline-dir \
        src/evaluation/recsys_bench/theme_study/results/2026-10-08     # thêm cột số cũ 08/10
    python -m src.evaluation.recsys_bench.theme_study.tables ci ci.json
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os

SPLIT_COLS = [("llbo", "hit@20"), ("llbo", "ndcg@10"), ("llbo", "hit@4"),
              ("temporal", "hit@20"), ("temporal", "ndcg@10"), ("temporal", "hit@4"),
              ("nexttrip", "hit@20"), ("nexttrip", "ndcg@10"), ("nexttrip", "hit@4")]
SHORT = {"llbo": "LLBO", "temporal": "temp", "nexttrip": "next", "hit@20": "h@20", "ndcg@10": "nDCG@10", "hit@4": "h@4"}
SYN_ORDER = ("between", "noisy", "noisy_paired", "open")


def load(path: str) -> dict:
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def configs(res: dict) -> dict:
    """Chỉ các khoá cấu hình `P…+F…` (bỏ parity, stats, calibration)."""
    return {k: v for k, v in res.items() if "+" in k and isinstance(v, dict)}


def cell(cfg: dict, stratum: str, metric: str):
    v = cfg.get(stratum)
    return None if not isinstance(v, dict) else v.get(metric)


def fmt(v) -> str:
    return "" if v is None else f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def metrics_table(results: list[str], baseline_dir: str | None = None) -> str:
    merged: dict = {}
    for p in results:
        for k, v in configs(load(p)).items():
            merged[k] = v
    old: dict = {}
    if baseline_dir:
        # Một cấu hình có thể nằm rải ở nhiều file (vd split thật của P2+F7 ở `profile_p2f7.json`, cột `noisy` ở
        # `profile_noisy.json`), nên gộp theo từng stratum; file đọc trước thắng khi trùng stratum.
        for p in sorted(glob.glob(os.path.join(baseline_dir, "*.json"))):
            try:
                found = configs(load(p))
            except (ValueError, OSError):
                continue
            for k, v in found.items():
                for stratum, metrics in v.items():
                    old.setdefault(k, {}).setdefault(stratum, metrics)
    syn = [s for s in SYN_ORDER if any(f"syn_{s}" in c for c in merged.values())]
    head = ["Cấu hình"] + [f"{SHORT[s]} {SHORT[m]}" for s, m in SPLIT_COLS] + [f"theme {s}" for s in syn]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, cfg in merged.items():
        row = [name] + [fmt(cell(cfg, s, m)) for s, m in SPLIT_COLS] + \
              [fmt(cell(cfg, f"syn_{s}", "themePrec")) for s in syn]
        lines.append("| " + " | ".join(row) + " |")
        if name in old:
            o = old[name]
            row = [f"↳ 08/10 (engine cũ)"] + [fmt(cell(o, s, m)) for s, m in SPLIT_COLS] + \
                  [fmt(cell(o, f"syn_{s}", "themePrec")) for s in syn]
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def ci_table(path: str, strata: list[str] | None = None, seed: str = "all") -> str:
    data = load(path)
    head = ["So sánh", "Stratum", "Chỉ số", "n", "mốc", "mới", "chênh", "CI 95 %", "khác 0?"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in data["rows"]:
        if r["seed"] != seed or (strata and r["stratum"] not in strata):
            continue
        lines.append("| " + " | ".join([
            f"{r['baseline']} → {r['config']}", r["stratum"], r["metric"], str(r["n"]),
            fmt(r["meanA"]), fmt(r["meanB"]), f"{r['diff']:+.4f}",
            f"[{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}]", "có" if r["significant"] else "không",
        ]) + " |")
    return "\n".join(lines)


def seed_table(path: str) -> str:
    data = load(path)
    head = ["Cấu hình", "Stratum", "Chỉ số", "theo seed", "trung bình", "độ lệch"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in data.get("seedSpread", []):
        lines.append("| " + " | ".join([r["config"], r["stratum"], r["metric"],
                                        " / ".join(fmt(x) for x in r["perSeed"]),
                                        fmt(r["mean"]), fmt(r["sd"])]) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["metrics", "ci", "seeds"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--baseline-dir", default=None, help="thư mục results cũ để thêm dòng đối chiếu (metrics)")
    ap.add_argument("--strata", default="", help="lọc stratum, phân cách bằng dấu phẩy (ci)")
    ap.add_argument("--seed", default="all", help="nhãn seed của dòng CI (ci)")
    a = ap.parse_args()
    if a.what == "metrics":
        print(metrics_table(a.files, a.baseline_dir))
    elif a.what == "ci":
        print(ci_table(a.files[0], [s for s in a.strata.split(",") if s] or None, a.seed))
    else:
        print(seed_table(a.files[0]))


if __name__ == "__main__":
    main()
