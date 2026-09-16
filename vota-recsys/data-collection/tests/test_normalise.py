"""Table-driven tests for the spec section 6.2 normalisation rules."""

from __future__ import annotations

from decimal import Decimal

import pytest


# =============================================================================
# price (spec section 6.2)
# =============================================================================
@pytest.mark.parametrize(
    "raw,expected,currency",
    [
        ("3.400.000đ", Decimal("3400000"), "VND"),
        ("3.400.000 đ", Decimal("3400000"), "VND"),
        ("3,400,000 VND", Decimal("3400000"), "VND"),
        ("1.234.567 ₫", Decimal("1234567"), "VND"),
        ("từ 2.500.000đ", Decimal("2500000"), "VND"),
        # A range: the lower bound is the useful number.
        ("12.000.000 - 18.000.000đ", Decimal("12000000"), "VND"),
        ("3,4tr", Decimal("3400000"), None),
        ("3.4 triệu", Decimal("3400000"), None),
        ("250k", Decimal("250000"), None),
        ("$150", Decimal("150"), "USD"),
        ("150 USD", Decimal("150"), "USD"),
        (3400000, Decimal("3400000"), None),
        # Nothing usable: a wrong price is worse than a missing one, because
        # quality_score can see a missing one.
        ("liên hệ", None, None),
        ("Giá liên hệ", None, None),
        ("", None, None),
        (None, None, None),
        # Implausible for VND — 500đ is not a room rate.
        ("500đ", None, "VND"),
    ],
)
def test_parse_price(cfg, raw, expected, currency):
    from normalise import parse_price

    value, code = parse_price(raw, cfg)
    assert value == expected
    if currency is not None:
        assert code == currency


def test_to_vnd_records_the_rate(cfg):
    from normalise import to_vnd

    vnd, rate = to_vnd(Decimal("100"), "USD", cfg)
    assert rate == Decimal(str(cfg.section("fx_rates")["rates"]["USD"]))
    assert vnd == (Decimal("100") * rate).quantize(Decimal("0.01"))


def test_unknown_currency_leaves_price_unset(cfg):
    """Better an empty price than one converted at a guessed rate."""
    from normalise import to_vnd

    assert to_vnd(Decimal("100"), "XYZ", cfg) == (None, None)


# =============================================================================
# destination (spec section 6.1)
# =============================================================================
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Nha Trang", "Nha Trang"),
        ("Khánh Hoà", "Nha Trang"),
        ("Khanh Hoa", "Nha Trang"),
        ("Cam Ranh", "Nha Trang"),
        ("Bãi Dài", "Nha Trang"),
        ("CXR", "Nha Trang"),
        # Three characters: a minimum-alias-length guard would lose these, and
        # Huế is one of the 15 canonical destinations.
        ("Huế", "Huế"),
        ("Hue", "Huế"),
        ("HUI", "Huế"),
        ("HAN", "Hà Nội"),
        ("Sài Gòn", "TP. Hồ Chí Minh"),
        ("Ho Chi Minh City", "TP. Hồ Chí Minh"),
        ("SGN", "TP. Hồ Chí Minh"),
        # Documented decision (question D1): HPH is the gateway airport.
        ("HPH", "Hạ Long"),
        ("Quảng Ninh", "Hạ Long"),
        ("Nam Hội An", "Nam Hội An"),
        ("Phu Quoc", "Phú Quốc"),
        # Never guessed (spec section 6.1: "không tự đoán").
        ("Somewhere Else", "unknown"),
        ("", "unknown"),
    ],
)
def test_map_destination(cfg, raw, expected):
    from normalise import map_destination

    name, _method = map_destination([raw], cfg)
    assert name == expected


def test_destination_matches_inside_a_longer_string(cfg):
    from normalise import map_destination

    for haystack in (
        "Thành phố Huế, Thừa Thiên Huế",
        "Khách sạn tại Huế",
        "Việt Nam > Huế > Trung tâm",
    ):
        name, method = map_destination([haystack], cfg)
        assert name == "Huế", haystack
        assert method in ("exact", "alias")


