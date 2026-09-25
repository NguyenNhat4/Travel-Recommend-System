"""Seed Insider clone: `partners`, `insider_profiles`, `identifiers`, `insider_events`, `channel_events`.

Theo MOCK_DATA_SPEC §6 (diễn giải cho chỗ mơ hồ: §0 "Điểm chốt 21/09"). Đầu vào là seed CDP do seed_histories.py sinh; **không sửa** file nào.

    python -m data_collection.seed.seed_insider [--seed-dir data/seed] [--out-dir data/seed] [--as-of YYYY-MM-DD] [--seed 42] [--events-per-profile 10]

Quy tắc (tham số ở config.py):
  * insider_profiles: một profile / cdp_user_id; attributes chỉ là tập con {vinclub_tier, home_city, last_destination, lifecycle_stage}.
    gdpr_optin = false cho khách tắt cả email / sms / push CỘNG 2% ngẫu nhiên (trừ persona); ngày opt-out = as_of − 0…180 ngày, lưu ở
    updated_at, không có channel_events nào sau đó.
  * identifiers: mỗi profile 3 dòng hiệu lực — cdp_user_id, email `<cdp_user_id viết thường>@example.com`, phone 090 + 7 số không trùng.
    1% profile có thêm một email cũ đã đóng (valid_to = as_of − 30), email hiện tại mở từ ngày đó.
  * insider_events = bản sao event CDP còn trong TTL: purchase 730 ngày gần nhất, các event khác 90 ngày gần nhất.
  * channel_events ≈ 10 dòng / profile trong 6 tháng: sent → delivered 97% → open 35% → click 8%; bounce 2% thay delivered; unsubscribe 1%,
    sau đó profile không còn dòng nào. Chỉ gửi qua kênh profile đã opt-in trong CDP. campaign_id = "CMP-" + yyyymm + "-" + 2 số.
Diễn giải tỷ lệ: delivered / bounce tính trên sent; open / click / unsubscribe tính trên delivered; mỗi click luôn có open trước đó.
Mọi thứ xác định theo --seed, ngày tương đối theo --as-of. Token đối tác giả; email / số điện thoại là dữ liệu giả (example.com, 090xxxxxxx).
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from collections import Counter
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

from . import config as C

NS = uuid.UUID("b7d2f4a1-3c68-4e0b-9a55-2f1e8c6d7a90")  # không gian tên cố định cho uuid5 (seed Insider)
OPTIN = {"email": "email_optin", "sms": "sms_optin", "push": "push_optin"}
EVENT_PARAMS = ("product_id", "taxonomy", "event_group_id", "quantity", "unit_price", "using_date")
PERSONA_IDS = {p[0] for p in C.PERSONAS}
F = C.FUNNEL
# dòng channel_events kỳ vọng / lần gửi (để quy đổi CHANNEL_EVENTS_PER_PROFILE ra số lần gửi)
EXPECTED_PER_SEND = 1 + F["bounce"] + (1 - F["bounce"] - F["drop"]) * (1 + F["open"] + F["click"] + F["unsubscribe"])


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(str(p) for p in parts)))


def delay(rng: random.Random, kind: str) -> timedelta:
    lo, hi = C.CHANNEL_DELAY_SECONDS[kind]
    return timedelta(seconds=rng.uniform(lo, hi))


def campaigns(now: datetime) -> list[tuple[str, str, datetime]]:
    """(campaign_id, tên, ngày) — CAMPAIGN_COUNT chiến dịch cách đều từ as_of − 176 tới as_of − 11; id = CMP-yyyymm-NN (NN: thứ tự trong tháng)."""
    step = (C.CAMPAIGN_SPAN_DAYS - C.CAMPAIGN_LAST_DAYS_AGO) / max(1, C.CAMPAIGN_COUNT - 1)
    out, per_month = [], Counter()
    for i in range(C.CAMPAIGN_COUNT):
        day = now - timedelta(days=round(C.CAMPAIGN_SPAN_DAYS - step * i))
        per_month[day.strftime("%Y%m")] += 1
        out.append((f"CMP-{day:%Y%m}-{per_month[day.strftime('%Y%m')]:02d}", C.CAMPAIGN_NAMES[i % len(C.CAMPAIGN_NAMES)], day))
    return out


def pick_channel(rng: random.Random, allowed: list[str]) -> str | None:
    opts = [(c, w) for c, w in C.CHANNEL_WEIGHTS.items() if c in allowed]
    if not opts:
        return None
    return rng.choices([c for c, _ in opts], [w for _, w in opts])[0]


def channel_events_for(p: dict, rng: random.Random, created: datetime, cutoff: datetime | None, now: datetime, camps, mean_sends: float) -> list[dict]:
    """Chuỗi channel_events của một profile. `cutoff` = thời điểm opt-out gdpr (không có dòng nào sau đó) hoặc None.
    Sau unsubscribe (ở bất kỳ kênh nào) profile không còn dòng nào."""
    allowed = [c for c, flag in OPTIN.items() if p.get(flag)]
    if not allowed:
        return []
    hi = cutoff or now
    eligible = [(cid, name, day) for cid, name, day in camps if created <= day < hi]
    k = min(max(0, round(rng.gauss(mean_sends, mean_sends * C.SENDS_SPREAD))), len(eligible))
    rows: list[dict] = []
    for cid, name, day in sorted(rng.sample(eligible, k), key=lambda x: x[2]):
        t0 = day + timedelta(hours=rng.uniform(0, C.SEND_WINDOW_HOURS))
        ch = pick_channel(rng, allowed)
        if ch is None or t0 >= hi:
            continue
        msg = uid("msg", p["cdp_user_id"], cid, ch)
        evs = [("sent", t0, {"messageId": msg})]
        r = rng.random()
        unsubscribed = None
        if r < F["bounce"]:
            evs.append(("bounce", t0 + delay(rng, "bounce"), {"messageId": msg, "reason": rng.choice(C.BOUNCE_REASONS)}))
        elif r >= F["bounce"] + F["drop"]:                 # drop: gửi đi nhưng nguồn không ghi delivered / bounce
            last = t0 + delay(rng, "delivered")
            evs.append(("delivered", last, {"messageId": msg}))
            if rng.random() < F["open"]:
                last = t0 + delay(rng, "open")
                evs.append(("open", last, {"messageId": msg}))
                if rng.random() < F["click"] / F["open"]:
                    last = last + delay(rng, "click")
                    evs.append(("click", last, {"messageId": msg, "url": f"https://vota.example/khuyen-mai/{name}"}))
            if rng.random() < F["unsubscribe"]:
                unsubscribed = last + delay(rng, "unsubscribe")
                evs.append(("unsubscribe", unsubscribed, {"messageId": msg}))
        for typ, t, meta in evs:
            if t < hi:   # không có dòng nào sau opt-out / sau as_of
                rows.append({"profile_id": None, "channel": ch, "event_type": typ, "campaign_id": cid, "event_time": t, "metadata": meta})
        if unsubscribed is not None:   # dừng hẳn: không gửi thêm chiến dịch nào, ở mọi kênh
            rows = [row for row in rows if row["event_time"] <= unsubscribed]
            break
    return rows


def generate(profiles: list[dict], events: list[dict], as_of: date, seed: int = C.DEFAULT_SEED,
             events_per_profile: float = C.CHANNEL_EVENTS_PER_PROFILE) -> dict:
    now = datetime.combine(as_of, dtime.min, tzinfo=timezone.utc)
    camps = campaigns(now)
    mean_sends = events_per_profile / EXPECTED_PER_SEND
    pid = {p["cdp_user_id"]: uid("profile", p["cdp_user_id"]) for p in profiles}
    partner_created = min([now - timedelta(days=C.INSIDER_PARTNER_CREATED_DAYS_AGO)]
                          + [parse_ts(p["created_at"]) - timedelta(days=1) for p in profiles])   # partner có trước mọi profile
    partners = [{"partner_name": C.INSIDER_PARTNER, "request_token": C.INSIDER_TOKEN_DEFAULT, "created_at": fmt(partner_created)}]
    closed_at = now - timedelta(days=C.EMAIL_HISTORY_CLOSED_DAYS_AGO)
    ordered = sorted(profiles, key=lambda r: r["cdp_user_id"])
    eligible = [p["cdp_user_id"] for p in ordered if parse_ts(p["created_at"]) < closed_at]
    history = set(random.Random(f"{seed}|insider|email-history").sample(eligible, min(len(eligible), round(C.EMAIL_HISTORY_RATE * len(ordered)))))
    out_profiles, identifiers, channel = [], [], []

    for idx, p in enumerate(ordered, start=1):
        user = p["cdp_user_id"]
        rng = random.Random(f"{seed}|insider|{user}")
        created, updated = parse_ts(p["created_at"]), parse_ts(p["updated_at"])
        all_off = not (p.get("email_optin") or p.get("sms_optin") or p.get("push_optin"))
        random_off = user not in PERSONA_IDS and rng.random() < C.GDPR_RANDOM_OFF_RATE
        gdpr, cutoff = True, None
        if all_off or random_off:
            gdpr = False
            cutoff = now - timedelta(days=rng.uniform(*C.GDPR_OPTOUT_DAYS_AGO))
            cutoff = min(now, max(cutoff, created + timedelta(days=1)))
            updated = cutoff   # thời điểm opt-out = lần cập nhật hồ sơ cuối (db/verify_insider.sql)

        def add(id_type: str, value: str, start: datetime, end: datetime | None = None) -> None:
            identifiers.append({"profile_id": pid[user], "id_type": id_type, "id_value": value,
                                "valid_from": fmt(start), "valid_to": fmt(end) if end else None})

        add("cdp_user_id", user, created)
        email = C.INSIDER_EMAIL.format(user=user.lower())
        if user in history:
            add("email", C.INSIDER_OLD_EMAIL.format(user=user.lower()), created, closed_at)
            add("email", email, closed_at)
        else:
            add("email", email, created)
        add("phone", f"{C.INSIDER_PHONE_PREFIX}{idx:07d}", created)

        out_profiles.append({"profile_id": pid[user], "partner_name": C.INSIDER_PARTNER,
                             "attributes": {k: p.get(k) for k in C.INSIDER_ATTRIBUTE_KEYS},   # null vẫn lưu (spec: null / '' vẫn lưu)
                             "gdpr_optin": gdpr, "created_at": fmt(created), "updated_at": fmt(updated)})
        for row in channel_events_for(p, rng, created, cutoff, now, camps, mean_sends):
            row["profile_id"] = pid[user]
            channel.append(row)

    for i, row in enumerate(identifiers, start=1):
        row["identifier_id"] = i
    channel.sort(key=lambda r: (r["event_time"], r["profile_id"], r["event_type"]))
    for i, row in enumerate(channel, start=1):
        row["channel_event_id"] = i
        row["event_time"] = fmt(row["event_time"])

    kept = []
    for e in sorted(events, key=lambda e: (e["timestamp"], e["event_id"])):
        if e["cdp_user_id"] not in pid:
            continue
        t = parse_ts(e["timestamp"])
        ttl = C.TTL_PURCHASE_DAYS if e["event_name"] == "purchase" else C.TTL_OTHER_DAYS
        if t + timedelta(days=ttl) <= now:   # đã hết TTL (cùng luật với view live_events)
            continue
        recv = t + timedelta(seconds=random.Random(f"{seed}|recv|{e['event_id']}").randint(*C.INSIDER_RECEIVE_DELAY_SECONDS))
        kept.append({"event_id": len(kept) + 1, "profile_id": pid[e["cdp_user_id"]], "event_name": e["event_name"],
                     "event_params": {k: e[k] for k in EVENT_PARAMS if e.get(k) is not None},
                     "event_time": fmt(t), "received_at": fmt(recv)})
    return {"partners": partners, "insider_profiles": out_profiles, "identifiers": identifiers,
            "insider_events": kept, "channel_events": channel}


def summary(res: dict, profiles: list[dict], as_of: date) -> dict:
    """Số liệu và các kiểm tra ràng buộc (mọi `viol_*` phải bằng 0)."""
    now = datetime.combine(as_of, dtime.min, tzinfo=timezone.utc)
    prof = {r["profile_id"]: r for r in res["insider_profiles"]}
    cdp = {uid("profile", p["cdp_user_id"]): p for p in profiles}
    ch = res["channel_events"]
    sent = sum(1 for r in ch if r["event_type"] == "sent")
    typ = Counter(r["event_type"] for r in ch)
    delivered = typ["delivered"]
    viol_optout = viol_optin = viol_created = viol_after_unsub = 0
    unsub_at: dict[str, str] = {}
    for r in ch:
        if r["event_type"] == "unsubscribe":
            unsub_at[r["profile_id"]] = min(unsub_at.get(r["profile_id"], "9999"), r["event_time"])
    for r in ch:
        p = prof[r["profile_id"]]
        if not p["gdpr_optin"] and r["event_time"] > p["updated_at"]:
            viol_optout += 1
        if not cdp[r["profile_id"]].get(OPTIN[r["channel"]]):
            viol_optin += 1
        if r["event_time"] < p["created_at"]:
            viol_created += 1
        if r["event_time"] > unsub_at.get(r["profile_id"], "9999"):   # sau unsubscribe profile không còn dòng nào
            viol_after_unsub += 1
    cur = [i for i in res["identifiers"] if i["valid_to"] is None]
    dup_value = len(cur) - len({(i["id_type"], i["id_value"]) for i in cur})
    dup_type = len(cur) - len({(i["profile_id"], i["id_type"]) for i in cur})
    bad_range = sum(1 for i in res["identifiers"] if i["valid_to"] and i["valid_to"] <= i["valid_from"])
    expired = sum(1 for e in res["insider_events"]
                  if parse_ts(e["event_time"]) + timedelta(days=C.TTL_PURCHASE_DAYS if e["event_name"] == "purchase" else C.TTL_OTHER_DAYS) <= now)
    return {
        "profiles": len(res["insider_profiles"]), "gdpr_off": sum(1 for r in res["insider_profiles"] if not r["gdpr_optin"]),
        "identifiers": len(res["identifiers"]), "identifiers_closed": len(res["identifiers"]) - len(cur),
        "events": len(res["insider_events"]), "events_by_name": dict(Counter(e["event_name"] for e in res["insider_events"])),
        "channel_events": len(ch), "channel_by_type": dict(typ), "channel_by_channel": dict(Counter(r["channel"] for r in ch)),
        "sent": sent, "delivered_rate": delivered / sent if sent else 0.0, "bounce_rate": typ["bounce"] / sent if sent else 0.0,
        "open_rate": typ["open"] / delivered if delivered else 0.0, "click_rate": typ["click"] / delivered if delivered else 0.0,
        "unsub_rate": typ["unsubscribe"] / delivered if delivered else 0.0,
        "per_profile": len(ch) / len(res["insider_profiles"]) if res["insider_profiles"] else 0.0,
        "viol_after_optout": viol_optout, "viol_channel_not_optin": viol_optin, "viol_before_created": viol_created,
        "viol_after_unsub": viol_after_unsub, "viol_dup_current_value": dup_value, "viol_dup_current_type": dup_type,
        "viol_identifier_range": bad_range, "viol_events_expired": expired,
    }


def report(s: dict, as_of: date, args: dict) -> str:
    pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    viol = {k: v for k, v in s.items() if k.startswith("viol_")}
    return "\n".join([
        f"# Kết quả seed_insider — as_of {as_of.isoformat()}, seed {args['seed']}", "",
        f"- partners: 1 (`{C.INSIDER_PARTNER}`, token giả) · insider_profiles: **{s['profiles']}** (gdpr_optin = false: {s['gdpr_off']}) · "
        f"identifiers: **{s['identifiers']}** (đã đóng valid_to: {s['identifiers_closed']})",
        f"- insider_events: **{s['events']}** {s['events_by_name']} (purchase ≤ {C.TTL_PURCHASE_DAYS} ngày, còn lại ≤ {C.TTL_OTHER_DAYS} ngày)",
        f"- channel_events: **{s['channel_events']}** ({s['per_profile']:.1f} dòng / profile) theo loại {s['channel_by_type']}, theo kênh {s['channel_by_channel']}",
        f"- Phễu: sent {s['sent']} → delivered {pct(s['delivered_rate'])} (bounce {pct(s['bounce_rate'])}) trên sent; "
        f"open {pct(s['open_rate'])} · click {pct(s['click_rate'])} · unsubscribe {pct(s['unsub_rate'])} trên delivered",
        f"- Kiểm tra ràng buộc (phải bằng 0): {viol}", "",
        "Không có email / số điện thoại thật: email dạng `…@example.com`, số dạng `090xxxxxxx`; token đối tác là chuỗi giả. "
        "Ngày tương đối theo `--as-of`, sinh lại trước demo.", ""])


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed-dir", default="data/seed")
    ap.add_argument("--out-dir", default="data/seed")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    ap.add_argument("--events-per-profile", type=float, default=C.CHANNEL_EVENTS_PER_PROFILE)
    a = ap.parse_args(argv)
    as_of, sd, od = date.fromisoformat(a.as_of), Path(a.seed_dir), Path(a.out_dir)
    profiles, events = (read_jsonl(sd / f) for f in ("cdp_profiles.jsonl", "cdp_events.jsonl"))
    res = generate(profiles, events, as_of, a.seed, a.events_per_profile)
    s = summary(res, profiles, as_of)
    od.mkdir(parents=True, exist_ok=True)
    for name, rows in res.items():
        write_jsonl(od / f"{name if name.startswith('insider_') else 'insider_' + name}.jsonl", rows)
    text = report(s, as_of, {"seed": a.seed})
    (od / "insider_report.md").write_text(text, encoding="utf-8")
    print(text)
    bad = {k: v for k, v in s.items() if k.startswith("viol_") and v}
    if bad:
        print(f"Vi phạm ràng buộc Insider: {bad}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
