"""Ba kịch bản khách giả lập cho thang OPH-L (plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §5.1 mục 8) — tách khỏi
`theme_exp.py` để bộ khách `between` / `open` / `noisy_paired` cũ giữ y nguyên từng byte. Mỗi kịch bản có luồng rng riêng
`seed · 1_000_003 + k`, nên thêm / bỏ kịch bản không xê dịch kịch bản khác.

- `booked_browse` (conformance cho O3, sửa I-3): lịch sử `between` + một chuyến đã mua (khách sạn ở X, có `eventGroupId`, mua
  5–30 ngày trước, `usingDate` = AS_OF + 5…30 ngày) + 2–4 lượt xem sau đó, cách 1–72 giờ (50 % ở X, 50 % ở điểm đến khác).
  Đích = điểm tham quan hoặc route bay tới X. Đo `tgtHit@4`, `xvAtX@4` (tỷ lệ món ở X có taxonomy chưa mua), `strategy`.
- `session_multi` (conformance cho O4): lịch sử `between` + 3–5 lượt xem lẻ trong 14 ngày rải trên hai điểm đến; điểm đến đa số
  có là điểm đến của lượt xem **mới nhất** hay không được ngẫu nhiên hoá (`majIsNewest`). Đích = khách sạn ở điểm đến đa số,
  **không** trùng món đã xem. `next` = điểm đến đa số.
- `dormant` (N2/N3): như `between` nhưng mọi chuyến cách 200–600 ngày (ngưỡng dormant đã chốt 365 ngày).

Nhãn chủ đề chỉ dùng để sinh và chấm điểm, engine không đọc.
"""
from __future__ import annotations

import random
from datetime import timedelta

from src.evaluation.recsys_bench.theme_study import theme_exp as TE

STREAM = {"booked_browse": 31, "session_multi": 37, "dormant": 41}
NEW_SCENARIOS = tuple(STREAM)


def _ev(w, uid, name, ts, i, gid=None, using=None):
    return {"cdpUserId": uid, "eventName": name, "timestamp": TE.iso(ts), "productId": w.pid[i], "taxonomy": w.tax[i],
            "eventGroupId": gid, "quantity": 1 if name == "purchase" else None, "unitPrice": None,
            "usingDate": using.date().isoformat() if using is not None else None}


def _pick_excluding(w, rng, dest, tax, exclude):
    cand = [i for i in w.by.get((dest, tax)) or [] if i not in exclude]
    if not cand:
        return None
    return cand[int(rng.choices(range(len(cand)), weights=[w.pop[i] + 1.0 for i in cand])[0])]


def booked_browse(w, rng, uid, theme):
    u = TE.make_user(w, rng, uid, theme, "between")
    now = TE.AS_OF
    x = w.pick_dest(rng, theme, exclude=u["past"][-1:])
    hotel = w.pick(rng, x, "hotel")
    t_buy = now - timedelta(days=rng.randint(5, 30))
    use = now + timedelta(days=rng.randint(5, 30))
    ev = list(u["events"]) + [_ev(w, uid, "purchase", t_buy, hotel, gid=f"{uid}-bk", using=use)]
    for _ in range(rng.randint(2, 4)):
        at_x = rng.random() < 0.5
        d = x if at_x else w.pick_dest(rng, theme, exclude=[x])
        i = w.pick(rng, d, rng.choice(["hotel", "attraction"])) or w.pick(rng, d, "hotel")
        ev.append(_ev(w, uid, "product_view", now - timedelta(hours=rng.randint(1, 72)), i))
    tax = rng.choice(["attraction", "flight"])
    target = w.pick(rng, x, tax) or w.pick(rng, x, "attraction") or w.pick(rng, x, "flight")
    ev.sort(key=lambda e: e["timestamp"])
    return {**u, "scenario": "booked_browse", "next": x, "target": target, "boughtTax": ["hotel"], "events": ev}


def session_multi(w, rng, uid, theme):
    u = TE.make_user(w, rng, uid, theme, "between")
    now = TE.AS_OF
    a = w.pick_dest(rng, theme, exclude=u["past"][-1:])
    b = w.pick_dest(rng, theme, exclude=[a])
    n = rng.randint(3, 5)
    n_a = n // 2 + 1
    maj_newest = rng.random() < 0.5
    hours = sorted(rng.sample(range(1, 14 * 24), n))                   # [0] = mới nhất
    dests = [a] * n_a + [b] * (n - n_a)
    rng.shuffle(dests)
    newest_want = a if maj_newest else b
    j = dests.index(newest_want)
    dests[0], dests[j] = dests[j], dests[0]
    viewed = set()
    ev = list(u["events"])
    for h, d in zip(hours, dests):
        i = w.pick(rng, d, rng.choice(["hotel", "attraction"])) or w.pick(rng, d, "hotel")
        viewed.add(i)
        ev.append(_ev(w, uid, "product_view", now - timedelta(hours=h), i))
    target = _pick_excluding(w, rng, a, "hotel", viewed)
    ev.sort(key=lambda e: e["timestamp"])
    return {**u, "scenario": "session_multi", "next": a, "target": target, "majIsNewest": maj_newest, "events": ev}


def dormant(w, rng, uid, theme):
    """`theme_exp.make_user` với mọi chuyến 200–600 ngày trước (thay vì 60–420)."""
    now = TE.AS_OF
    ev, past = [], []
    n = rng.choice([2, 3])
    for k, days in enumerate(sorted(rng.sample(range(200, 600), n), reverse=True)):
        d = w.pick_dest(rng, theme, exclude=past[-1:])
        past.append(d)
        t_buy = now - timedelta(days=days)
        use = t_buy + timedelta(days=rng.randint(7, 30))
        for _ in range(rng.randint(1, 3)):
            i = w.pick(rng, d, rng.choice(["hotel", "attraction"])) or w.pick(rng, d, "hotel")
            ev.append(_ev(w, uid, "product_view", t_buy - timedelta(hours=rng.randint(2, 96)), i))
        for tax in ["hotel"] + (["attraction"] if rng.random() < 0.5 else []):
            i = w.pick(rng, d, tax)
            if i is not None:
                ev.append(_ev(w, uid, "purchase", t_buy + timedelta(minutes=rng.randint(1, 60)), i, gid=f"{uid}-t{k}",
                              using=use))
    nxt = w.pick_dest(rng, theme, exclude=past[-1:])
    ev.sort(key=lambda e: e["timestamp"])
    return {"uid": uid, "theme": theme, "scenario": "dormant", "past": past, "next": nxt, "target": w.pick(rng, nxt, "hotel"),
            "open": [], "events": ev}


MAKERS = {"booked_browse": booked_browse, "session_multi": session_multi, "dormant": dormant}


def make_users(w, scenario: str, seed: int, n_per_theme: int) -> list[dict]:
    rng = random.Random(seed * 1_000_003 + STREAM[scenario])
    out = []
    for th in ("beach", "mountain", "city"):
        for n in range(n_per_theme):
            u = MAKERS[scenario](w, rng, f"SYN{seed}-{scenario[:2]}{th[0]}{n:04d}", th)
            if u["target"] is None:                          # World.pick trả None khi pool (điểm đến, taxonomy) rỗng
                continue
            u["seed"] = seed
            out.append(u)
    return out
