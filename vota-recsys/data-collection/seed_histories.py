"""Generate customer profiles, events, users and bookings (spec section 10).

Crawling gives products, not customers. These have to be generated — and the
spec is blunt about why generating them carelessly is worse than useless:
"dữ liệu random làm một recommender hỏng trông vẫn ổn". If the data has no
structure, every model scores the same and Week 3 learns nothing.

So the generator puts real structure in, and the sanity check in ``sanity.py``
measures whether it worked:

* **Trips, not loose events.** One ``event_group_id`` = one trip = one
  destination = a hotel plus, optionally, a flight for the same dates and
  attraction or golf tickets. This is the entire basis of cross-category
  recommendation in Week 3.
* **One destination per trip.** Otherwise filtering by destination is useless —
  which is why ``report`` asserts ``multi_destination_trips == 0``.
* **Popularity follows a power law**, and it is *per destination*: a Nha Trang
  hotel is popular among Nha Trang trips, not globally. A globally uniform
  popularity would make the most-popular-in-destination baseline identical to
  the most-popular one, and comparing them is the point.
* **Customers are sparse.** Most have 1-5 events a year. If everyone had fifty,
  cold start would never fire and nobody would build it.
* **Profiles are derived from events, never sampled independently.** A profile
  saying ``lifetime_order_count = 7`` next to three events is the kind of
  inconsistency that makes a feature look broken when the data was wrong.
* **Deliberately messy edges** (section 10): some events point at product_ids
  that do not exist — which is why ``events.product_id`` has no FK in section
  4.2 — some profiles have no events at all, and a minority have opted out.

Determinism: everything derives from ``--seed`` and ``--now``, including
``created_at`` values. Relying on ``DEFAULT now()`` would make two runs differ
by construction, and then no idempotency check could ever pass.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import random
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text

import db
import exitcodes
from config import Config
from ids import booking_reference, event_group_id

log = logging.getLogger("seed")

EVENT_NAMES = ("purchase", "add_to_cart", "product_view", "search")


class SeedError(Exception):
    pass


# =============================================================================
# sampling helpers
# =============================================================================
def zipf_weights(n: int, alpha: float) -> list[float]:
    """Normalised ``1/rank**alpha`` weights.

    Stdlib rather than ``numpy.random.zipf``: numpy's zipf samples ranks from an
    unbounded distribution and then needs clamping to the catalogue size, which
    distorts the tail. A precomputed weight vector over exactly the products
    that exist is both simpler and the thing actually wanted, and it keeps numpy
    out of the dependency set for one line.
    """
    if n <= 0:
        return []
    raw = [1.0 / ((r + 1) ** alpha) for r in range(n)]
    total = sum(raw)
    return [x / total for x in raw]


def top_share(weights: list[float], fraction: float = 0.2) -> float:
    """Share of total weight held by the top ``fraction`` of items.

    Used to *verify* the "~20% of products take ~80% of bookings" claim instead
    of asserting it in a comment.
    """
    if not weights:
        return 0.0
    k = max(1, int(len(weights) * fraction))
    return sum(sorted(weights, reverse=True)[:k])


def _weighted_choice(rng: random.Random, items: list[Any], weights: list[float]) -> Any:
    return rng.choices(items, weights=weights, k=1)[0]


def _triangular_int(rng: random.Random, lo: int, hi: int, mode: int) -> int:
    return int(round(rng.triangular(lo, hi, mode)))


# =============================================================================
# catalogue
# =============================================================================
@dataclass
class Catalogue:
    """Products grouped for two-level sampling (destination, then product)."""

    by_dest_tax: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    destinations: list[str] = field(default_factory=list)
    dest_weights: list[float] = field(default_factory=list)
    product_weights: dict[tuple[str, str], list[float]] = field(default_factory=dict)

    def pick_destination(self, rng: random.Random) -> str:
        return _weighted_choice(rng, self.destinations, self.dest_weights)

    def pick(self, rng: random.Random, destination: str, taxonomy: str) -> dict | None:
        key = (destination, taxonomy)
        pool = self.by_dest_tax.get(key)
        if not pool:
            return None
        return _weighted_choice(rng, pool, self.product_weights[key])


def load_catalogue(cfg: Config, rng: random.Random) -> Catalogue:
    """Read products and build the popularity distributions.

    Products are shuffled before weights are assigned, so "popular" is not
    simply "inserted first" — which would make popularity an artefact of crawl
    order rather than a property of the data.
    """
    seed_cfg = cfg.section("seed")
    alpha = float(seed_cfg.get("zipf_alpha", 1.2))
    dest_alpha = float(seed_cfg.get("destination_zipf_alpha", 1.0))

    with db.session_scope(cfg) as s:
        rows = s.execute(
            text(
                """
                SELECT product_id, name, taxonomy, destination, unit_price
                  FROM products
                 WHERE destination <> 'unknown'
                 ORDER BY product_id
                """
            )
        ).mappings().all()

    cat = Catalogue()
    for r in rows:
        cat.by_dest_tax.setdefault((r["destination"], r["taxonomy"]), []).append(dict(r))

    for key, pool in cat.by_dest_tax.items():
        rng.shuffle(pool)
        cat.product_weights[key] = zipf_weights(len(pool), alpha)

    dests = sorted({d for d, _ in cat.by_dest_tax})
    rng.shuffle(dests)
    cat.destinations = dests
    cat.dest_weights = zipf_weights(len(dests), dest_alpha)
    return cat


def check_catalogue(cat: Catalogue, cfg: Config) -> None:
    """Fail early and explain, rather than producing a useless dataset.

    Seeding against an empty or single-destination catalogue produces histories
    that cannot demonstrate anything, and the failure would otherwise surface as
    a confusing sanity-check result rather than a missing prerequisite.
    """
    if not cat.destinations:
        raise SeedError(
            "products is empty (or every row has destination='unknown'). "
            "Run the catalogue pipeline first:\n"
            "    python -m cli discover/fetch/parse --source <s>\n"
            "    python -m cli normalize && python -m cli dedup && python -m cli load"
        )
    hotels = sum(len(v) for (d, t), v in cat.by_dest_tax.items() if t == "hotel")
    if hotels == 0:
        log.warning(
            "no hotel products: trips will be built around whatever taxonomy is "
            "available, so the 'hotel + flight + ticket' shape spec section 10 "
            "describes cannot be reproduced faithfully."
        )
    if len(cat.destinations) < 3:
        log.warning(
            "only %d destination(s) in the catalogue — per-destination popularity "
            "will be nearly degenerate and the most-popular-in-destination baseline "
            "will be hard to distinguish from most-popular.",
            len(cat.destinations),
        )


# =============================================================================
# generation
# =============================================================================
@dataclass
class Generated:
    profiles: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    bookings: list[dict] = field(default_factory=list)
    users: list[dict] = field(default_factory=list)


def _trip_shape(rng: random.Random, cfg: Config) -> str:
    comp = cfg.section("seed").get("trip_composition") or {}
    names = list(comp) or ["hotel_only"]
    weights = [float(comp[n]) for n in names] if comp else [1.0]
    return _weighted_choice(rng, names, weights)


def _events_for_user(rng: random.Random, cfg: Config) -> int:
    spec = (cfg.section("seed").get("events_per_user") or {}).get("weights") or {1: 1.0}
    counts = [int(k) for k in spec]
    weights = [float(v) for v in spec.values()]
    return _weighted_choice(rng, counts, weights)


def _taxonomies_for_shape(shape: str) -> list[str]:
    return {
        "hotel_only": ["hotel"],
        "hotel_flight": ["hotel", "flight"],
        "hotel_flight_attraction": ["hotel", "flight", "attraction"],
        "hotel_attraction": ["hotel", "attraction"],
        "golf_trip": ["hotel", "golf"],
    }.get(shape, ["hotel"])


def generate(
    cfg: Config,
    cat: Catalogue,
    *,
    users: int,
    now: dt.date,
    rng: random.Random,
    group_seq: dict[str, int],
) -> Generated:
    seed_cfg = cfg.section("seed")
    window = int(seed_cfg.get("history_window_days", 540))
    lead = seed_cfg.get("lead_time_days") or {}
    funnel = seed_cfg.get("funnel") or {}
    messy = seed_cfg.get("messy_edges") or {}
    tiers = seed_cfg.get("vinclub_tiers") or {"none": 1.0}
    home_cities = seed_cfg.get("home_cities") or {"Hà Nội": 1.0}
    iata = cfg.iata_to_destination()
    dest_to_iata = {v: k for k, v in iata.items()}

    out = Generated()
    demo_ids = {d["cdp_user_id"] for d in (seed_cfg.get("demo_accounts") or [])}

    for i in range(1, users + 1):
        cdp_user_id = f"VP{i + 1000000:07d}"
        if cdp_user_id in demo_ids:
            cdp_user_id = f"VP{i + 2000000:07d}"

        home_city = _weighted_choice(
            rng, list(home_cities), [float(v) for v in home_cities.values()]
        )
        n_events = _events_for_user(rng, cfg)
        zero_event = rng.random() < float(messy.get("p_zero_event_profile", 0.08))

        user_events: list[dict] = []
        if not zero_event:
            # Events come in trips, so the number of trips is derived from the
            # target event count rather than sampled separately.
            #
            # The budget counts EVENTS, not purchases. Counting purchases and
            # then emitting a whole funnel per trip (a search, several views, a
            # cart, then the purchases) overshoots by roughly 4x: 500 users came
            # out at ~6,800 events against the ~1,500-2,500 spec section 10 asks
            # for, and the sparsity that makes cold start fire was gone.
            remaining = n_events
            attempts = 0
            while remaining > 0 and attempts < 12:
                attempts += 1
                trip_events = _make_trip(
                    cfg, cat, rng,
                    cdp_user_id=cdp_user_id,
                    now=now,
                    window=window,
                    lead=lead,
                    funnel=funnel,
                    messy=messy,
                    group_seq=group_seq,
                    home_city=home_city,
                    dest_to_iata=dest_to_iata,
                )
                if not trip_events:
                    continue
                user_events.extend(trip_events)
                remaining -= len(trip_events)

        out.events.extend(user_events)
        out.profiles.append(
            _profile_from_events(
                cdp_user_id, user_events, cfg, now=now, rng=rng,
                home_city=home_city, tiers=tiers, messy=messy,
            )
        )

    out.bookings = _bookings_from_events(out.events)
    out.users = _demo_users(cfg, out, now=now, rng=rng)
    return out


def _make_trip(
    cfg: Config,
    cat: Catalogue,
    rng: random.Random,
    *,
    cdp_user_id: str,
    now: dt.date,
    window: int,
    lead: dict,
    funnel: dict,
    messy: dict,
    group_seq: dict[str, int],
    home_city: str,
    dest_to_iata: dict[str, str],
) -> list[dict]:
    """One trip: a shared ``event_group_id``, one destination, one date window."""
    destination = cat.pick_destination(rng)
    # Someone in Hanoi does not fly Hanoi to Hanoi.
    if destination == home_city:
        for _ in range(3):
            destination = cat.pick_destination(rng)
            if destination != home_city:
                break
        else:
            return []

    shape = _trip_shape(rng, cfg)
    taxonomies = _taxonomies_for_shape(shape)

    using_date = now - dt.timedelta(days=rng.randint(0, window))
    lead_days = _triangular_int(
        rng, int(lead.get("min", 3)), int(lead.get("max", 90)), int(lead.get("mode", 21))
    )
    booked_at = dt.datetime.combine(
        using_date - dt.timedelta(days=lead_days),
        dt.time(rng.randint(8, 22), rng.randint(0, 59)),
        tzinfo=dt.timezone.utc,
    )
    if booked_at.date() > now:
        return []

    day_key = booked_at.date().isoformat()
    group_seq[day_key] = group_seq.get(day_key, 0) + 1
    group = event_group_id(day_key, group_seq[day_key])

    picks: list[dict] = []
    for taxonomy in taxonomies:
        product = cat.pick(rng, destination, taxonomy)
        if product is None and taxonomy != "hotel":
            continue
        if product is None:
            # No hotel in this destination: fall back to any taxonomy there so
            # the trip still exists rather than silently disappearing.
            for alt in ("combo", "attraction", "golf", "flight"):
                product = cat.pick(rng, destination, alt)
                if product:
                    break
        if product:
            picks.append(product)
    if not picks:
        return []

    events: list[dict] = []

    # Funnel: a search, then views, then optionally a cart, then the purchase.
    # Week 3 trains on these, so the path matters as much as the outcome.
    if rng.random() < float(funnel.get("p_search_before", 0.55)):
        events.append(
            _event(
                cdp_user_id, "search", booked_at - dt.timedelta(days=rng.randint(1, 5)),
                product=None, group=group, taxonomy=picks[0]["taxonomy"],
                payload={"query": destination, "destination": destination},
            )
        )

    for product in picks:
        if rng.random() < float(funnel.get("p_view_before", 0.85)):
            vpr = funnel.get("views_per_purchase") or {}
            for _ in range(rng.randint(int(vpr.get("min", 1)), int(vpr.get("max", 4)))):
                events.append(
                    _event(
                        cdp_user_id, "product_view",
                        booked_at - dt.timedelta(hours=rng.randint(1, 72)),
                        product=product, group=group,
                    )
                )
        if rng.random() < float(funnel.get("p_add_to_cart", 0.45)):
            events.append(
                _event(
                    cdp_user_id, "add_to_cart",
                    booked_at - dt.timedelta(minutes=rng.randint(5, 600)),
                    product=product, group=group,
                )
            )

    abandoned = rng.random() < float(funnel.get("p_abandoned_cart", 0.18))
    if not abandoned:
        for product in picks:
            quantity = rng.choice([1, 1, 2, 2, 2, 3, 4])
            payload: dict[str, Any] = {"destination": destination, "tripShape": shape}
            if product["taxonomy"] == "flight":
                payload["originIata"] = dest_to_iata.get(home_city)
                payload["destinationIata"] = dest_to_iata.get(destination)
            events.append(
                _event(
                    cdp_user_id, "purchase", booked_at, product=product, group=group,
                    quantity=quantity, using_date=using_date, payload=payload,
                )
            )

    # A few events deliberately point at a product that does not exist. Spec
    # section 4.2 leaves events.product_id without an FK precisely so this case
    # is representable, and section 10 asks for it.
    if events and rng.random() < float(messy.get("p_dangling_product_ref", 0.02)):
        import uuid as _uuid

        victim = rng.choice(events)
        victim["product_id"] = str(_uuid.UUID(int=rng.getrandbits(128), version=5))
        victim["payload"] = {**(victim.get("payload") or {}), "note": "product since deleted"}

    return events


def _event(
    cdp_user_id: str,
    name: str,
    when: dt.datetime,
    *,
    product: dict | None,
    group: str,
    taxonomy: str | None = None,
    quantity: int | None = None,
    using_date: dt.date | None = None,
    payload: dict | None = None,
) -> dict:
    price = product.get("unit_price") if product else None
    return {
        "cdp_user_id": cdp_user_id,
        "event_name": name,
        "timestamp": when,
        "product_id": str(product["product_id"]) if product else None,
        "taxonomy": taxonomy or (product["taxonomy"] if product else None),
        "event_group_id": group,
        "quantity": quantity,
        "unit_price": Decimal(str(price)) if name == "purchase" and price is not None else None,
        "using_date": using_date,
        "payload": payload or {},
        "_destination": (product or {}).get("destination"),
    }


def _profile_from_events(
    cdp_user_id: str,
    events: list[dict],
    cfg: Config,
    *,
    now: dt.date,
    rng: random.Random,
    home_city: str,
    tiers: dict,
    messy: dict,
) -> dict:
    """Derive the profile from the events.

    Every field here is computed, not sampled. A profile that disagrees with its
    own event history (seven orders, three events) makes a downstream feature
    look broken when the fault is in the data.
    """
    lifecycle_cfg = cfg.section("seed").get("lifecycle") or {}
    purchases = [e for e in events if e["event_name"] == "purchase"]
    last_purchase = max((e["timestamp"] for e in purchases), default=None)
    days_since = (now - last_purchase.date()).days if last_purchase else None

    if not purchases:
        stage = "new"
    elif days_since is not None and days_since <= int(
        (lifecycle_cfg.get("active") or {}).get("max_days_since", 90)
    ):
        stage = "active"
    elif days_since is not None and days_since <= int(
        (lifecycle_cfg.get("dormant") or {}).get("max_days_since", 365)
    ):
        stage = "dormant"
    else:
        stage = "churned"

    verticals = sorted({e["taxonomy"] for e in purchases if e.get("taxonomy")})
    last_dest = None
    if purchases:
        latest = max(purchases, key=lambda e: e["timestamp"])
        last_dest = latest.get("_destination")

    opted_out = rng.random() < float(messy.get("p_optout", 0.06))
    first_event = min((e["timestamp"] for e in events), default=None)
    created_at = (
        first_event - dt.timedelta(days=rng.randint(1, 60))
        if first_event
        else dt.datetime.combine(
            now - dt.timedelta(days=rng.randint(1, 720)), dt.time(12, 0), tzinfo=dt.timezone.utc
        )
    )

    return {
        "cdp_user_id": cdp_user_id,
        "lifecycle_stage": stage,
        "days_since_last_booking": days_since,
        "lifetime_order_count": len({e["event_group_id"] for e in purchases}),
        "vinclub_tier": _weighted_choice(rng, list(tiers), [float(v) for v in tiers.values()]),
        "purchased_verticals": verticals,
        "home_city": home_city,
        "last_destination": last_dest,
        "gdpr_optin": not opted_out,
        "email_optin": not opted_out and rng.random() > 0.1,
        "sms_optin": not opted_out and rng.random() > 0.3,
        "push_optin": not opted_out and rng.random() > 0.2,
        "created_at": created_at,
    }


def _bookings_from_events(events: list[dict]) -> list[dict]:
    """One booking per purchase event, sharing its ``event_group_id``."""
    out: list[dict] = []
    seq: dict[str, int] = {}
    for e in events:
        if e["event_name"] != "purchase" or not e.get("product_id"):
            continue
        day = e["timestamp"].date().isoformat()
        seq[day] = seq.get(day, 0) + 1
        out.append(
            {
                "cdp_user_id": e["cdp_user_id"],
                "event_group_id": e["event_group_id"],
                "product_id": e["product_id"],
                "quantity": e.get("quantity") or 1,
                "unit_price": e.get("unit_price"),
                "using_date": e.get("using_date"),
                "reference_no": booking_reference(day, seq[day]),
                "created_at": e["timestamp"],
            }
        )
    return out


# =============================================================================
# demo accounts (spec section 10)
# =============================================================================
def _demo_users(cfg: Config, out: Generated, *, now: dt.date, rng: random.Random) -> list[dict]:
    """The four personas Week 2 needs to show, with scripted histories.

    bcrypt so Spring Security's ``BCryptPasswordEncoder`` verifies them
    unchanged in Week 2 — see question E1 in
    ``docs/decisions/cdp-schema-questions.md``.
    """
    import bcrypt

    seed_cfg = cfg.section("seed")
    accounts = seed_cfg.get("demo_accounts") or []
    password = str(seed_cfg.get("demo_password", "vota-demo-2026"))
    # A fixed salt: the point is a byte-identical dataset across runs, and this
    # is a local demo credential, not a stored user secret.
    salt = bcrypt.gensalt(rounds=10, prefix=b"2b")
    digest = bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")

    users: list[dict] = []
    for acct in accounts:
        users.append(
            {
                "email": acct["email"],
                "password_hash": digest,
                "cdp_user_id": acct["cdp_user_id"],
                "created_at": dt.datetime.combine(
                    now - dt.timedelta(days=30), dt.time(9, 0), tzinfo=dt.timezone.utc
                ),
            }
        )
    return users


def _scripted_demo_histories(
    cfg: Config,
    cat: Catalogue,
    rng: random.Random,
    *,
    now: dt.date,
    group_seq: dict[str, int],
) -> Generated:
    """Personas: a Nha Trang regular, a first-timer, a 6-month-dormant, a blank.

    Shares the caller's ``group_seq`` counter. With a private one, a demo trip
    booked on the same calendar day as a generated trip gets the same sequence
    number, so both emit the same ``event_group_id`` — two unrelated trips merge
    into one group spanning two destinations, and the spec section 10 invariant
    "1 trip = 1 destination" breaks for reasons that look like a query bug.
    """
    seed_cfg = cfg.section("seed")
    out = Generated()
    iata = cfg.iata_to_destination()
    dest_to_iata = {v: k for k, v in iata.items()}

    for acct in seed_cfg.get("demo_accounts") or []:
        uid, persona = acct["cdp_user_id"], acct["persona"]
        events: list[dict] = []

        if persona == "nha_trang_regular":
            target = "Nha Trang" if ("Nha Trang", "hotel") in cat.by_dest_tax else None
            target = target or (cat.destinations[0] if cat.destinations else None)
            for months_ago in (14, 9, 5, 2):
                events.extend(
                    _scripted_trip(
                        cfg, cat, rng, uid, target, now - dt.timedelta(days=months_ago * 30),
                        group_seq, dest_to_iata,
                    )
                )
        elif persona == "first_timer":
            target = cat.destinations[0] if cat.destinations else None
            events.extend(
                _scripted_trip(
                    cfg, cat, rng, uid, target, now - dt.timedelta(days=9),
                    group_seq, dest_to_iata, purchase=False,
                )
            )
        elif persona == "dormant_6m":
            target = cat.destinations[-1] if cat.destinations else None
            events.extend(
                _scripted_trip(
                    cfg, cat, rng, uid, target, now - dt.timedelta(days=190),
                    group_seq, dest_to_iata,
                )
            )
        # empty_history: no events at all, on purpose — the cold-start case.

        out.events.extend(events)
        out.profiles.append(
            _profile_from_events(
                uid, events, cfg, now=now, rng=rng,
                home_city="Hà Nội" if persona != "first_timer" else "TP. Hồ Chí Minh",
                tiers={"gold": 1.0} if persona == "nha_trang_regular" else {"none": 1.0},
                messy={"p_optout": 0.0},
            )
        )
    out.bookings = _bookings_from_events(out.events)
    return out


def _scripted_trip(
    cfg: Config,
    cat: Catalogue,
    rng: random.Random,
    uid: str,
    destination: str | None,
    using_date: dt.date,
    group_seq: dict[str, int],
    dest_to_iata: dict[str, str],
    *,
    purchase: bool = True,
) -> list[dict]:
    if not destination:
        return []
    booked_at = dt.datetime.combine(
        using_date - dt.timedelta(days=21), dt.time(10, 30), tzinfo=dt.timezone.utc
    )
    day = booked_at.date().isoformat()
    group_seq[day] = group_seq.get(day, 0) + 1
    group = event_group_id(day, group_seq[day])

    picks = [
        p
        for p in (
            cat.pick(rng, destination, "hotel"),
            cat.pick(rng, destination, "attraction"),
            cat.pick(rng, destination, "combo"),
        )
        if p
    ]
    if not picks:
        return []

    events = [
        _event(uid, "search", booked_at - dt.timedelta(days=2), product=None, group=group,
               taxonomy=picks[0]["taxonomy"], payload={"query": destination}),
    ]
    for p in picks:
        events.append(
            _event(uid, "product_view", booked_at - dt.timedelta(hours=5), product=p, group=group)
        )
    if purchase:
        for p in picks:
            events.append(
                _event(uid, "purchase", booked_at, product=p, group=group, quantity=2,
                       using_date=using_date, payload={"destination": destination})
            )
    else:
        events.append(
            _event(uid, "add_to_cart", booked_at, product=picks[0], group=group)
        )
    return events


# =============================================================================
# writing
# =============================================================================
def _truncate(cfg: Config) -> None:
    """Replace the seeded data wholesale.

    Truncate-and-regenerate rather than upsert, because the generator's output
    is a single coherent sample: upserting half of a new sample over half of an
    old one produces profiles whose derived fields do not match their events,
    which is precisely the inconsistency this module works to avoid.
    """
    with db.session_scope(cfg) as s:
        # users and events both reference profiles; bookings has no FK but is
        # derived from events, so it goes too.
        s.execute(text("TRUNCATE bookings, users, events, profiles RESTART IDENTITY CASCADE"))
    log.info("truncated profiles, events, users, bookings")


def _write(cfg: Config, gen: Generated) -> None:
    with db.session_scope(cfg) as s:
        for p in gen.profiles:
            s.execute(
                text(
                    """
                    INSERT INTO profiles (cdp_user_id, lifecycle_stage, days_since_last_booking,
                        lifetime_order_count, vinclub_tier, purchased_verticals, home_city,
                        last_destination, gdpr_optin, email_optin, sms_optin, push_optin, created_at)
                    VALUES (:cdp_user_id, :lifecycle_stage, :days_since_last_booking,
                        :lifetime_order_count, :vinclub_tier, :purchased_verticals, :home_city,
                        :last_destination, :gdpr_optin, :email_optin, :sms_optin, :push_optin,
                        :created_at)
                    ON CONFLICT (cdp_user_id) DO NOTHING
                    """
                ),
                p,
            )
        for e in gen.events:
            s.execute(
                text(
                    """
                    INSERT INTO events (cdp_user_id, event_name, timestamp, product_id, taxonomy,
                        event_group_id, quantity, unit_price, using_date, payload)
                    VALUES (:cdp_user_id, :event_name, :timestamp, :product_id, :taxonomy,
                        :event_group_id, :quantity, :unit_price, :using_date, CAST(:payload AS jsonb))
                    """
                ),
                {
                    **{k: v for k, v in e.items() if not k.startswith("_")},
                    "payload": json.dumps(e.get("payload") or {}, ensure_ascii=False, default=str),
                },
            )
        for b in gen.bookings:
            s.execute(
                text(
                    """
                    INSERT INTO bookings (cdp_user_id, event_group_id, product_id, quantity,
                        unit_price, using_date, reference_no, created_at)
                    VALUES (:cdp_user_id, :event_group_id, :product_id, :quantity,
                        :unit_price, :using_date, :reference_no, :created_at)
                    ON CONFLICT (reference_no) DO NOTHING
                    """
                ),
                b,
            )
        for u in gen.users:
            s.execute(
                text(
                    """
                    INSERT INTO users (email, password_hash, cdp_user_id, created_at)
                    VALUES (:email, :password_hash, :cdp_user_id, :created_at)
                    ON CONFLICT (email) DO NOTHING
                    """
                ),
                u,
            )


# =============================================================================
# runner
# =============================================================================
def run_seed(
    cfg: Config,
    *,
    users: int | None = None,
    seed: int | None = None,
    now: str | None = None,
    truncate: bool = False,
    run_sanity: bool = True,
    argv: list[str] | None = None,
) -> int:
    db.check_connection(cfg)
    db.assert_migrated(cfg)
    seed_cfg = cfg.section("seed")
    n_users = int(users or seed_cfg.get("users", 500))
    rng_seed = int(seed if seed is not None else seed_cfg.get("random_seed", 42))
    reference = dt.date.fromisoformat(now or str(seed_cfg.get("reference_date")))

    with db.session_scope(cfg) as s:
        existing = int(s.execute(text("SELECT count(*) FROM profiles")).scalar() or 0)
    if existing and not truncate:
        log.error(
            "profiles already has %d row(s). Re-seeding would mix two samples and leave "
            "profiles whose derived fields disagree with their events. Pass --truncate to "
            "replace the seeded data.",
            existing,
        )
        return exitcodes.GATE_FAILED

    rng = random.Random(rng_seed)
    cat = load_catalogue(cfg, rng)
    try:
        check_catalogue(cat, cfg)
    except SeedError as exc:
        log.error("%s", exc)
        return exitcodes.GATE_FAILED

    # Verify the 80/20 claim numerically instead of asserting it in a comment.
    sample_key = max(cat.product_weights, key=lambda k: len(cat.product_weights[k]))
    share = top_share(cat.product_weights[sample_key], 0.2)
    log.info(
        "popularity: top 20%% of products in the largest block (%s/%s, n=%d) hold %.0f%% of "
        "the sampling weight (Zipf alpha=%s)",
        sample_key[0], sample_key[1], len(cat.product_weights[sample_key]), share * 100,
        seed_cfg.get("zipf_alpha", 1.2),
    )

    with db.command_lock(cfg, "seed"):
        with db.crawl_run("__seed__", "seed", cfg, argv=argv) as run:
            run.note("users", n_users)
            run.note("random_seed", rng_seed)
            run.note("reference_date", reference.isoformat())
            run.note("zipf_alpha", seed_cfg.get("zipf_alpha"))
            run.note("top20_weight_share", round(share, 4))

            if truncate and existing:
                _truncate(cfg)

            # One sequence space for every trip, generated and scripted alike.
            group_seq: dict[str, int] = {}
            gen = generate(
                cfg, cat, users=n_users, now=reference, rng=rng, group_seq=group_seq
            )
            demo = _scripted_demo_histories(
                cfg, cat, rng, now=reference, group_seq=group_seq
            )
            gen.profiles.extend(demo.profiles)
            gen.events.extend(demo.events)
            gen.bookings.extend(demo.bookings)

            _write(cfg, gen)

            run.set("profiles", len(gen.profiles))
            run.set("events", len(gen.events))
            run.set("bookings", len(gen.bookings))
            run.set("users", len(gen.users))
            run.set("trips", len({e["event_group_id"] for e in gen.events}))

    log.info(
        "seeded %d profiles, %d events, %d bookings, %d demo users (%d trips)",
        len(gen.profiles), len(gen.events), len(gen.bookings), len(gen.users),
        len({e["event_group_id"] for e in gen.events}),
    )

    if run_sanity:
        from sanity import run_sanity as _run_sanity

        return _run_sanity(cfg)
    return exitcodes.OK
