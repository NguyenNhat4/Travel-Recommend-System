"""quality_score (spec section 7) and the Vietnamese-text heuristic.

Spec section 7 wants a 0-1 score over: description >= 200 chars, real Vietnamese
present, has an image, has a price, has a valid destination. Products below 0.5
are not demo material.

The one subtlety is what to do about components that cannot apply. A flight has
no Vietnamese prose and no photo; golf is not required to carry a description
(section 5.1 marks description required for hotel/attraction/combo only). Scoring
those components 1.0 "because they do not apply" hands a flight 0.55 before any
real signal is measured, so a flight with no price, no image and
destination='unknown' would clear the 0.5 gate — the exact opposite of what the
gate exists for. So inapplicable components are dropped from the DENOMINATOR
instead: a flight is scored only on the things a flight can actually have.
"""

from __future__ import annotations

import re
import unicodedata

# Characters that only appear in Vietnamese orthography (plus the tone marks that
# NFD-decompose out of it). Used as a cheap "is this really Vietnamese" probe.
_VN_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩị"
                "òóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
                "ĂÂĐÊÔƠƯÀÁẢÃẠẰẮẲẴẶẦẤẨẪẬÈÉẺẼẸỀẾỂỄỆÌÍỈĨỊ"
                "ÒÓỎÕỌỒỐỔỖỘỜỚỞỠỢÙÚỦŨỤỪỨỬỮỰỲÝỶỸỴ")

#: Common Vietnamese function words. A diacritic ratio alone can be fooled by a
#: single accented proper noun in an otherwise English paragraph
#: ("Deluxe room at Vinpearl Nha Trang, Khánh Hòa"), which is exactly the
#: Amadeus-description case this has to catch.
_VN_STOPWORDS = frozenset(
    {
        "và", "của", "có", "với", "được", "cho", "tại", "trong", "các", "những",
        "là", "một", "không", "này", "khi", "từ", "đến", "cùng", "hoặc", "nếu",
        "phòng", "khách", "sạn", "biển", "nghỉ", "dưỡng", "dịch", "vụ", "tiện",
        "nghi", "trải", "nghiệm", "du", "lịch", "bạn", "sẽ", "thể", "rất",
    }
)


def real_vietnamese(text: str | None, *, min_diacritic_ratio: float = 0.02) -> float:
    """0-1 confidence that ``text`` is genuinely Vietnamese prose.

    Two signals, because either alone is easy to fool:

    * diacritic density — English text scores ~0 even with a Vietnamese place
      name in it;
    * Vietnamese function words — catches text that is mostly ASCII-transliterated
      but still Vietnamese.
    """
    if not text:
        return 0.0
    norm = unicodedata.normalize("NFC", text)
    letters = [c for c in norm if c.isalpha()]
    if len(letters) < 20:
        return 0.0
    diacritics = sum(1 for c in letters if c in _VN_CHARS)
    ratio = diacritics / len(letters)

    words = re.findall(r"[^\W\d_]+", norm.lower(), flags=re.UNICODE)
    hits = sum(1 for w in words if w in _VN_STOPWORDS)
    stop_ratio = hits / max(len(words), 1)

    score = 0.0
    if ratio >= min_diacritic_ratio:
        score += 0.6 * min(ratio / 0.08, 1.0)
    if hits >= 2:
        score += 0.4 * min(stop_ratio / 0.06, 1.0)
    return round(min(score, 1.0), 4)


def quality_score(record: dict, cfg) -> tuple[float, dict[str, float]]:  # noqa: ANN001
    """Return ``(score, per-component breakdown)``.

    The breakdown is returned so ``report`` can say *why* a product is below the
    demo threshold rather than just that it is.
    """
    q = cfg.section("quality")
    weights: dict[str, float] = {k: float(v) for k, v in (q.get("weights") or {}).items()}
    min_chars = int(q.get("description_min_chars", 200))
    min_ratio = float(q.get("vietnamese_min_diacritic_ratio", 0.02))
    exempt_by_tax: dict[str, list[str]] = q.get("exempt_components") or {}

    taxonomy = record.get("taxonomy") or ""
    exempt = set(exempt_by_tax.get(taxonomy, []))

    description = record.get("description") or ""
    components: dict[str, float] = {
        "description_len": min(len(description) / min_chars, 1.0) if description else 0.0,
        "real_vietnamese": real_vietnamese(description, min_diacritic_ratio=min_ratio),
        "has_image": 1.0 if (record.get("image_url") or record.get("images")) else 0.0,
        "has_price": 1.0 if record.get("unit_price") else 0.0,
        "valid_destination": 1.0
        if record.get("destination") and record["destination"] != "unknown"
        else 0.0,
    }

    active = {k: v for k, v in components.items() if k not in exempt and k in weights}
    denom = sum(weights[k] for k in active)
    if denom <= 0:
        return 0.0, components
    score = sum(weights[k] * v for k, v in active.items()) / denom
    return round(score, 4), components


def demo_threshold(cfg) -> float:  # noqa: ANN001
    """The single home for the 0.5 in spec section 7."""
    return float(cfg.section("quality").get("demo_threshold", 0.5))
