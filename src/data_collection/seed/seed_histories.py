"""Seed lịch sử khách hàng cho CDP clone: `cdp.profiles`, `cdp.events`, cùng `app.users` / `app.bookings` / `app.booking_items` cho 4 persona.

Theo "Kế hoạch mock data" trong file thiết kế DB của nhóm (20/09/2026). **Không sửa products.jsonl**; đầu ra là file để nạp vào DB.

    python seed_histories.py [--data-dir data] [--out-dir data/seed] [--as-of YYYY-MM-DD] [--seed 42] [--profiles 2000]

Quy tắc theo file (mọi con số là tham số, đổi được khi Evaluation chốt việc #11):
  * 2.000 profile, cdp_user_id "VP" + 7 số; 1–5 event/năm/khách trải 24 tháng (~7.000 event), không ai quá 15 event.
  * Vòng đời TÍNH TỪ event (không sinh độc lập): new = ≤ 2 event; còn lại theo số ngày từ lần đặt cuối: ≤ 180 active, 181–365 dormant, > 365 churned.
    Tỷ lệ đích: new 25% · active 45% · dormant 20% · churned 10% (còn lại là "new" có đặt chỗ).
  * Chuyến đi = một event_group_id ("OFF" + yyyymmdd + số thứ tự), một điểm đến; thứ tự hotel → flight → attraction/combo/golf; 65% chuyến
    có ≥ 2 loại; using_date cùng khoảng ngày; product_view đi trước purchase 0–7 ngày.
  * Độ phổ biến theo phân phối luỹ thừa (Zipf s mặc định = 0,8) trên sản phẩm ĐẶT ĐƯỢC trong từng điểm đến; Vinpearl được nâng trọng số.
  * Cạnh lộn xộn: 5% profile email_optin = false; 2% event trỏ product_id không tồn tại; 3% purchase thiếu event_group_id.
  * VinClub: Member 60% · Gold 25% · Platinum 10% · Diamond 5%; home_city từ 8 thành phố lớn.
  * 4 persona (UX spec §2): P1 Minh Anh (3 chuyến Nha Trang + 1 chuyến sắp tới đã đặt khách sạn, chưa có vé bay), P2 Quốc Bảo (2 product_view
    tuần qua), P3 Thu Hà (2 chuyến Phú Quốc, chuyến cuối ~6 tháng trước), P4 khách mới (0 event). Kèm 50 tài khoản test.
Mọi thứ có ngày sinh tương đối theo --as-of. Kết quả xác định theo --seed.
Mọi app.users dùng chung BCrypt cost 10 của mật khẩu demo `Demo@2026`; email / số điện thoại là dữ liệu giả.
"""
from __future__ import annotations

import argparse
import bisect
import json
import random
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .catalog_meta import build_meta, is_vinpearl, open_nights, room_calendar, variant
from .config import DEFAULT_ZIPF

NS = uuid.UUID("6f3b1f0e-8a52-4c1e-9d0a-7a0c5b1d2e77")  # không gian tên cố định cho uuid5 (seed)
HOME_CITIES = [("Hà Nội", 30), ("TP. Hồ Chí Minh", 30), ("Đà Nẵng", 10), ("Hải Phòng", 6), ("Cần Thơ", 6), ("Huế", 5), ("Nha Trang", 5), ("Đà Lạt", 4)]
TIERS = [("Member", 60), ("Gold", 25), ("Platinum", 10), ("Diamond", 5)]
VINPEARL_DESTS = {"Nha Trang", "Phú Quốc"}
DEMO_PASSWORD_HASH = "$2b$10$pNkZJv0LGcI21m4ThFX8l.0SDw.9BryHuyzbmXMifCcRPQP9kHICa"


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(str(p) for p in parts)))


class Sampler:
    """Chọn phần tử theo Zipf trên thứ hạng ngẫu nhiên cố định; Vinpearl nhân thêm hệ số."""

    def __init__(self, items: list[dict], key: str, seed: int, s: float, boost: float):
        order = sorted(items, key=lambda r: r["productId"])
        random.Random(f"{seed}|zipf|{key}").shuffle(order)
        self.items = order
        w = [(boost if is_vinpearl(r) else 1.0) / ((i + 1) ** s) for i, r in enumerate(order)]
        self.cum = []
        t = 0.0
        for x in w:
            t += x
            self.cum.append(t)

    def pick(self, rng: random.Random) -> dict:
        return self.items[min(bisect.bisect_left(self.cum, rng.random() * self.cum[-1]), len(self.items) - 1)]


