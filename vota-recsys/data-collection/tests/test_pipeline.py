"""Merge, load projection, dedup clustering, parsers, and the curated YAML."""

from __future__ import annotations

import pytest


# =============================================================================
# merge (spec section 7)
# =============================================================================
def _member(source: str, **over):
    base = {
        "source": source,
        "source_ref": f"{source}:x",
        "page_kind": "product",
        "name": f"Name from {source}",
        "taxonomy": "hotel",
        "destination": "Nha Trang",
        "description": f"Description from {source}",
        "attributes": {},
        "unit_price": None,
        "currency": "VND",
        "available": True,
        "available_from": None,
        "available_to": None,
        "image_url": None,
        "images": [],
        "latitude": None,
        "longitude": None,
        "quality_score": 0.5,
        "name_normalized": "name",
        "address": None,
        "phone": None,
        "star_rating": None,
        "brand": None,
        "quote_ctx": None,
        "is_primary": False,
    }
    base.update(over)
    return base


def test_vinpearl_wins_content_and_ota_wins_price(cfg):
    """The spec section 7 table, exercised."""
    from merge import merge_cluster

    members = [
        _member("vinpearl", description="Mô tả tiếng Việt", images=["vp1"], unit_price=None),
        _member("booking", description="English description", unit_price=3400000,
                attributes={"starRating": 5, "amenities": ["pool"]}),
    ]
    columns, attributes, winners = merge_cluster(members, cfg)
    assert columns["name"] == "Name from vinpearl"
    assert columns["description"] == "Mô tả tiếng Việt"
    assert columns["images"] == ["vp1"]
    assert columns["unit_price"] == 3400000
    assert attributes["starRating"] == 5
    by_field = {w["field"]: w["winning_source"] for w in winners}
    assert by_field["description"] == "vinpearl"
    assert by_field["unit_price"] == "booking"


def test_vietnamese_description_beats_source_order(cfg):
    """The language guard that makes ingesting English Amadeus text safe.

    Without it, an English description can win purely on source order and the
    Week 2 model comparison runs on a half-English corpus.
    """
    from merge import merge_cluster

    members = [
        _member("amadeus", description="A beachfront resort with an outdoor pool."),
        _member("agoda", description="Khu nghỉ dưỡng ven biển với hồ bơi ngoài trời và "
                                    "nhà hàng phục vụ các món ăn địa phương."),
    ]
    columns, _, _ = merge_cluster(members, cfg)
    assert "Khu nghỉ dưỡng" in columns["description"]


def test_rating_merge_picks_the_highest_review_count(cfg):
    from merge import merge_cluster

    members = [
        _member("booking", attributes={"aggregateRating": 4.35, "reviewCount": 120}),
        _member("agoda", attributes={"aggregateRating": 4.8, "reviewCount": 1200}),
    ]
    _, attributes, _ = merge_cluster(members, cfg)
    assert attributes["reviewCount"] == 1200
    assert attributes["aggregateRating"] == 4.8


def test_price_less_cluster_still_projects(cfg):
    """Most attraction and golf rows have no price.

    ``currency`` and ``available`` are NOT NULL, so a strategy that followed
    ``unit_price`` would hand NULL to both and every price-less product would
    fail to insert.
    """
    from merge import merge_cluster, project

    columns, attributes, _ = merge_cluster([_member("manual", unit_price=None)], cfg)
    row, problems = project(columns, attributes)
    assert problems == []
    assert row["currency"] == "VND"
    assert row["available"] is True
    assert row["unit_price"] is None


def test_project_emits_exactly_the_products_columns(cfg):
    from merge import merge_cluster, project
    from models import PRODUCTS_COLUMNS

    columns, attributes, _ = merge_cluster([_member("manual")], cfg)
    row, _ = project(columns, attributes)
    expected = {c for c in PRODUCTS_COLUMNS if c not in ("product_id", "created_at", "updated_at")}
    assert set(row) == expected, "project must not invent or drop a column"


