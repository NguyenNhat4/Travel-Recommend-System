"""Bước 2 (08/10/2026): các cách phối hợp điểm để so với F7, đều chỉ áp khi KHÔNG có chuyến mở (có chuyến mở = production).

- F13a / F13b  centering: trừ vector trung bình catalog khỏi vector sản phẩm và vector khách rồi chuẩn hoá lại, tính cos trên đó;
               trọng số 0,7/0,15/0,15 (a) hoặc 0,55/0,30/0,15 (b).
- F14          calibration phân vị cố định: semantic = clip((cos − q_low) / (q_high − q_low), 0, 1), q lấy từ tập calibration
               RIÊNG (khách giả lập seed khác bộ đo), không tính lại theo request; trọng số 0,55/0,30/0,15.
"""
from __future__ import annotations

import random

import numpy as np

from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.backend.app.domain.recommendation.profile import origin_mismatch


def engine_origin_mask(score, context):
    """Luật của engine (FR-REC-04, 09/10) cho nhánh không có chuyến mở: route bay sai điểm xuất phát bị loại (−∞). Công thức
    thử nghiệm ở nhánh này tự tính điểm nên phải áp lại để vẫn là "engine + công thức mới"."""
    if context is None or context.origin is None:
        return score
    return np.where(origin_mismatch(context), -np.inf, score)


def _unit(x):
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.where(n == 0, 1, n)


def make_centered(mean_vec, ws, wp, wl):
    m = np.asarray(mean_vec, dtype=np.float32)

    def score(profile, E, pop, context=None):
        if profile.active_trip is not None:
            return prod_score(profile, E, pop, context)
        u = profile.u_long
        Ec, uc = _unit(E - m), _unit(u - m)
        c = Ec @ uc                                   # không chuyến mở: u_short = u_long
        return engine_origin_mask(ws * c + wp * pop + wl * c, context), u
    return score


def make_quantile(q_low, q_high, ws=0.55, wp=0.30, wl=0.15):
    span = max(q_high - q_low, 1e-6)

    def score(profile, E, pop, context=None):
        if profile.active_trip is not None:
            return prod_score(profile, E, pop, context)
        u = profile.u_long
        s = np.clip((E @ u - q_low) / span, 0.0, 1.0)
        return engine_origin_mask(ws * s + wp * pop + wl * s, context), u
    return score


def calibrate_quantile(eng4, world, build_profile, as_of, seed=99, n_per_theme=40, lo=10, hi=99) -> dict:
    """Ngưỡng `q_low` / `q_high` của F14, đo trên tập calibration RIÊNG: khách giả lập `between` ở `seed` (phải khác seed
    của bộ đo, nếu không F14 được hiệu chuẩn trên chính tập nó bị đánh giá).

    Lấy phân vị của `E @ u_long` trên **đúng không gian ứng viên** mà engine chấm cho từng request (không phải trên toàn
    catalog), nên ngưỡng gắn với cả model embedding, `TEXT_BUILDER_VERSION` và tầng lấy ứng viên — đổi bất kỳ thứ nào
    cũng phải calibrate lại (plan WP5.3). Tách khỏi `eval_profile.py` 08/10 để `eval_slots.py` dùng cùng một bản."""
    import src.backend.app.application.recommendation.use_cases as UC
    from src.backend.app.domain.recommendation import build_profile as prod_build
    from src.evaluation.recsys_bench.theme_study import theme_exp as TE

    vals: list = []

    def rec_score(profile, E, pop, context=None):
        if profile.active_trip is None:
            vals.append(np.asarray(E @ profile.u_long, dtype=np.float64))
        return prod_score(profile, E, pop, context)

    UC.build_profile, UC.score_candidates = build_profile, rec_score
    try:
        rng = random.Random(seed)
        for th in ("beach", "mountain", "city"):
            for n in range(n_per_theme):
                u = TE.make_user(world, rng, f"CAL-{th[0]}{n:04d}", th, "between")
                eng4.recommend(u["uid"], as_of, 4, u["events"])
    finally:
        UC.build_profile, UC.score_candidates = prod_build, prod_score
    allv = np.concatenate(vals)
    # Giữ đủ độ chính xác cho scorer (bản 08/10 dùng giá trị chưa làm tròn); `q_display` chỉ để in và để đối chiếu với
    # công thức 4 chữ số viết trong báo cáo.
    q_low, q_high = float(np.percentile(allv, lo)), float(np.percentile(allv, hi))
    return {"calSeed": seed, "requests": len(vals), "q_low_p10": q_low, "q_high_p99": q_high,
            "q_display": [round(q_low, 4), round(q_high, 4)]}
