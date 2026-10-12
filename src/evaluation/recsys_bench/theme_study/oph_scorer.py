"""Hàm điểm OPH-L (plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §3.3), cùng chữ ký `score_candidates(profile, E, pop)`:

    có chuyến mở : s = 0,70·cos_short + 0,15·pop + 0,15·cos_long  − W_ORIGIN·mis  + W_CART·cart     (cos thô, pop production)
    không chuyến : s = (1 − w_pop)·cal(cos_long) + w_pop·pop_N     (F14c: w_pop = 0,35), route sai origin bị MASK

`cal(c) = clip((c − Q_LOW) / (Q_HIGH − Q_LOW), 0, 1)` với Q ghim theo lane B (0,8529 / 0,9387). `pop_N` là mảng `pop` engine
truyền vào — bằng `pop_h` khi `pop_smooth` được cài. `none_scorer="F0"` giữ công thức production ở nhánh không chuyến.

Mọi công tắc tắt ⇒ trả đúng `score_candidates` production (parity V0p). Đọc taxonomy / origin của ứng viên qua `state["space"]`
(đối tượng `_LocalSpace` của request — không gian lớn dần nên phải đọc lúc chấm điểm, xem `dest_diversity.install`).
"""
from __future__ import annotations

import numpy as np

from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.evaluation.recsys_bench.theme_study.origin import infer_origin, mismatch
from src.evaluation.recsys_bench.theme_study.step2_scorers import engine_origin_mask

#: Ngưỡng hiệu chỉnh cos ghim theo plan giai đoạn lane B (`docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md`).
Q_LOW, Q_HIGH = 0.8529, 0.9387
MASKED = -np.inf
W_LONG_NEXT = 0.15     # hạng u_long của F14c (`W_NEXT_LONG` của đề xuất [B])
CART_DAYS = 30.0


def cart_units(state: dict, profile, hint: dict | None = None) -> set[int]:
    """Unit cục bộ có add_to_cart trong `CART_DAYS` ngày và chưa mua; `hint["target_unit"]` (trần Z-cart) thêm món đích."""
    out = {e.unit for e in state.get("events", ()) if e.event_name == "add_to_cart" and e.days_ago <= CART_DAYS
           and e.unit not in profile.bought_units}
    g = (hint or {}).get("target_unit")
    space = state.get("space")
    if g is not None and space is not None and g in space.local:
        out.add(space.local[g])
    return out


def make_scorer(state: dict, index, *, none_scorer: str = "F0", w_pop_none: float = 0.35,
                w_pop_by_segment: dict | None = None, origin_mode: str | None = None, w_origin: float = 0.30,
                w_cart: float = 0.0, q: tuple[float, float] = (Q_LOW, Q_HIGH), hint: dict | None = None,
                origin_target: bool = False, cart_target: bool = False):
    span = max(q[1] - q[0], 1e-6)
    w_pop_by_segment = w_pop_by_segment or {}

    def score(profile, E, pop, context=None, next_trip_scoring=False):
        # `context` của engine (từ 09/10 engine đã có O1 điểm xuất phát): chuyển xuống `prod_score` để `B0+oph` = engine
        space = state.get("space")
        glob = list(space.glob) if space is not None else []
        origin = None
        if origin_mode is not None and glob:
            origin, ounit = infer_origin(state.get("events", ()), glob, index)
            g = (hint or {}).get("target_unit")
            if origin_target and g is not None and str(index.taxonomy[g]) == "flight" and index.attrs.origin_city[g]:
                origin, ounit = str(index.attrs.origin_city[g]), g
            state["origin"], state["origin_unit"] = origin, ounit
        if profile.active_trip is not None:
            s, u = prod_score(profile, E, pop, context, next_trip_scoring)
            if origin is not None:
                mis = mismatch(glob, index, origin)
                s = s - w_origin * mis if origin_mode == "pen" else np.where(mis, MASKED, s)
            if w_cart:
                cart = cart_units(state, profile, hint if cart_target else None)
                if cart:
                    s = s + w_cart * np.isin(np.arange(len(s)), list(cart))
            return s, u
        if none_scorer == "F0":
            s, u = prod_score(profile, E, pop, context, next_trip_scoring)
        else:
            u = profile.u_long
            wp = w_pop_by_segment.get(state.get("segment_cfg"), w_pop_none)
            sem = np.clip((E @ u - q[0]) / span, 0.0, 1.0)
            # dạng ba hạng của đề xuất [B] (0,50·s + 0,35·pop + 0,15·s) — cùng phép tính với engine PR-B để parity khớp từng bit
            ws, wl = 1.0 - wp - W_LONG_NEXT, W_LONG_NEXT
            s = ws * sem + wp * np.asarray(pop, dtype=np.float32) + wl * sem
            s = engine_origin_mask(s, context)                 # luật engine 09/10 cho nhánh không chuyến mở
        if origin is not None:
            s = np.where(mismatch(glob, index, origin), MASKED, s)
        return s, u

    return score
