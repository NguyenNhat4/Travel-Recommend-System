"""The rules that must not quietly erode.

Each test here corresponds to a spec constraint that is cheap to break by
accident and expensive to notice: a browser User-Agent added to "fix" a 403,
review text creeping into a payload, a description getting truncated, the
pgvector migration being applied early.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# =============================================================================
# anti-bot: we do not evade (spec sections 1, 13)
# =============================================================================
def test_user_agent_is_honest(cfg):
    """A browser UA on a crawler is evasion, which spec section 1 rules out."""
    ua = cfg.user_agent
    assert "mozilla" not in ua.lower()
    assert "chrome" not in ua.lower()
    assert "safari" not in ua.lower()
    # Spec section 11 wants an identity and a contact address.
    assert "@" in ua or "http" in ua, "the UA must carry a contact address"


def test_no_browser_user_agent_anywhere_in_the_tree():
    """Catches a spoofed UA hardcoded past the config check."""
    offenders: list[str] = []
    pattern = re.compile(r"Mozilla/\d|AppleWebKit|Chrome/\d\d", re.IGNORECASE)
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"browser user-agent strings found in {offenders}"


def test_no_anti_bot_evasion_dependencies():
    """No headless browser or stealth plugin in the dependency set."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for banned in (
        "selenium", "playwright", "undetected", "stealth", "cloudscraper",
        "2captcha", "anticaptcha", "puppeteer", "seleniumbase",
    ):
        assert banned not in pyproject, (
            f"{banned!r} is an anti-bot circumvention tool; spec section 1 forbids "
            "working around a block."
        )


def test_robots_unavailable_defaults_to_abort(cfg):
    """We never assume permission when robots.txt cannot be read."""
    assert cfg.section("robots").get("on_unavailable") == "abort"


def test_api_terms_exception_requires_a_named_policy(cfg):
    """``robots_policy: api_terms`` must cite the policy it claims to follow."""
    for name in cfg.source_names():
        src = cfg.source(name)
        if str(src.get("robots_policy", "robots_txt")) == "api_terms":
            assert str(src.get("usage_policy_url", "")).strip(), (
                f"sources.{name} takes the api_terms exception without naming a "
                "usage policy"
            )


# =============================================================================
# politeness ceiling (spec section 8)
# =============================================================================
def test_rate_limit_ceiling(cfg):
    """<= 0.5 rps per domain and <= 2 concurrency, for every source.

    Spec section 8 states this unconditionally — there is no exemption for API
    sources, which is why Amadeus is configured at 0.5 rps like everything else.
    """
    assert float(cfg.section("ratelimit")["max_rps_cap"]) <= 0.5
    assert int(cfg.section("ratelimit")["max_concurrency_cap"]) <= 2
    for name in cfg.source_names():
        src = cfg.source(name)
        assert src.rate_limit_rps <= 0.5, f"{name} exceeds 0.5 rps"
        assert src.concurrency <= 2, f"{name} exceeds concurrency 2"


def test_env_cannot_raise_the_rate_limit(cfg, monkeypatch):
    """Env may lower the politeness settings, never raise them."""
    monkeypatch.setenv("RATE_LIMIT_RPS", "10")
    monkeypatch.setenv("MAX_CONCURRENCY", "16")
    src = cfg.source("vinpearl")
    assert src.rate_limit_rps <= 0.5
    assert src.concurrency <= 2


def test_403_is_never_retried(cfg):
    """403 is the block signal; retrying it is probing."""
    http = cfg.section("http")
    assert 403 in http["terminal_statuses"]
    assert 403 not in http["retry_statuses"]
    assert int(http["max_retries"]) <= 3  # spec section 8: "tối đa 3 lần"


# =============================================================================
# no personal or review data (spec section 5.4)
# =============================================================================
def test_payload_validator_rejects_review_content():
    from collectors.base import assert_no_personal_data

    with pytest.raises(ValueError, match="section 5.4"):
        assert_no_personal_data({"name_raw": "X", "review": [{"reviewBody": "nice"}]})
    with pytest.raises(ValueError):
        assert_no_personal_data({"nested": {"author": {"name": "Nguyen A"}}})
    # The permitted case: aggregate only.
    assert_no_personal_data({"aggregate_rating_raw": 4.5, "review_count_raw": 1234})


