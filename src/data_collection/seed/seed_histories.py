"""Bước 3 — `cdp.profiles` + `cdp.events` (MOCK_DATA_SPEC §4).

Mục tiêu (handbook §6): dữ liệu ngẫu nhiên đều làm recommender hỏng trông vẫn ổn. Nên độ phổ biến
theo power-law, chuyến có cấu trúc (một destination, hotel → flight → attraction), và có cạnh lộn xộn thật.

Hai điểm bắt buộc về thứ tự ghi:

* `cdp.events.cdp_user_id` có FK sang `cdp.profiles` → phải insert profile trước event.
* Nhưng các trường của profile (`lifetime_order_count`, `days_since_last_booking`,
  `purchased_verticals`, `last_destination`, `lifecycle_stage`) **suy từ event**, không sinh độc lập (§4).

Nên làm ba lượt: dựng profile rỗng → insert event → UPDATE profile từ chính event vừa ghi.

`lifecycle_stage` không gán tay: chọn ngày chuyến sao cho stage suy ra khớp phân bố mục tiêu.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from . import config
from .common import (
    at_time,
    inclusive_int,
    insert_batch,
    make_rng,
    random_time_on,
    round_price,
    stable_order_key,
    uuid5_for,
    weighted_choice,
    window_end,
    zipf_weights,
)

PROFILE_COLUMNS = [
    "cdp_user_id", "lifecycle_stage", "days_since_last_booking", "lifetime_order_count",
    "vinclub_tier", "purchased_verticals", "home_city", "last_destination",
    "email_optin", "sms_optin", "push_optin", "created_at", "updated_at",
]
EVENT_COLUMNS = [
    "cdp_user_id", "event_name", "timestamp", "product_id", "taxonomy",
    "event_group_id", "quantity", "unit_price", "using_date",
]


def user_id(index: int) -> str:
    return f"{config.USER_ID_PREFIX}{index:0{config.USER_ID_DIGITS}d}"


def derive_stage(days_since_last_purchase: int | None) -> str:
    """Quy tắc §4 — stage suy từ số liệu, không gán tay."""
    if days_since_last_purchase is None:
        return "new"
    if days_since_last_purchase <= config.STAGE_ACTIVE_MAX_DAYS:
        return "active"
    if days_since_last_purchase <= config.STAGE_DORMANT_MAX_DAYS:
        return "dormant"
    return "churned"


class ProductPool:
    """Sản phẩm đặt được theo destination + taxonomy, kèm trọng số power-law cố định.

    Thứ tự hạng dựa trên `stable_order_key(product_id)` nên "sản phẩm nào phổ biến" không đổi
    giữa các lần chạy — điều kiện để Evaluation so sánh được hai lần seed.
    """

    #: Vị trí cột trong mỗi tuple, để chỗ khác không phải đếm tay.
    ID, TAXONOMY, DESTINATION, PRICE, BRAND, NAME, LEVEL, FROM, TO = range(9)

    def __init__(self, rows: list[tuple]):
        self.rows = list(rows)
        self.by_key: dict[tuple[str, str], list[tuple]] = {}
        for row in rows:
            self.by_key.setdefault((row[self.DESTINATION], row[self.TAXONOMY]), []).append(row)

        self.weights: dict[tuple[str, str], np.ndarray] = {}
        for key, items in self.by_key.items():
            items.sort(key=lambda r: stable_order_key(str(r[self.ID])))
            weights = zipf_weights(len(items))
            boosted = np.array(
                [
                    w * (config.VINPEARL_POPULARITY_FACTOR if item[self.BRAND] == "Vinpearl" else 1.0)
                    for w, item in zip(weights, items)
                ]
            )
            self.weights[key] = boosted / boosted.sum()

    def pick_vinpearl_room(self, destination: str, using_date: dt.date):
        """Hạng phòng Vinpearl đặt được, còn hiệu lực vào `using_date` — cho persona P1.

        Chọn tất định (sản phẩm phổ biến nhất theo thứ tự hạng cố định) chứ không ngẫu nhiên:
        demo phải ra cùng một phòng ở mọi lần chạy cùng seed.
        """
        candidates = [
            row
            for row in self.by_key.get((destination, "hotel"), [])
            if row[self.LEVEL] == "room"
            and row[self.FROM] is not None
            and row[self.FROM] <= using_date <= row[self.TO]
        ]
        if not candidates:
            return None
        vinpearl = [r for r in candidates if r[self.BRAND] == "Vinpearl"]
        return (vinpearl or candidates)[0]

    def destinations(self) -> list[str]:
        return sorted({key[0] for key in self.by_key})

    def has(self, destination: str, taxonomy: str) -> bool:
        return bool(self.by_key.get((destination, taxonomy)))

    def pick(self, rng: np.random.Generator, destination: str, taxonomy: str):
        """Chọn một sản phẩm theo power-law — sản phẩm phổ biến được chọn lại nhiều lần."""
        key = (destination, taxonomy)
        items = self.by_key.get(key)
        if not items:
            return None
        index = int(rng.choice(len(items), p=self.weights[key]))
        return items[index]

    def bookable_count(self, destination: str) -> int:
        return sum(len(v) for k, v in self.by_key.items() if k[0] == destination)


def _noisy_price(rng: np.random.Generator, unit_price) -> int | None:
    if unit_price is None:
        return None
    factor = 1.0 + float(rng.uniform(-config.PRICE_NOISE, config.PRICE_NOISE))
    return round_price(float(unit_price) * factor)


def build_trip_events(
    rng: np.random.Generator,
    *,
    cdp_user_id: str,
    destination: str,
    booked_on: dt.date,
    check_in: dt.date,
    pool: ProductPool,
    group_id: str,
    as_of: dt.date,
) -> list[dict]:
    """Event của một chuyến, theo đúng thứ tự thời gian (§4).

    search (30%) → 1–3 product_view → add_to_cart (40%) → purchase cho từng vertical.
    """
    events: list[dict] = []

    # Luôn 1 vertical; 65% chuyến có vertical thứ hai, 10% có thêm vertical thứ ba (§4).
    # Thêm từng cái một thay vì tung xúc xắc cho mọi taxonomy: cách kia cho trung bình ~2,1
    # vertical/chuyến và đẩy tổng event vượt cổng 6.000–8.000 của verify.sql.
    verticals = ["hotel"] if pool.has(destination, "hotel") else []
    if not verticals:
        for taxonomy in config.TRIP_VERTICAL_ORDER:
            if pool.has(destination, taxonomy):
                verticals = [taxonomy]
                break
    if not verticals:
        return events

    available = [
        t for t in ("flight", "attraction", "combo") if pool.has(destination, t) and t not in verticals
    ]
    if available and rng.random() < config.TRIP_MULTI_VERTICAL_RATE:
        chosen = available.pop(int(rng.integers(len(available))))
        verticals.append(chosen)
        if available and rng.random() < config.TRIP_THIRD_VERTICAL_RATE:
            verticals.append(available.pop(int(rng.integers(len(available)))))
    if pool.has(destination, "golf") and rng.random() < config.TRIP_GOLF_RATE:
        verticals.append("golf")

    verticals = [t for t in config.TRIP_VERTICAL_ORDER if t in verticals]
    picks = [(t, pool.pick(rng, destination, t)) for t in verticals]
    picks = [(t, p) for t, p in picks if p is not None]
    if not picks:
        return events

    # Một chuyến = một lần checkout, nên chốt thời điểm mua trước rồi đặt view/cart lùi về trước nó.
    # Nếu sinh view bằng giờ ngẫu nhiên trong ngày, view lead=0 có thể rơi vào buổi tối SAU khi đã mua
    # lúc sáng — sai thứ tự "product_view trước purchase 0–7 ngày" (§4).
    purchase_at = at_time(booked_on, int(rng.integers(10, 22)), int(rng.integers(0, 60)))

    view_times: list[dt.datetime] = []
    view_events: list[dict] = []
    # product_view có thể trỏ sản phẩm khác cùng destination — người ta xem rồi mới chọn.
    for _ in range(inclusive_int(rng, config.VIEWS_PER_TRIP)):
        taxonomy = picks[int(rng.integers(len(picks)))][0]
        viewed = pool.pick(rng, destination, taxonomy)
        if viewed is None:
            continue
        lead = inclusive_int(rng, config.VIEW_LEAD_DAYS)
        if lead == 0:
            viewed_at = purchase_at - dt.timedelta(minutes=int(rng.integers(30, 600)))
        else:
            viewed_at = random_time_on(rng, booked_on - dt.timedelta(days=lead))
        view_times.append(viewed_at)
        view_events.append(
            {
                "cdp_user_id": cdp_user_id,
                "event_name": "product_view",
                "timestamp": viewed_at,
                "product_id": str(viewed[0]),
                "taxonomy": viewed[1],
                "event_group_id": group_id,
                "quantity": None,
                "unit_price": None,
                "using_date": None,
            }
        )

    if rng.random() < config.SEARCH_EVENT_RATE:
        # search mở đầu chuyến: trước mọi product_view.
        earliest = min(view_times) if view_times else purchase_at
        events.append(
            {
                "cdp_user_id": cdp_user_id,
                "event_name": "search",
                "timestamp": earliest - dt.timedelta(minutes=int(rng.integers(5, 240))),
                "product_id": None,
                "taxonomy": None,
                "event_group_id": group_id,
                "quantity": None,
                "unit_price": None,
                "using_date": None,
            }
        )
    events.extend(view_events)

    for index, (taxonomy, product) in enumerate(picks):
        if taxonomy == "flight":
            using_date = check_in  # bay đúng ngày nhận phòng
        elif taxonomy == "attraction":
            using_date = check_in + dt.timedelta(days=config.ATTRACTION_OFFSET_DAYS)
        else:
            using_date = check_in

        # Bất biến của checkout: usingDate tương lai phải nằm trong [available_from, available_to]
        # của chính sản phẩm (verify.sql "future purchases inside window"). Ràng buộc này chỉ áp
        # cho chuyến sắp tới, không áp cho event lịch sử (DATABASE_SCHEMA §1 mục 13).
        # Chuyến bay là ca chặt nhất: from = to = đúng ngày bay.
        # Dùng `>=` kèm dung sai: verify so với current_date của database, seed chỉ biết as_of.
        if using_date >= as_of - dt.timedelta(days=config.WINDOW_CLAMP_SKEW_DAYS):
            start, finish = product[ProductPool.FROM], product[ProductPool.TO]
            if start is not None and finish is not None:
                using_date = min(max(using_date, start), finish)

        if rng.random() < config.ADD_TO_CART_RATE:
            events.append(
                {
                    "cdp_user_id": cdp_user_id,
                    "event_name": "add_to_cart",
                    "timestamp": purchase_at - dt.timedelta(minutes=int(rng.integers(5, 25))),
                    "product_id": str(product[0]),
                    "taxonomy": taxonomy,
                    "event_group_id": group_id,
                    "quantity": 1,
                    "unit_price": _noisy_price(rng, product[3]),
                    "using_date": using_date,
                }
            )

        events.append(
            {
                "cdp_user_id": cdp_user_id,
                "event_name": "purchase",
                # Các vertical của cùng một checkout cách nhau vài giây, giữ đúng thứ tự
                # hotel → flight → attraction → golf.
                "timestamp": purchase_at + dt.timedelta(seconds=10 * index),
                "product_id": str(product[0]),
                "taxonomy": taxonomy,
                "event_group_id": group_id,
                "quantity": inclusive_int(rng, config.PURCHASE_QUANTITY[taxonomy]),
                "unit_price": _noisy_price(rng, product[3]),
                "using_date": using_date,
            }
        )

    events.sort(key=lambda e: e["timestamp"])
    return events


def _group_id(counter: dict[dt.date, int], day: dt.date) -> str:
    counter[day] = counter.get(day, 0) + 1
    return f"OFF{day:%Y%m%d}{counter[day]:03d}"


def build_histories(
    *,
    seed: int,
    as_of: dt.date,
    pool: ProductPool,
    n_users: int,
    reserved: dict[str, list[dict]],
) -> tuple[list[tuple], list[dict]]:
    """Sinh profile + event cho toàn bộ khách.

    `reserved` là lịch sử đã dựng sẵn của persona (VP0000001..4) — seed_app cần chúng cố định,
    nên bước này chỉ chèn vào chứ không sinh ngẫu nhiên đè lên.
    """
    rng = make_rng(seed, "seed_histories")
    destinations = pool.destinations()
    if not destinations:
        raise RuntimeError("Không có sản phẩm đặt được nào — chạy load_products trước")

    # Chọn destination theo số sản phẩm bookable (§4).
    dest_weights = np.array([pool.bookable_count(d) for d in destinations], dtype=float)
    dest_weights /= dest_weights.sum()

    group_counter: dict[dt.date, int] = {}
    all_events: list[dict] = []
    profile_seed: list[dict] = []

    # Persona trước, để id VP0000001..4 luôn thuộc về họ.
    for uid, events in reserved.items():
        all_events.extend(events)

    stage_names = list(config.STAGE_DISTRIBUTION)
    stage_probs = np.array([config.STAGE_DISTRIBUTION[s] for s in stage_names])
    stage_probs /= stage_probs.sum()

    for index in range(1, n_users + 1):
        uid = user_id(index)
        is_persona = uid in reserved

        tier = weighted_choice(rng, config.VINCLUB_TIERS)
        home_city = weighted_choice(rng, config.HOME_CITIES)
        if is_persona:
            # Persona phải cố định, không phụ thuộc may rủi: UX spec §5 yêu cầu P1 là Gold,
            # và demo phải ra cùng một màn hình ở mọi lần chạy.
            persona_key = next(k for k, v in config.PERSONA_USER_IDS.items() if v == uid)
            meta = config.PERSONA_PROFILE[persona_key]
            tier, home_city = meta["vinclub_tier"], meta["home_city"]

        profile_seed.append(
            {
                "cdp_user_id": uid,
                "vinclub_tier": tier,
                "home_city": home_city,
                # Persona luôn nhận được mọi kênh: demo không nên phụ thuộc vào việc
                # có bị rơi vào 5% tắt email hay không.
                "email_optin": True if is_persona else bool(rng.random() >= config.EMAIL_OPTOUT_RATE),
                "sms_optin": True if is_persona else bool(rng.random() >= config.SMS_OPTOUT_RATE),
                "push_optin": True if is_persona else bool(rng.random() >= config.PUSH_OPTOUT_RATE),
            }
        )
        if is_persona:
            continue

        target_stage = stage_names[int(rng.choice(len(stage_names), p=stage_probs))]
        n_trips = int(weighted_choice(rng, config.STAGE_TRIP_WEIGHTS[target_stage]))
        if target_stage == "new":
            # new = chưa từng mua. Có thể có 1 chuyến chỉ gồm product_view.
            if n_trips:
                destination = destinations[int(rng.choice(len(destinations), p=dest_weights))]
                day = as_of - dt.timedelta(days=int(rng.integers(1, 120)))
                group = _group_id(group_counter, day)
                for _ in range(inclusive_int(rng, config.VIEWS_PER_TRIP)):
                    taxonomy = "hotel" if pool.has(destination, "hotel") else "attraction"
                    product = pool.pick(rng, destination, taxonomy)
                    if product is None:
                        continue
                    all_events.append(
                        {
                            "cdp_user_id": uid,
                            "event_name": "product_view",
                            "timestamp": random_time_on(rng, day),
                            "product_id": str(product[0]),
                            "taxonomy": product[1],
                            "event_group_id": group,
                            "quantity": None,
                            "unit_price": None,
                            "using_date": None,
                        }
                    )
            continue

        # Chuyến cuối nằm đúng khoảng ngày của stage → stage suy ra khớp phân bố mục tiêu.
        last_gap = inclusive_int(rng, config.STAGE_LAST_TRIP_DAYS[target_stage])
        gaps = [last_gap]
        for _ in range(n_trips - 1):
            extra = last_gap + int(rng.integers(60, config.HISTORY_MONTHS * 30))
            gaps.append(min(extra, config.HISTORY_MONTHS * 30))
        gaps.sort(reverse=True)  # chuyến cũ trước

        user_events: list[dict] = []
        for gap in gaps:
            booked_on = as_of - dt.timedelta(days=gap)
            check_in = booked_on + dt.timedelta(days=inclusive_int(rng, config.TRIP_LEAD_DAYS))
            # Chuyến trong tương lai phải nằm trong cửa sổ đặt chỗ, nếu không
            # verify "future purchases inside window" sẽ FAIL.
            if check_in > window_end(as_of):
                check_in = min(booked_on + dt.timedelta(days=7), window_end(as_of))
                if check_in < booked_on:
                    check_in = booked_on
            destination = destinations[int(rng.choice(len(destinations), p=dest_weights))]
            user_events.extend(
                build_trip_events(
                    rng,
                    cdp_user_id=uid,
                    destination=destination,
                    booked_on=booked_on,
                    check_in=check_in,
                    pool=pool,
                    group_id=_group_id(group_counter, booked_on),
                    as_of=as_of,
                )
            )

        # Trần cứng: verify.sql yêu cầu max(event/khách) <= 15.
        if len(user_events) > config.MAX_EVENTS_PER_USER:
            purchases = [e for e in user_events if e["event_name"] == "purchase"]
            others = [e for e in user_events if e["event_name"] != "purchase"]
            keep = config.MAX_EVENTS_PER_USER - len(purchases)
            user_events = sorted(purchases + others[: max(keep, 0)], key=lambda e: e["timestamp"])
        all_events.extend(user_events)

    return profile_seed, all_events


def apply_messy_edges(
    rng: np.random.Generator, events: list[dict], reserved_users: set[str]
) -> dict:
    """Cạnh lộn xộn (§4): event trỏ sản phẩm đã xoá, event mất nhóm, xem hai destination cùng ngày.

    Không đụng vào persona — demo phải đoán trước được.
    Đây là lý do `cdp.events.product_id` cố ý KHÔNG có FK (DATABASE_SCHEMA §3).
    """
    broken = missing_group = 0
    for index, event in enumerate(events):
        if event["cdp_user_id"] in reserved_users:
            continue
        if event["event_name"] == "purchase" and rng.random() < config.BROKEN_PRODUCT_RATE:
            # uuid5 chứ không phải uuid4: id "sản phẩm đã xoá" phải giống nhau giữa các lần chạy
            # cùng seed. Namespace riêng nên không bao giờ đụng product_id thật.
            event["product_id"] = str(uuid5_for("deleted-product", event["cdp_user_id"], str(index)))
            broken += 1
        if event["event_group_id"] and rng.random() < config.MISSING_GROUP_RATE:
            event["event_group_id"] = None
            missing_group += 1
    return {"broken_product_id": broken, "missing_group_id": missing_group}


def write_profiles_shell(conn, profiles: list[dict], as_of: dt.date) -> int:
    created = at_time(as_of, 8)
    rows = [
        (
            p["cdp_user_id"], "new", None, 0, p["vinclub_tier"], [], p["home_city"], None,
            p["email_optin"], p["sms_optin"], p["push_optin"], created, created,
        )
        for p in profiles
    ]
    with conn.cursor() as cur:
        insert_batch(cur, "cdp.profiles", PROFILE_COLUMNS, rows)
    return len(rows)


def write_events(conn, events: list[dict]) -> int:
    rows = [
        (
            e["cdp_user_id"], e["event_name"], e["timestamp"], e["product_id"], e["taxonomy"],
            e["event_group_id"], e["quantity"], e["unit_price"], e["using_date"],
        )
        for e in events
    ]
    with conn.cursor() as cur:
        # "timestamp" là từ khoá SQL, phải để trong ngoặc kép ở mọi câu lệnh.
        columns = [f'"{c}"' if c == "timestamp" else c for c in EVENT_COLUMNS]
        insert_batch(cur, "cdp.events", columns, rows)
    return len(rows)


def rebuild_profiles(conn, as_of: dt.date) -> None:
    """Tính lại profile TỪ event — không sinh độc lập (§4).

    Chỉ đếm purchase trỏ tới sản phẩm còn tồn tại: event mồ côi (cạnh lộn xộn) không phải đơn thật.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH purchases AS (
                SELECT e.cdp_user_id,
                       e.event_group_id,
                       e."timestamp",
                       e.taxonomy,
                       p.destination
                FROM   cdp.events e
                JOIN   cdp.products p ON p.product_id = e.product_id
                WHERE  e.event_name = 'purchase'
            ),
            agg AS (
                SELECT cdp_user_id,
                       count(DISTINCT coalesce(event_group_id, cdp_user_id || to_char("timestamp",'YYYYMMDDHH24MISS')))
                           AS order_count,
                       max("timestamp") AS last_purchase,
                       array_agg(DISTINCT taxonomy) AS verticals
                FROM   purchases GROUP BY cdp_user_id
            ),
            latest AS (
                SELECT DISTINCT ON (cdp_user_id) cdp_user_id, destination
                FROM   purchases ORDER BY cdp_user_id, "timestamp" DESC
            )
            UPDATE cdp.profiles pr
            SET    lifetime_order_count    = coalesce(a.order_count, 0),
                   days_since_last_booking = CASE WHEN a.last_purchase IS NULL THEN NULL
                                                  ELSE GREATEST((%s::date - a.last_purchase::date), 0) END,
                   purchased_verticals     = coalesce(a.verticals, '{}'),
                   last_destination        = l.destination,
                   lifecycle_stage         = CASE
                       WHEN a.last_purchase IS NULL THEN 'new'
                       WHEN (%s::date - a.last_purchase::date) <= %s THEN 'active'
                       WHEN (%s::date - a.last_purchase::date) <= %s THEN 'dormant'
                       ELSE 'churned' END,
                   -- Mốc thời gian suy từ as_of, không phải now(): cùng --seed + --as-of phải
                   -- cho cùng dữ liệu trên mọi máy, kể cả cột timestamp.
                   updated_at              = %s
            FROM   cdp.profiles base
            LEFT   JOIN agg a    ON a.cdp_user_id = base.cdp_user_id
            LEFT   JOIN latest l ON l.cdp_user_id = base.cdp_user_id
            WHERE  pr.cdp_user_id = base.cdp_user_id
            """,
            (
                as_of, as_of, config.STAGE_ACTIVE_MAX_DAYS,
                as_of, config.STAGE_DORMANT_MAX_DAYS, at_time(as_of, 8),
            ),
        )
    conn.commit()


def load_pool(conn) -> ProductPool:
    """Đọc sản phẩm đặt được. `is_bookable` chỉ định nghĩa ở view `product_meta` (PRODUCT_SCHEMA §4),
    nên JOIN vào view thay vì chép lại điều kiện — thêm ngoại lệ sau này chỉ sửa view."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.product_id, p.taxonomy, p.destination, p.unit_price,
                   p.attributes->>'brand', p.name, p.attributes->>'level',
                   p.available_from, p.available_to
            FROM   cdp.products p
            JOIN   catalog.product_meta m USING (product_id)
            WHERE  m.is_bookable AND p.available
            """
        )
        return ProductPool(cur.fetchall())


def run(
    conn, *, seed: int, as_of: dt.date, n_users: int,
    reserved: dict[str, list[dict]], pool: ProductPool,
) -> dict:
    profiles, events = build_histories(
        seed=seed, as_of=as_of, pool=pool, n_users=n_users, reserved=reserved
    )
    messy = apply_messy_edges(make_rng(seed, "messy_edges"), events, set(reserved))

    write_profiles_shell(conn, profiles, as_of)
    conn.commit()
    write_events(conn, events)
    conn.commit()
    rebuild_profiles(conn, as_of)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM cdp.profiles")
        profile_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM cdp.events")
        event_count = cur.fetchone()[0]
        cur.execute("SELECT lifecycle_stage, count(*) FROM cdp.profiles GROUP BY 1 ORDER BY 1")
        stages = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            "SELECT coalesce(max(n), 0) FROM (SELECT count(*) n FROM cdp.events GROUP BY cdp_user_id) t"
        )
        max_events = cur.fetchone()[0]
    return {
        "profiles": profile_count,
        "events": event_count,
        "max_events_per_user": max_events,
        "stages": stages,
        "stage_pct": {k: round(100 * v / profile_count, 1) for k, v in stages.items()},
        **messy,
    }