class World:
    def __init__(self, rows: list[dict], as_of: date, seed: int, zipf: float, boost: float):
        self.rows, self.as_of, self.seed = rows, as_of, seed
        self.by_id = {r["productId"]: r for r in rows}
        self.meta = build_meta(rows)
        rooms: dict[str, list[dict]] = defaultdict(list)
        self.flights: dict[tuple[str, str], list[dict]] = defaultdict(list)
        buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in rows:
            v = variant(r)
            if not self.meta[r["productId"]]["is_bookable"]:
                continue
            if v == "hotel_room":
                rooms[r["attributes"]["parentProductId"]].append(r)
            elif v == "flight":
                route = self.by_id.get(r["attributes"].get("parentProductId"))
                self.flights[(r["destination"], (route or r)["attributes"].get("originDestination") or "")].append(r)
            else:
                buckets[(r["destination"], v)].append(r)
        props: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if variant(r) == "hotel_property" and rooms.get(r["productId"]):
                props[r["destination"]].append(r)
        self.rooms = {pid: Sampler(rs, f"rooms|{pid}", seed, 0.8, 1.0) for pid, rs in rooms.items()}
        self.hotels = {d: Sampler(ps, f"hotels|{d}", seed, zipf, boost) for d, ps in props.items()}
        self.flight_pick = {k: Sampler(v, f"flights|{k}", seed, zipf, boost) for k, v in self.flights.items()}
        self.tickets = {k: Sampler(v, f"{k}", seed, zipf, boost) for k, v in buckets.items()}
        weight = {d: (len(ps) ** 0.7) * (1.5 if d in VINPEARL_DESTS else 1.0) for d, ps in props.items()}
        self.dest_names = sorted(weight)
        self.dest_cum = []
        t = 0.0
        for d in self.dest_names:
            t += weight[d]
            self.dest_cum.append(t)

    def destination(self, rng: random.Random) -> str:
        return self.dest_names[min(bisect.bisect_left(self.dest_cum, rng.random() * self.dest_cum[-1]), len(self.dest_names) - 1)]

    KIND_WEIGHT = {"attraction": 0.62, "combo": 0.28, "golf": 0.10}

    def pick_ticket(self, rng: random.Random, dest: str, kinds: tuple[str, ...]) -> dict | None:
        options = [k for k in kinds if (dest, k) in self.tickets]
        if not options:
            return None
        kind = rng.choices(options, [self.KIND_WEIGHT.get(k, 0.5) for k in options])[0]
        return self.tickets[(dest, kind)].pick(rng)

    def supports_multi(self, dest: str, home: str) -> bool:
        """Điểm đến có khách sạn và ít nhất một loại khác (vé bay từ home_city, điểm tham quan, combo, golf)."""
        return dest in self.hotels and ((dest, home) in self.flight_pick or any((dest, k) in self.tickets for k in ("attraction", "combo", "golf")))

    def pick_flight(self, rng: random.Random, dest: str, home: str) -> dict | None:
        s = self.flight_pick.get((dest, home))
        return s.pick(rng) if s else None


# ------------------------------------------------------------------ chuyến đi
def plan_items(w: World, rng: random.Random, dest: str, home: str, start: date, verticals: list[str]) -> list[dict]:
    """Các dòng đặt của một chuyến, theo thứ tự hotel → flight → attraction/combo/golf."""
    items: list[dict] = []
    nights = rng.choice([1, 2, 2, 3, 3, 4, 5])
    for v in verticals:
        if v == "hotel":
            prop = w.hotels[dest].pick(rng)
            room = w.rooms[prop["productId"]].pick(rng)
            items.append({"product": room, "view": prop, "quantity": nights, "using_date": start, "using_date_to": start + timedelta(days=nights)})
        elif v == "flight":
            f = w.pick_flight(rng, dest, home)
            if f:
                items.append({"product": f, "view": w.by_id.get(f["attributes"]["parentProductId"], f), "quantity": rng.choice([1, 1, 2, 3]),
                              "using_date": start, "using_date_to": None})
        else:
            t = w.pick_ticket(rng, dest, ("attraction", "combo", "golf") if v == "extra" else (v,))
            if t:
                items.append({"product": t, "view": t, "quantity": rng.choice([1, 2, 2, 3, 4]) if t["taxonomy"] != "golf" else rng.choice([1, 2, 4]),
                              "using_date": start + timedelta(days=rng.randint(0, max(0, nights - 1))), "using_date_to": None})
    return items


