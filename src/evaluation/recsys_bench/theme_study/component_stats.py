"""Phân bố ba thành phần của `score_candidates` TRƯỚC khi nhân trọng số: cos(u_short), pop, cos(u_long).

Bọc hàm `score_candidates` production để ghi lại giá trị trên đúng ma trận `E` mà engine chấm trong từng request
(ứng viên Weaviate + món phổ biến + món trong lịch sử khách). Không đổi điểm, không đổi thứ hạng.
Chạy: python -m src.evaluation.recsys_bench.theme_study.component_stats --vec npy:<prefix> --as-of <ISO> --out stats.json
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime

import numpy as np

import src.backend.app.application.recommendation.use_cases as UC
from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.evaluation.recsys_bench import splits as SP
from src.evaluation.recsys_bench.theme_study import theme_exp as TE

REC: list[dict] = []


def recording_score(profile, E, pop):
    u = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
    REC.append({"open": profile.active_trip is not None, "short": np.asarray(E @ u, dtype=np.float64),
                "long": np.asarray(E @ profile.u_long, dtype=np.float64), "pop": np.asarray(pop, dtype=np.float64)})
    return prod_score(profile, E, pop)


def summarize(rows, key):
    allv = np.concatenate([r[key] for r in rows]) if rows else np.array([])
    q = lambda a, p: round(float(np.percentile(a, p)), 4)
    per = {"min": [], "p50": [], "p90": [], "max": [], "p90_minus_p50": [], "max_minus_min": []}
    for r in rows:
        a = r[key]
        per["min"].append(a.min()); per["p50"].append(np.median(a)); per["p90"].append(np.percentile(a, 90))
        per["max"].append(a.max()); per["p90_minus_p50"].append(np.percentile(a, 90) - np.median(a))
        per["max_minus_min"].append(a.max() - a.min())
    return {
        "all_values": {"n": int(allv.size), "min": q(allv, 0), "p10": q(allv, 10), "p50": q(allv, 50), "p90": q(allv, 90),
                       "p99": q(allv, 99), "max": q(allv, 100), "share_zero": round(float(np.mean(allv == 0)), 3)},
        "per_request_median": {k: round(float(np.median(v)), 4) for k, v in per.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--max-users", type=int, default=300)
    ap.add_argument("--n-syn", type=int, default=50)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    TE.AS_OF = datetime.fromisoformat(a.as_of)
    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng = TE.OfflineEngine(idx, vec, purchases, mode="prod")
    UC.score_candidates = recording_score
    out = {}
    sp = SP.leave_last_booking_out(events, idx)
    for uid in sorted(sp.targets)[: a.max_users]:
        eng.recommend(uid, sp.as_of_by_user[uid], 4, sp.train_by_user[uid])
    out["llbo_real"] = {"requests": len(REC), "share_open": round(float(np.mean([r["open"] for r in REC])), 3),
                        **{k: summarize(REC, k) for k in ("short", "long", "pop")}}
    REC.clear()
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    rng = random.Random(7)
    for sc in ("between", "open"):
        for th in ("beach", "mountain", "city"):
            for n in range(a.n_syn):
                u = TE.make_user(w, rng, f"STAT-{sc[0]}{th[0]}{n:04d}", th, sc)
                eng.recommend(u["uid"], TE.AS_OF, 4, u["events"])
        out[f"syn_{sc}"] = {"requests": len(REC), "share_open": round(float(np.mean([r["open"] for r in REC])), 3),
                            **{k: summarize(REC, k) for k in ("short", "long", "pop")}}
        REC.clear()
    UC.score_candidates = prod_score
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
