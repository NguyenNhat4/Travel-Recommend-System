"""Giới hạn số món mỗi **điểm đến** khi khách không có chuyến mở — ứng viên giảm thiệt hại cho gate G2 (08/10/2026).

Vì sao: đo trên khách giả lập **có sở thích thật** cho thấy công thức bám sở thích (F7 / F14 / F13a) thắng production ở
việc đoán đúng *món* của chuyến kế tiếp (0,0 → 0,011–0,0125) nhưng thua rất nặng ở việc *điểm đến* của chuyến kế tiếp có
nằm trong danh sách hay không (0,47 → 0,13–0,24). Lý do: điểm gần `u_long` nhất dồn vào ít điểm đến, còn production rải
theo độ phổ biến nên phủ đúng các điểm đến lớn. Đó là vấn đề **độ phủ điểm đến**, không phải vấn đề trọng số — vặn `W_POP`
không sửa được (xem bảng quét pop trong `eval-2026-10-08-recsys-so-thich-ci.md` §3.4).

Cách sửa thử: giữ nguyên công thức điểm, chỉ thêm một giới hạn cứng "tối đa `cap` món mỗi điểm đến" vào bước MMR, và
**chỉ khi không có chuyến mở** (có chuyến mở thì mọi món vốn cùng một điểm đến X — giới hạn này sẽ phá nhánh đó).

Dùng trong tiến trình đo, không sửa engine:

    import src.backend.app.application.recommendation.use_cases as UC
    bp, mmr = install(make_build_profile(**PROFILES["P2_confidence"]), cap=1)
    UC.build_profile, UC.mmr_select = bp, mmr
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from src.backend.app.domain.recommendation import mmr_select as prod_mmr
from src.backend.app.domain.recommendation import profile as _profile


def install(build_profile, cap: int = 1):
    """Trả (build_profile đã bọc, mmr_select đã bọc, _LocalSpace đã bọc) dùng chung state của request hiện tại.

    Chi tiết đáng lưu: `_LocalSpace` của `use_cases` **lớn dần** trong một request — `build_profile` được gọi khi không
    gian chỉ có các unit của event (use_cases.py dòng 120), rồi ứng viên Weaviate và món phổ biến mới được thêm vào, nên
    `mmr_select` nhận hệ chỉ số dài hơn. Chụp `space.destination` lúc `build_profile` sẽ ra mảng **cũ và quá ngắn**
    (IndexError). Vì vậy phải giữ chính đối tượng `space` rồi đọc `space.destination` lúc MMR.

    Engine xử lý tuần tự từng request nên một ô state là đủ; không dùng được nếu chạy song song trong một tiến trình."""
    state: dict = {}

    def bp(events, E, taxonomy, destination, today=None):
        p = build_profile(events, E, taxonomy, destination, today)
        state["open"] = p.active_trip is not None
        return p

    def mmr(score, E, candidates, taxonomy, k, max_per_vertical=None):
        space = state.get("space")
        dest = space.destination if space is not None else None
        if state.get("open") or dest is None or cap is None:
            return prod_mmr(score, E, candidates, taxonomy, k, max_per_vertical=max_per_vertical)
        chosen: list[int] = []
        per_vertical: Counter = Counter()
        per_dest: Counter = Counter()
        cand = list(candidates)
        while cand and len(chosen) < k:
            best, best_val = None, -1e9
            for i in cand:
                if max_per_vertical is not None and per_vertical[str(taxonomy[i])] >= max_per_vertical:
                    continue
                if per_dest[str(dest[i])] >= cap:
                    continue
                div = max((float(E[i] @ E[j]) for j in chosen), default=0.0)
                lam = _profile.MMR_LAMBDA                 # đọc lúc gọi (plan 2026-10-09 §3.3): grid λ phải tới được nhánh này
                val = lam * float(score[i]) - (1 - lam) * div
                if val > best_val:
                    best, best_val = i, val
            if best is None:
                break
            chosen.append(best)
            per_vertical[str(taxonomy[best])] += 1
            per_dest[str(dest[best])] += 1
            cand.remove(best)
        return chosen

    import src.backend.app.application.recommendation.use_cases as UC

    class TrackedSpace(UC._LocalSpace):                       # noqa: SLF001 - đo lường, không phải code app
        """Giữ lại `space` của request đang chạy để `mmr` đọc `space.destination` ở đúng độ dài."""

        def __init__(self, index, dimension):
            super().__init__(index, dimension)
            state["space"] = self

    return bp, mmr, TrackedSpace