def choose_verticals(w: World, rng: random.Random, dest: str, home: str, want_multi: bool) -> list[str]:
    can_flight = (dest, home) in w.flight_pick
    can_extra = any((dest, k) in w.tickets for k in ("attraction", "combo", "golf"))
    if want_multi:  # ≥ 2 loại
        v = ["hotel"]
        if can_flight and (rng.random() < 0.55 or not can_extra):
            v.append("flight")
        if can_extra and (len(v) == 1 or rng.random() < 0.30):
            v.append("extra")
        return v
    r = rng.random()
    if r < 0.72 or not can_extra:
        return ["hotel"]
    return ["extra"] if r < 0.94 or not can_flight else ["flight"]


class Builder:
    def __init__(self, w: World, seed: int):
        self.w, self.events, self.bookings, self.booking_items = w, [], [], []
        self.seq: Counter = Counter()
        self.seed = seed

    def group_id(self, purchased: datetime) -> str:
        d = purchased.strftime("%Y%m%d")
        self.seq[d] += 1
        return f"OFF{d}{self.seq[d]:03d}"

    def add_trip(self, user: str, rng: random.Random, dest: str, home: str, purchased: datetime, start: date, verticals: list[str],
                 add_to_cart: float = 0.20, comparison_views: bool = True) -> list[dict]:
        items = plan_items(self.w, rng, dest, home, start, verticals)
        if not items:
            return []
        gid = self.group_id(purchased)
        for k, it in enumerate(items):
            p = it["product"]
            ts = purchased + timedelta(seconds=90 * k)
            view_ts = purchased - timedelta(days=rng.uniform(0, 7), hours=rng.uniform(0, 3)) + timedelta(seconds=k)
            if it["view"]["taxonomy"] == "hotel" or rng.random() < 0.55:  # xem trước khi đặt (khách sạn luôn xem; loại khác 55%)
                self.events.append(self.event(user, "product_view", view_ts, it["view"], None, None, None, None))
            if it["view"]["taxonomy"] == "hotel" and comparison_views:  # xem thêm 0–2 khách sạn khác trong cùng điểm đến trước khi chốt
                for _ in range(rng.choice([0, 0, 0, 1])):
                    other = self.w.hotels[it["view"]["destination"]].pick(rng)
                    if other["productId"] != it["view"]["productId"]:
                        t = purchased - timedelta(days=rng.uniform(0, 7), hours=rng.uniform(0, 3))
                        self.events.append(self.event(user, "product_view", t, other, None, None, None, None))
            if rng.random() < add_to_cart:
                mid = view_ts + (ts - view_ts) * rng.uniform(0.3, 0.95)
                self.events.append(self.event(user, "add_to_cart", mid, p, gid, it["quantity"], p["unitPrice"], it["using_date"]))
            self.events.append(self.event(user, "purchase", ts, p, gid, it["quantity"], p["unitPrice"], it["using_date"]))
        return items

    @staticmethod
    def event(user, name, ts, product, gid, qty, price, using):
        return {"cdp_user_id": user, "event_name": name, "timestamp": ts, "product_id": product["productId"], "taxonomy": product["taxonomy"],
                "event_group_id": gid, "quantity": qty, "unit_price": price, "using_date": using.isoformat() if using else None}


def at(day: date, rng: random.Random) -> datetime:
    return datetime(day.year, day.month, day.day, rng.randint(8, 22), rng.randint(0, 59), rng.randint(0, 59), tzinfo=timezone.utc)


def dt_iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ vòng đời
def lifecycle(events: list[dict], as_of: date) -> tuple[str, int | None]:
    buys = [e for e in events if e["event_name"] == "purchase"]
    days = (as_of - max(e["timestamp"] for e in buys).date()).days if buys else None
    if len(events) <= 2 or days is None:
        return "new", days
    return ("active" if days <= 180 else "dormant" if days <= 365 else "churned"), days


