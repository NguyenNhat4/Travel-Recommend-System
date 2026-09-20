"""Bước 4 — `app.users` + `app.bookings` (MOCK_DATA_SPEC §5).

Hai phần:

* `build_persona_events()` — lịch sử **cố định** của 4 persona, chạy TRƯỚC bước 3 và truyền vào đó,
  vì `seed_histories` phải chừa 4 id `VP0000001..4` và không được sinh ngẫu nhiên đè lên.
* `run()` — tài khoản đăng nhập + đơn của P1, chạy SAU bước 3 (FK `app.users.cdp_user_id` → profiles).

P1 phải có **đúng một** event purchase trong nhóm của đơn: `db/verify.sql` kiểm
`count(*) = 1` khi JOIN `app.bookings` với `cdp.events` theo `event_group_id`.
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
    uuid5_for,
    window_end,
)

USER_COLUMNS = ["user_id", "email", "password_hash", "display_name", "cdp_user_id", "persona", "created_at"]
BOOKING_COLUMNS = [
    "booking_id", "reference_code", "cdp_user_id", "event_group_id", "status",
    "contact_name", "contact_email", "contact_phone", "total_amount", "currency", "created_at",
]
BOOKING_ITEM_COLUMNS = [
    "booking_item_id", "booking_id", "product_id", "taxonomy", "product_name",
    "unit_price", "quantity", "using_date", "using_date_to", "guest_names",
]


#: Bảng chữ cái radix-64 của BCrypt — KHÁC base64 chuẩn (bắt đầu bằng "./", không có padding).
_BCRYPT_ALPHABET = b"./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def _bcrypt_b64(data: bytes) -> bytes:
    """Mã hoá 16 byte salt thành 22 ký tự theo đúng radix-64 của BCrypt.

    Không ghép chuỗi tuỳ ý vào salt của `gensalt()`: ký tự cuối chỉ mang 2 bit của byte cuối,
    nên phần lớn ký tự trong bảng là **không hợp lệ** ở vị trí đó và bcrypt trả "Invalid salt".
    """
    out = bytearray()
    index = 0
    length = len(data)
    while index < length:
        first = data[index]
        index += 1
        out.append(_BCRYPT_ALPHABET[(first >> 2) & 0x3F])
        first = (first & 0x03) << 4
        if index >= length:
            out.append(_BCRYPT_ALPHABET[first & 0x3F])
            break
        second = data[index]
        index += 1
        first |= (second >> 4) & 0x0F
        out.append(_BCRYPT_ALPHABET[first & 0x3F])
        first = (second & 0x0F) << 2
        if index >= length:
            out.append(_BCRYPT_ALPHABET[first & 0x3F])
            break
        third = data[index]
        index += 1
        first |= (third >> 6) & 0x03
        out.append(_BCRYPT_ALPHABET[first & 0x3F])
        out.append(_BCRYPT_ALPHABET[third & 0x3F])
    return bytes(out)


def hash_password(password: str, rng: np.random.Generator) -> str:
    """BCrypt cost 10, salt suy từ rng → cùng `--seed` cho cùng hash, dữ liệu tái lập được.

    Salt tất định là có chủ ý cho dữ liệu demo dùng chung một mật khẩu; tài khoản thật đăng ký
    qua backend vẫn phải dùng salt ngẫu nhiên.

    Import cục bộ: các hàm build_* test được mà không cần cài bcrypt.
    """
    import bcrypt

    salt_bytes = bytes(int(b) for b in rng.integers(0, 256, size=16))
    salt = b"$2b$%02d$" % config.BCRYPT_COST + _bcrypt_b64(salt_bytes)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def _event(
    uid: str, name: str, ts: dt.datetime, product, group: str | None,
    quantity=None, unit_price=None, using_date=None,
) -> dict:
    return {
        "cdp_user_id": uid,
        "event_name": name,
        "timestamp": ts,
        "product_id": str(product[0]) if product is not None else None,
        "taxonomy": product[1] if product is not None else None,
        "event_group_id": group,
        "quantity": quantity,
        "unit_price": unit_price,
        "using_date": using_date,
    }


def build_persona_events(seed: int, as_of: dt.date, pool) -> tuple[dict[str, list[dict]], dict]:
    """Lịch sử cố định của 4 persona (§5 bảng).

    Trả về (events theo cdp_user_id, thông tin đơn sắp tới của P1 để bước 4 dựng booking).
    """
    rng = make_rng(seed, "persona")
    events: dict[str, list[dict]] = {uid: [] for uid in config.PERSONA_USER_IDS.values()}

    p1 = config.PERSONA_USER_IDS["P1_frequent"]
    p2 = config.PERSONA_USER_IDS["P2_first_time"]
    p3 = config.PERSONA_USER_IDS["P3_dormant"]
    p4 = config.PERSONA_USER_IDS["P4_no_history"]

    nha_trang = config.PERSONA_PROFILE["P1_frequent"]["destination"]
    phu_quoc = config.PERSONA_PROFILE["P3_dormant"]["destination"]

    # --- P1: 3 chuyến Nha Trang trong 18 tháng (hotel + attraction) ---
    for days_ago in config.P1_PAST_TRIP_DAYS:
        booked = as_of - dt.timedelta(days=days_ago)
        check_in = booked + dt.timedelta(days=inclusive_int(rng, config.TRIP_LEAD_DAYS))
        group = f"OFF{booked:%Y%m%d}901"
        hotel = pool.pick(rng, nha_trang, "hotel")
        attraction = pool.pick(rng, nha_trang, "attraction")
        if hotel:
            events[p1].append(_event(p1, "product_view", random_time_on(rng, booked - dt.timedelta(days=2)), hotel, group))
            events[p1].append(_event(p1, "purchase", at_time(booked, 10), hotel, group, 1, round_price(float(hotel[3] or 0)), check_in))
        if attraction:
            events[p1].append(
                _event(p1, "purchase", at_time(booked, 11), attraction, group, 2,
                       round_price(float(attraction[3] or 0)), check_in + dt.timedelta(days=1))
            )

    # --- P1: chuyến sắp tới — ĐÚNG MỘT purchase (hotel_room Vinpearl), chưa có flight/attraction ---
    booked = as_of - dt.timedelta(days=config.P1_UPCOMING_BOOKED_DAYS_AGO)
    using_date = as_of + dt.timedelta(days=config.P1_UPCOMING_USING_OFFSET)
    upcoming_group = f"OFF{booked:%Y%m%d}902"
    room = pool.pick_vinpearl_room(nha_trang, using_date) or pool.pick(rng, nha_trang, "hotel")
    if room is None:
        raise RuntimeError(f"Không có hotel_room đặt được ở {nha_trang} cho persona P1")
    room_price = round_price(float(room[3] or 0))
    events[p1].append(_event(p1, "product_view", random_time_on(rng, booked - dt.timedelta(days=1)), room, upcoming_group))
    events[p1].append(_event(p1, "add_to_cart", at_time(booked, 9), room, upcoming_group, 1, room_price, using_date))
    events[p1].append(_event(p1, "purchase", at_time(booked, 9, 30), room, upcoming_group, 1, room_price, using_date))

    # --- P2: 2 product_view Phú Quốc, không purchase → stage new ---
    for days_ago in config.P2_VIEW_DAYS_AGO:
        day = as_of - dt.timedelta(days=days_ago)
        viewed = pool.pick(rng, phu_quoc, "hotel") or pool.pick(rng, phu_quoc, "attraction")
        if viewed:
            events[p2].append(_event(p2, "product_view", random_time_on(rng, day), viewed, f"OFF{day:%Y%m%d}903"))

    # --- P3: 2 chuyến Phú Quốc, chuyến cuối as_of - 190 → stage dormant ---
    for days_ago in config.P3_TRIP_DAYS:
        booked = as_of - dt.timedelta(days=days_ago)
        check_in = booked + dt.timedelta(days=inclusive_int(rng, config.TRIP_LEAD_DAYS))
        group = f"OFF{booked:%Y%m%d}904"
        hotel = pool.pick(rng, phu_quoc, "hotel")
        if hotel:
            events[p3].append(_event(p3, "product_view", random_time_on(rng, booked - dt.timedelta(days=3)), hotel, group))
            events[p3].append(_event(p3, "purchase", at_time(booked, 14), hotel, group, 1, round_price(float(hotel[3] or 0)), check_in))

    # --- P4: không có event nào (verify.sql: "P4 has no events") ---
    events[p4] = []

    upcoming = {
        "cdp_user_id": p1,
        "event_group_id": upcoming_group,
        "product_id": str(room[0]),
        "taxonomy": room[1],
        "product_name": room[5],
        "unit_price": room_price,
        "quantity": 1,
        "using_date": using_date,
        "booked_at": at_time(booked, 9, 30),
    }
    return events, upcoming


def _reference_code(rng: np.random.Generator, using_date: dt.date) -> str:
    alphabet = config.BOOKING_REFERENCE_ALPHABET
    suffix = "".join(
        alphabet[int(rng.integers(len(alphabet)))] for _ in range(config.BOOKING_REFERENCE_LENGTH)
    )
    return f"{config.BOOKING_REFERENCE_PREFIX}-{using_date:%Y%m%d}-{suffix}"


def run(conn, *, seed: int, as_of: dt.date, upcoming: dict) -> dict:
    rng = make_rng(seed, "seed_app")
    password_hash = hash_password(config.DEMO_PASSWORD, rng)
    created = at_time(as_of, 8)

    user_rows: list[tuple] = []
    for persona, uid in config.PERSONA_USER_IDS.items():
        meta = config.PERSONA_PROFILE[persona]
        user_rows.append(
            (
                str(uuid5_for("user", uid)), meta["email"], password_hash,
                meta["display_name"], uid, persona, created,
            )
        )

    # 50 tài khoản test: gán cho các khách seed thường, bỏ qua 4 id persona.
    for number in range(1, config.N_TEST_USERS + 1):
        uid = f"{config.USER_ID_PREFIX}{number + len(config.PERSONA_USER_IDS):0{config.USER_ID_DIGITS}d}"
        user_rows.append(
            (
                str(uuid5_for("user", uid)),
                config.TEST_USER_EMAIL_TEMPLATE.format(number),
                password_hash,
                f"Tài khoản test {number:02d}",
                uid,
                None,  # không phải persona → verify "persona users = 4" vẫn đúng
                created,
            )
        )

    with conn.cursor() as cur:
        insert_batch(cur, "app.users", USER_COLUMNS, user_rows)
    conn.commit()

    # --- Đơn của P1: khớp 1:1 với event purchase cùng event_group_id + product_id + using_date ---
    booking_id = str(uuid5_for("booking", upcoming["event_group_id"]))
    line_total = float(upcoming["unit_price"]) * upcoming["quantity"]
    persona_meta = config.PERSONA_PROFILE["P1_frequent"]
    booking_row = (
        booking_id,
        _reference_code(rng, upcoming["using_date"]),
        upcoming["cdp_user_id"],
        upcoming["event_group_id"],
        "confirmed",
        persona_meta["display_name"],
        persona_meta["email"],
        "0901234567",
        line_total,  # total_amount = Σ line_total
        "VND",
        upcoming["booked_at"],
    )
    item_row = (
        str(uuid5_for("booking_item", upcoming["event_group_id"], upcoming["product_id"])),
        booking_id,
        upcoming["product_id"],
        upcoming["taxonomy"],
        upcoming["product_name"],
        upcoming["unit_price"],
        upcoming["quantity"],
        upcoming["using_date"],
        upcoming["using_date"] + dt.timedelta(days=2),  # trả phòng
        [persona_meta["display_name"]],
    )
    with conn.cursor() as cur:
        # line_total là GENERATED — không liệt kê trong INSERT.
        insert_batch(cur, "app.bookings", BOOKING_COLUMNS, [booking_row])
        insert_batch(cur, "app.booking_items", BOOKING_ITEM_COLUMNS, [item_row])
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM app.users")
        users = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM app.users WHERE persona IS NOT NULL")
        personas = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM app.bookings")
        bookings = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM app.booking_items")
        items = cur.fetchone()[0]
    return {
        "users": users,
        "personas": personas,
        "bookings": bookings,
        "booking_items": items,
        "reference_code": booking_row[1],
        "demo_password": config.DEMO_PASSWORD,
    }