def test_nameless_cluster_is_rejected_not_placeholdered(cfg):
    from merge import merge_cluster, project

    columns, attributes, _ = merge_cluster([_member("manual", name=None)], cfg)
    _row, problems = project(columns, attributes)
    assert any("name" in p for p in problems)


def test_source_ref_takes_the_primary_member(cfg):
    """``products.source_ref`` is scalar; the full mapping is in product_sources
    (question A2)."""
    from merge import merge_cluster

    members = [_member("agoda"), _member("vinpearl")]
    columns, _, _ = merge_cluster(members, cfg)
    assert columns["source_ref"] == "vinpearl:x"


# =============================================================================
# dedup (spec section 7)
# =============================================================================
def test_union_find_root_is_the_smallest_key_regardless_of_order():
    """cluster_key must be stable, because load mints product_id from it."""
    from dedup import UnionFind

    forward = UnionFind()
    for a, b in (("a", "b"), ("b", "c"), ("c", "d")):
        forward.union(a, b)
    reverse = UnionFind()
    for a, b in (("c", "d"), ("b", "c"), ("a", "b")):
        reverse.union(a, b)
    assert forward.groups() == reverse.groups()
    assert list(forward.groups()) == ["a"]


def test_transitive_matches_form_one_cluster():
    from dedup import UnionFind

    uf = UnionFind()
    uf.union("a", "b")
    uf.union("b", "c")
    groups = uf.groups()
    assert len(groups) == 1
    assert groups["a"] == ["a", "b", "c"]


def test_match_score_ignores_absent_evidence(cfg):
    """An absent component must not be scored 0: it would punish a pair for
    missing data rather than for disagreeing."""
    from dedup import match_score

    only_name = match_score({"name_similarity": 0.9}, cfg)
    with_distance = match_score({"name_similarity": 0.9, "distance_m": 10.0}, cfg)
    assert only_name == pytest.approx(0.9, abs=0.01)
    assert with_distance > 0.9


def test_match_score_rewards_proximity(cfg):
    from dedup import match_score

    near = match_score({"name_similarity": 0.5, "distance_m": 10.0}, cfg)
    far = match_score({"name_similarity": 0.5, "distance_m": 5000.0}, cfg)
    assert near > far


# =============================================================================
# parsers (offline)
# =============================================================================
HOTEL_HTML = b"""<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Hotel","name":"Vinpearl Resort Nha Trang",
 "description":"Khu ngh\\u1ec9 d\\u01b0\\u1ee1ng 5 sao tr\\u00ean \\u0111\\u1ea3o H\\u00f2n Tre.",
 "telephone":"+84 258 3598 888",
 "starRating":{"@type":"Rating","ratingValue":5},
 "address":{"@type":"PostalAddress","addressLocality":"Nha Trang","streetAddress":"Hon Tre"},
 "geo":{"@type":"GeoCoordinates","latitude":12.2158,"longitude":109.2497},
 "image":["https://cdn/a.jpg"],
 "aggregateRating":{"ratingValue":4.5,"reviewCount":1234,"bestRating":5},
 "review":[{"@type":"Review","author":{"name":"Nguyen A"},"reviewBody":"Tuyet voi"}],
 "offers":[{"@type":"Offer","name":"Deluxe Ocean View","price":"3400000"},
           {"@type":"Offer","name":"Villa 3 Bedroom","price":"12000000"}]}
</script></head><body><h1>Vinpearl Resort Nha Trang</h1>
<div class="price"><span class="value">3.400.000d</span></div></body></html>"""


