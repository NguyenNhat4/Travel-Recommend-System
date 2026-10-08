"""Bước 2 (08/10/2026): các cách phối hợp điểm để so với F7, đều chỉ áp khi KHÔNG có chuyến mở (có chuyến mở = production).

- F13a / F13b  centering: trừ vector trung bình catalog khỏi vector sản phẩm và vector khách rồi chuẩn hoá lại, tính cos trên đó;
               trọng số 0,7/0,15/0,15 (a) hoặc 0,55/0,30/0,15 (b).
- F14          calibration phân vị cố định: semantic = clip((cos − q_low) / (q_high − q_low), 0, 1), q lấy từ tập calibration
               RIÊNG (khách giả lập seed khác bộ đo), không tính lại theo request; trọng số 0,55/0,30/0,15.
"""
from __future__ import annotations

import numpy as np

from src.backend.app.domain.recommendation import score_candidates as prod_score


def _unit(x):
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.where(n == 0, 1, n)


def make_centered(mean_vec, ws, wp, wl):
    m = np.asarray(mean_vec, dtype=np.float32)

    def score(profile, E, pop):
        if profile.active_trip is not None:
            return prod_score(profile, E, pop)
        u = profile.u_long
        Ec, uc = _unit(E - m), _unit(u - m)
        c = Ec @ uc                                   # không chuyến mở: u_short = u_long
        return ws * c + wp * pop + wl * c, u
    return score


def make_quantile(q_low, q_high, ws=0.55, wp=0.30, wl=0.15):
    span = max(q_high - q_low, 1e-6)

    def score(profile, E, pop):
        if profile.active_trip is not None:
            return prod_score(profile, E, pop)
        u = profile.u_long
        s = np.clip((E @ u - q_low) / span, 0.0, 1.0)
        return ws * s + wp * pop + wl * s, u
    return score
