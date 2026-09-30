"""Các "arm" được so trên cùng split: baseline và engine production. Mỗi arm trả danh sách productId đã xếp hạng.

Day 1 có `random` (baseline bắt buộc, handbook §12) và `engine`. Hai baseline còn lại (most-popular theo cửa sổ thời
gian, most-popular-in-destination) thuộc Day 2 của lịch.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .engine import OfflineEngine


@dataclass
class Ranked:
    product_ids: list[str]
    latency_ms: float
    meta: dict = field(default_factory=dict)


class RandomArm:
    """Bốc ngẫu nhiên trong đúng tập ứng viên của engine (`recommendable` và còn chỗ), tất định theo (seed, khách)."""

    family = "random"

    def __init__(self, index: UnitIndex, seed: int):
        self.seed, self.key = seed, f"random-s{seed}"
        self._ids = [index.units[i].product_id for i in np.flatnonzero(index.mask(only_recommendable=True))]

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        rng = np.random.default_rng([self.seed, zlib.crc32(cdp_user_id.encode("utf-8"))])
        picks = rng.choice(len(self._ids), size=min(k, len(self._ids)), replace=False) if self._ids else []
        return Ranked([self._ids[i] for i in picks], (perf_counter() - started) * 1000)


class EngineArm:
    """Engine production (`RecommendForUser`) qua `OfflineEngine`."""

    family = key = "engine"

    def __init__(self, engine: OfflineEngine):
        self.engine = engine

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        response = self.engine.recommend(cdp_user_id, as_of, k, events)
        latency = (perf_counter() - started) * 1000
        diagnostics = response.get("diagnostics") or {}
        return Ranked([r["productId"] for r in response.get("recommendations", [])], latency, {
            "strategy": response.get("strategy"), "destination": response.get("destination"),
            "nextVertical": response.get("nextVertical"), "eventsUsed": diagnostics.get("eventsUsed"),
            "coldStart": diagnostics.get("coldStart"), "excludedVerticals": diagnostics.get("excludedVerticals"),
        })
