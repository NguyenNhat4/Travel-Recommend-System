from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from src.backend.app.application.ports import CdpHistoryReader, UnitIndex, VectorSearchPort
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.search import hit
from src.backend.app.core.logging_config import log_event
from src.backend.app.domain.recommendation import Popularity, Purchase, ResolvedEvent, build_profile, explain, mmr_select, score_candidates
from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL, local_today, parse_using_date

logger = logging.getLogger("uvicorn.error")


def _using_date(value):
    """`usingDate` của event CDP → `date` (một parser chung với harness bench: `profile.parse_using_date`)."""
    return parse_using_date(value)


def _ts(x) -> float:
    if isinstance(x, datetime):
        return x.timestamp()
    return datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()


@dataclass
class BuildPopularity:
    """Job: từ CDP purchase events → Popularity. Chạy nightly (hoặc mỗi request khi mock nhỏ)."""
    index: UnitIndex
    cdp: CdpHistoryReader

    def __call__(self, now: datetime | None = None) -> Popularity:
        purchases = []
        for e in self.cdp.purchase_events():
            i = self.index.resolve(e["productId"])
            if i is None:
                continue
            purchases.append(Purchase(unit=i, destination=str(self.index.destination[i]), booked_at=_ts(e["timestamp"]),
                                      using_at=_ts(e["usingDate"]) if e.get("usingDate") else None))
        return Popularity(purchases, set(map(str, self.index.destination)), now=now)


class _LocalSpace:
    """Ma trận vector nhỏ chỉ gồm các unit request này cần (event + ứng viên top-K), đánh số lại 0..m-1.

    Hàm domain (`build_profile`, `score_candidates`, `mmr_select`, `explain`) nhận `E` tra theo số unit;
    đưa chúng không gian cục bộ này thay cho toàn bộ catalog, nên công thức giữ nguyên.
    """

    def __init__(self, index: UnitIndex, dimension: int):
        self.index, self.dimension = index, dimension
        self.glob: list[int] = []
        self.local: dict[int, int] = {}
        self.rows: list[np.ndarray] = []

    def add(self, unit: int, vector: np.ndarray) -> int:
        if unit not in self.local:
            self.local[unit] = len(self.glob)
            self.glob.append(unit)
            self.rows.append(np.asarray(vector, dtype=np.float32))
        return self.local[unit]

    @property
    def E(self) -> np.ndarray:
        return np.vstack(self.rows) if self.rows else np.zeros((0, self.dimension), dtype=np.float32)

    @property
    def taxonomy(self) -> np.ndarray:
        return self.index.taxonomy[self.glob] if self.glob else np.array([], dtype=str)

    @property
    def destination(self) -> np.ndarray:
        return self.index.destination[self.glob] if self.glob else np.array([], dtype=str)


