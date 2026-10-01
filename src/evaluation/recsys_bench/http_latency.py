"""Day 2 C — p95 `/recommendations` qua HTTP (Cloud hoặc local), lệnh `http-latency`.

Hai đường:
- **guest** (mặc định): `GET /api/v1/recommendations?k=` không cookie / token → strategy `popular`. Đây là đường duy nhất
  đo được từ ngoài trên Cloud hôm nay (`/internal/recommendations` cần `X-Service-Token` + `INTERNAL_API_ENABLED`, BFF
  không chuyển header) → số báo là **guest path, không phải 60 khách**.
- **users**: `GET /api/v1/internal/recommendations?cdp_user_id=&k=` với `X-Service-Token` lấy từ biến môi trường
  (`--token-env`, không in) cho danh sách khách trong file JSON (`{"users": [{"cdpUserId": …}, …]}`) — dùng khi ops mở
  tunnel IAP hoặc chạy backend local với `INTERNAL_API_ENABLED=true`.

Số đầu bảng = `diagnostics.latencyMs` (server); `client_ms` (gồm mạng) báo riêng. `drop_first` bỏ lượt 1 (làm nóng).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np

GUEST_PATH = "/api/v1/recommendations"
INTERNAL_PATH = "/api/v1/internal/recommendations"


class HttpLatencyError(RuntimeError):
    pass


@dataclass
class Sample:
    path: str
    user: str | None
    run: int
    status: int | None
    client_ms: float
    latency_ms: int | None = None
    strategy: str | None = None
    n_items: int = 0
    top_ids: list[str] = field(default_factory=list)
    error: str | None = None


def load_users(path: Path) -> list[str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    users = [str(u["cdpUserId"] if isinstance(u, dict) else u) for u in (raw.get("users") if isinstance(raw, dict) else raw) or []]
    if not users:
        raise HttpLatencyError(f"{path}: không có khách nào")
    return users


def _call(client: Any, url: str, params: dict, headers: dict, *, path: str, user: str | None, run: int) -> Sample:
    t0 = perf_counter()
    try:
        r = client.get(url, params=params, headers=headers)
        ms = (perf_counter() - t0) * 1000.0
        try:
            body = r.json()
        except ValueError:
            return Sample(path, user, run, r.status_code, round(ms, 1), error=f"không phải JSON ({r.status_code})")
        d = (body or {}).get("diagnostics") or {}
        items = (body or {}).get("recommendations") or []
        return Sample(path, user, run, r.status_code, round(ms, 1), latency_ms=d.get("latencyMs"), strategy=body.get("strategy"),
                      n_items=len(items), top_ids=[str(i.get("productId")) for i in items],
                      error=None if r.status_code == 200 else f"HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001 — timeout / DNS là dữ liệu đo
        return Sample(path, user, run, None, round((perf_counter() - t0) * 1000.0, 1), error=f"{type(e).__name__}: {e}")


def measure(base_url: str, *, runs: int, k: int, timeout_s: float, users: list[str] | None = None,
            token_env: str = "AUTH_SERVICE_TOKEN", client: Any = None,
            progress: Callable[[Sample], None] | None = None) -> list[Sample]:
    """Guest: mỗi lượt một GET (không cookie). Users: mỗi lượt một GET mỗi khách với X-Service-Token từ `token_env`."""
    import httpx
    base = base_url.rstrip("/")
    headers: dict = {}
    if users:
        token = os.environ.get(token_env, "")
        if len(token) < 32:
            raise HttpLatencyError(f"đường users cần {token_env} (≥ 32 ký tự) trong môi trường — không truyền qua tham số")
        headers = {"X-Service-Token": token}
    own = client is None
    client = client or httpx.Client(timeout=timeout_s, follow_redirects=True)
    out: list[Sample] = []
    try:
        for run in range(1, runs + 1):
            if users:
                for u in users:
                    s = _call(client, base + INTERNAL_PATH, {"cdp_user_id": u, "k": k}, headers, path="users", user=u, run=run)
                    out.append(s)
                    if progress:
                        progress(s)
            else:
                # guest: lặp `k` GET mỗi lượt để có đủ mẫu cho p95 (một khách popular mọi lần như nhau)
                for _ in range(max(1, k)):
                    s = _call(client, base + GUEST_PATH, {"k": k}, {}, path="guest", user=None, run=run)
                    out.append(s)
                    if progress:
                        progress(s)
    finally:
        if own:
            client.close()
    return out


def _pct(values: list[float | None], ps=(50, 95)) -> dict:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    return {f"p{p}": (float(np.percentile(arr, p)) if arr.size else None) for p in ps} | {"n": int(arr.size)}


def summarize(samples: list[Sample], *, drop_first: bool) -> dict:
    ok = [s for s in samples if s.error is None and s.status == 200]
    table = [s for s in ok if not (drop_first and s.run == 1)] or ok
    strategies: dict[str, int] = {}
    for s in ok:
        strategies[s.strategy or "?"] = strategies.get(s.strategy or "?", 0) + 1
    return {"path": samples[0].path if samples else None, "n_samples": len(samples), "n_ok": len(ok),
            "n_error": len(samples) - len(ok), "drop_first": drop_first, "runs": max((s.run for s in samples), default=0),
            "latency_ms": _pct([s.latency_ms for s in table]), "client_ms": _pct([s.client_ms for s in table]),
            "strategies": strategies, "n_items_min": min((s.n_items for s in ok), default=0),
            "errors": [{"user": s.user, "run": s.run, "error": s.error} for s in samples if s.error][:20]}


def write(directory: Path, *, base_url: str, samples: list[Sample], summary: dict, meta: dict | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / "http_latency.json"
    p.write_text(json.dumps({"base_url": base_url, **(meta or {}), "summary": summary, "samples": [asdict(s) for s in samples]},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    return p
