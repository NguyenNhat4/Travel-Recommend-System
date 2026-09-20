"""Bước 5 — database `insider` (MOCK_DATA_SPEC §6).

Đây là **storage của Insider clone**, một database riêng: đọc từ `vota` rồi ghi sang `insider`
bằng hai connection tách biệt. Không bao giờ gói hai connection vào một transaction.

Insider cố ý chỉ giữ **tập con** của CDP và có TTL — lịch sử dài hạn nằm ở CDP:
event thường 90 ngày, `purchase` 730 ngày. `ttl_days` là cột GENERATED nên không insert.

Một ràng buộc dễ bỏ sót: `db/verify_insider.sql` dùng `insider_profiles.updated_at` làm **mốc opt-out**
("gdpr opt-out has no channel events after opt-out"). Vì vậy profile `gdpr_optin = false` phải được
đặt `updated_at` = đúng ngày opt-out, không để mặc định `now()`.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from . import config
from .common import (
    at_time,
    inclusive_int,
    insert_batch,
    json_dump,
    make_rng,
    uuid5_for,
    weighted_choice,
)

PROFILE_COLUMNS = ["profile_id", "partner_name", "attributes", "gdpr_optin", "created_at", "updated_at"]
IDENTIFIER_COLUMNS = ["profile_id", "id_type", "id_value", "valid_from", "valid_to"]
EVENT_COLUMNS = ["profile_id", "event_name", "event_params", "event_time", "received_at"]
CHANNEL_COLUMNS = ["profile_id", "channel", "event_type", "campaign_id", "event_time", "metadata"]


def profile_id_for(cdp_user_id: str) -> str:
    """uuid5 thay vì gen_random_uuid(): chạy lại cùng seed cho cùng profile_id."""
    return str(uuid5_for("insider_profile", cdp_user_id))


def build_channel_events(
    rng: np.random.Generator,
    *,
    profile_id: str,
    as_of: dt.date,
    opt_out_at: dt.datetime | None,
) -> list[tuple]:
    """Phễu sent → delivered 97% → open 35% → click 8%; bounce 2% thay delivered; unsubscribe 1%.

    Sau `unsubscribe` không còn dòng nào. Profile đã opt-out không có dòng nào sau ngày opt-out.
    """
    rows: list[tuple] = []
    horizon = config.INSIDER_CHANNEL_MONTHS * 30
    unsubscribed = False

    for _ in range(inclusive_int(rng, config.INSIDER_SENDS_PER_PROFILE)):
        if unsubscribed:
            break
        days_ago = int(rng.integers(0, horizon))
        day = as_of - dt.timedelta(days=days_ago)
        if opt_out_at is not None and day > opt_out_at.date():
            continue

        channel = weighted_choice(rng, config.INSIDER_CHANNELS)
        campaign = f"CMP-{day:%Y%m}-{int(rng.integers(1, 100)):02d}"
        base = at_time(day, int(rng.integers(8, 20)), int(rng.integers(0, 60)))

        def add(event_type: str, minutes: int) -> None:
            rows.append(
                (profile_id, channel, event_type, campaign,
                 base + dt.timedelta(minutes=minutes), json_dump({}))
            )

        add("sent", 0)
        if rng.random() < config.INSIDER_BOUNCE_RATE:
            add("bounce", 2)
            continue
        if rng.random() >= config.INSIDER_DELIVERED_RATE:
            continue  # gửi đi nhưng không tới nơi
        add("delivered", 3)
        if rng.random() >= config.INSIDER_OPEN_RATE:
            continue
        add("open", int(rng.integers(10, 600)))
        if rng.random() < config.INSIDER_CLICK_RATE:
            add("click", int(rng.integers(600, 900)))
        if rng.random() < config.INSIDER_UNSUBSCRIBE_RATE:
            add("unsubscribe", 960)
            unsubscribed = True

    # Mốc so sánh của verify_insider.sql là `insider_profiles.updated_at` ĐÚNG ĐẾN GIÂY
    # (`c.event_time > p.updated_at`), không phải cuối ngày opt-out. Cắt theo đúng mốc đó,
    # nếu không những dòng sinh vào buổi chiều cùng ngày sẽ thành vi phạm.
    if opt_out_at is not None:
        rows = [r for r in rows if r[4] <= opt_out_at]
    return rows


def run(vota_conn, insider_conn, *, seed: int, as_of: dt.date) -> dict:
    rng = make_rng(seed, "seed_insider")

    with vota_conn.cursor() as cur:
        cur.execute(
            """
            SELECT cdp_user_id, vinclub_tier, home_city, last_destination, lifecycle_stage,
                   email_optin, sms_optin, push_optin
            FROM   cdp.profiles ORDER BY cdp_user_id
            """
        )
        profiles = cur.fetchall()

        # TTL là luật: chỉ chép event còn hiệu lực. Event thường 90 ngày, purchase 730 ngày.
        cur.execute(
            """
            SELECT e.cdp_user_id, e.event_name, e."timestamp", e.product_id, e.taxonomy,
                   e.quantity, e.unit_price, e.event_group_id, e.using_date
            FROM   cdp.events e
            WHERE  (e.event_name = 'purchase' AND e."timestamp" >= %s)
               OR  (e.event_name <> 'purchase' AND e."timestamp" >= %s)
            ORDER  BY e."timestamp"
            """,
            (
                at_time(as_of - dt.timedelta(days=config.INSIDER_PURCHASE_TTL_DAYS), 0),
                at_time(as_of - dt.timedelta(days=config.INSIDER_EVENT_TTL_DAYS), 0),
            ),
        )
        events = cur.fetchall()

    created = at_time(as_of, 8)
    profile_rows: list[tuple] = []
    identifier_rows: list[tuple] = []
    channel_rows: list[tuple] = []
    id_map: dict[str, str] = {}
    used_phones: set[str] = set()
    opt_out_count = 0

    for (cdp_user_id, tier, home_city, last_destination, stage,
         email_optin, sms_optin, push_optin) in profiles:
        profile_id = profile_id_for(cdp_user_id)
        id_map[cdp_user_id] = profile_id

        all_channels_off = not (email_optin or sms_optin or push_optin)
        gdpr_optin = not (all_channels_off or rng.random() < config.INSIDER_EXTRA_GDPR_OPTOUT_RATE)

        opt_out_at = None
        updated_at = created
        if not gdpr_optin:
            opt_out_count += 1
            opt_out_day = as_of - dt.timedelta(days=inclusive_int(rng, config.INSIDER_OPTOUT_DAYS_AGO))
            # verify_insider.sql dùng updated_at làm mốc opt-out — phải đặt tường minh.
            opt_out_at = at_time(opt_out_day, 12)
            updated_at = opt_out_at

        attributes = {
            "vinclub_tier": tier,
            "home_city": home_city,
            "last_destination": last_destination,
            "lifecycle_stage": stage,
        }
        profile_rows.append(
            (profile_id, config.INSIDER_PARTNER_NAME, json_dump(attributes),
             gdpr_optin, created, updated_at)
        )

        # 3 identifier đang hiệu lực / profile → verify: 2.000 × 3 = 6.000.
        identifier_rows.append((profile_id, "cdp_user_id", cdp_user_id, created, None))
        identifier_rows.append((profile_id, "email", f"{cdp_user_id.lower()}@example.com", created, None))
        while True:
            phone = "09" + "".join(str(int(d)) for d in rng.integers(0, 10, size=8))
            if phone not in used_phones:  # index UNIQUE (id_type, id_value) WHERE valid_to IS NULL
                used_phones.add(phone)
                break
        identifier_rows.append((profile_id, "phone", phone, created, None))

        # 1% có thêm email cũ đã đóng, để PATCH identity có lịch sử sẵn.
        if rng.random() < config.INSIDER_OLD_EMAIL_RATE:
            closed = at_time(as_of - dt.timedelta(days=config.INSIDER_OLD_EMAIL_CLOSED_DAYS_AGO), 12)
            identifier_rows.append(
                (profile_id, "email", f"old.{cdp_user_id.lower()}@example.com",
                 created - dt.timedelta(days=365), closed)
            )

        channel_rows.extend(
            build_channel_events(rng, profile_id=profile_id, as_of=as_of, opt_out_at=opt_out_at)
        )

    event_rows: list[tuple] = []
    for (cdp_user_id, event_name, timestamp, product_id, taxonomy,
         quantity, unit_price, event_group_id, using_date) in events:
        profile_id = id_map.get(cdp_user_id)
        if profile_id is None:
            continue
        params = {
            "product_id": str(product_id) if product_id else None,
            "taxonomy": taxonomy,
            "quantity": quantity,
            "unit_price": float(unit_price) if unit_price is not None else None,
            "event_group_id": event_group_id,
            "using_date": using_date.isoformat() if using_date else None,
        }
        # ttl_days là GENERATED — không liệt kê.
        event_rows.append((profile_id, event_name, json_dump(params), timestamp, created))

    with insider_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO partners (partner_name, request_token) VALUES (%s, %s) "
            "ON CONFLICT (partner_name) DO UPDATE SET request_token = EXCLUDED.request_token",
            (config.INSIDER_PARTNER_NAME, config.INSIDER_TOKEN),
        )
        insert_batch(cur, "insider_profiles", PROFILE_COLUMNS, profile_rows)
        insert_batch(cur, "identifiers", IDENTIFIER_COLUMNS, identifier_rows)
        insert_batch(cur, "insider_events", EVENT_COLUMNS, event_rows)
        insert_batch(cur, "channel_events", CHANNEL_COLUMNS, channel_rows)
    insider_conn.commit()

    with insider_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM insider_profiles")
        profile_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM identifiers WHERE valid_to IS NULL")
        current_ids = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM insider_events")
        event_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM live_events")
        live_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM channel_events")
        channel_count = cur.fetchone()[0]
    return {
        "profiles": profile_count,
        "current_identifiers": current_ids,
        "events": event_count,
        "live_events": live_count,
        "channel_events": channel_count,
        "gdpr_opt_out": opt_out_count,
    }
