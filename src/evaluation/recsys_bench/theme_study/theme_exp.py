"""Thí nghiệm local: RecSys có gợi ý điểm đến cùng "chủ đề" (biển / núi / thành phố) cho khách có sở thích nhất quán không,
và biến thể nào tốt nhất. Chạy từ gốc repo: `python -m src.evaluation.recsys_bench.theme_study.theme_exp --vec npy:<prefix>`.
Kết quả 08/10/2026: `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md`.

Không sửa engine: mọi biến thể là hậu xử lý trên output `RecommendForUser` (OfflineEngine, mode prod / eval) và vector e5-small.
Nhãn chủ đề CHỈ dùng để chấm điểm, không thuật toán nào đọc nó.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

from src.data_collection.seed import config as seed_config
from src.evaluation.recsys_bench.data_source import load_events, load_index
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import parse_ts

AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)

# Nhãn chủ đề theo hiểu biết phổ thông về điểm đến (duyệt tay); "mixed" = không rõ, bỏ khỏi sinh dữ liệu và chấm điểm.
# beach / mountain / city lấy từ `data_collection/seed/config.DEST_THEMES` (một nguồn, dùng chung với profile seed `g6-pref-v1`,
# MOCK_DATA_SPEC §4.3); "mixed" chỉ dùng ở thí nghiệm này nên giữ tại đây.
THEME = {
    **{t: list(ds) for t, ds in seed_config.DEST_THEMES.items()},
    "mixed": ["Nghệ An", "Hà Tĩnh", "Rạch Giá", "Quảng Bình", "Thanh Hóa", "Châu Đốc", "Bến Tre", "Bắc Ninh", "Biên Hòa",
              "Tây Ninh"],
}
THEME_OF = {d: t for t, ds in THEME.items() for d in ds}
W_EVENT = {"purchase": 1.0, "add_to_cart": 0.6, "product_view": 0.3}


class World:
    def __init__(self, idx, vec, purchases):
        self.idx, self.vec = idx, vec
        rec = idx.mask(only_recommendable=True)
        pos = {pid: i for i, pid in enumerate(vec.ids)} if hasattr(vec, "ids") else None
        E = getattr(vec, "E", None)
        if pos is None or E is None:
            raise SystemExit("NumpyVectorSearch không lộ ids/E")
        self.pid = [u.product_id for u in idx.units]
        self.row = np.array([pos.get(p, -1) for p in self.pid])
        self.E = np.zeros((len(self.pid), E.shape[1]), dtype=np.float32)
        ok = self.row >= 0
        self.E[ok] = E[self.row[ok]]
        self.E /= np.maximum(np.linalg.norm(self.E, axis=1, keepdims=True), 1e-9)
        self.dest = np.array([str(d) for d in idx.destination])
        self.tax = np.array([str(t) for t in idx.taxonomy])
        self.rec = rec & ok
        self.i_of = {p: i for i, p in enumerate(self.pid)}
        cnt = collections.Counter(e["productId"] for e in purchases)
        self.pop = np.array([cnt.get(p, 0) for p in self.pid], dtype=np.float64)
        self.by = collections.defaultdict(list)          # (dest, taxonomy) -> unit index
        for i in np.flatnonzero(self.rec):
            self.by[(self.dest[i], self.tax[i])].append(int(i))
        dests = sorted({d for d in self.dest[self.rec] if THEME_OF.get(d, "mixed") != "mixed"})
        self.dests = [d for d in dests if self.by.get((d, "hotel"))]
        self.centroid = {}
        for d in set(self.dest[self.rec]):
            m = self.rec & (self.dest == d)
            c = self.E[m].mean(axis=0)
            self.centroid[d] = c / max(np.linalg.norm(c), 1e-9)
        self.dest_size = collections.Counter(self.dest[self.rec])

    def pick(self, rng, dest, tax):
        cand = self.by.get((dest, tax)) or []
        if not cand:
            return None
        w = self.pop[cand] + 1.0
        return cand[int(rng.choices(range(len(cand)), weights=w)[0])]

    def pick_dest(self, rng, theme, exclude=()):
        same = [d for d in self.dests if THEME_OF[d] == theme and d not in exclude]
        other = [d for d in self.dests if THEME_OF[d] != theme and d not in exclude]
        pool = same if (rng.random() < 0.8 and same) else other
        return rng.choices(pool, weights=[math.sqrt(self.dest_size[d]) for d in pool])[0]


def iso(t):
    return t.astimezone(timezone.utc).isoformat()


def add_noise_views(w: World, rng, theme, ev):
    """Thêm 5–8 lượt xem lẻ ở điểm đến KHÁC chủ đề vào `ev` (tại chỗ) — phần `noisy` của `make_user`, tách ra 08/10 để
    kịch bản `noisy_paired` dùng đúng cùng một luật. Giữ nguyên từng lời gọi rng theo đúng thứ tự cũ để kịch bản
    `noisy` cho ra y nguyên bộ khách đã đo 08/10."""
    others = [d for d in w.dests if THEME_OF[d] != theme]
    for _ in range(rng.randint(5, 8)):
        d = rng.choice(others)
        i = w.pick(rng, d, "hotel") or w.pick(rng, d, "attraction")
        if i is None:
            continue
        ev.append({"cdpUserId": None, "eventName": "product_view", "timestamp": iso(AS_OF - timedelta(days=rng.randint(20, 300))),
                   "productId": w.pid[i], "taxonomy": w.tax[i], "eventGroupId": None, "quantity": None,
                   "unitPrice": None, "usingDate": None})
    return ev


def with_noise(w: World, rng, user, uid):
    """Bản sao của `user` (thường là khách `between`) + lượt xem nhiễu → so "nhiễu làm theme giảm bao nhiêu" trên CÙNG
    khách, thay vì so hai cohort khác nhau như kịch bản `noisy` (báo cáo cuối §2.2). Lịch sử nền giống hệt bản gốc."""
    ev = [dict(e) for e in user["events"]]
    add_noise_views(w, rng, user["theme"], ev)
    for e in ev:
        e["cdpUserId"] = uid
    ev.sort(key=lambda e: e["timestamp"])
    return {**user, "uid": uid, "scenario": "noisy_paired", "base_uid": user["uid"], "events": ev}


def make_user(w: World, rng, uid, theme, scenario):
    """2–3 chuyến xong (khách sạn + 50% tham quan, có view trước), rồi chuyến kế tiếp cùng chủ đề 80 %.
    scenario 'between': không có chuyến mở. 'open': đang xem 3 món ở điểm đến của chuyến kế tiếp (view-only, 1–2 ngày trước)."""
    ev, past = [], []
    n = rng.choice([2, 3])
    for k, days in enumerate(sorted(rng.sample(range(60, 420), n), reverse=True)):
        d = w.pick_dest(rng, theme, exclude=past[-1:])
        past.append(d)
        t_buy = AS_OF - timedelta(days=days)
        gid = f"{uid}-t{k}"
        use = t_buy + timedelta(days=rng.randint(7, 30))
        if use > AS_OF - timedelta(days=15):
            use = AS_OF - timedelta(days=15)
        for _ in range(rng.randint(1, 3)):
            i = w.pick(rng, d, rng.choice(["hotel", "attraction"])) or w.pick(rng, d, "hotel")
            ev.append({"cdpUserId": uid, "eventName": "product_view", "timestamp": iso(t_buy - timedelta(hours=rng.randint(2, 96))),
                       "productId": w.pid[i], "taxonomy": w.tax[i], "eventGroupId": None, "quantity": None,
                       "unitPrice": None, "usingDate": None})
        for tax in ["hotel"] + (["attraction"] if rng.random() < 0.5 else []):
            i = w.pick(rng, d, tax)
            if i is None:
                continue
            ev.append({"cdpUserId": uid, "eventName": "purchase", "timestamp": iso(t_buy + timedelta(minutes=rng.randint(1, 60))),
                       "productId": w.pid[i], "taxonomy": w.tax[i], "eventGroupId": gid, "quantity": 1,
                       "unitPrice": None, "usingDate": use.date().isoformat()})
    nxt = w.pick_dest(rng, theme, exclude=past[-1:])
    target = w.pick(rng, nxt, "hotel")
    open_items = []
    if scenario == "open":
        for _ in range(3):
            i = w.pick(rng, nxt, rng.choice(["hotel", "attraction"])) or w.pick(rng, nxt, "hotel")
            open_items.append(i)
            ev.append({"cdpUserId": uid, "eventName": "product_view", "timestamp": iso(AS_OF - timedelta(hours=rng.randint(3, 40))),
                       "productId": w.pid[i], "taxonomy": w.tax[i], "eventGroupId": None, "quantity": None,
                       "unitPrice": None, "usingDate": None})
    if scenario == "noisy":
        # 08/10: mua theo gu nhưng lướt xem 5–8 sản phẩm ở điểm đến KHÁC chủ đề (không eventGroupId, 20–300 ngày trước,
        # nên không tạo chuyến mở) — đo việc lượt xem lẻ lấn át u_long. Đây là cohort ĐỘC LẬP với `between`
        # (sinh tiếp từ cùng luồng rng); muốn so trên cùng khách thì dùng `with_noise` (kịch bản `noisy_paired`).
        add_noise_views(w, rng, theme, ev)
        for e in ev:
            e["cdpUserId"] = uid
    ev.sort(key=lambda e: e["timestamp"])
    return {"uid": uid, "theme": theme, "scenario": scenario, "past": past, "next": nxt, "target": target,
            "open": open_items, "events": ev}


def user_vectors(w: World, events, now):
    """u_long ≈ trung bình có trọng số (loại event × suy giảm 365 ngày) vector các món trong lịch sử; u_short = 14 ngày gần nhất."""
    vl = np.zeros(w.E.shape[1]); vs = np.zeros(w.E.shape[1])
    for e in events:
        i = w.i_of.get(e["productId"])
        if i is None:
            continue
        age = (now - parse_ts(e["timestamp"])).days
        wt = W_EVENT.get(e["eventName"], 0.3)
        vl += wt * math.exp(-age / 365) * w.E[i]
        if age <= 14:
            vs += wt * w.E[i]
    n = lambda v: v / max(np.linalg.norm(v), 1e-9)
    return n(vl), n(vs)


def explore(w: World, u, user, exclude_dest, bought, n_items, how, now):
    """Ô khám phá: n_items món ở điểm đến khác `exclude_dest`, mỗi điểm đến tối đa 1 món, chỉ hotel/attraction/combo."""
    ulong, ushort = u
    ok = w.rec & ~np.isin(w.dest, list(exclude_dest)) & np.isin(w.tax, ["hotel", "attraction", "combo"])
    ok[list(bought)] = False
    pop = np.log1p(w.pop); pop = pop / max(pop.max(), 1e-9)
    if how == "ulong":
        s = w.E @ ulong
    elif how == "ushort":
        s = w.E @ ushort
    elif how == "blend":
        s = 0.5 * (w.E @ ulong) + 0.5 * (w.E @ ushort)
    elif how in ("destsim", "destsim_pop"):
        # điểm đến giống "hồ sơ điểm đến" của khách (trung bình centroid các điểm đến đã đi/đang xem, trọng số event)
        prof = np.zeros(w.E.shape[1])
        for e in user["events"]:
            i = w.i_of.get(e["productId"])
            if i is not None:
                prof += W_EVENT.get(e["eventName"], .3) * w.centroid[w.dest[i]]
        prof /= max(np.linalg.norm(prof), 1e-9)
        dsc = {d: float(c @ prof) for d, c in w.centroid.items()}
        s = np.array([dsc.get(d, 0.0) for d in w.dest]) * 2.0 + 0.5 * (w.E @ ulong)
        if how == "destsim_pop":
            s = s + 0.15 * pop
    else:
        raise ValueError(how)
    s = np.where(ok, s, -np.inf)
    out, seen_d = [], set()
    for i in np.argsort(-s):
        if not np.isfinite(s[i]) or len(out) >= n_items:
            break
        if w.dest[i] in seen_d:
            continue
        seen_d.add(w.dest[i]); out.append(int(i))
    return out


def theme_prec(w, items, theme, skip_dest=()):
    xs = [w.dest[i] for i in items if w.dest[i] not in skip_dest and THEME_OF.get(w.dest[i], "mixed") != "mixed"]
    return (sum(THEME_OF[d] == theme for d in xs) / len(xs)) if xs else None


def run(args):
    idx, vec = load_index(args.vec)
    events = load_events()
    purchases = [e for e in events if e["eventName"] == "purchase" and parse_ts(e["timestamp"]) < AS_OF]
    w = World(idx, vec, purchases)
    eng_prod = OfflineEngine(idx, vec, purchases, mode="prod")
    eng_eval = OfflineEngine(idx, vec, purchases, mode="eval")
    rng = random.Random(args.seed)
    rows = []
    for scen in ("between", "open"):
        for theme in ("beach", "mountain", "city"):
            for n in range(args.n):
                user = make_user(w, rng, f"SYN-{scen[0]}{theme[0]}{n:04d}", theme, scen)
                r4 = eng_prod.recommend(user["uid"], AS_OF, 4, user["events"])
                r20 = eng_eval.recommend(user["uid"], AS_OF, 20, user["events"])
                ids4 = [w.i_of[x["productId"]] for x in r4["recommendations"] if x["productId"] in w.i_of]
                ids20 = [w.i_of[x["productId"]] for x in r20["recommendations"] if x["productId"] in w.i_of]
                bought = w.idx.purchase_closure({u for u in (w.idx.resolve(e["productId"]) for e in user["events"]
                                                      if e["eventName"] == "purchase") if u is not None})
                u = user_vectors(w, user["events"], AS_OF)
                cur = {r4.get("destination")} if r4.get("destination") else set()
                row = {"scen": scen, "theme": theme, "next": user["next"], "strategy": r4["strategy"],
                       "engine_dest": r4.get("destination"), "past": user["past"],
                       "V0_k4": ids4, "V0_k20": ids20, "target": user["target"], "open": user["open"]}
                for how in ("ulong", "ushort", "blend", "destsim", "destsim_pop"):
                    for nx in (1, 2):
                        ex = explore(w, u, user, cur | {user["past"][-1]} if scen == "between" else cur, bought, nx, how, AS_OF)
                        row[f"{how}_x{nx}"] = ex
                rows.append(row)
    return w, rows


def report(w, rows):
    out = {}
    for scen in ("between", "open"):
        R = [r for r in rows if r["scen"] == scen]
        res = {"n": len(R), "strategies": dict(collections.Counter(r["strategy"] for r in R))}
        def agg(key, fn):
            vals = [fn(r) for r in R]; vals = [v for v in vals if v is not None]
            return round(float(np.mean(vals)), 3) if vals else None
        # V0
        res["V0_k4_themePrec"] = agg("", lambda r: theme_prec(w, r["V0_k4"], r["theme"]))
        res["V0_k4_otherDestShare"] = agg("", lambda r: np.mean([w.dest[i] != r["engine_dest"] for i in r["V0_k4"]]) if r["V0_k4"] else None)
        res["V0_k4_nextDestHit"] = agg("", lambda r: float(any(w.dest[i] == r["next"] for i in r["V0_k4"])))
        res["V0_k20_nextDestHit"] = agg("", lambda r: float(any(w.dest[i] == r["next"] for i in r["V0_k20"])))
        res["V0_k20_targetHit"] = agg("", lambda r: float(r["target"] in r["V0_k20"]))
        res["V0_k20_themePrec"] = agg("", lambda r: theme_prec(w, r["V0_k20"], r["theme"]))
        res["V0_k4_openItemRepeat"] = agg("", lambda r: float(any(i in r["open"] for i in r["V0_k4"])) if r["open"] else None)
        for how in ("ulong", "ushort", "blend", "destsim", "destsim_pop"):
            for nx in (1, 2):
                k = f"{how}_x{nx}"
                res[f"{k}_themePrec"] = agg("", lambda r: theme_prec(w, r[k], r["theme"]))
                if scen == "between":
                    res[f"{k}_nextDestHit"] = agg("", lambda r: float(any(w.dest[i] == r["next"] for i in r[k])))
                res[f"{k}_distinctDests"] = agg("", lambda r: len({w.dest[i] for i in r[k]}))
        # mốc ngẫu nhiên có trọng số kích thước: tỷ lệ điểm đến cùng chủ đề
        res["random_dest_themePrec"] = agg("", lambda r: sum(math.sqrt(w.dest_size[d]) for d in w.dests if THEME_OF[d] == r["theme"])
                                            / sum(math.sqrt(w.dest_size[d]) for d in w.dests))
        out[scen] = res
    by_theme = {}
    for scen in ("between", "open"):
        for th in ("beach", "mountain", "city"):
            R = [r for r in rows if r["scen"] == scen and r["theme"] == th]
            f = lambda key: round(float(np.mean([v for v in (theme_prec(w, r[key], th) for r in R) if v is not None])), 3)
            by_theme[f"{scen}/{th}"] = {"V0_k4": f("V0_k4"), "ulong_x1": f("ulong_x1"), "blend_x1": f("blend_x1"),
                                       "destsim_x1": f("destsim_x1"), "destsim_pop_x1": f("destsim_pop_x1")}
    out["themePrec_by_theme"] = by_theme
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True, help="npy:<prefix> hoặc nguồn khác của load_index")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="theme_rows.json")
    a = ap.parse_args()
    w, rows = run(a)
    json.dump([{k: v for k, v in r.items()} for r in rows], open(a.out, "w"), default=lambda o: int(o) if isinstance(o, np.integer) else str(o))
    print(json.dumps(report(w, rows), ensure_ascii=False, indent=1))
