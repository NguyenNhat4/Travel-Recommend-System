"""Hậu xử lý list production 4 món (trang chủ) trên split thật + người dùng giả lập có chủ đề:
  base      : list production (công thức chọn qua --scorer)
  noSeen    : bỏ món khách đã xem / thêm giỏ trong lịch sử (lấy 12 món rồi lọc, lấp đủ 4)
  explore1  : 3 món đầu của engine + 1 món khám phá ở điểm đến khác (destsim, xem theme_exp.explore)
  noSeen+explore1
Đo: hit@4 (split thật), tỷ lệ chủ đề và tỷ lệ món đã xem (giả lập), số điểm đến khác.

08/10 (plan WP4.1): thêm `--profile` và các scorer F13 / F14 để chạy ô khám phá **cùng tổ hợp sẽ triển khai** (P2 + công
thức đã chọn), không chỉ profile production + F0 như lượt 08/10 đầu tiên."""
from __future__ import annotations

import argparse
import collections
import json
import random
import time

import numpy as np

import src.backend.app.application.recommendation.use_cases as UC
from src.backend.app.domain.recommendation import build_profile as prod_build
from src.evaluation.recsys_bench.theme_study import eval_formula as EF
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
from src.evaluation.recsys_bench.theme_study.eval_profile import F14_WEIGHTS
from src.evaluation.recsys_bench.theme_study.profile_variants import PROFILES, make_build_profile
from src.evaluation.recsys_bench.theme_study.step2_scorers import calibrate_quantile, make_centered, make_quantile
from src.evaluation.recsys_bench import splits as SP


def seen_ids(events):
    return {e["productId"] for e in events if e["eventName"] in ("product_view", "add_to_cart")}


def variants(eng, w, uid, as_of, events, how="destsim"):
    full = eng.recommend(uid, as_of, 12, events)
    recs = full["recommendations"]
    ids = [x["productId"] for x in recs]
    seen = seen_ids(events)
    base = ids[:4]
    no_seen = [p for p in ids if p not in seen][:4]
    if len(no_seen) < 4:
        no_seen += [p for p in ids if p not in no_seen][: 4 - len(no_seen)]
    cur = {full.get("destination")} if full.get("destination") else set()
    bought = {w.i_of[e["productId"]] for e in events if e["eventName"] == "purchase" and e["productId"] in w.i_of}
    user = {"events": events}
    u = TE.user_vectors(w, events, as_of)
    excl = cur if cur else {r["destination"] for r in recs[:3]}
    ex = [w.pid[i] for i in TE.explore(w, u, user, excl, bought, 1, how, as_of)]
    explore1 = base[:3] + [p for p in ex if p not in base[:3]][:1]
    nse = no_seen[:3] + [p for p in ex if p not in no_seen[:3]][:1]
    fill = base + [p for p in ex if p not in base][: max(0, 4 - len(base))]   # chỉ lấp chỗ trống, không thay món
    return {"base": base, "noSeen": no_seen, "explore1": explore1, "noSeen+explore1": nse, "fillExplore": fill}, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--scorer", default="F0_prod")
    ap.add_argument("--profile", default="P0_prod", choices=sorted(PROFILES))
    ap.add_argument("--f14-cal-seed", type=int, default=99)
    ap.add_argument("--n-syn", type=int, default=100)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-users", type=int, default=0)
    ap.add_argument("--how", default="destsim", choices=["ulong", "ushort", "blend", "destsim", "destsim_pop"],
                    help="cách xếp hạng món khám phá (theme_exp.explore). Mặc định destsim = đúng lượt đo 08/10; "
                         "production sẽ xếp theo cos(u_long, v) qua near_vector → dùng `ulong` khi trích số cho đề xuất")
    a = ap.parse_args()
    if a.as_of:
        from datetime import datetime
        TE.AS_OF = datetime.fromisoformat(a.as_of)
    t0 = time.time()
    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng = TE.OfflineEngine(idx, vec, purchases, mode="prod")
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    out = {"scorer": a.scorer, "profile": a.profile, "how": a.how}
    bp = make_build_profile(**PROFILES[a.profile])
    # F13 / F14 không nằm sẵn trong EF.VARIANTS: F13 cần vector trung bình catalog, F14 cần tập calibration riêng.
    if a.scorer.startswith("F13"):
        mean_vec = np.asarray(vec.E, dtype=np.float32).mean(0)
        EF.VARIANTS.setdefault("F13a_betweenCenter", make_centered(mean_vec, 0.70, 0.15, 0.15))
        EF.VARIANTS.setdefault("F13b_betweenCenterPop30", make_centered(mean_vec, 0.55, 0.30, 0.15))
    if a.scorer.startswith("F14"):
        if a.scorer not in F14_WEIGHTS:
            raise SystemExit(f"scorer {a.scorer!r} chưa có trọng số trong F14_WEIGHTS: {sorted(F14_WEIGHTS)}")
        cal = calibrate_quantile(eng, w, bp, TE.AS_OF, seed=a.f14_cal_seed)
        out["F14_calibration"] = {"profile": a.profile, **cal}
        EF.VARIANTS[a.scorer] = make_quantile(cal["q_low_p10"], cal["q_high_p99"], *F14_WEIGHTS[a.scorer])
        print("calibration", out["F14_calibration"], flush=True)
    EF.set_variant(a.scorer)
    UC.build_profile = bp
    for name, sp in (("llbo", SP.leave_last_booking_out(events, idx)), ("temporal", SP.temporal_split(events, idx))):
        hits = collections.Counter(); n = 0; tgt_seen = 0
        for uid in sorted(sp.targets)[:a.max_users or None]:
            tr = sp.train_by_user[uid]
            v, seen = variants(eng, w, uid, sp.as_of_by_user[uid], tr, how=a.how)
            tgt = sp.targets[uid]; n += 1; tgt_seen += tgt in seen
            for k, ids in v.items():
                hits[k] += tgt in ids
        out[name] = {"n": n, "targetWasSeenBefore": round(tgt_seen / n, 3), **{f"hit@4_{k}": round(c / n, 4) for k, c in hits.items()}}
        print(name, out[name], flush=True)
    rng = random.Random(11)
    for sc in ("between", "open"):
        agg = collections.defaultdict(list)
        for th in ("beach", "mountain", "city"):
            for i in range(a.n_syn):
                u = TE.make_user(w, rng, f"SYS-{sc[0]}{th[0]}{i:04d}", th, sc)
                v, seen = variants(eng, w, u["uid"], TE.AS_OF, u["events"], how=a.how)
                for k, ids in v.items():
                    ix = [w.i_of[p] for p in ids if p in w.i_of]
                    tp = TE.theme_prec(w, ix, th)
                    if tp is not None:
                        agg[f"themePrec_{k}"].append(tp)
                    agg[f"seenShare_{k}"].append(np.mean([p in seen for p in ids]) if ids else 0)
                    agg[f"otherDest_{k}"].append(len({w.dest[j] for j in ix}) - 1 if ix else 0)
                    agg[f"len_{k}"].append(len(ids))
        out[f"syn_{sc}"] = {k: round(float(np.mean(v)), 3) for k, v in sorted(agg.items())}
        print(sc, out[f"syn_{sc}"], flush=True)
    UC.build_profile = prod_build
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