@dataclass
class RecommendForUser:
    index: UnitIndex
    vectors: VectorSearchPort
    cdp: CdpHistoryReader
    popularity: Popularity | None = None
    candidate_k: int = 200
    popular_k: int = 50   # ứng viên thêm theo popularity: W_POP đủ lớn để món phổ biến xa profile vẫn lọt top
    # Giới hạn món mỗi taxonomy sau MMR (spec §4.7, production = MAX_PER_VERTICAL). `None` chỉ dành cho harness đánh giá
    # offline (`src/evaluation/recsys_bench`, mode eval: k = 20 cần đủ 20 món); main.py không đổi giá trị này.
    max_per_vertical: int | None = MAX_PER_VERTICAL

    def __call__(self, cdp_user_id: str | None, k: int = 5, now: datetime | None = None,
                 events: list[dict] | None = None, destination: str | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        t0 = now.timestamp()
        idx = self.index
        base = {"generatedAt": now.isoformat(), "modelVersion": idx.model_version}
        try:
            raw = events if events is not None else (self.cdp.events_for_user(cdp_user_id) if cdp_user_id else [])
        except CdpUnavailableError as exc:
            # CDP sập/timeout vẫn trả 200 popular; chỉ lỗi CDP mới log WARNING, không log cdp_user_id
            # (hop-dong-tich-hop-cdp.md §6, §8).
            log_event(logger, "recsys.fallback", "WARNING", reason="cdp_unavailable",
                      message=f"recommend.cdp_unavailable reason={type(exc.__cause__ or exc).__name__}; fallback popular")
            return {**base, **self._cold_start(k, now, destination)}

        units = {e.get("productId") or "": idx.resolve(e.get("productId") or "") for e in raw}
        stored = self.vectors.vectors(sorted({idx.units[i].product_id for i in units.values() if i is not None}))
        space = _LocalSpace(idx, self.vectors.dimension)
        resolved = []
        for e in raw:
            i = units[e.get("productId") or ""]
            if i is None or idx.units[i].product_id not in stored:  # ngoài catalog hoặc chưa index
                continue
            resolved.append(ResolvedEvent(unit=space.add(i, stored[idx.units[i].product_id]), event_name=e["eventName"],
                                          days_ago=max(0.0, (t0 - _ts(e["timestamp"])) / 86400),
                                          trip_id=e.get("eventGroupId") or f"_solo_{e['productId']}", product_id=e["productId"],
                                          using_date=_using_date(e.get("usingDate"))))
        # trip đang mở xét theo usingDate (FR-REC-02, 01/10/2026): "hôm nay" theo giờ Việt Nam vì usingDate là ngày địa phương
        profile = build_profile(resolved, space.E, space.taxonomy, space.destination, today=local_today(now))

        if not profile.trips:
            return {**base, **self._cold_start(k, now, destination)}

        # candidate mask
        if profile.active_trip is not None:
            t = profile.active_trip
            dest, done = destination or t.destination, t.purchased_taxonomies
            m = idx.mask(destination=dest, only_recommendable=True) & ~np.isin(idx.taxonomy, list(done))
            if not m.any() and destination is None:
                m = idx.mask(only_recommendable=True) & ~np.isin(idx.taxonomy, list(done))
        else:
            dest, done = destination, set()
            m = idx.mask(destination=dest, only_recommendable=True)
        for u in profile.bought_units:
            m[space.glob[u]] = False

        # Top-K ứng viên quanh cả vector ngắn hạn lẫn dài hạn: score_candidates trộn cả hai.
        allowed = idx.allowed_ids(m)
        u_short = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
        queries = [u_short] if profile.active_trip is None else [u_short, profile.u_long]
        cand: list[int] = []
        for q in queries:
            for h in self.vectors.near_vector(q, allowed, self.candidate_k, with_vectors=True):
                if h.product_id in idx.idx and h.vector is not None:
                    local = space.add(idx.idx[h.product_id], h.vector)
                    if local not in cand:
                        cand.append(local)

        pop_global = self.popularity.unit_scores(dest) if self.popularity else {}
        popular = [g for g in sorted(pop_global, key=lambda g: -pop_global[g]) if m[g]][: self.popular_k]
        fetched = self.vectors.vectors([idx.units[g].product_id for g in popular if g not in space.local])
        for g in popular:
            vec = fetched.get(idx.units[g].product_id)
            if g in space.local or vec is not None:
                local = space.local[g] if g in space.local else space.add(g, vec)
                if local not in cand:
                    cand.append(local)
        pop = np.array([pop_global.get(g, 0.0) for g in space.glob], dtype=np.float32)
        E = space.E
        score, _ = score_candidates(profile, E, pop)
        cand = sorted(cand, key=lambda j: -score[j])[: self.candidate_k]
        chosen = mmr_select(score, E, cand, space.taxonomy, k, max_per_vertical=self.max_per_vertical)
        if not chosen:
            return {**base, **self._cold_start(k, now, destination)}

        recs = []
        for rank, j in enumerate(chosen, 1):
            because = [{"productId": b["productId"], "productName": idx.units[space.glob[b["unit"]]].name, "event": b["event"],
                        "daysAgo": int(b["daysAgo"]), "contribution": b["contribution"]} for b in explain(profile, j, E)]
            recs.append(hit(idx, space.glob[j], score[j], rank=rank, because=because))
        from collections import Counter
        return {**base, "strategy": profile.strategy, "destination": dest,
                "nextVertical": str(Counter(idx.taxonomy[space.glob[j]] for j in chosen).most_common(1)[0][0]) if chosen else None,
                "recommendations": recs, "sections": [],
                "diagnostics": {"eventsUsed": profile.n_events, "coldStart": profile.n_events < 3,
                                "excludedVerticals": sorted(map(str, done)), "trips": len(profile.trips)}}

    # ---- khách mới: điểm đến của tháng + theo mùa; because[] rỗng, lý do ở section.reason
    def _cold_start(self, k: int, now: datetime, destination: str | None = None) -> dict:
        idx = self.index
        sections, flat, used = [], [], set()
        if destination:
            flat = [{**p, "rank": rank} for rank, p in enumerate(self._top_products(destination, k), 1)]
        elif self.popularity:
            groups = [("Điểm đến được đặt nhiều tháng %d" % now.month, self.popularity.top_destinations_month(k=3)),
                      ("Điểm đến phổ biến theo mùa", self.popularity.seasonal_destinations(k=3))]
            seen = set()
            for title, dests in groups:
                for d in dests:
                    if d["destination"] in seen:
                        continue
                    seen.add(d["destination"])
                    sections.append({"title": title, **d, "products": self._top_products(d["destination"], k)})
            for sec in sections:
                for p in sec["products"]:
                    if p["productId"] not in used and len(flat) < k:
                        used.add(p["productId"]); flat.append({**p, "rank": len(flat) + 1})
        else:  # chưa có event → xếp theo reviewCount
            m = idx.mask(only_recommendable=True)
            order = sorted((i for i in range(len(idx.units)) if m[i]), key=lambda i: -(idx.units[i].attributes.get("reviewCount") or 0))
            flat = [hit(idx, i, 0.0, rank=r, because=[]) for r, i in enumerate(order[:k], 1)]
        return {"strategy": "popular", "destination": destination, "nextVertical": None, "sections": sections, "recommendations": flat,
                "diagnostics": {"eventsUsed": 0, "coldStart": True, "excludedVerticals": [],
                                "popularitySource": "events" if self.popularity else "reviewCount"}}

    def _top_products(self, destination: str, k: int) -> list[dict]:
        idx = self.index
        scores = self.popularity.unit_scores(destination) if self.popularity else {}
        m = idx.mask(destination=destination, only_recommendable=True)
        ranked = sorted((i for i in range(len(idx.units)) if m[i]),
                        key=lambda i: (-scores.get(i, 0.0), -(idx.units[i].attributes.get("reviewCount") or 0)))
        return [hit(idx, i, scores.get(i, 0.0), because=[]) for i in ranked[:k]]