def stage_plan(n_profiles: int, mix: tuple[float, float, float, float]) -> list[str]:
    """Số khách mỗi giai đoạn đúng tỷ lệ (làm tròn, phần dư vào active)."""
    counts = [round(n_profiles * m) for m in mix]
    counts[1] += n_profiles - sum(counts)
    return ["new"] * counts[0] + ["active"] * counts[1] + ["dormant"] * counts[2] + ["churned"] * counts[3]


def plan_generic(w: World, b: Builder, rng: random.Random, user: str, stage: str, home: str, as_of: date) -> None:
    """Một khách thường: sinh chuyến theo giai đoạn (lifecycle_stage sẽ được tính lại từ event)."""
    def trip(days_ago: int):
        # điểm đặt cách đây days_ago ngày; chuyến diễn ra sau đó 3–40 ngày nhưng không quá hôm qua
        purchased_day = as_of - timedelta(days=days_ago)
        start = min(purchased_day + timedelta(days=rng.randint(3, 40)), as_of - timedelta(days=1))
        want_multi = rng.random() < 0.75
        dest = w.destination(rng)
        for _ in range(30):  # chuyến nhiều loại thì chọn điểm đến có đủ sản phẩm
            if not want_multi or w.supports_multi(dest, home):
                break
            dest = w.destination(rng)
        return b.add_trip(user, rng, dest, home, at(purchased_day, rng), max(start, purchased_day + timedelta(days=1)),
                          choose_verticals(w, rng, dest, home, want_multi and w.supports_multi(dest, home)))

    if stage == "new":
        r = rng.random()
        if r < 0.40:
            return
        if r < 0.80:  # chỉ xem
            for _ in range(rng.randint(1, 2)):
                dest = w.destination(rng)
                prop = w.hotels[dest].pick(rng)
                b.events.append(b.event(user, "product_view", at(as_of - timedelta(days=rng.randint(1, 90)), rng), prop, None, None, None, None))
            return
        dest = w.destination(rng)  # một lần đặt một loại: view + purchase = 2 event
        purchased_day = as_of - timedelta(days=rng.randint(10, 90))
        b.add_trip(user, rng, dest, home, at(purchased_day, rng), min(purchased_day + timedelta(days=rng.randint(3, 30)), as_of - timedelta(days=1)),
                   ["hotel"], add_to_cart=0.0, comparison_views=False)
        return
    last = {"active": (10, 170), "dormant": (185, 360), "churned": (370, 690)}[stage]
    n_trips = {"active": rng.choices([1, 2, 3], [0.78, 0.19, 0.03])[0], "dormant": rng.choices([1, 2], [0.85, 0.15])[0],
               "churned": rng.choices([1, 2], [0.88, 0.12])[0]}[stage]
    days_ago = rng.randint(*last)
    for _ in range(n_trips):
        trip(days_ago)
        days_ago += rng.randint(75, 260)
        if days_ago > 700:
            break
    mine = [e for e in b.events if e["cdp_user_id"] == user]
    while len(mine) <= 2:  # đã đặt chỗ thì phải có > 2 event, nếu không vòng đời tính từ event sẽ thành "new": thêm lần xem so sánh
        buy = next((e for e in mine if e["event_name"] == "purchase"), None)
        dest = w.by_id[buy["product_id"]]["destination"] if buy and buy["product_id"] in w.by_id else w.destination(rng)
        t = (buy["timestamp"] if buy else at(as_of - timedelta(days=days_ago), rng)) - timedelta(days=rng.uniform(0, 6))
        b.events.append(b.event(user, "product_view", t, w.hotels[dest].pick(rng), None, None, None, None))
        mine = [e for e in b.events if e["cdp_user_id"] == user]


def cap_events(evs: list[dict], limit: int) -> list[dict]:
    """Không quá `limit` event/khách: bỏ add_to_cart trước, rồi product_view cũ nhất."""
    if len(evs) <= limit:
        return evs
    for name in ("add_to_cart", "product_view"):
        cand = sorted((e for e in evs if e["event_name"] == name), key=lambda e: e["timestamp"])
        while len(evs) > limit and cand:
            evs.remove(cand.pop(0))
    return evs


