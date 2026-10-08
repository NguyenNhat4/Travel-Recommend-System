"""Popularity làm mượt `pop_h` (bậc N1 của plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §3.3; mục [C7] của spec
search-recommendation, người dùng đưa vào phạm vi 09/10):

    n_i     = Σ_{purchase p của i, booked_at ∈ (now − 730 d, now]} 2^(−(now − booked_at) / H_POP)
    m_g     = trung bình n_j trên unit recommendable j cùng nhóm g(i) = (điểm đến, taxonomy)
    pop_h(i) = (n_i + α·m_g) / max_j (n_j + α·m_j)

`box=W` thay suy giảm bằng hộp W ngày (trọng số 1 trong `[now − W, now]`) — với `box=90, alpha=0` cho đúng dict của
`Popularity.unit_scores` production (kiểm parity).

Cài bằng cách thay `Popularity.unit_scores` ở mức class trong tiến trình đo; chỉ trả `pop_h` khi `state["ctx"]` thuộc `scope`
(mặc định chỉ nhánh không có chuyến mở), còn lại gọi bản production — nên cold start, listing, suggest không đổi.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from src.backend.app.domain.recommendation.popularity import Popularity

WINDOW_DAYS = 730


def smoothed_scores(pop: Popularity, index, destination: str | None, h_pop: float | None, alpha: float,
                    box: float | None = None, window_days: float = WINDOW_DAYS) -> dict[int, float]:
    t0 = pop.now.timestamp()
    n: dict[int, float] = defaultdict(float)
    for x in pop.p:
        if destination is not None and x.destination != destination:
            continue
        age = (t0 - x.booked_at) / 86400
        if box is not None:
            if 0 <= age <= box:
                n[x.unit] += 1.0
        elif 0 <= age < window_days:
            n[x.unit] += 2 ** (-age / h_pop)
    if alpha:
        rec = index.recommendable & index.available
        if destination is not None:
            rec = rec & (index.destination == destination)
        units = np.flatnonzero(rec)
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for j in units:
            groups[(str(index.destination[j]), str(index.taxonomy[j]))].append(int(j))
        mean = {g: sum(n.get(j, 0.0) for j in js) / len(js) for g, js in groups.items()}
        raw = {int(j): n.get(int(j), 0.0) + alpha * mean[(str(index.destination[j]), str(index.taxonomy[j]))] for j in units}
        raw.update({u: v for u, v in n.items() if u not in raw})       # unit đã mua nhưng nay không recommendable
        raw = {u: v for u, v in raw.items() if v > 0}
    else:
        raw = dict(n)
    mx = max(raw.values(), default=1.0) or 1.0
    return {u: v / mx for u, v in raw.items()}


def install(index, state: dict, h_pop: float | None, alpha: float, *, box: float | None = None,
            scope: str = "none"):
    """Trả hàm `restore()`. `scope`: "none" = chỉ khi không có chuyến mở; "global" = mọi nhánh có lịch sử (arm D-popGlobal)."""
    orig = Popularity.unit_scores
    cache: dict = {}
    ctxs = {"none"} if scope == "none" else {"none", "booked", "session"}

    def unit_scores(self, destination=None, window_days=90):
        if state.get("ctx") not in ctxs:
            return orig(self, destination, window_days)
        key = (id(self), self.now, len(self.p), destination)
        if key not in cache:
            if len(cache) > 256:
                cache.clear()
            cache[key] = smoothed_scores(self, index, destination, h_pop, alpha, box)
        return cache[key]

    Popularity.unit_scores = unit_scores

    def restore():
        Popularity.unit_scores = orig

    return restore