def test_ambiguous_aliases_do_not_match(cfg):
    """"Việt Nam" must not resolve to a destination."""
    from normalise import map_destination

    name, _ = map_destination(["Việt Nam"], cfg)
    assert name == "unknown"


def test_geo_fallback_is_bounded(cfg):
    from normalise import destination_from_geo

    near, method = destination_from_geo(12.2388, 109.1967, cfg)
    assert near == "Nha Trang" and method == "geo"
    # Middle of the South China Sea: nearest-centroid-at-any-distance would
    # still name a city, which is how a product ends up in the wrong place.
    far, method = destination_from_geo(5.0, 120.0, cfg)
    assert far == "unknown" and method == "none"


# =============================================================================
# images (spec section 6.2)
# =============================================================================
def test_resize_params_are_dropped(cfg):
    from normalise import clean_image_url

    out = clean_image_url(
        "https://cdn.vinpearl.com/a.jpg?w=400&h=300&quality=70&id=7", "vinpearl", cfg
    )
    assert "w=400" not in out and "quality=70" not in out
    assert "id=7" in out, "non-resize parameters must survive"


def test_booking_thumbnail_bucket_is_rewritten(cfg):
    """Spec section 5.1 wants the largest version, and booking encodes size in
    the path rather than in a query parameter."""
    from normalise import clean_image_url

    out = clean_image_url(
        "https://cf.bstatic.com/xdata/images/hotel/square60/1.jpg?k=a&o=b", "booking", cfg
    )
    assert "square60" not in out
    assert "max1920x1080" in out
    assert "k=a" not in out


# =============================================================================
# phone (spec section 5.3)
# =============================================================================
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+84 258 3598 888", "+842583598888"),
        ("0258 3598 888", "+842583598888"),
        ("(+84) 258-3598-888", "+842583598888"),
        ("0084 258 3598 888", "+842583598888"),
        ("", None),
        (None, None),
    ],
)
def test_normalise_phone(cfg, raw, expected):
    from normalise import normalise_phone

    assert normalise_phone(raw, cfg) == expected


# =============================================================================
# ratings (spec section 7)
# =============================================================================
@pytest.mark.parametrize(
    "value,source,best,expected",
    [
        (8.7, "booking", None, 4.35),   # 0-10 -> 0-5
        (9.0, "agoda", None, 4.5),
        (87, "amadeus", 100, 4.35),     # 0-100 -> 0-5
        (4.5, "vinpearl", 5, 4.5),      # JSON-LD bestRating
        (9.0, "vinpearl", 10, 4.5),
        (None, "booking", None, None),
    ],
)
def test_rescale_rating(cfg, value, source, best, expected):
    """Without one shared scale, section 7's max-by-reviewCount merge writes
    8.7, 4.4 and 87 into one column with no unit."""
    from normalise import rescale_rating

    assert rescale_rating(value, source, best, cfg) == expected


# =============================================================================
# taxonomy (spec section 6.2)
# =============================================================================
def test_taxonomy_hint_wins(cfg):
    from normalise import map_taxonomy

    assert map_taxonomy("vinpearl", {"taxonomy_hint": "golf"}, cfg) == "golf"


def test_taxonomy_falls_back_to_the_category_table(cfg):
    from normalise import map_taxonomy

    assert map_taxonomy("vinpearl", {"category_raw": "Vé VinWonders"}, cfg) == "attraction"
    assert map_taxonomy("booking", {"category_raw": "Resort"}, cfg) == "hotel"


def test_unmapped_taxonomy_is_none_not_a_guess(cfg):
    from normalise import map_taxonomy

    assert map_taxonomy("vinpearl", {"category_raw": "Nội dung khác"}, cfg) is None