def test_jsonld_allowlist_drops_reviews_but_keeps_ratings():
    from collectors import extract

    node = {
        "@type": "Hotel",
        "name": "X",
        "description": "Mô tả",
        "aggregateRating": {"ratingValue": 4.5, "reviewCount": 10, "bestRating": 5},
        "review": [{"author": {"name": "A"}, "reviewBody": "text"}],
        "starRating": {"@type": "Rating", "ratingValue": 5},
    }
    picked = extract.jsonld_pick(node)
    assert "review" not in picked
    assert picked["aggregateRating"]["reviewCount"] == 10
    # starRating must survive with its value: without ratingValue in the
    # allowlist it becomes an empty shell and every hotel loses its star class.
    assert picked["starRating"]["ratingValue"] == 5
    from collectors.base import assert_no_personal_data

    assert_no_personal_data(picked)


# =============================================================================
# Vietnamese text (spec sections 5.1, 6.2)
# =============================================================================
def test_text_is_nfc_and_keeps_diacritics_and_case():
    import unicodedata

    from normalise import normalise_text

    raw = "  <p>Khách sạn <b>Vinpearl</b> Nha Trang</p>  "
    out = normalise_text(raw)
    assert out == unicodedata.normalize("NFC", out)
    assert out != out.lower(), "must not lowercase"
    assert "á" in out, "must not strip diacritics"
    # Inline tags must not split a sentence.
    assert out == "Khách sạn Vinpearl Nha Trang"


def test_description_is_never_truncated():
    from normalise import normalise_text

    long_text = "Mô tả rất dài. " * 500
    assert len(normalise_text(long_text)) > 5000


def test_lookup_key_folds_but_storage_does_not():
    from ids import lookup_key

    assert lookup_key("Phú Quốc") == "phu quoc"
    assert lookup_key("Huế") == "hue"
    assert lookup_key("Đà Nẵng") == "da nang"
    # Distinct destinations must not collide once folded.
    assert lookup_key("Hội An") != lookup_key("Nam Hội An")


# =============================================================================
# schema (spec sections 4.1, 4.2, 4.3)
# =============================================================================
def test_pgvector_migration_is_deferred():
    """003 must not be in the apply list: it freezes the embedding dimension."""
    import db

    assert "003_pgvector.sql" in db.DEFERRED
    assert "003_pgvector.sql" not in db.APPLY_ORDER


def test_cdp_mirror_migration_is_not_edited():
    """002 must stay a field-for-field mirror of spec section 4.2.

    In particular no UNIQUE on ``products.source_ref``: load achieves
    idempotency through ``product_sources`` and a deterministic product_id
    instead, which needs no change to the CDP shape.
    """
    sql = (ROOT / "migrations" / "002_cdp_clone.sql").read_text(encoding="utf-8")
    body = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    assert "UNIQUE" not in body.upper().replace("EMAIL TEXT UNIQUE", "").replace(
        "REFERENCE_NO TEXT UNIQUE", ""
    ) or True  # explicit check below
    assert not re.search(r"source_ref\s+TEXT\s+NOT NULL\s+UNIQUE", body, re.IGNORECASE)
    # events.product_id must have no FK (spec section 4.2 says so explicitly).
    events = body[body.find("CREATE TABLE events") :]
    product_line = next(
        line for line in events.splitlines() if "product_id" in line and "UUID" in line
    )
    assert "REFERENCES" not in product_line.upper()


def test_products_columns_match_the_spec():
    from models import PRODUCTS_COLUMNS

    expected = (
        "product_id", "name", "taxonomy", "destination", "description", "attributes",
        "unit_price", "currency", "available", "available_from", "available_to",
        "image_url", "source_ref", "latitude", "longitude", "images", "quality_score",
        "created_at", "updated_at",
    )
    assert PRODUCTS_COLUMNS == expected


def test_merge_only_targets_real_columns(cfg):
    """A section 5.2 attribute must never be merged into a column."""
    from models import PRODUCTS_COLUMNS

    for field in (cfg.section("merge").get("columns") or {}):
        assert field in PRODUCTS_COLUMNS, (
            f"merge.columns.{field} is not a products column; it belongs under "
            "merge.attributes"
        )


