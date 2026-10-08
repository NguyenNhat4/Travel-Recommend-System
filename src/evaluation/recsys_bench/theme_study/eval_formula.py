"""So các biến thể công thức chấm điểm RecSys trên split thật (LLBO, temporal, nexttrip) + người dùng giả lập có chủ đề.
Engine production không sửa: chỉ thay `use_cases.score_candidates` lúc chạy (monkeypatch) trong tiến trình đo.

Biến thể (s_short = E·u_short, s_long = E·u_long, pop ∈ [0,1]):
  F0  production: 0.7 s_short + 0.15 pop + 0.15 s_long (cosine thô)
  F1  min-max: cosine chuẩn hoá min-max trên không gian ứng viên của request, cùng trọng số
  F2  rank: cosine đổi thành phân vị (0–1) trong không gian ứng viên
  F3  thô, W_POP 0.05 (0.8 / 0.05 / 0.15)
  F4  min-max, W_POP 0.30 (0.55 / 0.30 / 0.15)
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys
import time

import numpy as np

import src.backend.app.application.recommendation.use_cases as UC
from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.evaluation.recsys_bench import splits as SP
from src.evaluation.recsys_bench.theme_study.theme_exp import AS_OF, THEME_OF, World, make_user, theme_prec, load_events, load_index, OfflineEngine, parse_ts


def _mm(x):
    lo, hi = float(x.min()), float(x.max())
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def _rank(x):
    r = np.argsort(np.argsort(x))
    return r / max(len(x) - 1, 1)


def make_scorer(kind, ws=0.7, wp=0.15, wl=0.15, only_between=False):
    def score(profile, E, pop):
        if only_between and profile.active_trip is not None:
            return prod_score(profile, E, pop)
        u = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
        s_short, s_long = E @ u, E @ profile.u_long
        if kind == "minmax":
            s_short, s_long = _mm(s_short), _mm(s_long)
        elif kind == "minmax3":  # giãn cả pop (F11, thêm 08/10)
            s_short, s_long, pop = _mm(s_short), _mm(s_long), _mm(np.asarray(pop, dtype=np.float64))
        elif kind == "rank":
            s_short, s_long = _rank(s_short), _rank(s_long)
        return ws * s_short + wp * pop + wl * s_long, u
    return score


VARIANTS = {
    "F0_prod": None,
    "F1_minmax": make_scorer("minmax"),
    "F2_rank": make_scorer("rank"),
    "F3_rawPop05": make_scorer("raw", 0.8, 0.05, 0.15),
    "F4_minmaxPop30": make_scorer("minmax", 0.55, 0.30, 0.15),
    "F5_minmaxPop25": make_scorer("minmax", 0.60, 0.25, 0.15),
    "F6_minmaxPop35": make_scorer("minmax", 0.50, 0.35, 0.15),
    "F7_betweenMinmaxPop30": make_scorer("minmax", 0.55, 0.30, 0.15, only_between=True),
    "F8_betweenMinmaxPop25": make_scorer("minmax", 0.60, 0.25, 0.15, only_between=True),
    "F9_betweenMinmaxPop45": make_scorer("minmax", 0.40, 0.45, 0.15, only_between=True),
    "F10_betweenMinmaxPop60": make_scorer("minmax", 0.25, 0.60, 0.15, only_between=True),
    "F11_betweenMinmax3Pop30": make_scorer("minmax3", 0.55, 0.30, 0.15, only_between=True),
    "F11b_betweenMinmax3Pop10": make_scorer("minmax3", 0.75, 0.10, 0.15, only_between=True),
    # F12: không giãn, chỉ hạ trọng số pop khi không có chuyến mở (thêm 08/10)
    "F12_betweenRawPop03": make_scorer("raw", 0.82, 0.03, 0.15, only_between=True),
    "F12b_betweenRawPop05": make_scorer("raw", 0.80, 0.05, 0.15, only_between=True),
}


def set_variant(name):
    UC.score_candidates = prod_score if VARIANTS[name] is None else VARIANTS[name]


def eval_split(split, eng20, eng4, idx, max_users=None, sink=None, row_base=None):
    """`sink`: callable nhận một dict / khách (plan WP2.1) để ghi kết quả từng khách ra JSONL — điều kiện để tính CI
    ghép cặp (`paired_ci.py`). Không truyền thì chỉ trả chỉ số tổng hợp như trước.

    `idx` (UnitIndex, có thể None): khi có, tính thêm `destHit@20` = điểm đến của target có trong list 20 không. Trên dữ
    liệu có sở thích, lợi ích bám sở thích phải hiện ở mức ĐIỂM ĐẾN của chuyến kế tiếp trước khi hiện ở hit@20 món
    (khách sạn cụ thể còn phụ thuộc Zipf) — plan lane A2 / B2."""
    users = sorted(split.targets)[: max_users or None]
    h20 = n10 = h4 = d20 = 0.0
    dest_of = (lambda pid: (str(idx.destination[idx.idx[pid]]) if pid in idx.idx else None)) if idx is not None else (lambda pid: None)
    for u in users:
        tgt, as_of, train = split.targets[u], split.as_of_by_user[u], split.train_by_user[u]
        rec20 = eng20.recommend(u, as_of, 20, train)["recommendations"]
        r20 = [x["productId"] for x in rec20]
        r4 = [x["productId"] for x in eng4.recommend(u, as_of, 4, train)["recommendations"]]
        tdest = dest_of(tgt)
        dhit = float(tdest is not None and any(x.get("destination") == tdest for x in rec20))
        d20 += dhit
        hit20 = ndcg = 0.0
        if tgt in r20:
            hit20 = 1.0
            rk = r20.index(tgt)
            ndcg = (1 / math.log2(rk + 2)) if rk < 10 else 0.0
        hit4 = float(tgt in r4)
        h20 += hit20
        n10 += ndcg
        h4 += hit4
        if sink is not None:
            sink({**(row_base or {}), "uid": u, "hit@20": hit20, "ndcg@10": round(ndcg, 6), "hit@4": hit4,
                  "destHit@20": dhit if tdest is not None else None, "target": tgt, "list4": r4})
    n = max(len(users), 1)
    out = {"n": len(users), "hit@20": round(h20 / n, 4), "ndcg@10": round(n10 / n, 4), "hit@4": round(h4 / n, 4)}
    if idx is not None:
        out["destHit@20"] = round(d20 / n, 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", default=None, help="mốc của người dùng giả lập (ISO); mặc định theo theme_exp.AS_OF")
    ap.add_argument("--n-syn", type=int, default=100)
    ap.add_argument("--splits", default="llbo,temporal,nexttrip")
    ap.add_argument("--max-users", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variants", default="")
    a = ap.parse_args()
    if a.variants:
        for k in [k for k in VARIANTS if k not in a.variants.split(",")]:
            del VARIANTS[k]
    from src.evaluation.recsys_bench.theme_study import theme_exp
    if a.as_of:
        from datetime import datetime
        theme_exp.AS_OF = datetime.fromisoformat(a.as_of)
    as_of_syn = theme_exp.AS_OF
    t0 = time.time()
    idx, vec = load_index(a.vec)
    events = load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng20 = OfflineEngine(idx, vec, purchases, mode="eval")
    eng4 = OfflineEngine(idx, vec, purchases, mode="prod")
    split_objs = {}
    for s in a.splits.split(","):
        if s == "llbo":
            split_objs[s] = SP.leave_last_booking_out(events, idx)
        elif s == "temporal":
            split_objs[s] = SP.temporal_split(events, idx)
        elif s == "nexttrip":
            split_objs[s] = SP.next_trip_split(events, idx)
    w = World(idx, vec, [e for e in purchases if parse_ts(e["timestamp"]) < as_of_syn])
    rng = random.Random(7)
    syn = [make_user(w, rng, f"SYN-{sc[0]}{th[0]}{n:04d}", th, sc)
           for sc in ("between", "open") for th in ("beach", "mountain", "city") for n in range(a.n_syn)]
    print(f"loaded {time.time()-t0:.0f}s; splits", {k: len(v.targets) for k, v in split_objs.items()}, flush=True)
    res = {}
    for name in VARIANTS:
        set_variant(name)
        r = {}
        for s, sp in split_objs.items():
            r[s] = eval_split(sp, eng20, eng4, None, a.max_users)
        # người dùng giả lập: độ đúng chủ đề của list production 4 món
        for sc in ("between", "open"):
            tp, by = [], collections.defaultdict(list)
            dests = collections.Counter()
            for u in [x for x in syn if x["events"] and x["uid"].startswith(f"SYN-{sc[0]}")]:
                rec = eng4.recommend(u["uid"], as_of_syn, 4, u["events"])["recommendations"]
                ds = [x["destination"] for x in rec]
                dests.update(ds)
                v = theme_prec(w, [w.i_of[x["productId"]] for x in rec if x["productId"] in w.i_of], u["theme"])
                if v is not None:
                    tp.append(v); by[u["theme"]].append(v)
            r[f"syn_{sc}"] = {"themePrec": round(float(np.mean(tp)), 3),
                              **{f"themePrec_{k}": round(float(np.mean(v)), 3) for k, v in by.items()},
                              "distinctDestsTotal": len(dests), "top5Dests": dests.most_common(5)}
        res[name] = r
        print(name, json.dumps(r, ensure_ascii=False), flush=True)
    UC.score_candidates = prod_score  # trả lại công thức production
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