# ------------------------------------------------------------------ persona
PERSONAS = [
    ("VP0000001", "P1_frequent", "Minh Anh", "minh.anh@example.com", "TP. Hồ Chí Minh", "Gold"),
    ("VP0000002", "P2_first_time", "Quốc Bảo", "quoc.bao@example.com", "Hà Nội", "Member"),
    ("VP0000003", "P3_dormant", "Thu Hà", "thu.ha@example.com", "Hà Nội", "Member"),
    ("VP0000004", "P4_no_history", "Khách mới", "khach.moi@example.com", "Đà Nẵng", "Member"),
]


def seed_personas(w: World, b: Builder, rng: random.Random, as_of: date) -> dict:
    info: dict = {}
    dest = "Nha Trang"
    for days_ago in (520, 300, 125):  # P1: 3 chuyến Nha Trang trong 18 tháng (khách sạn + điểm tham quan)
        day = as_of - timedelta(days=days_ago)
        b.add_trip("VP0000001", rng, dest, "TP. Hồ Chí Minh", at(day, rng), day + timedelta(days=rng.randint(5, 20)), ["hotel", "attraction"], add_to_cart=0.0, comparison_views=False)
    # chuyến sắp tới: đã đặt khách sạn (chưa có vé bay), đêm ở nằm trong cửa sổ và còn trống
    prop_sampler = w.hotels[dest]
    for attempt in range(400):
        prop = prop_sampler.pick(rng)
        room = w.rooms[prop["productId"]].pick(rng)
        cal = room_calendar(room, as_of)
        start = as_of + timedelta(days=rng.randint(8, 20))
        nights = rng.choice([2, 3])
        if open_nights(cal, as_of, start, nights):
            break
    else:
        raise SystemExit("Không tìm được hạng phòng Nha Trang còn trống cho chuyến sắp tới của P1")
    purchased = at(as_of - timedelta(days=2), rng)
    gid = b.group_id(purchased)
    b.events.append(b.event("VP0000001", "product_view", purchased - timedelta(days=1, hours=3), prop, None, None, None, None))
    b.events.append(b.event("VP0000001", "add_to_cart", purchased - timedelta(minutes=20), room, gid, nights, room["unitPrice"], start))
    b.events.append(b.event("VP0000001", "purchase", purchased, room, gid, nights, room["unitPrice"], start))
    booking_id = uid("booking", gid)
    total = room["unitPrice"] * nights
    b.bookings.append({"booking_id": booking_id, "reference_code": f"VOTA-{start.strftime('%Y%m%d')}-{uid('ref', gid)[:4].upper()}",
                       "cdp_user_id": "VP0000001", "event_group_id": gid, "status": "confirmed", "contact_name": "Minh Anh",
                       "contact_email": "minh.anh@example.com", "contact_phone": "0900000001", "special_request": None,
                       "total_amount": total, "currency": "VND", "created_at": dt_iso(purchased)})
    b.booking_items.append({"booking_item_id": uid("item", gid, room["productId"]), "booking_id": booking_id, "product_id": room["productId"],
                            "taxonomy": "hotel", "product_name": room["name"], "unit_price": room["unitPrice"], "quantity": nights,
                            "using_date": start.isoformat(), "using_date_to": (start + timedelta(days=nights)).isoformat(),
                            "guest_names": ["Minh Anh"], "line_total": total})
    info["P1_upcoming"] = {"room": room["name"], "using_date": start.isoformat(), "nights": nights, "event_group_id": gid}

    dest2 = "Đà Lạt" if "Đà Lạt" in w.hotels else w.destination(rng)  # P2: 2 lần xem trong tuần qua
    seen = set()
    while len(seen) < 2:
        seen.add(w.hotels[dest2].pick(rng)["productId"])
    for k, pid in enumerate(sorted(seen)):
        b.events.append(b.event("VP0000002", "product_view", at(as_of - timedelta(days=1 + 2 * k), rng), w.by_id[pid], None, None, None, None))

    for days_ago in (470, 205):  # P3: 2 chuyến Phú Quốc, chuyến cuối ~6 tháng trước
        day = as_of - timedelta(days=days_ago)
        b.add_trip("VP0000003", rng, "Phú Quốc", "Hà Nội", at(day, rng), day + timedelta(days=rng.randint(5, 20)), ["hotel", "extra"],
                   add_to_cart=0.0, comparison_views=False)
    return info