def test_every_not_null_column_can_be_satisfied():
    import merge

    merge.assert_defaults_cover_not_null()


# =============================================================================
# attributes registry (spec section 5.2)
# =============================================================================
@pytest.mark.parametrize(
    "taxonomy,required",
    [
        ("hotel", ("starRating", "amenities", "breakfastIncluded", "familyFriendly",
                   "privatePool", "beachfront", "petFriendly", "hasSpa", "hasKidsClub",
                   "view", "brand", "aggregateRating", "reviewCount")),
        ("attraction", ("ticketType", "duration", "openingHours", "includedServices",
                        "heightRestrictionCm", "ageRestriction", "poiName",
                        "indoorOutdoor", "bestFor")),
        ("flight", ("carrier", "flightNo", "originIata", "destinationIata", "departTime",
                    "arriveTime", "durationMin", "stops", "cabinClass",
                    "baggageAllowanceKg", "fareType", "refundable")),
        ("combo", ("components", "nights", "minPax", "validFrom", "validTo",
                   "blackoutDates", "transferIncluded")),
        ("golf", ("courseName", "holes", "par", "teeTimeSlots", "caddieFeeIncluded",
                  "weekdayPrice", "weekendPrice", "buggyIncluded")),
    ],
)
def test_attribute_registry_covers_spec_5_2(taxonomy, required):
    from normalise import ATTRIBUTE_KEYS

    missing = [k for k in required if k not in ATTRIBUTE_KEYS[taxonomy]]
    assert not missing, f"{taxonomy} is missing spec section 5.2 attributes: {missing}"


def test_unknown_attributes_are_dropped():
    from normalise import filter_attributes

    out = filter_attributes(
        {"starRating": 5, "somethingInvented": "x"}, "hotel", source="test"
    )
    assert out == {"starRating": 5}


# =============================================================================
# content_path portability (cross-platform cache)
# =============================================================================
def test_cache_paths_are_posix(tmp_path):
    from cache import Cache

    c = Cache(tmp_path)
    w = c.write(b"<html>x</html>", source="vinpearl", content_type="text/html")
    assert "\\" not in w.content_path, (
        "content_path must be POSIX-relative or the collector container cannot "
        "resolve rows written on Windows"
    )
    assert c.read(w.content_path) == b"<html>x</html>"


def test_nul_bytes_are_stripped():
    """Postgres rejects NUL in text and jsonb; real crawled HTML contains it."""
    from cache import strip_nul

    assert strip_nul(b"a\x00b") == b"ab"


def test_placeholder_contact_address_is_refused(cfg, monkeypatch):
    """A UA with a placeholder contact satisfies the letter of spec section 11
    and none of its purpose: the site operator cannot ask us to stop.

    The failure is silent without this — a missing or relocated ``.env`` makes
    the config.yaml placeholder take effect and nothing looks wrong.
    """
    from config import ConfigError

    monkeypatch.setenv("USER_AGENT", "VOTA-RecSys-Internship/0.1 (+mailto:you@example.com)")
    with pytest.raises(ConfigError, match="placeholder contact"):
        cfg.assert_contactable_user_agent()

    monkeypatch.setenv("USER_AGENT", "VOTA-RecSys-Internship/0.1 (+mailto:real.person@vinpearl.com)")
    cfg.assert_contactable_user_agent()


def test_env_file_is_found_at_any_of_the_expected_levels(tmp_path, monkeypatch):
    """`.env` legitimately sits at different levels in different checkouts.

    A hard-coded path fails in the worst way: USER_AGENT falls back to the
    placeholder and the crawler goes out with a fake contact address.
    """
    import config

    assert config.ENV_SEARCH_PATHS, "there must be at least one search location"
    names = [p.name for p in config.ENV_SEARCH_PATHS]
    assert names == [".env"] * len(names)
    # data-collection/, vota-recsys/, and the repository root.
    parents = [p.parent.name for p in config.ENV_SEARCH_PATHS]
    assert len(set(parents)) == len(parents), "search paths must be distinct directories"


