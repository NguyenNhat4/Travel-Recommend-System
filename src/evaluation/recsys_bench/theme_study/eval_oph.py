"""Đo các cấu hình OPH-L (plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §4, §6, §7) trên split thật + khách giả lập.

Khác `eval_profile.py` (để nguyên cho lane A/B):
- cấu hình là tên `registry` (`B0`, `B1p`, `O1`, `P2+F14c+destCap2+slotB+popH:90:1` …), không phải profile × scorer;
- `--split-source frozen`: split dựng trên event đã qua `events.filter_events` như CLI rồi **kiểm sha256** với file đóng băng
  `frozen/split-<kind>-prodcopy-asof20261008.json` (lệch → dừng); `theme` = cách dựng cũ của theme_study (không lọc event);
- `--user-part tune|test|all`: TUNE = `sha1(uid) mod 10 < 3`, TEST = phần còn lại (plan §7.1);
- dòng per-user có thêm `segment`, `ctx0`, `ctx`, `strategy`, `targetTax`, `origin`, `originIsTarget`, `tgtInCart`, `rank20`,
  `mrr@20`, `daysToUse`, `becauseN`, `list20` — để phân tầng và để đếm nDiscordant (`--parity A:B`).

Chạy (Git Bash, từ repo root; env DSN/WEAVIATE như plan §6):
    python -m src.evaluation.recsys_bench.theme_study.eval_oph --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 \
        --configs B0,V0p --split-source frozen --user-part tune --parity B0:V0p --out o.json --per-user-out o.jsonl
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from src.backend.app.domain.recommendation.profile import local_today
from src.evaluation.recsys_bench import splits as SP
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
from src.evaluation.recsys_bench.theme_study.registry import Installed, expand, parse

FROZEN = Path(__file__).resolve().parents[1] / "frozen"
FROZEN_TAG = "prodcopy-asof20261008"
TUNE_MOD = 3


def user_part(uid: str) -> str:
    return "tune" if int(hashlib.sha1(uid.encode("utf-8")).hexdigest(), 16) % 10 < TUNE_MOD else "test"


def build_splits(kinds, events, idx, source: str):
    """(splits, info). `frozen`: lọc event theo mốc của file đóng băng, dựng lại với đúng tham số, kiểm sha."""
    out, info = {}, {"source": source}
    if source == "theme":
        make = {"llbo": lambda: SP.leave_last_booking_out(events, idx), "temporal": lambda: SP.temporal_split(events, idx),
                "nexttrip": lambda: SP.next_trip_split(events, idx), "coldstart": lambda: SP.cold_start_split(events, idx)}
        return {k: make[k]() for k in kinds}, info
    kept = None
    for k in kinds:
        path = FROZEN / f"split-{k}-{FROZEN_TAG}.json"
        frozen = json.loads(path.read_text(encoding="utf-8"))
        p = frozen["canonical"]["params"]
        if kept is None:
            kept, rep = filter_events(events, idx, datetime.fromisoformat(frozen["dbAsOf"]))
            info["filter"] = rep.as_dict()
        if k == "llbo":
            sp = SP.leave_last_booking_out(kept, idx, min_purchases=p["minPurchases"], min_trips=p["minTrips"])
        elif k == "temporal":
            sp = (SP.temporal_split(kept, idx, quantile=p["quantile"]) if p.get("quantile") is not None
                  else SP.temporal_split(kept, idx, cutoff=datetime.fromisoformat(p["T"])))
        elif k == "nexttrip":
            sp = SP.next_trip_split(kept, idx, min_trips=p["minTrips"], browse_days=p["browseDays"])
        else:
            sp = SP.cold_start_split(kept, idx, min_events=p["minEvents"])
        info[k] = {"file": path.name, "sha256": sp.verify(path)}
        out[k] = sp
    return out, info


def make_syn(w, scenarios, seeds, n_syn):
    """Khách giả lập — đúng luồng rng của `eval_profile.main` (seed 7 = bộ đã đo 08/10)."""
    syn = []
    for seed in seeds:
        rng = random.Random(seed)
        base = {}
        for sc in [s for s in scenarios if s != "noisy_paired"]:
            for th in ("beach", "mountain", "city"):
                for n in range(n_syn):
                    u = TE.make_user(w, rng, f"SYN{seed}-{sc[0]}{th[0]}{n:04d}", th, sc)
                    u["seed"] = seed
                    syn.append(u)
                    if sc == "between":
                        base[(th, n)] = u
        if "noisy_paired" in scenarios:
            nrng = random.Random(seed * 1_000_003 + 17)
            for (th, n), u in base.items():
                p = TE.with_noise(w, nrng, u, f"SYN{seed}-p{th[0]}{n:04d}")
                p["seed"] = seed
                syn.append(p)
    return syn


def _cart_units(train, idx):
    return {idx.resolve(str(e.get("productId") or "")) for e in train if e.get("eventName") == "add_to_cart"} - {None}


def _state_fields(inst, as_of, target_unit=None) -> dict:
    st = inst.state
    prof = st.get("profile")
    d2u = None
    if prof is not None and prof.active_trip is not None and prof.active_trip.ends_on is not None:
        d2u = (prof.active_trip.ends_on - local_today(as_of)).days
    ou = st.get("origin_unit")
    return {"segment": st.get("segment"), "ctx0": st.get("ctx0"), "ctx": st.get("ctx"), "origin": st.get("origin"),
            "originIsTarget": (ou == target_unit) if (ou is not None and target_unit is not None) else None,
            "daysToUse": d2u}


def eval_real(inst, split, eng20, eng4, idx, users, sink):
    agg = collections.defaultdict(float)
    for u in users:
        tgt, as_of, train = split.targets[u], split.as_of_by_user[u], split.train_by_user[u]
        g = idx.idx.get(tgt)
        inst.hint["target_unit"] = g                       # chỉ cấu hình trần (origTgt / cartTgt) đọc
        r20 = inst.recommend(eng20, u, as_of, 20, train)["recommendations"]
        resp4 = inst.recommend(eng4, u, as_of, 4, train)
        inst.hint.clear()
        r4 = resp4["recommendations"]
        ids20, ids4 = [x["productId"] for x in r20], [x["productId"] for x in r4]
        tdest = str(idx.destination[g]) if g is not None else None
        rank = ids20.index(tgt) + 1 if tgt in ids20 else None
        row = {"uid": u, "hit@20": float(rank is not None), "ndcg@10": round(1 / math.log2(rank + 1), 6) if rank and rank <= 10 else 0.0,
               "mrr@20": round(1 / rank, 6) if rank else 0.0, "hit@4": float(tgt in ids4),
               "destHit@20": float(any(x.get("destination") == tdest for x in r20)) if tdest else None,
               "rank20": rank, "target": tgt, "targetTax": str(idx.taxonomy[g]) if g is not None else None,
               "tgtInCart": g in _cart_units(train, idx) if g is not None else None,
               "strategy": resp4.get("strategy"), "becauseN": sum(bool(x.get("because")) for x in r4),
               "list4": ids4, "list20": ids20, **_state_fields(inst, as_of, g)}
        for m in ("hit@20", "ndcg@10", "mrr@20", "hit@4"):
            agg[m] += row[m]
        agg["destHit@20"] += row["destHit@20"] or 0.0
        sink(row)
    n = max(len(users), 1)
    return {"n": len(users), **{m: round(v / n, 4) for m, v in agg.items()}}


def eval_syn(inst, w, syn, scenarios, eng20, eng4, as_of, sink, syn_target):
    out = {}
    for sc in scenarios:
        tp, by, dests, tgt = [], collections.defaultdict(list), collections.Counter(), collections.defaultdict(list)
        for u in [x for x in syn if x["events"] and x["scenario"] == sc]:
            resp = inst.recommend(eng4, u["uid"], as_of, 4, u["events"])
            rec = resp["recommendations"]
            dests.update(x["destination"] for x in rec)
            ids4 = [w.i_of[x["productId"]] for x in rec if x["productId"] in w.i_of]
            v = TE.theme_prec(w, ids4, u["theme"])
            if v is not None:
                tp.append(v)
                by[u["theme"]].append(v)
            row = {"stratum": f"syn_{sc}", "seed": u["seed"], "uid": u["uid"], "theme": u["theme"], "baseUid": u.get("base_uid"),
                   "themePrec": v, "strategy": resp.get("strategy"), "list4": [x["productId"] for x in rec],
                   "dests4": [x["destination"] for x in rec], **_state_fields(inst, as_of)}
            if syn_target:
                r20 = inst.recommend(eng20, u["uid"], as_of, 20, u["events"])["recommendations"]
                ids20 = [w.i_of[x["productId"]] for x in r20 if x["productId"] in w.i_of]
                row["list20"] = [x["productId"] for x in r20]
                row["tgtHit@20"], row["tgtHit@4"] = float(u["target"] in ids20), float(u["target"] in ids4)
                row["nextDestHit@20"] = float(any(w.dest[i] == u["next"] for i in ids20))
                row["nextDestHit@4"] = float(any(w.dest[i] == u["next"] for i in ids4))
                for k in ("tgtHit@20", "tgtHit@4", "nextDestHit@20", "nextDestHit@4"):
                    tgt[k].append(row[k])
            sink(row)
        out[f"syn_{sc}"] = {"n": len(tp), "themePrec": round(float(np.mean(tp)), 4) if tp else None,
                            **{f"themePrec_{k}": round(float(np.mean(v)), 4) for k, v in by.items()},
                            **{k: round(float(np.mean(v)), 4) for k, v in sorted(tgt.items())},
                            "distinctDestsTotal": len(dests)}
    return out


def parity(rows: list[dict], pairs: list[tuple[str, str]]) -> dict:
    """nDiscordant theo stratum: số khách có list4 hoặc list20 khác nhau giữa hai cấu hình (0 = cổng parity đạt)."""
    by = {(r["config"], r["stratum"], r.get("seed"), r["uid"]): r for r in rows}
    out = {}
    for a, b in pairs:
        res = collections.defaultdict(lambda: {"n": 0, "nDiscordant4": 0, "nDiscordant20": 0})
        for (c, s, seed, uid), ra in by.items():
            if c != a:
                continue
            rb = by.get((b, s, seed, uid))
            if rb is None:
                continue
            x = res[s]
            x["n"] += 1
            x["nDiscordant4"] += ra.get("list4") != rb.get("list4")
            x["nDiscordant20"] += ra.get("list20") != rb.get("list20")
        out[f"{a}:{b}"] = dict(res)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", required=True, help="mốc khách giả lập (ISO)")
    ap.add_argument("--configs", required=True, help="tên cấu hình registry, phân tách bằng dấu phẩy")
    ap.add_argument("--splits", default="llbo,temporal,nexttrip")
    ap.add_argument("--split-source", default="frozen", choices=["frozen", "theme"])
    ap.add_argument("--user-part", default="all", choices=["tune", "test", "all"])
    ap.add_argument("--max-users", type=int, default=0, help="0 = mọi khách của phần đã chọn")
    ap.add_argument("--scenarios", default="between,open,noisy_paired")
    ap.add_argument("--syn-seeds", default="13")
    ap.add_argument("--n-syn", type=int, default=80)
    ap.add_argument("--syn-target", action="store_true")
    ap.add_argument("--q", default=None, help="ghim 'q_low,q_high' cho F14c; mặc định 0.8529,0.9387 (lane B)")
    ap.add_argument("--parity", default="", help="cặp 'A:B,…' để đếm nDiscordant list4/list20")
    ap.add_argument("--per-user-out", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    configs = [c for c in a.configs.split(",") if c]
    for c in configs:
        parse(c)                                                   # lỗi tên cấu hình → dừng trước khi nạp DB
    TE.AS_OF = datetime.fromisoformat(a.as_of)
    q = tuple(float(x) for x in a.q.split(",")) if a.q else None
    t0 = time.time()
    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    eng20 = TE.OfflineEngine(idx, vec, purchases, mode="eval", popularity_cache=64)
    eng4 = TE.OfflineEngine(idx, vec, purchases, mode="prod", popularity_cache=64)
    kinds = [s for s in a.splits.split(",") if s]
    splits, split_info = build_splits(kinds, events, idx, a.split_source)
    users = {k: [u for u in sorted(sp.targets) if a.user_part == "all" or user_part(u) == a.user_part][: a.max_users or None]
             for k, sp in splits.items()}
    scenarios = [s for s in a.scenarios.split(",") if s]
    seeds = [int(s) for s in a.syn_seeds.split(",") if s]
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    syn = make_syn(w, scenarios, seeds, a.n_syn) if scenarios else []
    res = {"args": vars(a), "splits": split_info, "users": {k: len(v) for k, v in users.items()},
           "expanded": {c: "+".join(expand(c)) for c in configs}, "configs": {}}
    print(f"loaded {time.time()-t0:.0f}s; users {res['users']}; syn {len(syn)}", flush=True)
    rows: list[dict] = []
    pu = open(a.per_user_out, "w", encoding="utf-8") if a.per_user_out else None
    try:
        for name in configs:
            t1 = time.time()
            inst = Installed(parse(name), idx, [eng20, eng4], **({"q": q} if q else {}))
            try:
                def sink(row, _name=name, _stratum=None):
                    row = {"config": _name, **row}
                    rows.append(row)
                    if pu is not None:
                        pu.write(json.dumps(row, ensure_ascii=False) + "\n")
                r = {}
                for k, sp in splits.items():
                    r[k] = eval_real(inst, sp, eng20, eng4, idx, users[k],
                                     lambda row, _k=k: sink({"stratum": _k, "seed": None, **row}))
                r.update(eval_syn(inst, w, syn, scenarios, eng20, eng4, TE.AS_OF, sink, a.syn_target))
            finally:
                inst.restore()
            r["seconds"] = round(time.time() - t1, 1)
            res["configs"][name] = r
            print(name, json.dumps(r, ensure_ascii=False), flush=True)
            if pu is not None:
                pu.flush()
            json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    finally:
        if pu is not None:
            pu.close()
    if a.parity:
        pairs = [tuple(p.split(":", 1)) for p in a.parity.split(",") if p]
        res["parity"] = parity(rows, pairs)
        print("parity", json.dumps(res["parity"], ensure_ascii=False), flush=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
