"""Seed Insider clone: `partners`, `insider_profiles`, `identifiers`, `insider_events`, `channel_events`.

Theo "Kế hoạch mock data" trong file thiết kế DB của nhóm (20/09/2026). Đầu vào là seed CDP do seed_histories.py sinh; **không sửa** file nào.

    python seed_insider.py [--seed-dir data/seed] [--out-dir data/seed] [--as-of YYYY-MM-DD] [--seed 42] [--events-per-profile 10]

Quy tắc theo file:
  * insider_profiles + identifiers cho mọi profile CDP: mỗi profile có cdp_user_id, email, phone (~6.000 dòng cho 2.000 profile). Có lịch sử:
    ~8% profile đổi email (dòng cũ đóng valid_to, dòng mới cùng id_type mở); mỗi (id_type, id_value) chỉ hiệu lực ở một profile.
  * insider_events = bản sao event CDP còn trong TTL: purchase 730 ngày gần nhất, các event khác 90 ngày gần nhất.
  * channel_events ≈ 10 dòng / profile trong 6 tháng: sent → delivered 97% → open 35% → click 8%; bounce 2%, unsubscribe 1%.
    Chỉ gửi qua kênh profile đã opt-in trong CDP (email_optin / sms_optin / push_optin); profile gdpr_optin = false (3%) không có dòng nào
    sau ngày opt-out (= updated_at); sau unsubscribe ở một kênh thì không gửi thêm ở kênh đó.
Diễn giải tỷ lệ: delivered / bounce tính trên sent; open / click / unsubscribe tính trên delivered; mỗi click luôn có open trước đó.
Mọi thứ xác định theo --seed, ngày tương đối theo --as-of. Token đối tác giả; email / số điện thoại là dữ liệu giả (example.com, 090xxxxxxx).
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

NS = uuid.UUID("b7d2f4a1-3c68-4e0b-9a55-2f1e8c6d7a90")  # không gian tên cố định cho uuid5 (seed Insider)
PARTNER = "vota"
CHANNELS = (("email", 55), ("push", 35), ("sms", 10))   # trọng số chọn kênh trong số kênh đã opt-in
OPTIN = {"email": "email_optin", "sms": "sms_optin", "push": "push_optin"}
CAMPAIGN_NAMES = ["welcome", "hotel-weekend", "flight-flash-sale", "vinwonders-combo", "golf-open", "summer-beach",
                  "dormant-winback", "tier-upgrade", "autumn-getaway", "family-trip", "last-minute", "member-perk"]
P_BOUNCE, P_DROP = 0.02, 0.01          # delivered = 1 - bounce - drop = 97% (drop: gửi đi nhưng nguồn không ghi delivered / bounce)
P_OPEN, P_CLICK, P_UNSUB = 0.35, 0.08, 0.01
EXPECTED_PER_SEND = 1 + P_BOUNCE + (1 - P_BOUNCE - P_DROP) * (1 + P_OPEN + P_CLICK + P_UNSUB)   # dòng channel_events kỳ vọng / lần gửi
HISTORY_SHARE, GDPR_OFF_SHARE = 0.08, 0.03
TTL_PURCHASE, TTL_OTHER = 730, 90
EVENT_PARAMS = ("product_id", "taxonomy", "event_group_id", "quantity", "unit_price", "using_date")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(str(p) for p in parts)))


def campaigns(now: datetime) -> list[tuple[str, datetime]]:
    """12 chiến dịch rải trong ~6 tháng; chiến dịch cuối cách as_of 11 ngày."""
    out = []
    for i, name in enumerate(CAMPAIGN_NAMES):
        day = now - timedelta(days=176 - 15 * i)
        out.append((f"CMP{day:%Y%m%d}-{name}", day))
    return out


def pick_channel(rng: random.Random, allowed: list[str], banned: set[str]) -> str | None:
    opts = [(c, w) for c, w in CHANNELS if c in allowed and c not in banned]
    if not opts:
        return None
    x, acc = rng.uniform(0, sum(w for _, w in opts)), 0.0
    for c, w in opts:
        acc += w
        if x <= acc:
            return c
    return opts[-1][0]


def channel_events_for(p: dict, rng: random.Random, created: datetime, cutoff: datetime, now: datetime, camps, mean_sends: float) -> list[dict]:
    """Chuỗi channel_events của một profile. `cutoff` = thời điểm opt-out (không có dòng nào sau đó) hoặc None."""
    allowed = [c for c, flag in OPTIN.items() if p.get(flag)]
    if not allowed:
        return []
    hi = cutoff or now
    eligible = [(cid, day) for cid, day in camps if day >= created and day < hi]
    k = min(max(0, round(rng.gauss(mean_sends, mean_sends * 0.5))), len(eligible))
    rows: list[dict] = []
    unsub_at: dict[str, datetime] = {}
    for cid, day in sorted(rng.sample(eligible, k), key=lambda x: x[1]):
        t0 = day + timedelta(hours=rng.uniform(0, 72))
        ch = pick_channel(rng, allowed, {c for c, u in unsub_at.items() if t0 >= u})
        if ch is None or t0 >= hi:
            continue
        msg = uid("msg", p["cdp_user_id"], cid, ch)
        evs = [("sent", t0, {"messageId": msg})]
        r = rng.random()
        if r < P_BOUNCE:
            evs.append(("bounce", t0 + timedelta(seconds=rng.randint(1, 60)),
                        {"messageId": msg, "reason": rng.choice(["mailbox_full", "invalid_address", "blocked"])}))
        elif r >= P_BOUNCE + P_DROP:
            last = t0 + timedelta(seconds=rng.randint(1, 30))
            evs.append(("delivered", last, {"messageId": msg}))
            if rng.random() < P_OPEN:
                last = t0 + timedelta(seconds=rng.uniform(300, 172800))
                evs.append(("open", last, {"messageId": msg}))
                if rng.random() < P_CLICK / P_OPEN:
                    last = last + timedelta(seconds=rng.uniform(10, 1800))
                    evs.append(("click", last, {"messageId": msg, "url": f"https://vota.example/khuyen-mai/{cid.lower()}"}))
            if rng.random() < P_UNSUB:
                last = last + timedelta(seconds=rng.uniform(5, 3600))
                evs.append(("unsubscribe", last, {"messageId": msg}))
                unsub_at[ch] = last
        for typ, t, meta in evs:
            if t < hi:   # không có dòng nào sau opt-out / sau as_of
                rows.append({"profile_id": None, "channel": ch, "event_type": typ, "campaign_id": cid, "event_time": t, "metadata": meta})
    return rows


def generate(profiles: list[dict], events: list[dict], users: list[dict], as_of: date, seed: int = 42, events_per_profile: float = 10.0) -> dict:
    now = datetime.combine(as_of, dtime.min, tzinfo=timezone.utc)
    camps = campaigns(now)
    mean_sends = events_per_profile / EXPECTED_PER_SEND
    email_of = {u["cdp_user_id"]: u["email"] for u in users if u.get("email")}
    pid = {p["cdp_user_id"]: uid("profile", p["cdp_user_id"]) for p in profiles}
    partners = [{"partner_name": PARTNER, "request_token": "dev-" + uuid.uuid5(NS, "token|" + PARTNER).hex,
                 "created_at": fmt(now - timedelta(days=900))}]
    out_profiles, identifiers, channel = [], [], []

    for idx, p in enumerate(sorted(profiles, key=lambda r: r["cdp_user_id"]), start=1):
        user = p["cdp_user_id"]
        rng = random.Random(f"{seed}|insider|{user}")
        created, updated = parse_ts(p["created_at"]), parse_ts(p["updated_at"])
        gdpr, cutoff = True, None
        if rng.random() < GDPR_OFF_SHARE:
            lo, hi = created + timedelta(days=30), now - timedelta(days=10)
            if lo < hi:
                gdpr, cutoff = False, lo + (hi - lo) * rng.random()
                updated = cutoff   # thời điểm opt-out = lần cập nhật hồ sơ cuối

        def add(id_type: str, value: str, start: datetime, end: datetime | None = None) -> None:
            identifiers.append({"profile_id": pid[user], "id_type": id_type, "id_value": value,
                                "valid_from": fmt(start), "valid_to": fmt(end) if end else None})

        add("cdp_user_id", user, created)
        email = email_of.get(user) or f"{user.lower()}@example.com"
        span = (now - timedelta(days=30)) - (created + timedelta(days=30))
        if user not in email_of and span > timedelta(days=10) and rng.random() < HISTORY_SHARE:
            change = created + timedelta(days=30) + span * rng.random()
            add("email", f"{user.lower()}.cu@example.com", created, change)
            add("email", email, change)
        else:
            add("email", email, created)
        add("phone", f"090{idx:07d}", created)

        attrs = {k: p.get(k) for k in ("lifecycle_stage", "vinclub_tier", "home_city", "last_destination", "lifetime_order_count",
                                       "days_since_last_booking", "purchased_verticals")}   # null vẫn lưu (spec: null / '' vẫn lưu)
        out_profiles.append({"profile_id": pid[user], "partner_name": PARTNER, "attributes": attrs, "gdpr_optin": gdpr,
                             "created_at": fmt(created), "updated_at": fmt(updated)})
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
        ttl = TTL_PURCHASE if e["event_name"] == "purchase" else TTL_OTHER
        if t + timedelta(days=ttl) <= now:   # đã hết TTL (cùng luật với view live_events)
            continue
        recv = t + timedelta(seconds=random.Random(f"{seed}|recv|{e['event_id']}").randint(1, 300))
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
    unsub_at: dict[tuple, str] = {}
    for r in ch:
        if r["event_type"] == "unsubscribe":
            unsub_at[(r["profile_id"], r["channel"])] = r["event_time"]
    for r in ch:
        p = prof[r["profile_id"]]
        if not p["gdpr_optin"] and r["event_time"] > p["updated_at"]:
            viol_optout += 1
        if not cdp[r["profile_id"]].get(OPTIN[r["channel"]]):
            viol_optin += 1
        if r["event_time"] < p["created_at"]:
            viol_created += 1
        if r["event_type"] == "sent" and r["event_time"] > unsub_at.get((r["profile_id"], r["channel"]), "9999"):
            viol_after_unsub += 1
    cur = [i for i in res["identifiers"] if i["valid_to"] is None]
    dup_value = len(cur) - len({(i["id_type"], i["id_value"]) for i in cur})
    dup_type = len(cur) - len({(i["profile_id"], i["id_type"]) for i in cur})
    expired = sum(1 for e in res["insider_events"]
                  if parse_ts(e["event_time"]) + timedelta(days=TTL_PURCHASE if e["event_name"] == "purchase" else TTL_OTHER) <= now)
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
        "viol_send_after_unsub": viol_after_unsub, "viol_dup_current_value": dup_value, "viol_dup_current_type": dup_type,
        "viol_events_expired": expired,
    }


def report(s: dict, as_of: date, args: dict) -> str:
    pct = lambda x: f"{100 * x:.1f}%"
    viol = {k: v for k, v in s.items() if k.startswith("viol_")}
    return "\n".join([
        f"# Kết quả seed_insider — as_of {as_of.isoformat()}, seed {args['seed']}", "",
        f"- partners: 1 (`{PARTNER}`, token giả) · insider_profiles: **{s['profiles']}** (gdpr_optin = false: {s['gdpr_off']}) · "
        f"identifiers: **{s['identifiers']}** (đã đóng valid_to: {s['identifiers_closed']})",
        f"- insider_events: **{s['events']}** {s['events_by_name']} (purchase ≤ {TTL_PURCHASE} ngày, còn lại ≤ {TTL_OTHER} ngày)",
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
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--events-per-profile", type=float, default=10.0)
    a = ap.parse_args(argv)
    as_of, sd, od = date.fromisoformat(a.as_of), Path(a.seed_dir), Path(a.out_dir)
    profiles, events, users = (read_jsonl(sd / f) for f in ("cdp_profiles.jsonl", "cdp_events.jsonl", "app_users.jsonl"))
    res = generate(profiles, events, users, as_of, a.seed, a.events_per_profile)
    od.mkdir(parents=True, exist_ok=True)
    for name, rows in res.items():
        write_jsonl(od / f"{name if name.startswith('insider_') else 'insider_' + name}.jsonl", rows)
    text = report(summary(res, profiles, as_of), as_of, {"seed": a.seed})
    (od / "insider_report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
