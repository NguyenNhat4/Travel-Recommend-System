"""Day 5 — regression gọn cho search (plan Day 4–5 §2.3 việc 5; quyết định người dùng 05/10: bản gọn, chưa làm
Part 12–13 đầy đủ).

`baseline_v1.json` = ảnh chụp metric **từng câu** của một arm (mặc định cấu hình production `APP.hybrid_norm`) trên một
gold đã tag. `regress` so một lượt chạy mới của cùng arm với ảnh chụp đó:

- FAIL khi Δ overall của một metric trong `metrics` < −`max_drop_overall` điểm, hoặc Δ của một slice < −`max_drop_slice`
  điểm (điểm = ×100). Ngưỡng ở `regression.regress_v1` trong `sbench.yaml`.
- Mọi trung bình tính lại từ metric từng câu trên **tập câu chung** của hai bên (và của `--split`), nên chạy trên chính
  run làm baseline luôn ra Δ = 0 → PASS.
- Khác `gold_version` → không so (cần `sb rescore` lượt chạy mới trên gold của baseline). Khác `resolved_config_hash`
  chỉ cảnh báo: đó chính là thay đổi đang kiểm.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from . import paths

BASELINE_VERSION = "baseline_v1"


class RegressError(ValueError):
    pass


@dataclass(frozen=True)
class Thresholds:
    metrics: tuple[str, ...]
    max_drop_overall: float
    max_drop_slice: float
    worst_n: int = 10

    @classmethod
    def from_cfg(cls, cfg) -> "Thresholds":
        r = (cfg.regression.model_extra or {}).get("regress_v1")
        if not r:
            raise RegressError("sbench.yaml thiếu regression.regress_v1 (metrics, max_drop_overall, max_drop_slice)")
        return cls(metrics=tuple(r["metrics"]), max_drop_overall=float(r["max_drop_overall"]),
                   max_drop_slice=float(r["max_drop_slice"]), worst_n=int(r.get("worst_n", 10)))


def baseline_path(cfg) -> Path:
    rel = (cfg.regression.model_extra or {}).get("baseline_file")
    if not rel:
        raise RegressError("sbench.yaml thiếu regression.baseline_file")
    return paths.PKG_DIR / rel


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=paths.repo_root(), capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _num(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


def per_query(rows: list[dict], metric_names: tuple[str, ...]) -> dict[str, dict]:
    return {r["qid"]: {"slice": r["slice"], "top_ids": list(r.get("top_ids") or [])[:10],
                       **{m: _num(r.get(m)) for m in metric_names}} for r in rows}


def make_baseline(results: dict, rows: list[dict], th: Thresholds, *, items_sha256: str | None, note: str,
                  by: str | None = None) -> dict:
    if not results.get("gold_version"):
        raise RegressError("kết quả chưa gắn gold_version (gold chưa tag) — không dùng làm baseline")
    if not note.strip():
        raise RegressError("baseline cần --note (vì sao đặt mốc này)")
    dirty = bool(_git("status", "--porcelain"))
    return {"version": BASELINE_VERSION, "arm": results["arm"], "run_id": results["run_id"],
            "resolved_config_hash": results["resolved_config_hash"], "model": results.get("model"),
            "gold_version": results["gold_version"], "gold_sha256": results["gold_sha256"],
            "items_sha256": items_sha256, "n_items": results.get("n_items"), "k": results.get("k"),
            "git_commit": _git("rev-parse", "HEAD") or None, "git_dirty": dirty,
            "metrics": list(th.metrics), "overall": {m: results["overall"].get(m) for m in th.metrics},
            "by_slice": {s: {m: v.get(m) for m in th.metrics} | {"n": v.get("n")} for s, v in results["by_slice"].items()},
            "per_query": per_query(rows, th.metrics), "note": note.strip(), "by": by or _git("config", "user.name") or None,
            "at": datetime.now().astimezone().replace(microsecond=0).isoformat()}


def write_baseline(data: dict, p: Path, *, force: bool = False) -> Path:
    if p.exists() and not force:
        raise RegressError(f"{p.name} đã có — đổi mốc phải chủ động (--force + --note lý do)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def load_baseline(p: Path) -> dict:
    if not p.exists():
        raise RegressError(f"chưa có {p} — chạy `sb regress baseline` trước")
    return json.loads(p.read_text(encoding="utf-8"))


def _mean(vals: list[float | None]) -> float | None:
    v = [x for x in vals if x is not None]
    return float(np.mean(v)) if v else None


def _delta(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else (b - a) * 100.0


def check(baseline: dict, results: dict, rows: list[dict], th: Thresholds, *, qids: set[str] | None = None) -> dict:
    """So lượt chạy mới với baseline. `qids` giới hạn tập câu (vd split dev)."""
    if results.get("gold_version") != baseline["gold_version"]:
        raise RegressError(f"gold khác nhau: baseline {baseline['gold_version']}, lượt chạy {results.get('gold_version')} — "
                           f"`sb rescore --run-id {results.get('run_id')}` trên gold của baseline rồi chạy lại")
    if results.get("arm") != baseline["arm"]:
        raise RegressError(f"arm khác nhau: baseline {baseline['arm']}, lượt chạy {results.get('arm')}")
    base = baseline["per_query"]
    cur = per_query(rows, th.metrics)
    common = set(base) & set(cur)
    if qids is not None:
        common &= qids
    if not common:
        raise RegressError("không có câu chung giữa baseline và lượt chạy")
    lines, failures = [], []

    def _line(scope: str, n: int, metric: str, a: float | None, b: float | None, limit: float) -> None:
        d = _delta(a, b)
        bad = d is not None and d < -limit and not np.isclose(d, -limit, rtol=0.0, atol=1e-9)
        lines.append({"scope": scope, "n": n, "metric": metric, "baseline": a, "current": b, "delta": d,
                      "limit": -limit, "status": "FAIL" if bad else "ok"})
        if bad:
            failures.append(f"{scope} {metric} {d:+.2f} < −{limit:g}")

    for m in th.metrics:
        _line("overall", len(common), m, _mean([base[q][m] for q in common]), _mean([cur[q][m] for q in common]),
              th.max_drop_overall)
    slices = sorted({base[q]["slice"] for q in common})
    for s in slices:
        qs = [q for q in common if base[q]["slice"] == s]
        for m in th.metrics:
            _line(s, len(qs), m, _mean([base[q][m] for q in qs]), _mean([cur[q][m] for q in qs]), th.max_drop_slice)
    lead = th.metrics[0]
    drops = []
    for q in common:
        d = _delta(base[q][lead], cur[q][lead])
        if d is not None and d < 0:
            drops.append({"qid": q, "slice": base[q]["slice"], "metric": lead, "delta": d,
                          "top5_before": base[q]["top_ids"][:5], "top5_after": cur[q]["top_ids"][:5]})
    drops.sort(key=lambda x: (x["delta"], x["qid"]))
    changed = sum(1 for q in common if base[q]["top_ids"] != cur[q]["top_ids"])
    warnings = []
    if results.get("resolved_config_hash") != baseline["resolved_config_hash"]:
        warnings.append(f"config hash {baseline['resolved_config_hash'][:8]} → {results.get('resolved_config_hash', '')[:8]}")
    return {"status": "FAIL" if failures else "PASS", "failures": failures, "warnings": warnings,
            "baseline": {k: baseline.get(k) for k in ("version", "arm", "run_id", "gold_version", "git_commit", "note")},
            "run_id": results.get("run_id"), "n_queries": len(common), "n_top_ids_changed": changed,
            "thresholds": {"metrics": list(th.metrics), "max_drop_overall": th.max_drop_overall,
                           "max_drop_slice": th.max_drop_slice}, "lines": lines, "worst": drops[: th.worst_n]}
