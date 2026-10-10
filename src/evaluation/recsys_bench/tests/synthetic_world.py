"""World tổng hợp cho test registry (không DB): 60 search unit (3 điểm đến × 5 taxonomy × 4), vector 16-d đơn vị seed cố định, 12 khách
với trip mở / đã đóng / view lẻ không gid. Dùng với `OfflineEngine(candidate_k=10, popular_k=3)` để pool của engine **bị cắt thật**
(mask một điểm đến ≈ 12–16 unit > 10; không trip mở ≈ 54 unit) — fixture `world` 11 sản phẩm không bao giờ cắt pool."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.vectors.numpy_search import NumpyVectorSearch

DESTS = ("Nha Trang", "Đà Nẵng", "Phú Quốc")
TAXOS = ("hotel", "flight", "attraction", "combo", "golf")
AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def build_world(seed: int = 7, per_cell: int = 4, dim: int = 16) -> tuple[UnitIndex, NumpyVectorSearch]:
    rng = np.random.default_rng(seed)
    units = [Product(f"{t[:2]}-{d[:2]}-{j}", f"{t} {d} {j}", t, d, "", unit_price=100.0, available=True)
             for d in DESTS for t in TAXOS for j in range(per_cell)]
    n = len(units)
    available = np.ones(n, dtype=bool)
    available[rng.choice(n, 3, replace=False)] = False
    recommendable = np.ones(n, dtype=bool)
    recommendable[rng.choice(n, 3, replace=False)] = False
    index = UnitIndex(units=units, taxonomy=np.array([p.taxonomy for p in units]), destination=np.array([p.destination for p in units]),
                      available=available, recommendable=recommendable, parent_of={}, model_version="synthetic")
    E = rng.normal(size=(n, dim)).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    return index, NumpyVectorSearch([p.product_id for p in units], E)


def build_events(index: UnitIndex, seed: int = 11, n_users: int = 12, as_of: datetime = AS_OF) -> list[dict]:
    """Mỗi khách 2–4 trip; mỗi trip 1–3 purchase cùng điểm đến (taxonomy khác nhau, cách nhau 1 giờ); 40 % trip có một view lẻ không
    gid một ngày trước; trip cuối của 2/3 khách có `usingDate` sau as_of (mở), còn lại `usingDate` = ngày mua + 5–30."""
    rng = np.random.default_rng(seed)
    by_dest = {d: [p for p in index.units if p.destination == d] for d in DESTS}
    events: list[dict] = []
    for u in range(n_users):
        user = f"S{u:03d}"
        n_trips = int(rng.integers(2, 5))
        days_back = sorted(rng.integers(5, 700, size=n_trips).tolist(), reverse=True)
        for ti, back in enumerate(days_back):
            dest = DESTS[int(rng.integers(0, len(DESTS)))]
            gid = f"G{u:03d}{ti}"
            t0 = as_of - timedelta(days=int(back), hours=int(rng.integers(0, 20)))
            taxos = [str(t) for t in rng.permutation(TAXOS)[: int(rng.integers(1, 4))]]
            open_trip = ti == n_trips - 1 and u % 3 != 0
            for k, taxo in enumerate(taxos):
                options = [p for p in by_dest[dest] if p.taxonomy == taxo]
                p = options[int(rng.integers(0, len(options)))]
                ts = t0 + timedelta(hours=k)
                using = (as_of + timedelta(days=int(rng.integers(3, 30)))).date() if open_trip else (ts + timedelta(days=int(rng.integers(5, 30)))).date()
                events.append({"cdpUserId": user, "eventName": "purchase", "productId": p.product_id, "timestamp": _iso(ts),
                               "eventGroupId": gid, "usingDate": using.isoformat()})
            if rng.random() < 0.4:
                p = by_dest[dest][int(rng.integers(0, len(by_dest[dest])))]
                events.append({"cdpUserId": user, "eventName": "product_view", "productId": p.product_id,
                               "timestamp": _iso(t0 - timedelta(days=1)), "eventGroupId": None, "usingDate": None})
    return events
