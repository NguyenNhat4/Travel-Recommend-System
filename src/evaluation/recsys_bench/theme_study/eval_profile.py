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
from src.backend.app.domain.recommendation import mmr_select as prod_mmr

prod_space = UC._LocalSpace
from src.evaluation.recsys_bench.theme_study.dest_diversity import install as install_dest_cap
from src.evaluation.recsys_bench.theme_study.profile_variants import PROFILES, make_build_profile
from src.evaluation.recsys_bench.theme_study.step2_scorers import calibrate_quantile, make_centered, make_quantile

CAPTURED: list = []

#: Biến thể trọng số của F14 (calibration phân vị) — cùng ngưỡng q, khác `W_POP`. Thêm 08/10 cho plan WP3.1: `W_POP` là núm
#: vặn giữa "bám sở thích" và "món bán chạy" (báo cáo cuối §4.1), nên ứng viên F14 phải được thử ở vài mức pop.
F14_WEIGHTS = {
    "F14_betweenQuantilePop30": (0.55, 0.30, 0.15),
    "F14b_betweenQuantilePop25": (0.60, 0.25, 0.15),
    "F14c_betweenQuantilePop35": (0.50, 0.35, 0.15),
    #: Bản thận trọng, song song F9 của bước 1: giữ pop cao để mất ít nhất ở temporal / nexttrip.
    "F14d_betweenQuantilePop45": (0.40, 0.45, 0.15),
}


def _trip_fields(p):
    """Mọi trường của Trip mà engine dùng để quyết định (trừ vector, so riêng): để parity bắt được cả lệch nghiệp vụ,
    không chỉ lệch u_long. Mở rộng 08/10 theo plan WP0.3 — bản cũ chỉ so trips / u_long / trip_id của chuyến mở."""
    return {tid: (round(t.age_days, 6), t.ends_on, t.ended, tuple(sorted(t.purchased_taxonomies)), t.destination,
                  len(t.events)) for tid, t in p.trips.items()}


