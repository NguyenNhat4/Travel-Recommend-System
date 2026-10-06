"""Seed lịch sử khách hàng cho CDP clone: `cdp.profiles`, `cdp.events`, cùng `app.users` / `app.bookings` / `app.booking_items` cho 4 persona.

Theo MOCK_DATA_SPEC §4–§5 (diễn giải cho chỗ mơ hồ: §0 "Điểm chốt 21/09"). **Không sửa products.jsonl**; đầu ra là file để nạp vào DB.

    python -m data_collection.seed.seed_histories [--data-dir data] [--out-dir data/seed] [--as-of YYYY-MM-DD] [--seed 42] [--profiles 2000]

Quy tắc (mọi tỷ lệ, khoảng, trọng số nằm trong config.py):
  * 2.000 profile, cdp_user_id "VP" + 7 số tuần tự từ VP0000001 (4 persona giữ 1–4). Stage đích new 25 · active 45 · dormant 20 · churned 10.
  * Chuyến đi = một event_group_id ("OFF" + yyyymmdd + 3 số), một điểm đến chọn theo số sản phẩm bookable; 65% chuyến ≥ 2 vertical,
    3% chuyến có golf; thứ tự checkout hotel → flight → attraction/combo → golf. Sản phẩm chọn theo Zipf s = 0,8 trên thứ tự
    crc32(product_id), Vinpearl ×2. Nhận phòng = ngày mua + 7–45 ngày, vé = nhận phòng + 1, không sau as_of − 1.
  * Event một chuyến: [search 30%] → 1–3 product_view (0–7 ngày trước mua) → [add_to_cart 40% chuyến] → purchase. Chỉ purchase có
    event_group_id. quantity: hotel 1 · flight 1–3 · attraction 2–4 · combo/golf 1–2; unit_price = giá catalog ±5%, làm tròn nghìn.
  * Không khách nào quá 15 event (bỏ search → add_to_cart → product_view cũ nhất; purchase không bao giờ bị bỏ).
  * Cạnh lộn xộn (không áp cho persona): 2% purchase trỏ product_id không tồn tại; 3% purchase mất event_group_id; 1% khách có
    product_view ở hai điểm đến khác nhau cùng ngày.
  * Profile TÍNH TỪ event: lifetime_order_count = số event_group_id khác NULL có purchase; lifecycle 0 purchase → new, ≤ 180 ngày
    active, 181–365 dormant, > 365 churned. Lệch stage đích quá 5% thì dừng.
  * 4 persona (§5): P1 3 chuyến Nha Trang + đặt phòng Vinpearl Nha Trang tại as_of − 3 cho đêm as_of + 12 (có app.bookings, chưa có vé bay);
    P2 2 lần xem Phú Quốc tại as_of − 2 / − 1; P3 2 chuyến Phú Quốc, chuyến cuối as_of − 190; P4 0 event. Kèm 50 tài khoản test.
Mọi thứ có ngày sinh tương đối theo --as-of, giờ theo múi +07:00. Kết quả xác định theo --seed.
Mọi app.users dùng mật khẩu demo `Demo@2026`, băm Argon2id (salt tất định theo user_id); email / số điện thoại là dữ liệu giả.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import random
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from argon2.low_level import Type, hash_secret

from . import config as C
from .catalog_meta import build_meta, is_vinpearl, open_nights, room_calendar, stable_order_key, variant

NS = uuid.UUID("6f3b1f0e-8a52-4c1e-9d0a-7a0c5b1d2e77")  # không gian tên cố định cho uuid5 (seed)
TZ_VN = timezone(timedelta(hours=7))
TICKET_KINDS = ("attraction", "combo")
CHECKOUT_ORDER = {"hotel": 0, "flight": 1, "attraction": 2, "combo": 2, "golf": 3}
PERSONA_IDS = {p[0] for p in C.PERSONAS}


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(str(p) for p in parts)))


def demo_password_hash(user_id: str) -> str:
    """Argon2id (PHC) của mật khẩu demo, đúng tham số backend nên không bị rehash khi đăng nhập.

    Salt 16 byte suy từ user_id thay vì ngẫu nhiên: seed phải tái lập được byte-for-byte, và mỗi
    user vẫn có salt riêng. Chỉ chấp nhận được vì mật khẩu demo vốn công khai.
    """
    salt = hashlib.sha256(f"vota-seed-salt|{user_id}".encode()).digest()[:16]
    return hash_secret(C.DEMO_PASSWORD.encode(), salt, time_cost=C.ARGON2_TIME_COST, memory_cost=C.ARGON2_MEMORY_KIB,
                       parallelism=C.ARGON2_PARALLELISM, hash_len=C.ARGON2_HASH_LEN, type=Type.ID).decode()


def weighted(rng: random.Random, weights: dict) -> str:
    keys = list(weights)
    return rng.choices(keys, [weights[k] for k in keys])[0]


def inclusive(rng: random.Random, bounds: tuple[int, int]) -> int:
    return rng.randint(bounds[0], bounds[1])


def noisy_price(rng: random.Random, price: float | None) -> int | None:
    """unit_price lúc mua = giá catalog × U(1 − noise, 1 + noise), làm tròn nghìn (MOCK_DATA_SPEC §4)."""
    if price is None:
        return None
    step = C.PRICE_ROUNDING
    return max(step, int(round(price * rng.uniform(1 - C.PRICE_NOISE, 1 + C.PRICE_NOISE) / step)) * step)


def local_day(ts: datetime) -> date:
    return ts.astimezone(TZ_VN).date()


def end_of_day(ts: datetime) -> datetime:
    return datetime.combine(local_day(ts), datetime.max.time().replace(microsecond=0), tzinfo=TZ_VN)


def distinct_picks(sampler: "Sampler", rng: random.Random, n: int, taken: list[dict] | None = None, tries: int = 20) -> list[dict]:
    """n sản phẩm khác nhau (và khác `taken`) theo Zipf; chỉ cho trùng khi nhóm có quá ít sản phẩm."""
    seen = {r["productId"] for r in taken or []}
    out: list[dict] = []
    for _ in range(n):
        pick = sampler.pick(rng)
        for _ in range(tries):
            if pick["productId"] not in seen:
                break
            pick = sampler.pick(rng)
        seen.add(pick["productId"])
        out.append(pick)
    return out


class Sampler:
    """Chọn phần tử theo Zipf trên thứ hạng cố định crc32(productId); Vinpearl nhân thêm hệ số."""

    def __init__(self, items: list[dict], s: float, boost: float, by_id: dict[str, dict]):
        self.items = sorted(items, key=lambda r: (stable_order_key(r["productId"]), r["productId"]))
        self.cum: list[float] = []
        total = 0.0
        for i, r in enumerate(self.items):
            total += (boost if is_vinpearl(r, by_id) else 1.0) / ((i + 1) ** s)
            self.cum.append(total)

    def pick(self, rng: random.Random) -> dict:
        return self.items[min(bisect.bisect_left(self.cum, rng.random() * self.cum[-1]), len(self.items) - 1)]


class World:
    """Catalog đã phân nhóm: sản phẩm đặt được theo (điểm đến, vertical), vé bay theo (điểm đến, nơi đi), search unit để xem."""

    def __init__(self, rows: list[dict], zipf: float, boost: float):
        self.by_id = {r["productId"]: r for r in rows}
        self.meta = build_meta(rows)
        buy: dict[tuple[str, str], list[dict]] = defaultdict(list)
        flights: dict[tuple[str, str], list[dict]] = defaultdict(list)
        views: dict[str, list[dict]] = defaultdict(list)
        props: dict[str, list[dict]] = defaultdict(list)
        weight: Counter = Counter()
        for r in rows:
            m, v = self.meta[r["productId"]], variant(r)
            if m["is_search_unit"] and m["is_recommendable"]:
                views[r["destination"]].append(r)
                if v == "hotel_property":
                    props[r["destination"]].append(r)
            if not m["is_bookable"]:
                continue
            weight[r["destination"]] += 1
            if v == "hotel_room":
                buy[(r["destination"], "hotel")].append(r)
            elif v == "flight":
                route = self.by_id.get(r["attributes"].get("parentProductId") or "")
                flights[(r["destination"], (route or r)["attributes"].get("originDestination") or "")].append(r)
            else:
                buy[(r["destination"], v)].append(r)
        sampler = lambda items: Sampler(items, zipf, boost, self.by_id)  # noqa: E731
        self.buy = {k: sampler(v) for k, v in buy.items()}
        self.flights = {k: sampler(v) for k, v in flights.items()}
        self.views = {k: sampler(v) for k, v in views.items()}
        self.props = {k: sampler(v) for k, v in props.items()}
        self.dest_names = sorted(weight)
        self.dest_cum: list[float] = []
        total = 0.0
        for d in self.dest_names:
            total += weight[d]
            self.dest_cum.append(total)
        # hết lượt bốc lại: chuyến chỉ khách sạn ở điểm đến nặng nhất có phòng
        self.fallback_dest = max((d for d in self.dest_names if (d, "hotel") in self.buy), key=lambda d: (weight[d], d))

    def destination(self, rng: random.Random) -> str:
        return self.dest_names[min(bisect.bisect_left(self.dest_cum, rng.random() * self.dest_cum[-1]), len(self.dest_names) - 1)]

    @staticmethod
    def origin(home: str) -> str:
        return C.HOME_CITY_FLIGHT_ORIGIN.get(home, home)

    def has(self, dest: str, vertical: str, home: str) -> bool:
        if vertical == "flight":
            return (dest, self.origin(home)) in self.flights
        if vertical == "ticket":
            return any((dest, k) in self.buy for k in TICKET_KINDS)
        return (dest, vertical) in self.buy

    def pick(self, rng: random.Random, dest: str, vertical: str, home: str) -> dict:
        if vertical == "flight":
            return self.flights[(dest, self.origin(home))].pick(rng)
        if vertical == "ticket":
            kinds = {k: C.TICKET_KIND_WEIGHTS[k] for k in TICKET_KINDS if (dest, k) in self.buy}
            vertical = weighted(rng, kinds)
        return self.buy[(dest, vertical)].pick(rng)

    def view_of(self, product: dict) -> dict:
        """Search unit mà khách xem trước khi mua: property của hạng phòng, tuyến của chuyến bay, còn lại là chính nó."""
        parent = self.by_id.get(product["attributes"].get("parentProductId") or "")
        return parent or product


# ------------------------------------------------------------------ chuyến đi
def plan_trip(w: World, rng: random.Random, home: str) -> tuple[str, list[str]]:
    """(điểm đến, danh sách vertical theo thứ tự checkout). 3% chuyến có golf, 65% chuyến ≥ 2 vertical (MOCK_DATA_SPEC §4)."""
    r = rng.random()
    golf = r < C.GOLF_TRIP_RATE
    if golf or r < C.MULTI_VERTICAL_RATE:
        for _ in range(C.DEST_REDRAWS):
            dest = w.destination(rng)
            can_flight, can_ticket = w.has(dest, "flight", home), w.has(dest, "ticket", home)
            if w.has(dest, "hotel", home) and (w.has(dest, "golf", home) if golf else (can_flight or can_ticket)):
                break
        else:
            return w.fallback_dest, ["hotel"]
        add_flight = can_flight and rng.random() < C.MULTI_FLIGHT_RATE
        add_ticket = can_ticket and rng.random() < C.MULTI_TICKET_RATE
        if not golf and not (add_flight or add_ticket):  # chuyến nhiều vertical: ép loại có sẵn
            if can_flight and can_ticket:
                add_flight = rng.random() < C.MULTI_FLIGHT_RATE / (C.MULTI_FLIGHT_RATE + C.MULTI_TICKET_RATE)
                add_ticket = not add_flight
            else:
                add_flight, add_ticket = can_flight, can_ticket
        return dest, ["hotel"] + ["flight"] * add_flight + ["ticket"] * add_ticket + ["golf"] * golf
    vertical = weighted(rng, C.SINGLE_VERTICAL_WEIGHTS)
    for _ in range(C.DEST_REDRAWS):
        dest = w.destination(rng)
        if w.has(dest, vertical, home):
            return dest, [vertical]
    return w.fallback_dest, ["hotel"]


class Builder:
    def __init__(self, w: World, as_of: date):
        self.w, self.as_of = w, as_of
        self.events: list[dict] = []
        self.bookings: list[dict] = []
        self.booking_items: list[dict] = []
        self.seq: Counter = Counter()

    def group_id(self, purchased: datetime) -> str:
        d = local_day(purchased).strftime("%Y%m%d")
        self.seq[d] += 1
        return f"OFF{d}{self.seq[d]:03d}"

    @staticmethod
    def event(user, name, ts, product, gid=None, qty=None, price=None, using=None) -> dict:
        return {"cdp_user_id": user, "event_name": name, "timestamp": ts,
                "product_id": product["productId"] if product else None, "taxonomy": product["taxonomy"] if product else None,
                "event_group_id": gid, "quantity": qty, "unit_price": price, "using_date": using.isoformat() if using else None}

    def trip(self, user: str, rng: random.Random, dest: str, home: str, verticals: list[str], purchased: datetime, *,
             n_views: int, search: bool, cart: bool, lead: tuple[int, int] = C.LEAD_DAYS) -> list[dict]:
        """Sinh một chuyến đã chốt thời điểm checkout `purchased`; trả về các dòng purchase (có giá lúc mua).
        Vertical mà điểm đến không có (catalog tổng hợp, persona) bị bỏ qua; không còn mục nào thì không sinh gì."""
        products = [self.w.pick(rng, dest, v, home) for v in verticals if self.w.has(dest, v, home)]
        if not products:
            return []
        products.sort(key=lambda p: CHECKOUT_ORDER[p["taxonomy"]])
        latest = self.as_of - timedelta(days=C.LATEST_PAST_USING_DAYS)
        has_ticket = any(p["taxonomy"] not in ("hotel", "flight") for p in products)
        check_in = local_day(purchased) + timedelta(days=inclusive(rng, lead))
        check_in = min(check_in, latest - timedelta(days=C.TICKET_DAY_OFFSET if has_ticket else 0))
        gid = self.group_id(purchased)
        purchases, carts = [], []
        for k, p in enumerate(products):
            ts = purchased + timedelta(seconds=C.ITEM_GAP_SECONDS * k)
            using = check_in + timedelta(days=0 if p["taxonomy"] in ("hotel", "flight") else C.TICKET_DAY_OFFSET)
            qty, price = inclusive(rng, C.QUANTITY[p["taxonomy"]]), noisy_price(rng, p["unitPrice"])
            if cart:
                cart_ts = purchased - timedelta(minutes=inclusive(rng, C.CART_BEFORE_PURCHASE_MIN)) + timedelta(seconds=k)
                carts.append(self.event(user, "add_to_cart", cart_ts, p, None, qty, price, using))
            purchases.append(self.event(user, "purchase", ts, p, gid, qty, price, using))
        first_touch = min([purchased] + [c["timestamp"] for c in carts])
        first = self.w.view_of(products[0])
        view_targets = [first] + distinct_picks(self.w.views[dest], rng, n_views - 1, [first])
        views = []
        latest_view = C.VIEW_LEAD_DAYS[1] * 86400
        earliest_view = max(C.VIEW_LEAD_DAYS[0] * 86400, (purchased - first_touch).total_seconds() + 60)
        for target in view_targets:
            views.append(self.event(user, "product_view", purchased - timedelta(seconds=rng.uniform(earliest_view, latest_view)), target))
        events = views + carts + purchases
        if search:
            first_view = min(v["timestamp"] for v in views)
            events.insert(0, self.event(user, "search", first_view - timedelta(minutes=inclusive(rng, C.SEARCH_BEFORE_VIEW_MIN)), None))
        self.events.extend(events)
        return purchases

    def abandoned(self, user: str, rng: random.Random, dest: str, home: str, verticals: list[str], carted: datetime, *,
                  n_views: int) -> int:
        """Lần bỏ giỏ (profile eval): product_view → add_to_cart mọi mục tại `carted`, không purchase, không event_group_id
        (như app thật). using_date của giỏ = ngày dự định đi, kẹp ≤ as_of − 1 như chuyến thường. Trả số event đã sinh."""
        products = [self.w.pick(rng, dest, v, home) for v in verticals if self.w.has(dest, v, home)]
        if not products:
            return 0
        products.sort(key=lambda p: CHECKOUT_ORDER[p["taxonomy"]])
        latest = self.as_of - timedelta(days=C.LATEST_PAST_USING_DAYS)
        check_in = min(local_day(carted) + timedelta(days=inclusive(rng, C.LEAD_DAYS)), latest - timedelta(days=C.TICKET_DAY_OFFSET))
        carts = []
        for k, p in enumerate(products):
            using = check_in + timedelta(days=0 if p["taxonomy"] in ("hotel", "flight") else C.TICKET_DAY_OFFSET)
            carts.append(self.event(user, "add_to_cart", carted + timedelta(seconds=C.ITEM_GAP_SECONDS * k), p, None,
                                    inclusive(rng, C.QUANTITY[p["taxonomy"]]), noisy_price(rng, p["unitPrice"]), using))
        first = self.w.view_of(products[0])
        targets = [first] + distinct_picks(self.w.views[dest], rng, n_views - 1, [first])
        views = [self.event(user, "product_view", carted - timedelta(seconds=rng.uniform(60, C.VIEW_LEAD_DAYS[1] * 86400)), t)
                 for t in targets]
        self.events.extend(views + carts)
        return len(views) + len(carts)


def at(day: date, rng: random.Random) -> datetime:
    """Giờ ngẫu nhiên trong ngày (giờ Việt Nam)."""
    return datetime(day.year, day.month, day.day, rng.randint(C.EVENT_HOURS[0], C.EVENT_HOURS[1]), rng.randint(0, 59),
                    rng.randint(0, 59), tzinfo=TZ_VN)


def dt_iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ vòng đời
def lifecycle(events: list[dict], as_of: date) -> tuple[str, int | None]:
    """0 purchase → new; còn lại theo số ngày từ lần mua cuối: ≤ 180 active, 181–365 dormant, > 365 churned (MOCK_DATA_SPEC §4)."""
    buys = [e for e in events if e["event_name"] == "purchase"]
    if not buys:
        return "new", None
    days = (as_of - local_day(max(e["timestamp"] for e in buys))).days
    return ("active" if days <= 180 else "dormant" if days <= 365 else "churned"), days


def stage_plan(n_profiles: int) -> list[str]:
    """Số khách mỗi giai đoạn đúng tỷ lệ STAGE_MIX (làm tròn, phần dư vào active)."""
    counts = {s: round(n_profiles * m) for s, m in C.STAGE_MIX.items()}
    counts["active"] += n_profiles - sum(counts.values())
    return [s for s, n in counts.items() for _ in range(n)]


def plan_generic(w: World, b: Builder, rng: random.Random, user: str, stage: str, home: str, as_of: date, max_events: int) -> None:
    """Một khách thường: sinh chuyến theo giai đoạn; lifecycle_stage được tính lại từ event sau đó."""
    views = lambda: rng.choices(range(1, len(C.VIEWS_PER_TRIP) + 1), C.VIEWS_PER_TRIP)[0]  # noqa: E731
    if stage == "new":
        if rng.random() >= C.NEW_VIEW_TRIP_RATE:
            return
        dest = w.destination(rng)
        for _ in range(C.DEST_REDRAWS):
            if dest in w.views:
                break
            dest = w.destination(rng)
        t0 = at(as_of - timedelta(days=inclusive(rng, C.NEW_VIEW_DAYS_AGO)), rng)
        for k, target in enumerate(distinct_picks(w.views[dest], rng, views())):   # một chuyến chỉ có product_view, không mua
            ts = min(t0 + timedelta(minutes=inclusive(rng, C.NEW_VIEW_GAP_MIN) * k), end_of_day(t0))
            b.events.append(b.event(user, "product_view", ts, target))
        return
    n_trips = rng.choices(range(1, len(C.TRIPS_PER_STAGE[stage]) + 1), C.TRIPS_PER_STAGE[stage])[0]
    oldest = C.HISTORY_DAYS - C.VIEW_LEAD_DAYS[1] - 1          # view / search của chuyến cũ nhất vẫn nằm trong 24 tháng
    days_ago = min(inclusive(rng, C.LAST_PURCHASE_DAYS_AGO[stage]), oldest)
    purchases = 0
    for _ in range(n_trips):
        if days_ago > oldest:
            break
        dest, verticals = plan_trip(w, rng, home)
        if purchases and purchases + len(verticals) > max_events:   # purchase không bị cắt, nên không nhận thêm chuyến cũ vượt cap
            break
        purchases += len(b.trip(user, rng, dest, home, verticals, at(as_of - timedelta(days=days_ago), rng), n_views=views(),
                                search=rng.random() < C.SEARCH_TRIP_RATE, cart=rng.random() < C.ADD_TO_CART_TRIP_RATE))
        if C.ABANDONED_CART_RATE and rng.random() < C.ABANDONED_CART_RATE:   # profile eval: bỏ giỏ trước chuyến này
            back = days_ago + inclusive(rng, C.ABANDONED_DAYS_BEFORE)
            if back <= oldest:
                a_dest, a_verticals = (dest, verticals) if rng.random() < C.ABANDONED_SAME_DEST_RATE else plan_trip(w, rng, home)
                b.abandoned(user, rng, a_dest, home, a_verticals, at(as_of - timedelta(days=back), rng), n_views=views())
        days_ago += inclusive(rng, C.TRIP_GAP_DAYS)


def cap_events(evs: list[dict], limit: int) -> list[dict]:
    """Không quá `limit` event/khách: bỏ theo EVENT_TRIM_ORDER (search → add_to_cart → product_view cũ nhất); không bỏ purchase."""
    if len(evs) <= limit:
        return evs
    for name in C.EVENT_TRIM_ORDER:
        cand = sorted((e for e in evs if e["event_name"] == name), key=lambda e: e["timestamp"])
        while len(evs) > limit and cand:
            evs.remove(cand.pop(0))
    return evs


# ------------------------------------------------------------------ persona
def seed_personas(w: World, b: Builder, rng: random.Random, as_of: date) -> dict:
    """Lịch sử cố định của 4 persona (MOCK_DATA_SPEC §5). Khuôn: không search, 1 view / chuyến, không add_to_cart ở chuyến cũ."""
    homes = {p[0]: p[4] for p in C.PERSONAS}
    p1, p2, p3 = (p[0] for p in C.PERSONAS[:3])

    def persona_trip(user: str, spec: dict, verticals, days_ago: int) -> None:
        if not b.trip(user, rng, spec["destination"], homes[user], list(verticals), at(as_of - timedelta(days=days_ago), rng),
                      n_views=1, search=False, cart=False, lead=C.PERSONA_LEAD_DAYS):
            raise SystemExit(f"Catalog không có sản phẩm {'/'.join(verticals)} đặt được ở {spec['destination']} cho persona {user}")

    for days_ago in C.P1["past_trip_days_ago"]:
        persona_trip(p1, C.P1, C.P1["past_verticals"], days_ago)

    # P1 — chuyến sắp tới: đã đặt 1 phòng Vinpearl Nha Trang (1 đêm), chưa có vé bay / vé tham quan
    using = as_of + timedelta(days=C.P1["upcoming_using_in_days"])
    nights = C.P1["upcoming_nights"]
    room = None
    rooms = w.buy.get((C.P1["destination"], "hotel"))
    for cand in rooms.items if rooms else []:                       # thứ tự Zipf: phòng phổ biến nhất còn trống trước
        brand_ok = is_vinpearl(cand, w.by_id) if C.P1["upcoming_brand"] == "Vinpearl" else cand["attributes"].get("brand") == C.P1["upcoming_brand"]
        if brand_ok and cand["available"] and open_nights(room_calendar(cand, as_of, w.by_id), as_of, using, nights):
            room = cand
            break
    if room is None:
        raise SystemExit(f"Không có hạng phòng {C.P1['upcoming_brand']} {C.P1['destination']} còn trống đêm {using} cho chuyến sắp tới của P1")
    purchased = at(as_of - timedelta(days=C.P1["upcoming_purchase_days_ago"]), rng)
    price = noisy_price(rng, room["unitPrice"])
    gid = b.group_id(purchased)
    b.events.append(b.event(p1, "product_view", purchased - timedelta(days=C.P1["upcoming_view_days_before"]), w.view_of(room)))
    b.events.append(b.event(p1, "add_to_cart", purchased - timedelta(minutes=C.P1["upcoming_cart_minutes_before"]), room, None, 1, price, using))
    b.events.append(b.event(p1, "purchase", purchased, room, gid, 1, price, using))
    booking_id = uid("booking", gid)
    name, email = next((p[2], p[3]) for p in C.PERSONAS if p[0] == p1)
    b.bookings.append({"booking_id": booking_id, "reference_code": f"VOTA-{using.strftime('%Y%m%d')}-{uid('ref', gid)[:4].upper()}",
                       "cdp_user_id": p1, "event_group_id": gid, "status": "confirmed", "contact_name": name,
                       "contact_email": email, "contact_phone": C.P1["phone"], "special_request": None,
                       "total_amount": price * 1, "currency": "VND", "created_at": dt_iso(purchased)})
    b.booking_items.append({"booking_item_id": uid("item", gid, room["productId"]), "booking_id": booking_id, "product_id": room["productId"],
                            "taxonomy": "hotel", "product_name": room["name"], "unit_price": price, "quantity": 1,
                            "using_date": using.isoformat(), "using_date_to": (using + timedelta(days=nights)).isoformat(),
                            "guest_names": [name], "line_total": price * 1})
    info = {"P1_upcoming": {"room": room["name"], "using_date": using.isoformat(), "nights": nights, "event_group_id": gid}}

    props = w.props.get(C.P2["destination"])                            # P2: 2 lần xem khách sạn Phú Quốc, chưa mua
    n_views = len(C.P2["view_days_ago"])
    if props is None or len(props.items) < n_views:
        raise SystemExit(f"Catalog không đủ {n_views} khách sạn ở {C.P2['destination']} cho persona {p2}")
    for days_ago, prop in zip(C.P2["view_days_ago"], distinct_picks(props, rng, n_views)):
        b.events.append(b.event(p2, "product_view", at(as_of - timedelta(days=days_ago), rng), prop))

    for days_ago in C.P3["trip_days_ago"]:                              # P3: 2 chuyến Phú Quốc, chuyến cuối as_of − 190
        persona_trip(p3, C.P3, C.P3["verticals"], days_ago)
    return info


# ------------------------------------------------------------------ cạnh lộn xộn
def messy_edges(w: World, b: Builder, rng: random.Random, max_events: int, n_profiles: int) -> None:
    """Sau khi sinh (trừ persona): 2% purchase trỏ sản phẩm không tồn tại, 3% purchase mất gid, 1% khách xem hai điểm đến cùng ngày."""
    noisy = [e for e in b.events if e["cdp_user_id"] not in PERSONA_IDS]
    buys = [e for e in noisy if e["event_name"] == "purchase"]
    for e in rng.sample(buys, round(C.MESSY_PURCHASE_BAD_PRODUCT * len(buys))):
        e["product_id"] = uid("deleted-product", e["product_id"], dt_iso(e["timestamp"]))
    grouped = [e for e in buys if e["event_group_id"]]
    for e in rng.sample(grouped, round(C.MESSY_DROP_GROUP * len(grouped))):
        e["event_group_id"] = None
    per_user = Counter(e["cdp_user_id"] for e in noisy)
    viewers = sorted({e["cdp_user_id"] for e in noisy if e["event_name"] == "product_view" and per_user[e["cdp_user_id"]] < max_events})
    for user in rng.sample(viewers, min(len(viewers), round(C.MESSY_TWO_DEST_VIEW_USERS * n_profiles))):
        view = rng.choice(sorted((e for e in noisy if e["cdp_user_id"] == user and e["event_name"] == "product_view"),
                                 key=lambda e: e["timestamp"]))
        dest = w.by_id[view["product_id"]]["destination"]
        other = [d for d in sorted(w.views) if d != dest]
        target = w.views[rng.choice(other)].pick(rng)
        ts = min(view["timestamp"] + timedelta(minutes=inclusive(rng, C.MESSY_SECOND_VIEW_AFTER_MIN)), end_of_day(view["timestamp"]))
        b.events.append(b.event(user, "product_view", ts, target))


# ------------------------------------------------------------------ chính
class profile_overrides:
    """Ghi đè hằng của config.py theo `config.PROFILES[name]` trong lúc sinh (None → seed demo, không đổi gì); khôi phục khi xong."""

    def __init__(self, name: str | None):
        if name is not None and name not in C.PROFILES:
            raise SystemExit(f"--profile {name!r}: chỉ có {', '.join(C.PROFILES)}")
        self.values = dict(C.PROFILES[name]) if name else {}
        self.saved: dict = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = getattr(C, k)
            setattr(C, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(C, k, v)


def generate(rows: list[dict], as_of: date, seed: int = C.DEFAULT_SEED, n_profiles: int | None = None, zipf: float = C.ZIPF_S,
             boost: float = C.VINPEARL_BOOST, max_events: int | None = None, profile: str | None = None) -> dict:
    """`profile` (vd `eval-v2`): ghi đè tham số theo `config.PROFILES`; `n_profiles` / `max_events` None → giá trị của profile / demo."""
    with profile_overrides(profile):
        res = _generate(rows, as_of, seed, C.DEFAULT_USERS if n_profiles is None else n_profiles, zipf, boost,
                        C.MAX_EVENTS_PER_USER if max_events is None else max_events)
    res["profile"] = profile
    return res


def _generate(rows: list[dict], as_of: date, seed: int, n_profiles: int, zipf: float, boost: float, max_events: int) -> dict:
    w = World(rows, zipf, boost)
    b = Builder(w, as_of)
    rng = random.Random(f"{seed}|seed")
    persona_info = seed_personas(w, b, random.Random(f"{seed}|personas"), as_of)

    generic_ids = [f"VP{i:07d}" for i in range(len(C.PERSONAS) + 1, n_profiles + 1)]
    stages = stage_plan(len(generic_ids))
    rng.shuffle(stages)
    homes: dict[str, str] = {p[0]: p[4] for p in C.PERSONAS}
    tiers: dict[str, str] = {p[0]: p[5] for p in C.PERSONAS}
    for user, stage in zip(generic_ids, stages):
        homes[user] = weighted(rng, C.HOME_CITIES)
        tiers[user] = weighted(rng, C.VINCLUB_TIERS)
        plan_generic(w, b, random.Random(f"{seed}|{user}"), user, stage, homes[user], as_of, max_events)

    by_user: dict[str, list[dict]] = defaultdict(list)
    for e in b.events:
        by_user[e["cdp_user_id"]].append(e)
    b.events = []
    for user in homes:
        evs = sorted(by_user.get(user, []), key=lambda e: e["timestamp"])
        b.events.extend(evs if user in PERSONA_IDS else cap_events(evs, max_events))
    messy_edges(w, b, random.Random(f"{seed}|messy"), max_events, n_profiles)

    b.events.sort(key=lambda e: (e["timestamp"], e["cdp_user_id"], e["event_name"]))
    for i, e in enumerate(b.events, 1):
        e["event_id"] = i
    by_user = defaultdict(list)
    for e in b.events:
        by_user[e["cdp_user_id"]].append(e)
    over = {u: len(evs) for u, evs in by_user.items() if len(evs) > max_events}
    if over:
        raise SystemExit(f"Vượt {max_events} event/khách: {over}")

    optin_rng = random.Random(f"{seed}|optin")
    profiles, stage_of = [], {}
    for user in homes:
        evs = by_user.get(user, [])
        stage, days = lifecycle(evs, as_of)
        stage_of[user] = stage
        buys = sorted((e for e in evs if e["event_name"] == "purchase"), key=lambda e: e["timestamp"], reverse=True)
        last_dest = next((w.by_id[e["product_id"]]["destination"] for e in buys if e["product_id"] in w.by_id), None)
        prng = random.Random(f"{seed}|profile|{user}")
        if evs:
            created = evs[0]["timestamp"] - timedelta(days=inclusive(prng, C.PROFILE_CREATED_BEFORE_FIRST_EVENT_DAYS))
        else:
            created = datetime.combine(as_of - timedelta(days=inclusive(prng, C.PROFILE_CREATED_NO_EVENT_DAYS)), datetime.min.time(), tzinfo=TZ_VN)
        optin = {k: True if user in PERSONA_IDS else optin_rng.random() >= C.OPTOUT_RATE[k] for k in ("email", "sms", "push")}
        profiles.append({"cdp_user_id": user, "lifecycle_stage": stage, "days_since_last_booking": days,
                         "lifetime_order_count": len({e["event_group_id"] for e in buys if e["event_group_id"]}),
                         "vinclub_tier": tiers[user], "purchased_verticals": sorted({e["taxonomy"] for e in buys}), "home_city": homes[user],
                         "last_destination": last_dest, "email_optin": optin["email"], "sms_optin": optin["sms"], "push_optin": optin["push"],
                         "created_at": dt_iso(created), "updated_at": dt_iso(max([created] + [e["timestamp"] for e in evs]))})
    profiles.sort(key=lambda p: p["cdp_user_id"])
    shares = Counter(stage_of.values())
    drift = {s: round(shares[s] / len(profiles) - target, 4) for s, target in C.STAGE_MIX.items()}
    if any(abs(d) > C.STAGE_TOLERANCE for d in drift.values()):
        raise SystemExit(f"Phân bố stage lệch quá {C.STAGE_TOLERANCE:.0%} so với STAGE_MIX: {drift} — chỉnh số chuyến trong config.py")

    users = []
    persona_by_id = {p[0]: p for p in C.PERSONAS}
    created_of = {p["cdp_user_id"]: p["created_at"] for p in profiles}
    for n, user in enumerate([p[0] for p in C.PERSONAS] + generic_ids[:C.TEST_USERS], start=1 - len(C.PERSONAS)):
        p = persona_by_id.get(user)
        users.append({"user_id": uid("user", user), "email": p[3] if p else C.TEST_USER_EMAIL.format(n=n), "password_hash": demo_password_hash(uid("user", user)),
                      "display_name": p[2] if p else C.TEST_USER_NAME.format(n=n), "cdp_user_id": user, "persona": p[1] if p else None,
                      "created_at": created_of[user], "last_login_at": None})
    events = [{"event_id": e["event_id"], "cdp_user_id": e["cdp_user_id"], "event_name": e["event_name"], "timestamp": dt_iso(e["timestamp"]),
               "product_id": e["product_id"], "taxonomy": e["taxonomy"], "event_group_id": e["event_group_id"], "quantity": e["quantity"],
               "unit_price": e["unit_price"], "using_date": e["using_date"]} for e in b.events]
    return {"profiles": profiles, "events": events, "users": users, "bookings": b.bookings, "booking_items": b.booking_items,
            "persona": persona_info, "world": w}


def recall_at_k(res: dict, k: int = C.RECALL_K) -> tuple[Counter, Counter]:
    """Baseline "phổ biến nhất tại điểm đến": ẩn lần đặt cuối của mỗi khách có ≥ 2 event_group_id khác NULL, đoán bằng top-k của điểm đến."""
    w = res["world"]
    hist: dict[str, list[dict]] = defaultdict(list)
    for e in res["events"]:
        if e["event_name"] == "purchase" and e["cdp_user_id"] not in PERSONA_IDS and e["product_id"] in w.by_id:
            hist[e["cdp_user_id"]].append(e)
    last: dict[str, dict] = {}
    for u, es in hist.items():
        es.sort(key=lambda e: (e["timestamp"], e["event_id"]))
        if len({x["event_group_id"] for x in es if x["event_group_id"]}) >= 2:
            last[u] = es[-1]
    hidden = {e["event_id"] for e in last.values()}
    pop: dict[str, Counter] = defaultdict(Counter)
    for es in hist.values():
        for e in es:
            if e["event_id"] not in hidden:
                pop[w.by_id[e["product_id"]]["destination"]][e["product_id"]] += 1
    top = {d: {p for p, _ in c.most_common(k)} for d, c in pop.items()}
    hit_by: Counter = Counter()
    tot_by: Counter = Counter()
    for e in last.values():
        tot_by[e["taxonomy"]] += 1
        hit_by[e["taxonomy"]] += e["product_id"] in top.get(w.by_id[e["product_id"]]["destination"], set())
    return hit_by, tot_by


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
    golf = sum(1 for g in groups.values() if any(e["taxonomy"] == "golf" for e in g))
    dests_ok = all(len({w.by_id[e["product_id"]]["destination"] for e in g if e["product_id"] in w.by_id}) <= 1 for g in groups.values())
    by_tax = Counter(e["taxonomy"] for e in buys)
    exist = sum(1 for e in buys if e["product_id"] not in w.by_id)
    parse = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    carts: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for e in ev:
        if e["event_name"] == "add_to_cart":
            carts[(e["cdp_user_id"], e["product_id"])].append(parse(e["timestamp"]))
    generic_groups = [g for g in groups.values() if g[0]["cdp_user_id"] not in PERSONA_IDS]
    window_cart = timedelta(minutes=C.CART_BEFORE_PURCHASE_MIN[1] + 1)

    def has_cart(g: list[dict]) -> bool:
        first = min(parse(e["timestamp"]) for e in g)
        return any(first - window_cart <= t <= first for e in g for t in carts.get((e["cdp_user_id"], e["product_id"]), ()))

    cart_trips = sum(1 for g in generic_groups if has_cart(g))
    search_generic = sum(1 for e in ev if e["event_name"] == "search" and e["cdp_user_id"] not in PERSONA_IDS)
    hit_by, tot_by = recall_at_k(res)
    hits, hidden = sum(hit_by.values()), sum(tot_by.values())
    recall = hits / max(1, hidden)
    top_share = 0.0
    prod = Counter(e["product_id"] for e in buys)
    if prod:
        top_share = sum(c for _, c in prod.most_common(max(1, len(prod) // 10))) / len(buys)
    pers = res["persona"]
    no_group = sum(1 for e in buys if e["event_group_id"] is None)
    # bỏ giỏ = add_to_cart không có purchase cùng khách + sản phẩm trong cửa sổ cart của chuyến (profile eval)
    bought_after: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for e in buys:
        bought_after[(e["cdp_user_id"], e["product_id"])].append(parse(e["timestamp"]))
    abandoned_carts = sum(1 for e in ev if e["event_name"] == "add_to_cart" and not any(
        parse(e["timestamp"]) <= t <= parse(e["timestamp"]) + window_cart for t in bought_after.get((e["cdp_user_id"], e["product_id"]), ())))
    trips_per_user = Counter(g[0]["cdp_user_id"] for g in generic_groups)
    buyers = len(trips_per_user)
    returning = sum(1 for n_ in trips_per_user.values() if n_ >= 2)
    lines = [f"# Kết quả seed_histories — as_of {as_of.isoformat()}, seed {args['seed']}", "",
             f"- Profile: **{n}** · event: **{len(ev)}** ({', '.join(f'{k} {v}' for k, v in names.most_common())}) · "
             f"trung bình {len(ev) / n:.1f} event/khách, nhiều nhất {max(per.values() or [0])} (giới hạn {args['max_events']})",
             "- Vòng đời (tính từ event): " + " · ".join(f"{k} {v} ({100 * v / n:.1f}%)" for k, v in stages.most_common()),
             f"- Chuyến (event_group_id): {len(groups)}; có ≥ 2 loại sản phẩm: {multi} ({100 * multi / max(1, len(groups)):.0f}%); có golf: "
             f"{golf} ({100 * golf / max(1, len(groups)):.1f}%); mỗi chuyến đúng một điểm đến: {'đạt' if dests_ok else 'KHÔNG đạt'}",
             f"- Theo chuyến của khách thường ({len(generic_groups)} chuyến có event_group_id): có search "
             f"≈ {100 * search_generic / max(1, len(generic_groups)):.0f}% (mục tiêu {100 * C.SEARCH_TRIP_RATE:.0f}%), có add_to_cart "
             f"{cart_trips} ({100 * cart_trips / max(1, len(generic_groups)):.0f}%, mục tiêu {100 * C.ADD_TO_CART_TRIP_RATE:.0f}%)",
             "- Purchase theo loại: " + " · ".join(f"{k} {v}" for k, v in by_tax.most_common()),
             f"- Độ phổ biến: 10% sản phẩm được đặt nhiều nhất chiếm {100 * top_share:.0f}% số lần đặt",
             f"- Baseline phổ biến nhất tại điểm đến (ẩn lần đặt cuối của khách có ≥ 2 chuyến, top-{C.RECALL_K}): {hits}/{hidden} = "
             f"{100 * recall:.1f}% (spec: không gần 0, không vượt {100 * C.RECALL_CEILING:.0f}%"
             + (" — **VƯỢT TRẦN**, xem MOCK_DATA_SPEC §0" if recall > C.RECALL_CEILING else "") + "). Theo loại: "
             + " · ".join(f"{k} {100 * hit_by[k] / tot_by[k]:.0f}% ({tot_by[k]})" for k in sorted(tot_by, key=lambda k: -tot_by[k])),
             f"- Cạnh lộn xộn: email_optin=false {sum(1 for p in pr if not p['email_optin'])} · sms_optin=false "
             f"{sum(1 for p in pr if not p['sms_optin'])} · push_optin=false {sum(1 for p in pr if not p['push_optin'])} · "
             f"purchase trỏ product_id không tồn tại {exist}/{len(buys)} ({100 * exist / max(1, len(buys)):.1f}%) · "
             f"purchase thiếu event_group_id {no_group}/{len(buys)} ({100 * no_group / max(1, len(buys)):.1f}%)",
             f"- Persona: P1 có chuyến sắp tới đã đặt `{pers['P1_upcoming']['room'][:50]}` đêm {pers['P1_upcoming']['using_date']} "
             f"({pers['P1_upcoming']['nights']} đêm, chưa có vé bay); "
             + " · ".join(f"{p['cdp_user_id']} {p['lifecycle_stage']} ({per.get(p['cdp_user_id'], 0)} event)" for p in pr if p["cdp_user_id"] in PERSONA_IDS),
             f"- app.users: {len(res['users'])} ({len(C.PERSONAS)} persona + {C.TEST_USERS} test) · app.bookings: {len(res['bookings'])} · "
             f"app.booking_items: {len(res['booking_items'])}",
             f"- Profile sinh: **{res.get('profile') or 'demo'}** · khách thường có mua: {buyers}, quay lại (≥ 2 chuyến có event_group_id): "
             f"{returning} ({100 * returning / max(1, buyers):.0f}%) · add_to_cart bỏ giỏ (không mua sau đó): {abandoned_carts}", "",
             "`app.users.password_hash` là Argon2id của mật khẩu demo chung; email / số điện thoại là dữ liệu giả. "
             "Event `search` không có câu truy vấn (cdp.events không có cột này; `app.search_logs` không seed). "
             "Insider clone (`partners`, `insider_profiles`, `identifiers`, `insider_events`, `channel_events`) sinh từ các file này ở bước sau."]
    return "\n".join(lines) + "\n", {"stages": dict(stages), "events": len(ev), "hits": hits, "last": hidden, "recall": recall}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    ap.add_argument("--profiles", type=int, default=None, help=f"mặc định {C.DEFAULT_USERS} (demo) hoặc theo --profile")
    ap.add_argument("--zipf", type=float, default=C.ZIPF_S)
    ap.add_argument("--vinpearl-boost", type=float, default=C.VINPEARL_BOOST)
    ap.add_argument("--max-events", type=int, default=None, help=f"mặc định {C.MAX_EVENTS_PER_USER} (demo) hoặc theo --profile")
    ap.add_argument("--profile", choices=sorted(C.PROFILES), default=None,
                    help="bộ đánh giá RecSys (vd eval-v2): ghi đè tham số theo config.PROFILES; nạp vào database RIÊNG, không phải demo")
    a = ap.parse_args(argv)
    out = a.out_dir or a.data_dir / "seed"
    with open(a.data_dir / "products.jsonl", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    res = generate(rows, a.as_of, a.seed, a.profiles, a.zipf, a.vinpearl_boost, a.max_events, profile=a.profile)
    out.mkdir(parents=True, exist_ok=True)
    for name, key in (("cdp_profiles", "profiles"), ("cdp_events", "events"), ("app_users", "users"), ("app_bookings", "bookings"),
                      ("app_booking_items", "booking_items")):
        write_jsonl(out / f"{name}.jsonl", res[key])
    max_events = a.max_events or (C.PROFILES.get(a.profile, {}).get("MAX_EVENTS_PER_USER") if a.profile else None) or C.MAX_EVENTS_PER_USER
    text, stats = report(res, a.as_of, {"seed": a.seed, "max_events": max_events})
    (out / "seed_report.md").write_text(text, encoding="utf-8")
    print(text)
    if stats["recall"] > C.RECALL_CEILING and not a.profile:   # không chặn pipeline: DoD #5 đo trên seed demo; seed khác có thể vượt do tập ẩn nhỏ
        print(f"WARNING: baseline Recall@{C.RECALL_K} = {stats['recall']:.3f} > {C.RECALL_CEILING} với --seed {a.seed}; "
              "chỉnh MULTI_FLIGHT_RATE / MULTI_TICKET_RATE / SINGLE_VERTICAL_WEIGHTS trong config.py hoặc dùng seed demo.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
