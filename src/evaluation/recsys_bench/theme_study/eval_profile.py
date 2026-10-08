"""Bước 1 (08/10/2026): đo các biến thể dựng profile (`profile_variants.PROFILES`) × công thức điểm (`eval_formula.VARIANTS`).

Cùng bộ đo với `eval_formula`: split thật LLBO / temporal / nexttrip + khách giả lập theo chủ đề (between / open).
Chạy: python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec npy:<prefix> --as-of <ISO> \
        --profiles P0_prod,P4_all --scorers F0_prod,F7_betweenMinmaxPop30 --out out.json
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import time
from datetime import datetime

import numpy as np

import src.backend.app.application.recommendation.use_cases as UC
from src.backend.app.domain.recommendation import build_profile as prod_build
from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.evaluation.recsys_bench import splits as SP
from src.evaluation.recsys_bench.theme_study import eval_formula as EF
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
from src.evaluation.recsys_bench.theme_study.profile_variants import PROFILES, make_build_profile
from src.evaluation.recsys_bench.theme_study.step2_scorers import make_centered, make_quantile

CAPTURED: list = []


def parity(split, eng, n=200):
    """Bản viết lại với mọi công tắc tắt phải cho đúng profile như production."""
    reimpl = make_build_profile(force=True)
    bad = 0

    def cmp(events, E, tax, dest, today=None):
        nonlocal bad
        a, b = prod_build(events, E, tax, dest, today), reimpl(events, E, tax, dest, today)
        same = (set(a.trips) == set(b.trips) and np.allclose(a.u_long, b.u_long, atol=1e-5)
                and (a.active_trip is None) == (b.active_trip is None)
                and (a.active_trip is None or a.active_trip.trip_id == b.active_trip.trip_id))
        bad += not same
        return a
    UC.build_profile = cmp
    for u in sorted(split.targets)[:n]:
        eng.recommend(u, split.as_of_by_user[u], 4, split.train_by_user[u])
    UC.build_profile = prod_build
    return bad


def profile_stats(bp, split, eng, n=300):
    """Cấu trúc profile: số chuyến, tỷ lệ chuyến chỉ có xem / thêm giỏ, tỷ lệ có chuyến mở."""
    rows = []

    def wrap(events, E, tax, dest, today=None):
        p = bp(events, E, tax, dest, today)
        weak = [t for t in p.trips.values() if not any(e.event_name == "purchase" for e in t.events)]
        rows.append((len(p.trips), len(weak) / max(len(p.trips), 1), p.active_trip is not None))
        return p
    UC.build_profile = wrap
    for u in sorted(split.targets)[:n]:
        eng.recommend(u, split.as_of_by_user[u], 4, split.train_by_user[u])
    UC.build_profile = prod_build
    a = np.array(rows, dtype=float)
    return {"trips_p50": float(np.median(a[:, 0])), "share_trips_without_purchase": round(float(a[:, 1].mean()), 3),
            "share_open": round(float(a[:, 2].mean()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--n-syn", type=int, default=80)
    ap.add_argument("--max-users", type=int, default=800)
    ap.add_argument("--profiles", default=",".join(PROFILES))
    ap.add_argument("--scorers", default="F0_prod")
    ap.add_argument("--splits", default="llbo,temporal,nexttrip", help="rỗng = chỉ đo khách giả lập")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    TE.AS_OF = datetime.fromisoformat(a.as_of)
    t0 = time.time()
    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng20 = TE.OfflineEngine(idx, vec, purchases, mode="eval")
    eng4 = TE.OfflineEngine(idx, vec, purchases, mode="prod")
    splits = {"llbo": SP.leave_last_booking_out(events, idx), "temporal": SP.temporal_split(events, idx),
              "nexttrip": SP.next_trip_split(events, idx)}
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    rng = random.Random(7)                                   # cùng seed với eval_formula → cùng khách giả lập
    syn = [TE.make_user(w, rng, f"SYN-{sc[0]}{th[0]}{n:04d}", th, sc)
           for sc in ("between", "open", "noisy") for th in ("beach", "mountain", "city") for n in range(a.n_syn)]
    res = {"parity_mismatch_llbo200": parity(splits["llbo"], eng4)}
    need = a.scorers.split(",")
    if any(x.startswith("F13") for x in need):
        mean_vec = np.asarray(vec.E, dtype=np.float32).mean(0)
        EF.VARIANTS["F13a_betweenCenter"] = make_centered(mean_vec, 0.70, 0.15, 0.15)
        EF.VARIANTS["F13b_betweenCenterPop30"] = make_centered(mean_vec, 0.55, 0.30, 0.15)
    if any(x.startswith("F14") for x in need):
        # tập calibration riêng: khách giả lập "between" seed 99 (bộ đo dùng seed 7), dựng theo profile đầu tiên được yêu cầu
        cal_vals = []
        def rec_score(profile, E, pop):
            if profile.active_trip is None:
                cal_vals.append(np.asarray(E @ profile.u_long, dtype=np.float64))
            return prod_score(profile, E, pop)
        UC.build_profile = make_build_profile(**PROFILES[a.profiles.split(",")[0]])
        UC.score_candidates = rec_score
        crng = random.Random(99)
        for th in ("beach", "mountain", "city"):
            for n in range(40):
                u = TE.make_user(w, crng, f"CAL-{th[0]}{n:04d}", th, "between")
                eng4.recommend(u["uid"], TE.AS_OF, 4, u["events"])
        UC.build_profile, UC.score_candidates = prod_build, prod_score
        allv = np.concatenate(cal_vals)
        q_low, q_high = float(np.percentile(allv, 10)), float(np.percentile(allv, 99))
        res["F14_calibration"] = {"requests": len(cal_vals), "q_low_p10": round(q_low, 4), "q_high_p99": round(q_high, 4)}
        EF.VARIANTS["F14_betweenQuantilePop30"] = make_quantile(q_low, q_high)
        print("calibration", res["F14_calibration"], flush=True)
    print(f"loaded {time.time()-t0:.0f}s; parity mismatches = {res['parity_mismatch_llbo200']}", flush=True)
    for pname in a.profiles.split(","):
        bp = make_build_profile(**PROFILES[pname])
        res[f"{pname}/stats"] = profile_stats(bp, splits["llbo"], eng4)
        for sname in a.scorers.split(","):
            UC.build_profile = bp
            EF.set_variant(sname)
            r = {s: EF.eval_split(sp, eng20, eng4, None, a.max_users) for s, sp in splits.items() if s in a.splits.split(",")}
            for sc in ("between", "open", "noisy"):
                tp, by, dests = [], collections.defaultdict(list), collections.Counter()
                for u in [x for x in syn if x["events"] and x["uid"].startswith(f"SYN-{sc[0]}")]:
                    rec = eng4.recommend(u["uid"], TE.AS_OF, 4, u["events"])["recommendations"]
                    dests.update(x["destination"] for x in rec)
                    v = TE.theme_prec(w, [w.i_of[x["productId"]] for x in rec if x["productId"] in w.i_of], u["theme"])
                    if v is not None:
                        tp.append(v); by[u["theme"]].append(v)
                r[f"syn_{sc}"] = {"themePrec": round(float(np.mean(tp)), 3),
                                  **{f"themePrec_{k}": round(float(np.mean(v)), 3) for k, v in by.items()},
                                  "distinctDestsTotal": len(dests), "top5Dests": dests.most_common(5)}
            res[f"{pname}+{sname}"] = r
            print(pname, sname, json.dumps(r, ensure_ascii=False), flush=True)
            UC.build_profile, UC.score_candidates = prod_build, prod_score
            json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"done {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