def parity(split, eng, n=200):
    """Bản viết lại với mọi công tắc tắt phải cho đúng profile như production."""
    reimpl = make_build_profile(force=True)
    bad = 0
    diffs: collections.Counter = collections.Counter()

    def cmp(events, E, tax, dest, today=None):
        nonlocal bad
        a, b = prod_build(events, E, tax, dest, today), reimpl(events, E, tax, dest, today)
        checks = {
            "trips": set(a.trips) == set(b.trips),
            "u_long": np.allclose(a.u_long, b.u_long, atol=1e-5),
            "active_trip": ((a.active_trip is None) == (b.active_trip is None)
                            and (a.active_trip is None or a.active_trip.trip_id == b.active_trip.trip_id)),
            "bought_units": a.bought_units == b.bought_units,
            "n_events": a.n_events == b.n_events,
            "strategy": a.strategy == b.strategy,
            "trip_fields": _trip_fields(a) == _trip_fields(b),
            "trip_vecs": all(np.allclose(a.trips[t].vec, b.trips[t].vec, atol=1e-5)
                             for t in set(a.trips) & set(b.trips)),
        }
        for name, ok in checks.items():
            if not ok:
                diffs[name] += 1
        bad += not all(checks.values())
        return a
    UC.build_profile = cmp
    for u in sorted(split.targets)[:n]:
        eng.recommend(u, split.as_of_by_user[u], 4, split.train_by_user[u])
    UC.build_profile = prod_build
    return bad, dict(diffs)


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
    ap.add_argument("--splits", default="llbo,temporal,nexttrip", help="llbo,temporal,nexttrip,coldstart; rỗng = chỉ đo khách giả lập")
    ap.add_argument("--scenarios", default="between,open,noisy",
                    help="kịch bản khách giả lập; `noisy_paired` = cùng khách với `between` + lượt xem nhiễu (WP2.3)")
    ap.add_argument("--syn-seeds", default="7", help="một hoặc nhiều seed khách giả lập, vd 42,7,2026 (WP2.4). "
                                                    "Mặc định 7 = đúng bộ khách đã đo 08/10")
    ap.add_argument("--f14-cal-profile", default=None,
                    help="profile dùng để calibrate F14; mặc định profile đầu tiên của --profiles")
    ap.add_argument("--f14-q", default=None,
                    help="ghim ngưỡng F14 'q_low,q_high' (vd 0.8529,0.9387 = hằng sẽ ship) thay vì dùng q calibrate trên DB đang đo; "
                         "calibration vẫn chạy và được ghi vào JSON để đối chiếu (lane B2)")
    ap.add_argument("--f14-cal-seed", type=int, default=99,
                    help="seed của tập calibration F14 (WP3.1: đổi seed để xem q có bền không). 99 = bản đã đo 08/10")
    ap.add_argument("--per-user-out", default=None, help="file JSONL ghi kết quả từng khách (plan WP2.1)")
    ap.add_argument("--dest-cap", type=int, default=0,
                    help="tối đa N món mỗi điểm đến khi KHÔNG có chuyến mở (0 = tắt, như production). Ứng viên giảm "
                         "thiệt hại độ phủ điểm đến cho gate G2 — xem theme_study/dest_diversity.py")
    ap.add_argument("--syn-target", action="store_true",
                    help="đo thêm dự đoán chuyến kế tiếp của khách giả lập (tgtHit, nextDestHit) — bộ đo duy nhất có sở "
                         "thích thật, dùng cho gate G2. Thêm 1 lượt gọi engine k=20 / khách")
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
              "nexttrip": SP.next_trip_split(events, idx),
              # coldstart (plan lane A2): target = lần mua hợp lệ đầu tiên; trên prodcopy gần như mọi khách có chuyến chỉ-xem
              # đang mở (N = 14) nên nhánh không-chuyến-mở hiếm khi chạy — là kiểm KHÔNG-hồi-quy, không phải lợi ích.
              "coldstart": SP.cold_start_split(events, idx)}
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    scenarios = [s for s in a.scenarios.split(",") if s]
    seeds = [int(s) for s in a.syn_seeds.split(",") if s]
    # Một seed = một bộ khách giả lập độc lập; đo nhiều seed để biết chênh giữa các cấu hình có bền qua seed không (WP2.4).
    # Với seeds=[7] và kịch bản mặc định, luồng rng y nguyên bản 08/10 (uid chỉ là nhãn, engine không đọc nó).
    syn = []
    for seed in seeds:
        rng = random.Random(seed)                            # seed 7 = cùng bộ khách với eval_formula
        base = {}
        for sc in [s for s in scenarios if s != "noisy_paired"]:
            for th in ("beach", "mountain", "city"):
                for n in range(a.n_syn):
                    u = TE.make_user(w, rng, f"SYN{seed}-{sc[0]}{th[0]}{n:04d}", th, sc)
                    u["seed"] = seed
                    syn.append(u)
                    if sc == "between":
                        base[(th, n)] = u
        if "noisy_paired" in scenarios:
            if not base:
                raise SystemExit("--scenarios noisy_paired cần cả `between` (lịch sử nền của cùng khách)")
            nrng = random.Random(seed * 1_000_003 + 17)       # luồng riêng: không xê dịch bộ khách `between` / `open` / `noisy`
            for (th, n), u in base.items():
                p = TE.with_noise(w, nrng, u, f"SYN{seed}-p{th[0]}{n:04d}")
                p["seed"] = seed
                syn.append(p)
    n_bad, by_field = parity(splits["llbo"], eng4)
    res = {"parity_mismatch_llbo200": n_bad, "parity_mismatch_by_field": by_field}
    need = a.scorers.split(",")
    if any(x.startswith("F13") for x in need):
        mean_vec = np.asarray(vec.E, dtype=np.float32).mean(0)
        EF.VARIANTS["F13a_betweenCenter"] = make_centered(mean_vec, 0.70, 0.15, 0.15)
        EF.VARIANTS["F13b_betweenCenterPop30"] = make_centered(mean_vec, 0.55, 0.30, 0.15)
    if any(x.startswith("F14") for x in need):
        cal_profile = a.f14_cal_profile or a.profiles.split(",")[0]
        cal = calibrate_quantile(eng4, w, make_build_profile(**PROFILES[cal_profile]), TE.AS_OF, seed=a.f14_cal_seed)
        res["F14_calibration"] = {"profile": cal_profile, **cal}
        q_low, q_high = cal["q_low_p10"], cal["q_high_p99"]
        if a.f14_q:
            q_low, q_high = (float(x) for x in a.f14_q.split(","))
            res["F14_calibration"]["pinned"] = [q_low, q_high]
        for name in [x for x in need if x.startswith("F14")]:
            if name not in F14_WEIGHTS:
                raise SystemExit(f"scorer {name!r} chưa có trọng số trong F14_WEIGHTS: {sorted(F14_WEIGHTS)}")
            EF.VARIANTS[name] = make_quantile(q_low, q_high, *F14_WEIGHTS[name])
        print("calibration", res["F14_calibration"], flush=True)
    print(f"loaded {time.time()-t0:.0f}s; parity mismatches = {res['parity_mismatch_llbo200']} {by_field or ''}",
          flush=True)
    syn_target = a.syn_target
    pu = open(a.per_user_out, "w", encoding="utf-8") if a.per_user_out else None
    try:
        for pname in a.profiles.split(","):
            bp = make_build_profile(**PROFILES[pname])
            res[f"{pname}/stats"] = profile_stats(bp, splits["llbo"], eng4)
            for sname in a.scorers.split(","):
                cfg = f"{pname}+{sname}" + (f"+destCap{a.dest_cap}" if a.dest_cap else "")
                UC.build_profile = bp
                EF.set_variant(sname)
                if a.dest_cap:
                    UC.build_profile, UC.mmr_select, UC._LocalSpace = install_dest_cap(bp, a.dest_cap)

                def sink(row, _cfg=cfg):
                    if pu is not None:
                        pu.write(json.dumps({"config": _cfg, **row}, ensure_ascii=False) + "\n")

                r = {s: EF.eval_split(sp, eng20, eng4, idx, a.max_users, sink=sink if pu else None,
                                      row_base={"stratum": s, "seed": None})
                     for s, sp in splits.items() if s in a.splits.split(",")}
                for sc in scenarios:
                    tp, by, dests = [], collections.defaultdict(list), collections.Counter()
                    tgt = collections.defaultdict(list)
                    for u in [x for x in syn if x["events"] and x["scenario"] == sc]:
                        rec = eng4.recommend(u["uid"], TE.AS_OF, 4, u["events"])["recommendations"]
                        dests.update(x["destination"] for x in rec)
                        ids4 = [w.i_of[x["productId"]] for x in rec if x["productId"] in w.i_of]
                        v = TE.theme_prec(w, ids4, u["theme"])
                        if v is not None:
                            tp.append(v); by[u["theme"]].append(v)
                        # Dự đoán chuyến kế tiếp trên dữ liệu CÓ sở thích (plan WP3 / gate G2): `target` là khách sạn của
                        # chuyến kế tiếp và `next` là điểm đến của nó, do `theme_exp.make_user` sinh ra. Split thật không
                        # đo được việc này vì `seed_histories.plan_trip` bốc điểm đến độc lập với khách.
                        row = {"stratum": f"syn_{sc}", "seed": u["seed"], "uid": u["uid"], "theme": u["theme"],
                               "baseUid": u.get("base_uid"), "themePrec": v,
                               "list4": [x["productId"] for x in rec], "dests4": [x["destination"] for x in rec]}
                        if syn_target:
                            r20 = eng20.recommend(u["uid"], TE.AS_OF, 20, u["events"])["recommendations"]
                            ids20 = [w.i_of[x["productId"]] for x in r20 if x["productId"] in w.i_of]
                            row["tgtHit@20"] = float(u["target"] in ids20)
                            row["tgtHit@4"] = float(u["target"] in ids4)
                            row["nextDestHit@20"] = float(any(w.dest[i] == u["next"] for i in ids20))
                            row["nextDestHit@4"] = float(any(w.dest[i] == u["next"] for i in ids4))
                            for k2 in ("tgtHit@20", "tgtHit@4", "nextDestHit@20", "nextDestHit@4"):
                                tgt[k2].append(row[k2])
                        sink(row)
                    r[f"syn_{sc}"] = {"themePrec": round(float(np.mean(tp)), 3),
                                      **{f"themePrec_{k}": round(float(np.mean(v)), 3) for k, v in by.items()},
                                      **{k2: round(float(np.mean(v)), 4) for k2, v in sorted(tgt.items())},
                                      "distinctDestsTotal": len(dests), "top5Dests": dests.most_common(5)}
                res[cfg] = r
                print(cfg, json.dumps(r, ensure_ascii=False), flush=True)
                UC.build_profile, UC.score_candidates = prod_build, prod_score
                UC.mmr_select, UC._LocalSpace = prod_mmr, prod_space
                json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                if pu is not None:
                    pu.flush()
    finally:
        if pu is not None:
            pu.close()
    print(f"done {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
