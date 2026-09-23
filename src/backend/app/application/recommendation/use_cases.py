from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from src.backend.app.application.ports import CdpHistoryReader, UnitIndex
from src.backend.app.application.search import hit
from src.backend.app.domain.recommendation import Popularity, Purchase, ResolvedEvent, build_profile, explain, mmr_select, score_candidates


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


@dataclass
class RecommendForUser:
    index: UnitIndex
    cdp: CdpHistoryReader
    popularity: Popularity | None = None
    candidate_k: int = 200

    def __call__(self, cdp_user_id: str | None, k: int = 5, now: datetime | None = None, events: list[dict] | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        t0 = now.timestamp()
        raw = events if events is not None else (self.cdp.events_for_user(cdp_user_id) if cdp_user_id else [])

        resolved = []
        for e in raw:
            i = self.index.resolve(e.get("productId") or "")
            if i is None:
                continue
            resolved.append(ResolvedEvent(unit=i, event_name=e["eventName"], days_ago=max(0.0, (t0 - _ts(e["timestamp"])) / 86400),
                                          trip_id=e.get("eventGroupId") or f"_solo_{e['productId']}", product_id=e["productId"]))
        idx = self.index
        profile = build_profile(resolved, idx.E, idx.taxonomy, idx.destination)
        base = {"generatedAt": now.isoformat(), "modelVersion": idx.model_version}

        if not profile.trips:
            return {**base, **self._cold_start(k, now)}

        # candidate mask
        if profile.active_trip is not None:
            t = profile.active_trip
            dest, done = t.destination, t.purchased_taxonomies
            m = idx.mask(destination=dest, only_recommendable=True) & ~np.isin(idx.taxonomy, list(done))
            if not m.any():
                m = idx.mask(only_recommendable=True) & ~np.isin(idx.taxonomy, list(done))
        else:
            dest, done = None, set()
            m = idx.mask(only_recommendable=True)
        for u in profile.bought_units:
            m[u] = False

        pop = np.zeros(len(idx.units), dtype=np.float32)
        if self.popularity:
            for u, s in self.popularity.unit_scores(dest).items():
                pop[u] = s
        score, _ = score_candidates(profile, idx.E, pop)
        cand = [i for i in np.argsort(-score) if m[i]][: self.candidate_k]
        chosen = mmr_select(score, idx.E, cand, idx.taxonomy, k)

        recs = []
        for rank, i in enumerate(chosen, 1):
            because = [{"productId": b["productId"], "productName": idx.units[b["unit"]].name, "event": b["event"],
                        "daysAgo": b["daysAgo"], "contribution": b["contribution"]} for b in explain(profile, i, idx.E)]
            recs.append(hit(idx, i, score[i], rank=rank, because=because))
        from collections import Counter
        return {**base, "strategy": profile.strategy, "destination": dest,
                "nextVertical": str(Counter(idx.taxonomy[i] for i in chosen).most_common(1)[0][0]) if chosen else None,
                "recommendations": recs, "sections": [],
                "diagnostics": {"eventsUsed": profile.n_events, "coldStart": profile.n_events < 3,
                                "excludedVerticals": sorted(map(str, done)), "trips": len(profile.trips)}}

    # ---- khách mới: điểm đến của tháng + theo mùa; because[] rỗng, lý do ở section.reason
    def _cold_start(self, k: int, now: datetime) -> dict:
        idx = self.index
        sections, flat, used = [], [], set()
        if self.popularity:
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
        return {"strategy": "popular", "destination": None, "nextVertical": None, "sections": sections, "recommendations": flat,
                "diagnostics": {"eventsUsed": 0, "coldStart": True, "excludedVerticals": [],
                                "popularitySource": "events" if self.popularity else "reviewCount"}}

    def _top_products(self, destination: str, k: int) -> list[dict]:
        idx = self.index
        scores = self.popularity.unit_scores(destination) if self.popularity else {}
        m = idx.mask(destination=destination, only_recommendable=True)
        ranked = sorted((i for i in range(len(idx.units)) if m[i]),
                        key=lambda i: (-scores.get(i, 0.0), -(idx.units[i].attributes.get("reviewCount") or 0)))
        return [hit(idx, i, scores.get(i, 0.0), because=[]) for i in ranked[:k]]