def test_vinpearl_hotel_page_emits_property_plus_rooms(cfg):
    """Spec section 9: one product per room type."""
    from collectors.base import RawPage, assert_no_personal_data, get_collector
    from collectors.net import NoNetFetcher

    collector = get_collector(cfg, "vinpearl", fetcher=NoNetFetcher())
    raw = RawPage(
        url="https://vinpearl.com/vi/khach-san-resort/vinpearl-resort-nha-trang",
        http_status=200, content=HOTEL_HTML, content_type="text/html",
        quote_ctx="base", raw_page_id=1, target_id=1,
        meta={"quote_params": cfg.resolve_quote_context("base"), "taxonomy_hint": "hotel"},
    )
    rows = collector.parse(raw)
    kinds = [r["page_kind"] for r in rows]
    assert kinds.count("property") == 1
    assert kinds.count("room") == 2
    for r in rows:
        assert_no_personal_data(r)  # no reviewer name may survive
    rooms = [r for r in rows if r["page_kind"] == "room"]
    assert all(r["parent_source_ref"] == "vinpearl:vinpearl-resort-nha-trang" for r in rooms)
    prop = next(r for r in rows if r["page_kind"] == "property")
    assert prop["phone_raw"] == "+84 258 3598 888"
    assert prop["star_rating_raw"] == 5
    assert prop["review_count_raw"] == 1234
    assert prop["latitude"] == 12.2158


def test_full_normalise_of_a_parsed_hotel(cfg):
    """staging payload -> products_normalised, end to end, no database."""
    from collectors.base import RawPage, get_collector
    from collectors.net import NoNetFetcher
    from normalise import fold_property_rows, normalise_record

    collector = get_collector(cfg, "vinpearl", fetcher=NoNetFetcher())
    raw = RawPage(
        url="https://vinpearl.com/vi/khach-san-resort/vinpearl-resort-nha-trang",
        http_status=200, content=HOTEL_HTML, content_type="text/html",
        quote_ctx="base", raw_page_id=1, target_id=1,
        meta={"quote_params": cfg.resolve_quote_context("base"), "taxonomy_hint": "hotel"},
    )
    payloads = collector.parse(raw)
    records = []
    for i, payload in enumerate(payloads):
        result = normalise_record(
            {"id": i, "source": "vinpearl", "source_ref": payload["source_ref"],
             "parser_version": "vinpearl-1.0.0", "payload": payload},
            cfg,
        )
        assert not isinstance(result, tuple), f"rejected: {result}"
        records.append(result)

    records = fold_property_rows(records)
    rooms = [r for r in records if r["page_kind"] == "room"]
    assert len(rooms) == 2
    deluxe = next(r for r in rooms if "Deluxe" in r["name"])
    assert deluxe["destination"] == "Nha Trang"
    assert deluxe["unit_price"] == 3400000
    assert "Hòn Tre" in deluxe["description"], "the property description must fold down"
    assert deluxe["attributes"]["starRating"] == 5
    assert deluxe["attributes"]["aggregateRating"] == 4.5
    assert deluxe["phone"] == "+842583598888"
    assert deluxe["latitude"] == 12.2158


def test_amadeus_facets_do_not_collide(cfg):
    """Three endpoints describe one hotel; identical refs would collide on
    UNIQUE (source, source_ref, parser_version) and silently overwrite."""
    import json

    from collectors.base import RawPage, get_collector
    from collectors.net import NoNetFetcher

    collector = get_collector(cfg, "amadeus", fetcher=NoNetFetcher())
    hotels = RawPage(
        url="x", http_status=200, quote_ctx=None, content_type="application/json",
        content=json.dumps({"data": [{"hotelId": "HTNHA001", "name": "Resort",
                                      "geoCode": {"latitude": 12.2, "longitude": 109.2},
                                      "address": {"cityName": "Nha Trang"}}]}).encode(),
        meta={"endpoint": "hotels_by_geocode", "destination": "Nha Trang"},
    )
    sentiments = RawPage(
        url="x", http_status=200, quote_ctx=None, content_type="application/json",
        content=json.dumps({"data": [{"hotelId": "HTNHA001", "overallRating": 87,
                                      "numberOfReviews": 300}]}).encode(),
        meta={"endpoint": "hotel_sentiments"},
    )
    a = collector.parse(hotels)[0]
    b = collector.parse(sentiments)[0]
    assert a["source_ref"] != b["source_ref"]
    assert b["parent_source_ref"] == a["source_ref"]
    # 0-100 on this endpoint; normalise rescales it to the shared 0-5 scale.
    assert b["rating_best_raw"] == 100