# ------------------------------------------------------------------ chính
def pick_weighted(rng: random.Random, pairs: list[tuple[str, int]]) -> str:
    return rng.choices([p[0] for p in pairs], [p[1] for p in pairs])[0]


def generate(rows: list[dict], as_of: date, seed: int = 42, n_profiles: int = 2000, zipf: float = DEFAULT_ZIPF, boost: float = 2.0,
             mix: tuple[float, float, float, float] = (0.25, 0.45, 0.20, 0.10), max_events: int = 15) -> dict:
    w = World(rows, as_of, seed, zipf, boost)
    b = Builder(w, seed)
    rng = random.Random(f"{seed}|seed")
    persona_info = seed_personas(w, b, random.Random(f"{seed}|personas"), as_of)

    ids = set()
    while len(ids) < n_profiles - len(PERSONAS):
        ids.add(f"VP{rng.randint(100000, 9999999):07d}")
    generic_ids = sorted(ids)
    stages = stage_plan(n_profiles - len(PERSONAS), mix)
    rng.shuffle(stages)
    homes: dict[str, str] = {p[0]: p[4] for p in PERSONAS}
    tiers: dict[str, str] = {p[0]: p[5] for p in PERSONAS}
    for user, stage in zip(generic_ids, stages):
        homes[user] = pick_weighted(rng, HOME_CITIES)
        tiers[user] = pick_weighted(rng, TIERS)
        plan_generic(w, b, random.Random(f"{seed}|{user}"), user, stage, homes[user], as_of)

    by_user: dict[str, list[dict]] = defaultdict(list)
    for e in b.events:
        by_user[e["cdp_user_id"]].append(e)
    b.events = []
    for user in list(homes):
        evs = sorted(by_user.get(user, []), key=lambda e: e["timestamp"])
        if user not in {p[0] for p in PERSONAS}:
            evs = cap_events(evs, max_events)
        by_user[user] = evs
        b.events.extend(evs)

    # Cạnh lộn xộn (không áp cho persona): 5% email_optin=false, 2% product_id không tồn tại,
    # 3% purchase thiếu event_group_id. Tỷ lệ cuối phải <= 4% theo db/verify.sql.
    persona_ids = {p[0] for p in PERSONAS}
    noisy = [e for e in b.events if e["cdp_user_id"] not in persona_ids]
    mrng = random.Random(f"{seed}|messy")
    for e in mrng.sample(noisy, round(0.02 * len(noisy))):
        e["product_id"] = uid("deleted-product", e["product_id"], e["timestamp"])
    grouped_purchases = [e for e in noisy if e["event_name"] == "purchase" and e["event_group_id"]]
    for e in mrng.sample(grouped_purchases, round(0.03 * len(grouped_purchases))):
        e["event_group_id"] = None
    optout = set(mrng.sample(generic_ids, round(0.05 * len(generic_ids))))

    b.events.sort(key=lambda e: (e["timestamp"], e["cdp_user_id"], e["event_name"]))
    for i, e in enumerate(b.events, 1):
        e["event_id"] = i

    profiles = []
    stage_of: dict[str, str] = {}
    for user in list(homes):
        evs = by_user[user]
        stage, days = lifecycle(evs, as_of)
        stage_of[user] = stage
        buys = [e for e in evs if e["event_name"] == "purchase"]
        groups = {e["event_group_id"] or f"solo-{e['event_id']}" for e in buys}
        last_buy = max(buys, key=lambda e: e["timestamp"]) if buys else None
        last_dest = w.by_id[last_buy["product_id"]]["destination"] if last_buy and last_buy["product_id"] in w.by_id else None
        first = evs[0]["timestamp"] if evs else None
        prng = random.Random(f"{seed}|profile|{user}")
        created = (first - timedelta(days=prng.randint(1, 240))) if first else datetime.combine(as_of - timedelta(days=prng.randint(20, 900)), datetime.min.time(), tzinfo=timezone.utc)
        profiles.append({"cdp_user_id": user, "lifecycle_stage": stage, "days_since_last_booking": days, "lifetime_order_count": len(groups),
                         "vinclub_tier": tiers[user], "purchased_verticals": sorted({e["taxonomy"] for e in buys}), "home_city": homes[user],
                         "last_destination": last_dest, "email_optin": user not in optout,
                         "sms_optin": prng.random() < 0.7, "push_optin": prng.random() < 0.6,
                         "created_at": dt_iso(created), "updated_at": dt_iso(max([created] + [e["timestamp"] for e in evs]))})
    profiles.sort(key=lambda p: p["cdp_user_id"])

    users = []
    persona_by_id = {p[0]: p for p in PERSONAS}
    for user in [p[0] for p in PERSONAS] + generic_ids[:50]:
        p = persona_by_id.get(user)
        n = len(users) - len(PERSONAS) + 1
        users.append({"user_id": uid("user", user), "email": p[3] if p else f"test{n:02d}@vota.demo", "password_hash": DEMO_PASSWORD_HASH,
                      "display_name": p[2] if p else f"Khách test {n:02d}", "cdp_user_id": user, "persona": p[1] if p else None,
                      "created_at": next(q["created_at"] for q in profiles if q["cdp_user_id"] == user), "last_login_at": None})
    events = [{"event_id": e["event_id"], "cdp_user_id": e["cdp_user_id"], "event_name": e["event_name"], "timestamp": dt_iso(e["timestamp"]),
               "product_id": e["product_id"], "taxonomy": e["taxonomy"], "event_group_id": e["event_group_id"], "quantity": e["quantity"],
               "unit_price": e["unit_price"], "using_date": e["using_date"]} for e in b.events]
    return {"profiles": profiles, "events": events, "users": users, "bookings": b.bookings, "booking_items": b.booking_items,
            "persona": persona_info, "world": w, "stage": stage_of}


