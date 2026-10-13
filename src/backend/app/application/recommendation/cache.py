"""Cache kết quả gợi ý cá nhân hoá trên kho dùng chung (Redis), chốt 2026-10-12.

PRD `docs/prd/architecture.md` §4; đề xuất `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md`.

Quy tắc:
- **Khoá theo nội dung.** Khoá gồm namespace mã nguồn, phiên bản engine (catalog, bảng phổ biến, model, luật, knob), người
  dùng, `k`, `destination`, ngày theo giờ Việt Nam và **dấu vân tay toàn bộ event** đọc từ CDP ngay trong request. Event mới
  bất kỳ (xem, thêm giỏ, mua, huỷ) cho khoá mới, nên không bao giờ trả gợi ý tính từ lịch sử cũ và không cần xoá khoá khi mua
  hay huỷ (K1, AC-REC-02).
- **TTL bắt buộc** (Redis `noeviction`), mặc định 900 giây; không ghi giá trị lớn hơn `max_bytes`.
- **Chống tính trùng:** request đầu lấy khoá tính (`SET NX PX`), request cùng khoá chờ kết quả tối đa `wait_seconds` rồi tự tính.
- **Kho lỗi thì tính trực tiếp.** Đường lui khi CDP lỗi không đi qua đây (engine trả trước), nên không bao giờ được ghi.

Hằng ở đây, không ở `domain/recommendation/profile.py`: harness bench băm hằng chữ hoa của `profile.py` vào `configHash`.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import time
import uuid
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from src.backend.app.application.ports.recommendation_cache import RecommendationCacheStore, RecommendationCacheUnavailable
from src.backend.app.domain.recommendation.profile import ENGINE_RULES_VERSION

KEY_PREFIX = "rec:v1:"
LOCK_PREFIX = "rec:v1:lock:"
#: Khoá `diagnostics` của riêng một lần gọi (đo đạc, kết quả tra cache): không lưu vào cache.
VOLATILE_DIAGNOSTICS = ("stageMs", "userVectorCacheHit", "cacheOutcome", "eventsRead")
#: Kết quả tra cache, ghi vào `diagnostics.cacheOutcome` (chỉ dành cho log).
OUTCOMES = ("hit", "wait_hit", "miss", "wait_timeout", "too_large", "unserializable", "error")


@dataclasses.dataclass(frozen=True)
class CachePolicy:
    ttl_seconds: int = 900
    max_bytes: int = 65536
    lock_ttl_ms: int = 30_000             # ≥ thời gian một lần tính chậm nhất (timeout Weaviate 30 s)
    wait_seconds: float = 10.0            # bằng timeout gợi ý của Web: sau đó không còn ai chờ
    poll_seconds: tuple[float, float] = (0.025, 0.25)


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def events_fingerprint(events: list[dict]) -> str:
    """Dấu vân tay của đúng danh sách event engine dùng, theo thứ tự đọc (thứ tự đổi cách phá hoà nên phải tính vào)."""
    return _digest(events)


def popularity_digest(popularity) -> str:
    """Dấu vân tay tập purchase dựng bảng phổ biến; không gồm `now` (mỗi lần nạp một `now`, gồm vào thì các worker không
    bao giờ dùng chung khoá)."""
    if popularity is None:
        return "none"
    rows = sorted((p.unit, p.destination, p.booked_at, -1.0 if p.using_at is None else p.using_at) for p in popularity.p)
    return _digest(rows)


def engine_version(engine) -> str:
    """Phiên bản engine dùng trong khoá: catalog (mã băm Postgres + metadata vector), model, luật, bảng phổ biến và mọi knob
    kiểu đơn giản của dataclass engine (tự gồm knob thêm sau này)."""
    knobs = {f.name: getattr(engine, f.name) for f in dataclasses.fields(engine)
             if f.init and isinstance(getattr(engine, f.name), (bool, int, float, str, type(None)))}
    return _digest({"catalog": engine.catalog_version, "model": engine.index.model_version, "rules": ENGINE_RULES_VERSION,
                    "popularity": popularity_digest(engine.popularity), "knobs": knobs})[:32]


def source_digest(*modules: ModuleType) -> str:
    """Băm mã nguồn các module quyết định output. Dùng làm namespace của khoá: deploy code mới không đọc kết quả của code cũ."""
    h = hashlib.sha256()
    for module in modules:
        try:
            h.update(Path(module.__file__).read_bytes())
        except (OSError, TypeError, AttributeError):
            h.update(b"unknown")
    return h.hexdigest()[:16]


class RecommendationCache:
    def __init__(self, store: RecommendationCacheStore, policy: CachePolicy = CachePolicy(), *, namespace: str = "",
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 new_token: Callable[[], str] = lambda: uuid.uuid4().hex):
        self.store, self.policy, self.namespace = store, policy, namespace
        self._clock, self._sleep, self._new_token = clock, sleep, new_token

    def key(self, *, engine_version: str, cdp_user_id: str, k: int, destination: str | None, today: date,
            events: list[dict]) -> str:
        """Id người dùng chỉ nằm trong mã băm, không xuất hiện ở dạng rõ trong kho."""
        return KEY_PREFIX + _digest({"ns": self.namespace, "engine": engine_version, "user": cdp_user_id, "k": k,
                                     "destination": destination, "day": today.isoformat(),
                                     "events": events_fingerprint(events)})

    def get_or_compute(self, key: str, compute: Callable[[], dict]) -> tuple[dict, str]:
        """(kết quả, outcome). Trúng thì trả bản `json.loads` mới, nên request không dùng chung dict với nhau."""
        lock = LOCK_PREFIX + key[len(KEY_PREFIX):]
        try:
            cached = self._load(key)
            if cached is not None:
                return cached, "hit"
            token = self._new_token()
            leader = self.store.try_lock(lock, token, self.policy.lock_ttl_ms)
        except RecommendationCacheUnavailable:
            return compute(), "error"
        if leader:
            return self._lead(key, lock, token, compute)
        deadline = self._clock() + self.policy.wait_seconds
        delay = self.policy.poll_seconds[0]
        while (left := deadline - self._clock()) > 0:
            self._sleep(min(delay, left))
            delay = min(2 * delay, self.policy.poll_seconds[1])
            try:
                cached = self._load(key)
                if cached is not None:
                    return cached, "wait_hit"
                if self.store.try_lock(lock, token, self.policy.lock_ttl_ms):   # người giữ đã nhả không ghi, hoặc hết hạn
                    return self._lead(key, lock, token, compute)
            except RecommendationCacheUnavailable:
                return compute(), "error"
        result = compute()
        return result, self._store(key, result, ok="wait_timeout")

    def _lead(self, key: str, lock: str, token: str, compute: Callable[[], dict]) -> tuple[dict, str]:
        try:
            result = compute()
            return result, self._store(key, result, ok="miss")
        finally:
            try:
                self.store.unlock(lock, token)
            except RecommendationCacheUnavailable:
                pass   # khoá tự hết hạn sau lock_ttl_ms

    def _load(self, key: str) -> dict | None:
        raw = self.store.get(key)
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            return None   # giá trị hỏng: coi như trượt, lần tính sau ghi đè
        return value if isinstance(value, dict) else None

    def _store(self, key: str, result: dict, *, ok: str) -> str:
        diagnostics = {k: v for k, v in (result.get("diagnostics") or {}).items() if k not in VOLATILE_DIAGNOSTICS}
        try:
            payload = json.dumps({**result, "diagnostics": diagnostics}, ensure_ascii=False, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            return "unserializable"
        if len(payload) > self.policy.max_bytes:
            return "too_large"
        try:
            self.store.put(key, payload, self.policy.ttl_seconds)
        except RecommendationCacheUnavailable:
            return "error"
        return ok