def test_manual_yaml_is_valid(cfg):
    from collectors.manual import validate_manual_files

    problems = validate_manual_files(cfg)
    assert not problems, "curated YAML problems:\n  " + "\n  ".join(problems)


def test_manual_yaml_invents_no_prices(cfg):
    """An invented price flows straight into products.unit_price and is
    indistinguishable from a crawled one."""
    from pathlib import Path

    import yaml

    for rel in cfg.source("manual").get("files") or []:
        doc = yaml.safe_load(
            (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")
        )
        for item in doc.get("items") or []:
            assert item.get("price_raw") is None, (
                f"{rel}: {item.get('name')!r} has a hand-written price. Leave it null "
                "unless it was taken from a published source and dated."
            )


# =============================================================================
# quality (spec section 7)
# =============================================================================
def test_empty_flight_does_not_clear_the_demo_gate(cfg):
    """Exempt components must leave the denominator, not score 1.0.

    Scoring them 1.0 hands a flight 0.55 before any real signal is measured.
    """
    from quality import demo_threshold, quality_score

    score, _ = quality_score(
        {"taxonomy": "flight", "description": None, "images": [], "unit_price": None,
         "destination": "unknown"},
        cfg,
    )
    assert score < demo_threshold(cfg)


def test_golf_is_not_penalised_for_a_description_it_need_not_have(cfg):
    """Section 5.1 requires a description for hotel/attraction/combo only."""
    from quality import demo_threshold, quality_score

    score, _ = quality_score(
        {"taxonomy": "golf", "description": "Sân golf 18 hố " * 20, "images": [],
         "unit_price": None, "destination": "Nha Trang"},
        cfg,
    )
    assert score >= demo_threshold(cfg)


@pytest.mark.parametrize(
    "text,minimum,maximum",
    [
        ("Khu nghỉ dưỡng ven biển với hồ bơi ngoài trời và nhà hàng phục vụ các món "
         "ăn địa phương, rất phù hợp cho gia đình.", 0.5, 1.0),
        ("Beachfront resort with an outdoor pool and a restaurant in Nha Trang, "
         "Khanh Hoa province, Vietnam.", 0.0, 0.2),
        ("", 0.0, 0.0),
    ],
)
def test_real_vietnamese(text, minimum, maximum):
    from quality import real_vietnamese

    assert minimum <= real_vietnamese(text) <= maximum


# =============================================================================
# seeding (spec section 10)
# =============================================================================
def test_zipf_weights_reproduce_the_80_20_shape():
    """Spec section 10 wants ~20% of products taking ~80% of bookings."""
    from seed_histories import top_share, zipf_weights

    weights = zipf_weights(500, 1.2)
    assert weights == sorted(weights, reverse=True)
    assert abs(sum(weights) - 1.0) < 1e-9
    share = top_share(weights, 0.2)
    assert 0.6 <= share <= 0.95, f"top-20% share is {share:.2f}"


def test_event_group_id_matches_the_handbook_shape():
    from ids import event_group_id

    assert event_group_id("2026-08-10", 1) == "OFF20260810001"


def test_ids_are_deterministic():
    """Changing NS_VOTA_PRODUCT re-mints the whole catalogue."""
    from ids import NS_VOTA_PRODUCT, product_uuid

    assert str(NS_VOTA_PRODUCT) == "6f2a1c74-9b3e-5d81-a4c0-1e7b8d5f3a29"
    assert str(product_uuid("vinpearl:a")) == str(product_uuid("vinpearl:a"))
    assert product_uuid("vinpearl:a") != product_uuid("vinpearl:b")


def test_url_hash_ignores_tracking_parameters():
    from ids import url_hash

    assert url_hash("https://vinpearl.com/a?utm_source=x") == url_hash(
        "https://www.vinpearl.com/a/"
    )


def _synthetic_catalogue():
    """Two destinations, several taxonomies, no database."""
    import random
    import uuid

    from seed_histories import Catalogue, zipf_weights

    cat = Catalogue()
    for dest in ("Nha Trang", "Phú Quốc", "Đà Nẵng"):
        for tax in ("hotel", "flight", "attraction", "combo", "golf"):
            pool = [
                {
                    "product_id": uuid.uuid5(uuid.NAMESPACE_URL, f"{dest}-{tax}-{i}"),
                    "name": f"{tax} {i} {dest}",
                    "taxonomy": tax,
                    "destination": dest,
                    "unit_price": 1000000 + i,
                }
                for i in range(6)
            ]
            cat.by_dest_tax[(dest, tax)] = pool
            cat.product_weights[(dest, tax)] = zipf_weights(len(pool), 1.2)
    cat.destinations = ["Nha Trang", "Phú Quốc", "Đà Nẵng"]
    cat.dest_weights = zipf_weights(3, 1.0)
    return cat


def test_every_generated_trip_has_exactly_one_destination(cfg):
    """Spec section 10: one trip, one destination.

    Regression guard for a subtle way to break it — the demo personas used to
    keep a private ``event_group_id`` counter, so a scripted trip booked on the
    same calendar day as a generated one produced a duplicate group id and the
    two unrelated trips merged into a single group spanning two destinations.
    """
    import datetime as dt
    import random

    from seed_histories import _scripted_demo_histories, generate

    cat = _synthetic_catalogue()
    rng = random.Random(7)
    now = dt.date(2026, 9, 15)
    group_seq: dict[str, int] = {}

    gen = generate(cfg, cat, users=60, now=now, rng=rng, group_seq=group_seq)
    demo = _scripted_demo_histories(cfg, cat, rng, now=now, group_seq=group_seq)

    by_product = {
        str(p["product_id"]): p["destination"]
        for pool in cat.by_dest_tax.values()
        for p in pool
    }
    groups: dict[str, set[str]] = {}
    for e in gen.events + demo.events:
        dest = by_product.get(str(e["product_id"]))
        if e["event_group_id"] and dest:
            groups.setdefault(e["event_group_id"], set()).add(dest)

    offenders = {g: d for g, d in groups.items() if len(d) > 1}
    assert not offenders, f"trips spanning several destinations: {offenders}"
    assert len(groups) > 10, "the generator produced almost no trips"


def test_generated_histories_are_sparse(cfg):
    """Most customers have few events (spec section 10).

    If everyone had fifty, cold start would never fire and nobody would build
    it.
    """
    import datetime as dt
    import random
    from collections import Counter

    from seed_histories import generate

    gen = generate(
        cfg, _synthetic_catalogue(), users=120, now=dt.date(2026, 9, 15),
        rng=random.Random(11), group_seq={},
    )
    per_user = Counter(e["cdp_user_id"] for e in gen.events)
    counts = sorted(per_user.values())
    median = counts[len(counts) // 2]
    assert median <= 12, f"median events per user is {median}; histories are not sparse"


def test_profiles_agree_with_their_events(cfg):
    """Derived, never sampled: a profile that disagrees with its own history
    makes a downstream feature look broken when the data was wrong."""
    import datetime as dt
    import random

    from seed_histories import generate

    gen = generate(
        cfg, _synthetic_catalogue(), users=80, now=dt.date(2026, 9, 15),
        rng=random.Random(3), group_seq={},
    )
    events_by_user: dict[str, list[dict]] = {}
    for e in gen.events:
        events_by_user.setdefault(e["cdp_user_id"], []).append(e)

    for profile in gen.profiles:
        events = events_by_user.get(profile["cdp_user_id"], [])
        purchases = [e for e in events if e["event_name"] == "purchase"]
        assert profile["lifetime_order_count"] == len(
            {e["event_group_id"] for e in purchases}
        )
        if not purchases:
            assert profile["lifecycle_stage"] == "new"
            assert profile["days_since_last_booking"] is None
        else:
            assert profile["lifecycle_stage"] in ("active", "dormant", "churned")
        for vertical in profile["purchased_verticals"] or []:
            assert vertical in {e["taxonomy"] for e in purchases}