def report(res: dict, as_of: date, args: dict) -> tuple[str, dict]:
    ev, pr, w = res["events"], res["profiles"], res["world"]
    n = len(pr)
    per = Counter(e["cdp_user_id"] for e in ev)
    stages = Counter(p["lifecycle_stage"] for p in pr)
    names = Counter(e["event_name"] for e in ev)
    buys = [e for e in ev if e["event_name"] == "purchase"]
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in buys:
        if e["event_group_id"]:
            groups[e["event_group_id"]].append(e)
    multi = sum(1 for g in groups.values() if len({e["taxonomy"] for e in g}) >= 2)
    dests_ok = all(len({w.by_id[e["product_id"]]["destination"] for e in g if e["product_id"] in w.by_id}) <= 1 for g in groups.values())
    by_tax = Counter(e["taxonomy"] for e in buys)
    exist = sum(1 for e in ev if e["product_id"] not in w.by_id)
    # baseline "phổ biến nhất tại điểm đến": ẩn lần đặt cuối của mỗi khách (≥ 2 lần đặt), đoán lại bằng top-20 của điểm đến đó
    last: dict[str, dict] = {}
    hist: dict[str, list[dict]] = defaultdict(list)
    for e in buys:
        if e["cdp_user_id"] in {p[0] for p in PERSONAS} or e["product_id"] not in w.by_id:
            continue
        hist[e["cdp_user_id"]].append(e)
    pop: dict[str, Counter] = defaultdict(Counter)
    for u, es in hist.items():
        es.sort(key=lambda e: e["timestamp"])
        if len({x["event_group_id"] for x in es}) >= 2:
            last[u] = es[-1]
    hidden = {id(e) for e in last.values()}
    for u, es in hist.items():
        for e in es:
            if id(e) not in hidden:
                pop[w.by_id[e["product_id"]]["destination"]][e["product_id"]] += 1
    top20 = {d: {p for p, _ in c.most_common(20)} for d, c in pop.items()}
    hit_by: Counter = Counter()
    tot_by: Counter = Counter()
    for e in last.values():
        tot_by[e["taxonomy"]] += 1
        hit_by[e["taxonomy"]] += e["product_id"] in top20.get(w.by_id[e["product_id"]]["destination"], set())
    hits = sum(hit_by.values())
    top_share = 0.0
    prod = Counter(e["product_id"] for e in buys)
    if prod:
        top = max(1, len(prod) // 10)
        top_share = sum(c for _, c in prod.most_common(top)) / len(buys)
    pers = res["persona"]
    lines = [f"# Kết quả seed_histories — as_of {as_of.isoformat()}, seed {args['seed']}", "",
             f"- Profile: **{n}** · event: **{len(ev)}** ({', '.join(f'{k} {v}' for k, v in names.most_common())}) · "
             f"trung bình {len(ev) / n:.1f} event/khách, nhiều nhất {max(per.values() or [0])} (giới hạn {args['max_events']})",
             "- Vòng đời (tính từ event): " + " · ".join(f"{k} {v} ({100 * v / n:.0f}%)" for k, v in stages.most_common()),
             f"- Chuyến (event_group_id): {len(groups)}; có ≥ 2 loại sản phẩm: {multi} ({100 * multi / max(1, len(groups)):.0f}%); mỗi chuyến đúng một điểm đến: "
             f"{'đạt' if dests_ok else 'KHÔNG đạt'}",
             "- Purchase theo loại: " + " · ".join(f"{k} {v}" for k, v in by_tax.most_common()),
             f"- Độ phổ biến: 10% sản phẩm được đặt nhiều nhất chiếm {100 * top_share:.0f}% số lần đặt",
             f"- Baseline phổ biến nhất tại điểm đến (ẩn lần đặt cuối, top-20): {hits}/{len(last)} = {100 * hits / max(1, len(last)):.1f}% "
             "(spec: không được gần 0 và không được bất khả chiến bại). Theo loại: "
             + " · ".join(f"{k} {100 * hit_by[k] / tot_by[k]:.0f}% ({tot_by[k]})" for k in sorted(tot_by, key=lambda k: -tot_by[k]))
             + " — điểm tham quan / golf gần bão hoà vì mỗi điểm đến chỉ có ít sản phẩm; khách sạn (phần lớn dữ liệu) còn nhiều chỗ để mô hình thắng. "
             "Muốn phân bố phẳng hơn thì giảm `--zipf`.",
             f"- Cạnh lộn xộn: email_optin=false {sum(1 for p in pr if not p['email_optin'])} ({100 * sum(1 for p in pr if not p['email_optin']) / n:.1f}%) · "
             f"event trỏ product_id không tồn tại {exist} ({100 * exist / max(1, len(ev)):.1f}%) · "
             f"purchase thiếu event_group_id {sum(1 for e in buys if e['event_group_id'] is None)}/{len(buys)} "
             f"({100 * sum(1 for e in buys if e['event_group_id'] is None) / max(1, len(buys)):.1f}%)",
             f"- Persona: P1 có chuyến sắp tới đã đặt `{pers['P1_upcoming']['room'][:50]}` ngày {pers['P1_upcoming']['using_date']} "
             f"({pers['P1_upcoming']['nights']} đêm, chưa có vé bay); "
             + " · ".join(f"{p['cdp_user_id']} {p['lifecycle_stage']} ({per.get(p['cdp_user_id'], 0)} event)" for p in pr if p["cdp_user_id"] in {x[0] for x in PERSONAS}),
             f"- app.users: {len(res['users'])} (4 persona + 50 test) · app.bookings: {len(res['bookings'])} · app.booking_items: {len(res['booking_items'])}", "",
             "`app.users.password_hash` là BCrypt cost 10 của mật khẩu demo chung; email / số điện thoại là dữ liệu giả. "
             "Không sinh event `search` (UserEvent search không có sản phẩm; nội dung tìm kiếm nằm ở `app.search_logs`). "
             "Insider clone (`partners`, `insider_profiles`, `identifiers`, `insider_events`, `channel_events`) sinh từ các file này ở bước sau."]
    return "\n".join(lines) + "\n", {"stages": dict(stages), "events": len(ev), "hits": hits, "last": len(last)}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--profiles", type=int, default=2000)
    ap.add_argument("--zipf", type=float, default=DEFAULT_ZIPF)
    ap.add_argument("--vinpearl-boost", type=float, default=2.0)
    ap.add_argument("--max-events", type=int, default=15)
    a = ap.parse_args(argv)
    out = a.out_dir or a.data_dir / "seed"
    with open(a.data_dir / "products.jsonl", encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    res = generate(rows, a.as_of, a.seed, a.profiles, a.zipf, a.vinpearl_boost, max_events=a.max_events)
    out.mkdir(parents=True, exist_ok=True)
    for name, key in (("cdp_profiles", "profiles"), ("cdp_events", "events"), ("app_users", "users"), ("app_bookings", "bookings"),
                      ("app_booking_items", "booking_items")):
        write_jsonl(out / f"{name}.jsonl", res[key])
    text, _ = report(res, a.as_of, {"seed": a.seed, "max_events": a.max_events})
    (out / "seed_report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
