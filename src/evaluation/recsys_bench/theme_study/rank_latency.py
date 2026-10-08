"""Thời gian xếp hạng một request `/recommendations` cho từng cấu hình (plan WP4.3, một phần).

**Đây không phải latency đầu-cuối của API.** Nó đo đúng phần mà nghiên cứu này đổi: dựng profile → chấm điểm → MMR, chạy
in-process trên vector `.npy` thay vì Weaviate. Phần không đo: HTTP, auth, truy vấn `near_vector` thật của Weaviate, đọc
CDP. Tiêu chí G1 "p95 `/recommendations` không tăng quá 50 ms" phải đo bằng `recsys_bench http_latency` hoặc API local;
số ở đây chỉ trả lời "cấu hình mới có làm bước xếp hạng đắt hơn đáng kể không".

Giới hạn số món mỗi điểm đến (`--dest-cap`) làm vòng lặp MMR phải quét và loại nhiều ứng viên hơn, nên đây là cấu hình
duy nhất có lý do để chậm hơn — cần số trước khi đề xuất nó.

Chạy:
    python -m src.evaluation.recsys_bench.theme_study.rank_latency --vec npy:<prefix> --as-of <ISO> \
      --arms "prod:P0_prod:F0_prod:0,f14c:P2_confidence:F14c_betweenQuantilePop35:0,f14cdc2:P2_confidence:F14c_betweenQuantilePop35:2" \
      --n-users 400 --repeat 3 --out latency.json
"""
from __future__ import annotations

import argparse
import io
import json
import time

import numpy as np

import src.backend.app.application.recommendation.use_cases as UC
from src.backend.app.domain.recommendation import build_profile as prod_build
from src.backend.app.domain.recommendation import mmr_select as prod_mmr
from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.evaluation.recsys_bench import splits as SP
from src.evaluation.recsys_bench.theme_study import eval_formula as EF
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
from src.evaluation.recsys_bench.theme_study.dest_diversity import install as install_dest_cap
from src.evaluation.recsys_bench.theme_study.eval_profile import F14_WEIGHTS
from src.evaluation.recsys_bench.theme_study.profile_variants import PROFILES, make_build_profile
from src.evaluation.recsys_bench.theme_study.step2_scorers import calibrate_quantile, make_centered, make_quantile

PROD_SPACE = UC._LocalSpace                                     # noqa: SLF001 - đo lường, không phải code app


def restore():
    UC.build_profile, UC.score_candidates = prod_build, prod_score
    UC.mmr_select, UC._LocalSpace = prod_mmr, PROD_SPACE


def setup_arm(profile: str, scorer: str, dest_cap: int, eng, world, as_of, vec, cal_seed=99):
    bp = make_build_profile(**PROFILES[profile])
    if scorer.startswith("F13"):
        m = np.asarray(vec.E, dtype=np.float32).mean(0)
        EF.VARIANTS.setdefault("F13a_betweenCenter", make_centered(m, 0.70, 0.15, 0.15))
    if scorer.startswith("F14"):
        cal = calibrate_quantile(eng, world, bp, as_of, seed=cal_seed)
        EF.VARIANTS[scorer] = make_quantile(cal["q_low_p10"], cal["q_high_p99"], *F14_WEIGHTS[scorer])
    EF.set_variant(scorer)
    UC.build_profile = bp
    if dest_cap:
        UC.build_profile, UC.mmr_select, UC._LocalSpace = install_dest_cap(bp, dest_cap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--arms", required=True, help="nhãn:profile:scorer:destCap, phân cách bằng dấu phẩy")
    ap.add_argument("--split", default="llbo", choices=["llbo", "temporal", "nexttrip"])
    ap.add_argument("--k", type=int, default=4, help="k của production (trang chủ 4 món)")
    ap.add_argument("--n-users", type=int, default=400)
    ap.add_argument("--repeat", type=int, default=3, help="số lượt lặp trên cùng tập khách; lấy lượt nhanh nhất mỗi khách")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from datetime import datetime
    TE.AS_OF = datetime.fromisoformat(a.as_of)
    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng = TE.OfflineEngine(idx, vec, purchases, mode="prod")
    world = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    split = {"llbo": SP.leave_last_booking_out, "temporal": SP.temporal_split,
             "nexttrip": SP.next_trip_split}[a.split](events, idx)
    users = sorted(split.targets)[: a.n_users]
    # Nạp trước bảng popularity cho mọi as_of để không tính thời gian dựng cache vào lượt đo đầu.
    for u in users:
        eng.popularity_at(split.as_of_by_user[u])

    out = {"split": a.split, "k": a.k, "nUsers": len(users), "repeat": a.repeat, "arms": {}}
    for spec in a.arms.split(","):
        label, profile, scorer, cap = spec.split(":")
        restore()
        setup_arm(profile, scorer, int(cap), eng, world, TE.AS_OF, vec)
        best = np.full(len(users), np.inf)
        for _ in range(a.repeat):
            for i, u in enumerate(users):
                t0 = time.perf_counter()
                eng.recommend(u, split.as_of_by_user[u], a.k, split.train_by_user[u])
                best[i] = min(best[i], (time.perf_counter() - t0) * 1000.0)
        restore()
        out["arms"][label] = {"profile": profile, "scorer": scorer, "destCap": int(cap),
                             "p50_ms": round(float(np.percentile(best, 50)), 2),
                             "p95_ms": round(float(np.percentile(best, 95)), 2),
                             "p99_ms": round(float(np.percentile(best, 99)), 2),
                             "mean_ms": round(float(best.mean()), 2), "max_ms": round(float(best.max()), 2)}
        print(label, out["arms"][label], flush=True)
    base = next(iter(out["arms"]))
    for label, v in out["arms"].items():
        v["delta_p95_ms_vs_" + base] = round(v["p95_ms"] - out["arms"][base]["p95_ms"], 2)
    json.dump(out, io.open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["arms"], ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
