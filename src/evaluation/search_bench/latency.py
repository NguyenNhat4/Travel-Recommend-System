"""Part 9 (30/09) — `sb latency http`: đo `/search` thật qua HTTP (Cloud qua BFF hoặc backend local).

Hai nhóm câu của `config/latency_queries.yaml`: `prewarmed` (câu gold, nằm trong danh sách prewarm của backend) và `cold`
(không có trong gold). Mỗi lượt (`runs`) gọi hết mọi câu theo thứ tự; mỗi mẫu ghi wall phía client (`client_ms`, gồm
mạng), `diagnostics.latencyMs` (route), `diagnostics.stageMs.*` (engine, contract 1.11.0), `embedCache` (contract 1.12.0),
`searchMode` và top-10 `productId`. `drop_first` bỏ lượt 1 khỏi p50/p95 (làm nóng kết nối) nhưng lượt 1 vẫn là nguồn
mẫu **miss** (lần gặp đầu của mỗi câu). Số đầu bảng là số server; `client_ms` báo riêng vì gồm RTT tới VM.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np
import yaml

from . import paths

SEARCH_PATH = "/api/v1/search"
STAGES = ("normalize", "embed", "dense", "lexical", "fuse", "hydrate")
_WS = re.compile(r"\s+")


class LatencyError(RuntimeError):
    pass


def canonical(text: str) -> str:
    """Gộp khoảng trắng — đúng khoá cache embedding của backend (không fold hoa/thường/dấu)."""
    return _WS.sub(" ", text).strip()


def load_queries(path: Path) -> dict[str, list[str]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    groups = {g: [canonical(str(t)) for t in (raw.get(g) or [])] for g in ("prewarmed", "cold")}
    if not any(groups.values()):
        raise LatencyError(f"{path}: không có câu nào trong prewarmed / cold")
    dup = set(groups["prewarmed"]) & set(groups["cold"])
    if dup:
        raise LatencyError(f"{path}: câu có ở cả hai nhóm: {sorted(dup)[:3]}")
    return groups


@dataclass
class Sample:
    group: str
    text: str
    run: int
    status: int | None
    client_ms: float
    latency_ms: int | None = None
    stage_ms: dict[str, int] = field(default_factory=dict)
    embed_cache: str | None = None
    search_mode: str | None = None
    top_ids: list[str] = field(default_factory=list)
    error: str | None = None


def search_once(client: Any, base_url: str, text: str, *, limit: int) -> tuple[int | None, dict | None, float, str | None]:
    """Một lượt GET; trả (status, json, client_ms, error). Lỗi mạng / JSON không ném — ghi vào mẫu."""
    t0 = perf_counter()
    try:
        r = client.get(base_url.rstrip("/") + SEARCH_PATH, params={"q": text, "limit": limit})
        ms = (perf_counter() - t0) * 1000.0
        try:
            body = r.json()
        except ValueError:
            return r.status_code, None, ms, f"không phải JSON ({r.status_code})"
        return r.status_code, body, ms, None if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001 — timeout, DNS… là dữ liệu đo, không phải lỗi chương trình
        return None, None, (perf_counter() - t0) * 1000.0, f"{type(e).__name__}: {e}"


def sample_from(group: str, text: str, run: int, status: int | None, body: dict | None, ms: float, err: str | None) -> Sample:
    d = (body or {}).get("diagnostics") or {}
    stage = d.get("stageMs") or {}
    return Sample(group=group, text=text, run=run, status=status, client_ms=round(ms, 1),
                  latency_ms=d.get("latencyMs"), stage_ms={k: int(v) for k, v in stage.items()},
                  embed_cache=d.get("embedCache"), search_mode=d.get("searchMode"),
                  top_ids=[str(x.get("productId")) for x in ((body or {}).get("results") or [])], error=err)


def measure(base_url: str, groups: dict[str, list[str]], *, runs: int, limit: int, timeout_s: float,
            client: Any = None, progress: Callable[[Sample], None] | None = None) -> list[Sample]:
    """`runs` lượt × mọi câu (prewarmed rồi cold), tuần tự — không song song để không tự tạo tải."""
    import httpx
    own = client is None
    client = client or httpx.Client(timeout=timeout_s, follow_redirects=True)
    out: list[Sample] = []
    try:
        for run in range(1, runs + 1):
            for group in ("prewarmed", "cold"):
                for text in groups.get(group) or []:
                    status, body, ms, err = search_once(client, base_url, text, limit=limit)
                    s = sample_from(group, text, run, status, body, ms, err)
                    out.append(s)
                    if progress:
                        progress(s)
    finally:
        if own:
            client.close()
    return out


def _pct(values: list[float], percentiles: tuple[int, ...]) -> dict[str, float | None]:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    return {f"p{p}": (float(np.percentile(arr, p)) if arr.size else None) for p in percentiles} | {"n": int(arr.size)}


def summarize(samples: list[Sample], *, drop_first: bool, percentiles: tuple[int, ...] = (50, 95)) -> dict:
    """Bảng theo nhóm và theo stage (lượt ≥ 2 khi drop_first), tách hit/miss theo `embedCache` (miss = lần gặp đầu),
    `top10_stable` = số câu có top-10 giống nhau ở mọi lượt thành công."""
    ok = [s for s in samples if s.error is None and s.status == 200]
    table = [s for s in ok if not (drop_first and s.run == 1)] or ok
    by_group: dict[str, dict] = {}
    for g in ("all", "prewarmed", "cold"):
        rows = table if g == "all" else [s for s in table if s.group == g]
        if not rows:
            continue
        by_group[g] = {"latency_ms": _pct([s.latency_ms for s in rows], percentiles),
                       "client_ms": _pct([s.client_ms for s in rows], percentiles),
                       "stage_ms": {st: _pct([s.stage_ms[st] for s in rows if st in s.stage_ms], percentiles)
                                    for st in STAGES if any(st in s.stage_ms for s in rows)}}
    first_seen: dict[str, Sample] = {}
    for s in ok:
        first_seen.setdefault(s.text, s)
    miss = [s for s in first_seen.values() if s.embed_cache == "miss"]
    hit = [s for s in ok if s.embed_cache == "hit"]
    by_cache = {name: {"latency_ms": _pct([s.latency_ms for s in rows], percentiles),
                       "embed_ms": _pct([s.stage_ms.get("embed") for s in rows], percentiles),
                       "client_ms": _pct([s.client_ms for s in rows], percentiles)}
                for name, rows in (("hit", hit), ("miss", miss)) if rows}
    tops: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    for s in ok:
        tops[s.text].append(tuple(s.top_ids))
    stable = sum(1 for t in tops.values() if len(set(t)) == 1)
    modes = sorted({s.search_mode for s in ok if s.search_mode})
    return {"n_samples": len(samples), "n_ok": len(ok), "n_error": len(samples) - len(ok), "drop_first": drop_first,
            "runs": max((s.run for s in samples), default=0), "search_modes": modes,
            "embed_cache_seen": sorted({s.embed_cache for s in ok if s.embed_cache}),
            "by_group": by_group, "by_cache": by_cache,
            "top10_stable": stable, "top10_total": len(tops),
            "top10": {t: list(v[-1]) for t, v in tops.items()},
            "errors": [{"text": s.text, "run": s.run, "error": s.error} for s in samples if s.error][:20]}


def latency_path(run_id: str, label: str | None) -> Path:
    return paths.run_dir(run_id) / (f"latency-{label}.json" if label else "latency.json")


def write_latency(run_id: str, *, base_url: str, queries_path: Path, samples: list[Sample], summary: dict,
                  label: str | None, meta: dict | None = None) -> Path:
    p = latency_path(run_id, label)
    payload = {"run_id": run_id, "label": label, "base_url": base_url, "queries": str(queries_path),
               **(meta or {}), "summary": summary, "samples": [asdict(s) for s in samples]}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