# =============================================================================
# description assembly (spec sections 5.1, 5.4)
# =============================================================================
def test_review_sections_are_dropped_not_truncated(cfg):
    from normalise import build_description

    payload = {
        "description_blocks": [
            {"heading": "Giới thiệu", "html": "<p>" + "Mô tả thật. " * 30 + "</p>"},
            {"heading": "Tiện nghi", "html": "<p>" + "Hồ bơi ngoài trời. " * 20 + "</p>"},
            {"heading": "Đánh giá của khách", "html": "<p>Khách A: tuyệt vời!</p>"},
        ]
    }
    out = build_description(payload, cfg)
    assert "Mô tả thật" in out
    assert "Hồ bơi" in out, "a later real section must survive the review drop"
    assert "tuyệt vời" not in out, "review content must not reach the description"


# =============================================================================
# derived attributes (spec section 5.2)
# =============================================================================
def test_hotel_booleans_are_derived_from_prose(cfg):
    from normalise import derive_attributes

    payload = {
        "name_raw": "Deluxe Ocean View",
        "description_html": "Phòng hướng biển, có hồ bơi riêng, phù hợp gia đình.",
        "amenity_labels": ["Spa", "Kids club"],
    }
    attrs = derive_attributes(payload, "hotel", cfg)
    assert attrs.get("view") == "ocean"
    assert attrs.get("privatePool") is True
    assert attrs.get("familyFriendly") is True
    assert attrs.get("hasSpa") is True
    assert attrs.get("hasKidsClub") is True


def test_attraction_duration_default_is_labelled(cfg):
    """Week 4 needs a duration; a guess must be visibly a guess."""
    from normalise import derive_attributes

    attrs = derive_attributes({"name_raw": "Công viên"}, "attraction", cfg)
    assert "mặc định" in str(attrs.get("duration", ""))


def test_opening_hours_survive_from_a_spec_table(cfg):
    from normalise import derive_attributes

    payload = {
        "name_raw": "VinWonders",
        "spec_pairs": [{"label": "Giờ mở cửa", "value": "08:30 - 21:00"}],
    }
    attrs = derive_attributes(payload, "attraction", cfg)
    assert attrs.get("openingHours") == "08:30 - 21:00"


# =============================================================================
# property/room folding
# =============================================================================
def test_property_fields_fold_onto_rooms():
    """Without the fold, rooms have no description and the property row becomes
    a priceless phantom hotel duplicating its own rooms."""
    from normalise import fold_property_rows

    rows = [
        {
            "source_ref": "vinpearl:hotel-a", "page_kind": "property",
            "parent_source_ref": None, "name": "Hotel A", "description": "Mô tả khách sạn",
            "images": ["u1"], "latitude": 12.0, "longitude": 109.0, "address": "Addr",
            "attributes": {"starRating": 5}, "destination": "Nha Trang",
        },
        {
            "source_ref": "vinpearl:hotel-a:deluxe", "page_kind": "room",
            "parent_source_ref": "vinpearl:hotel-a", "name": "Hotel A - Deluxe",
            "description": None, "images": [], "latitude": None, "longitude": None,
            "address": None, "attributes": {"roomType": "Deluxe"}, "destination": "Nha Trang",
        },
    ]
    folded = fold_property_rows(rows)
    room = next(r for r in folded if r["page_kind"] == "room")
    assert room["description"] == "Mô tả khách sạn"
    assert room["images"] == ["u1"]
    assert room["latitude"] == 12.0
    assert room["attributes"] == {"starRating": 5, "roomType": "Deluxe"}
    # The parent stays a merge parent; load skips it.
    assert next(r for r in folded if r["source_ref"] == "vinpearl:hotel-a")["page_kind"] == "property"


def test_childless_property_stays_a_product():
    """A hotel must not vanish because its room list is client-rendered."""
    from normalise import fold_property_rows

    rows = [{
        "source_ref": "vinpearl:hotel-b", "page_kind": "property", "parent_source_ref": None,
        "name": "Hotel B", "description": "Mô tả", "images": [], "attributes": {},
        "destination": "Huế",
    }]
    assert fold_property_rows(rows)[0]["page_kind"] == "product"
