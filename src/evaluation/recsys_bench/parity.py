"""B9 (01/10) — offline = HTTP: engine offline của harness phải trả **đúng** list production cho cùng khách.

Đường HTTP: `GET /api/v1/internal/recommendations?cdp_user_id=&k=` của backend local (cùng checkout, cùng Postgres 5432,
cùng Weaviate 8080) với `X-Service-Token` lấy từ biến môi trường `AUTH_SERVICE_TOKEN` (không in). Đường offline:
`OfflineEngine(mode="prod")` với mọi khác biệt được trung hoà:
- `as_of` = `generatedAt` của response (production dùng `datetime.now()`), nên `days_ago` và cửa sổ phổ biến trùng;
- event của khách = event thô, mới nhất trước, đúng thứ tự `PostgresCdpReader.events_for_user` (`ORDER BY "timestamp" DESC`);
- bảng phổ biến từ purchase thô trước `as_of` (`popularity_at`), như `build_recsys` lúc khởi động (khởi động lại backend ngay
  trước khi đo để hai bảng cùng cửa sổ);
- k = 5 (list production), `candidate_k` cùng settings, cap 2 món / taxonomy.
So `strategy`, `destination`, `excludedVerticals`, `eventsUsed`, top-k đúng thứ tự → đạt khi 60/60. Báo thêm p50/p95 HTTP
local (`diagnostics.latencyMs` và wall phía client).

`make_users`: 4 persona + 56 khách phân tầng theo lifecycle tính từ event thô tại `as_of` DB (seed rule), tất định theo seed —
ghi `frozen/users60.json`. Danh sách 60 khách của brute-force check 24/09 không được lưu nên bộ này mới, mix sẽ khác.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .engine import OfflineEngine
from .events import PERSONA_IDS, parse_ts
from .sanity import lifecycle_seed_rule

INTERNAL_PATH = "/api/v1/internal/recommendations"
STAGE_QUOTA = {"new": 14, "active": 25, "dormant": 11, "churned": 6}      # 56 khách theo 25/45/20/10
COMPARE_FIELDS = ("strategy", "destination", "excludedVerticals", "eventsUsed")


class ParityError(RuntimeError):
    pass


def make_users(events: list[dict], as_of: datetime, *, seed: int = 42, quota: dict[str, int] | None = None) -> dict:
    """4 persona + 56 khách phân tầng lifecycle (seed rule) từ event thô; `random.Random(seed)` trên danh sách đã sắp xếp."""
    quota = dict(quota or STAGE_QUOTA)
    by_user: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_user[str(e.get("cdpUserId"))].append(e)
    as_of_day = as_of.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Ho_Chi_Minh")).date()
    stage_of = {u: lifecycle_seed_rule(evs, as_of_day)[0] for u, evs in by_user.items() if u not in PERSONA_IDS}
    rng = random.Random(seed)
    users = []
    for stage, n in quota.items():
        pool = sorted(u for u, s in stage_of.items() if s == stage)
        if len(pool) < n:
            raise ParityError(f"chỉ có {len(pool)} khách {stage} (cần {n})")
        users += [{"cdpUserId": u, "stage": stage} for u in rng.sample(pool, n)]
    personas = [{"cdpUserId": u, "stage": stage_of_persona(by_user.get(u, []), as_of_day), "persona": True} for u in sorted(PERSONA_IDS)]
    return {"seed": seed, "asOf": as_of.isoformat(), "quota": quota, "users": personas + users}


def stage_of_persona(evs: list[dict], as_of_day) -> str:
    return lifecycle_seed_rule(evs, as_of_day)[0]


def load_users(path: Path | str) -> list[str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    users = [str(u["cdpUserId"] if isinstance(u, dict) else u) for u in (raw.get("users") if isinstance(raw, dict) else raw) or []]
    if not users:
        raise ParityError(f"{path}: không có khách nào")
    return users


@dataclass
class ParityRow:
    user: str
    http_status: int | None
    http_ids: list[str]
    offline_ids: list[str]
    fields_http: dict = field(default_factory=dict)
    fields_offline: dict = field(default_factory=dict)
    latency_ms: int | None = None
    client_ms: float = 0.0
    error: str | None = None

    @property
    def ids_equal(self) -> bool:
        return self.http_ids == self.offline_ids

    @property
    def fields_equal(self) -> bool:
        return all(self.fields_http.get(f) == self.fields_offline.get(f) for f in COMPARE_FIELDS)

    @property
    def equal(self) -> bool:
        return self.error is None and self.ids_equal and self.fields_equal


def _fields(response: dict) -> dict:
    d = response.get("diagnostics") or {}
    return {"strategy": response.get("strategy"), "destination": response.get("destination"),
            "excludedVerticals": list(d.get("excludedVerticals") or []), "eventsUsed": d.get("eventsUsed")}


def events_desc(events: list[dict]) -> list[dict]:
    """Như `events_for_user`: mới nhất trước (sort ổn định theo timestamp giảm dần)."""
    return sorted(events, key=lambda e: parse_ts(e["timestamp"]), reverse=True)


def compare_user(user: str, http_response: dict, engine: OfflineEngine, user_events: list[dict], *, k: int,
                 http_status: int | None = 200, client_ms: float = 0.0) -> ParityRow:
    as_of = parse_ts(http_response["generatedAt"])
    offline = engine.recommend(user, as_of, k, events_desc([e for e in user_events if parse_ts(e["timestamp"]) < as_of]))
    return ParityRow(user, http_status, [r["productId"] for r in http_response.get("recommendations") or []],
                     [r["productId"] for r in offline.get("recommendations") or []], _fields(http_response), _fields(offline),
                     (http_response.get("diagnostics") or {}).get("latencyMs"), round(client_ms, 1))


def parity_http(base_url: str, users: list[str], engine: OfflineEngine, events: list[dict], *, k: int, token: str,
                timeout_s: float = 30.0, client: Any = None) -> list[ParityRow]:
    import httpx
    if len(token) < 32:
        raise ParityError("AUTH_SERVICE_TOKEN phải ≥ 32 ký tự (backend từ chối token ngắn hơn)")
    by_user: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_user[str(e.get("cdpUserId"))].append(e)
    own = client is None
    client = client or httpx.Client(timeout=timeout_s)
    rows = []
    try:
        for u in users:
            t0 = perf_counter()
            try:
                r = client.get(base_url.rstrip("/") + INTERNAL_PATH, params={"cdp_user_id": u, "k": k}, headers={"X-Service-Token": token})
                ms = (perf_counter() - t0) * 1000
                if r.status_code != 200:
                    rows.append(ParityRow(u, r.status_code, [], [], client_ms=round(ms, 1), error=f"HTTP {r.status_code}"))
                    continue
                rows.append(compare_user(u, r.json(), engine, by_user.get(u, []), k=k, http_status=r.status_code, client_ms=ms))
            except Exception as exc:  # noqa: BLE001 — một khách lỗi không chặn 59 khách còn lại
                rows.append(ParityRow(u, None, [], [], client_ms=round((perf_counter() - t0) * 1000, 1), error=f"{type(exc).__name__}: {exc}"))
    finally:
        if own:
            client.close()
    return rows


def verdict(rows: list[ParityRow]) -> dict:
    ok = [r for r in rows if r.error is None]
    equal = [r for r in rows if r.equal]
    lat = np.asarray([r.latency_ms for r in ok if r.latency_ms is not None], dtype=float)
    cli = np.asarray([r.client_ms for r in ok], dtype=float)
    pct = lambda a, q: float(np.percentile(a, q)) if a.size else None  # noqa: E731
    return {"n": len(rows), "nOk": len(ok), "equal": len(equal), "pass": len(equal) == len(rows) and bool(rows),
            "idsMismatch": [r.user for r in ok if not r.ids_equal], "fieldsMismatch": [r.user for r in ok if not r.fields_equal],
            "errors": [{"user": r.user, "error": r.error} for r in rows if r.error],
            "latencyMs": {"p50": pct(lat, 50), "p95": pct(lat, 95), "n": int(lat.size)},
            "clientMs": {"p50": pct(cli, 50), "p95": pct(cli, 95), "n": int(cli.size)}}


def write_parity(directory: Path, *, base_url: str, rows: list[ParityRow], result: dict, meta: dict | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / "parity.json"
    p.write_text(json.dumps({"baseUrl": base_url, **(meta or {}), "verdict": result,
                             "rows": [{**asdict(r), "equal": r.equal} for r in rows]}, ensure_ascii=False, indent=1, default=str),
                 encoding="utf-8")
    return p


def _ms(v) -> str:
    return "-" if v is None else f"{v:.0f}"


def markdown(rows: list[ParityRow], result: dict, *, k: int) -> str:
    lines = [f"| Khách | HTTP | strategy HTTP / offline | điểm đến | loại trừ | eventsUsed | top-{k} trùng | latencyMs |",
             "|---|---|---|---|---|---:|---|---:|"]
    for r in rows:
        if r.error:
            lines.append(f"| {r.user} | {r.http_status} | lỗi: {r.error} | | | | | |")
            continue
        h, o = r.fields_http, r.fields_offline
        lines.append(f"| {r.user} | {r.http_status} | {h['strategy']} / {o['strategy']} | {h['destination']} / {o['destination']} | "
                     f"{h['excludedVerticals']} / {o['excludedVerticals']} | {h['eventsUsed']} / {o['eventsUsed']} | "
                     f"{'✓' if r.ids_equal else '✗ ' + str(r.http_ids[:3]) + ' vs ' + str(r.offline_ids[:3])} | {r.latency_ms} |")
    lines += ["", f"**{result['equal']}/{result['n']}** khách trùng hoàn toàn · lệch ids {result['idsMismatch']} · lệch trường {result['fieldsMismatch']} · "
              f"lỗi {len(result['errors'])} · HTTP local `latencyMs` p50 {_ms(result['latencyMs']['p50'])} / p95 {_ms(result['latencyMs']['p95'])} ms · "
              f"client p50 {_ms(result['clientMs']['p50'])} / p95 {_ms(result['clientMs']['p95'])} ms"]
    return "\n".join(lines)
