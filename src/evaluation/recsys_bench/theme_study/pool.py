"""Đưa món trong giỏ vào pool ứng viên (bậc O5 / trần Z-cart, plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §3.3).

`use_cases.RecommendForUser` dựng pool từ `near_vector` + món phổ biến; biến `cand` là cục bộ nên không monkeypatch được. Bọc
`VectorSearchPort`: mỗi lần `near_vector` khi khách đang có chuyến mở, nối thêm hit cho unit có add_to_cart ≤ 30 ngày chưa
mua, **chỉ khi unit nằm trong `allowed`** (mask của request: điểm đến, taxonomy đã mua, món đã mua). Không có giỏ hoặc không có
chuyến mở thì trả đúng kết quả gốc (parity khi tắt).
"""
from __future__ import annotations

from src.backend.app.application.ports.vector_search import VectorHit
from src.evaluation.recsys_bench.theme_study.oph_scorer import CART_DAYS

OPEN = {"booked", "session"}


class CartPool:
    def __init__(self, inner, index, state: dict, hint: dict | None = None):
        self.inner, self.index, self.state, self.hint = inner, index, state, hint
        self.dimension = inner.dimension

    def __getattr__(self, name):                       # ids, E, source… của NumpyVectorSearch
        return getattr(self.inner, name)

    def vectors(self, product_ids):
        return self.inner.vectors(product_ids)

    def near_vector(self, vector, allowed, limit, *, with_vectors=False):
        hits = self.inner.near_vector(vector, allowed, limit, with_vectors=with_vectors)
        st = self.state
        space = st.get("space")
        if st.get("ctx") not in OPEN or space is None:
            return hits
        bought = st["profile"].bought_units if st.get("profile") is not None else set()
        pids = []
        for e in st.get("events", ()):
            if e.event_name == "add_to_cart" and e.days_ago <= CART_DAYS and e.unit not in bought:
                pid = self.index.units[space.glob[e.unit]].product_id
                if pid not in pids:
                    pids.append(pid)
        g = (self.hint or {}).get("target_unit")
        if g is not None:                               # `bought` là chỉ số cục bộ; món đã mua bị `allowed` chặn ở dưới
            pid = self.index.units[g].product_id
            if pid not in pids:
                pids.append(pid)
        allow = None if allowed is None else set(allowed)
        have = {h.product_id for h in hits}
        extra = [p for p in pids if p not in have and (allow is None or p in allow)]
        if not extra:
            return hits
        vecs = self.inner.vectors(extra)
        return hits + [VectorHit(product_id=p, score=0.0, vector=vecs[p] if with_vectors else None)
                       for p in extra if p in vecs]