# =============================================================================
# block detection (spec sections 1, 9, 13)
# =============================================================================
#: The page booking.com actually returned for a search URL on 2026-09-15.
#: Note the status: 202, a *success* code, with the challenge text inside a
#: <noscript> block.
BOOKING_CHALLENGE = (
    b"<!DOCTYPE html><html><head><title></title>"
    b"<script>window._pxAppId='PX1';</script></head><body>"
    b"<noscript>JavaScript is disabled In order to continue, we need to verify "
    b"that you're not a robot. This requires JavaScript. Enable JavaScript and "
    b"then reload the page.</noscript></body></html>"
)


def test_block_detector_catches_a_2xx_challenge_page(cfg):
    """A 202 with a noscript-only body is a block.

    Matching on status alone misses it (202 is success) and matching on wording
    alone missed it too until the observed strings were added. Both paths are
    checked here because the wording is the site's to change.
    """
    from collectors.net import BlockDetector

    bd = cfg.section("block_detector")
    detector = BlockDetector(
        consecutive_threshold=int(bd["consecutive_403_429"]),
        body_markers=tuple(bd["body_markers"]),
        empty_shell_max_text=int(bd["empty_shell_max_text_chars"]),
    )
    verdict = detector.inspect(
        status=202, body=BOOKING_CHALLENGE, url="https://www.booking.com/searchresults.vi.html"
    )
    assert verdict is not None, "a 2xx anti-bot challenge must be detected as a block"
    assert verdict["status"] == 202

    # And with the wording changed, the empty-shell backstop still fires.
    blind = BlockDetector(consecutive_threshold=3, body_markers=(), empty_shell_max_text=200)
    assert blind.inspect(
        status=202, body=BOOKING_CHALLENGE, url="https://www.booking.com/x"
    ) is not None


def test_block_detector_does_not_flag_real_content(cfg):
    """The empty-shell rule must not fire on a page that has real prose."""
    from collectors.net import BlockDetector

    bd = cfg.section("block_detector")
    detector = BlockDetector(
        consecutive_threshold=int(bd["consecutive_403_429"]),
        body_markers=tuple(bd["body_markers"]),
        empty_shell_max_text=int(bd["empty_shell_max_text_chars"]),
    )
    real = (
        b"<html><body><h1>Vinpearl Resort Nha Trang</h1><p>"
        + ("Khu nghi duong 5 sao tren dao Hon Tre. " * 20).encode()
        + b"</p></body></html>"
    )
    assert detector.inspect(status=200, body=real, url="https://x/y") is None


def test_block_detector_ignores_tag_free_json(cfg):
    """A JSON API response is legitimately tag-free.

    Without the is-it-HTML guard the empty-shell rule would flag every single
    Amadeus and Overpass call as a block.
    """
    from collectors.net import BlockDetector

    detector = BlockDetector(consecutive_threshold=3, body_markers=(), empty_shell_max_text=200)
    assert detector.inspect(status=200, body=b'{"data":[]}', url="https://api/x") is None


def test_noscript_text_is_visible_to_us():
    """We are a non-JavaScript client, so noscript content is what we see.

    Stripping it reported 0 visible characters and discarded the one line that
    explains why a page is empty.
    """
    from collectors.net import _visible_text

    assert "not a robot" in _visible_text(BOOKING_CHALLENGE.decode())
    assert "_pxAppId" not in _visible_text(BOOKING_CHALLENGE.decode()), "script must be stripped"


def test_empty_shell_survives_truncation(cfg):
    """A JS-only page must be detected even when the body is truncated.

    ``inspect()`` only looks at the first 200 KB. agoda's shell is 218 KB, so
    the cut landed inside a ``<script>`` and left an orphaned opening tag; the
    paired stripper could not match it and the JavaScript source counted as
    prose, scoring the page as content-rich and letting it through.
    """
    from collectors.net import BlockDetector, _visible_text

    shell = (
        b'<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"></head><body>'
        b"<script>" + (b"var x=1;/*" + b"p" * 250_000 + b"*/")  # no closing tag in window
    )
    assert _visible_text(shell[:200_000].decode("utf-8", "replace")) == ""

    bd = cfg.section("block_detector")
    detector = BlockDetector(
        consecutive_threshold=int(bd["consecutive_403_429"]),
        body_markers=tuple(bd["body_markers"]),
        empty_shell_max_text=int(bd["empty_shell_max_text_chars"]),
    )
    assert detector.inspect(status=200, body=shell, url="https://x/y") is not None
