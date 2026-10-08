"""Hậu xử lý list production 4 món (trang chủ) trên split thật + người dùng giả lập có chủ đề:
  base      : list production (công thức chọn qua --scorer)
  noSeen    : bỏ món khách đã xem / thêm giỏ trong lịch sử (lấy 12 món rồi lọc, lấp đủ 4)
  explore1  : 3 món đầu của engine + 1 món khám phá ở điểm đến khác (destsim, xem theme_exp.explore)
  noSeen+explore1
Đo: hit@4 (split thật), tỷ lệ chủ đề và tỷ lệ món đã xem (giả lập), số điểm đến khác."""
from __future__ import annotations

import argparse
import collections
import json
import random
import time

import numpy as np

from src.evaluation.recsys_bench.theme_study import eval_formula as EF
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
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
    ap.add_argument("--n-syn", type=int, default=100)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-users", type=int, default=0)
    a = ap.parse_args()
    if a.as_of:
        from datetime import datetime
        TE.AS_OF = datetime.fromisoformat(a.as_of)
    EF.set_variant(a.scorer)
    t0 = time.time()
    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng = TE.OfflineEngine(idx, vec, purchases, mode="prod")
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    out = {"scorer": a.scorer}
    for name, sp in (("llbo", SP.leave_last_booking_out(events, idx)), ("temporal", SP.temporal_split(events, idx))):
        hits = collections.Counter(); n = 0; tgt_seen = 0
        for uid in sorted(sp.targets)[:a.max_users or None]:
            tr = sp.train_by_user[uid]
            v, seen = variants(eng, w, uid, sp.as_of_by_user[uid], tr)
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
                v, seen = variants(eng, w, u["uid"], TE.AS_OF, u["events"])
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
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
