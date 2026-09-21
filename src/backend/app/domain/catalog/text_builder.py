"""Text builder theo variant — EMBEDDING_AND_ENGINES.md §2.6. Thuần Python, test được không cần model."""
from __future__ import annotations

from .models import Product

_NUM = {1: "một", 2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy"}


def _num_words(n) -> str:
    try:
        return _NUM.get(int(n), str(n))
    except (TypeError, ValueError):
        return str(n)


def _star(star) -> str:
    if not star:
        return ""
    s = float(star)
    return f" {int(s) if s.is_integer() else s} sao"


def build_text(p: Product, children: list[Product], max_desc_words: int = 60) -> str:
    a = p.attributes
    prov = a.get("province") or ""
    where = f"tại {p.destination}" + (f" ({prov})" if prov and prov != p.destination else "")
    desc_short = " ".join(p.description.split()[:max_desc_words])
    parts: list[str] = []
    v = p.variant

    if v == "hotel_property":
        parts.append(f"{p.name} — {a.get('propertyType') or 'khách sạn'}{_star(a.get('starRating'))} {where}.")
        vibe = [s for flag, s in (("oceanView", "hướng biển"), ("familyFriendly", "phù hợp gia đình có trẻ nhỏ")) if a.get(flag)]
        if vibe:
            parts.append(", ".join(vibe).capitalize() + ".")
        am = [x for x in (a.get("amenities") or []) if isinstance(x, str)][:10]
        if am:
            parts.append("Tiện ích nổi bật: " + ", ".join(am) + ".")
        rooms = sorted({c.attributes.get("roomName") or c.name.split(" - ")[-1] for c in children})
        if rooms:
            parts.append("Loại phòng: " + ", ".join(rooms[:8]) + ".")
        parts.append(desc_short)

    elif v == "flight_route":
        airlines = sorted({c.attributes.get("airline") for c in children if c.attributes.get("airline")})
        o, d = a.get("originCity") or "", a.get("destinationCity") or p.destination
        parts.append(f"{p.name}. Chuyến bay từ {o} đến {d}, {prov or p.destination}" + (f"; hãng bay: {', '.join(airlines)}" if airlines else "") + ".")
        parts.append(f"Bay đến {p.destination} để du lịch, nghỉ dưỡng.")
        parts.append(desc_short)

    elif v == "attraction":
        venue = a.get("venue")
        parts.append(f"{p.name} — điểm tham quan" + (f" tại {venue}," if venue else "") + f" {where}.")
        if a.get("ticketed") is False:
            parts.append("Điểm tham quan công cộng, miễn phí, không cần vé.")
        if a.get("audience"):
            parts.append("Phù hợp: " + ", ".join(map(str, a["audience"])) + ".")
        if a.get("highlights"):
            parts.append("Điểm nổi bật: " + ", ".join(map(str, a["highlights"][:5])) + ".")
        parts.append(desc_short)

    elif v == "combo":
        nights = a.get("nights")
        parts.append(f"{p.name} — combo" + (f" {_num_words(nights)} đêm" if nights else "") + f" {where}.")
        # TODO khi có catalog.combo_items: tổng hợp một câu "nghỉ tại X, vé Y, ăn sáng" thay cho description
        parts.append(desc_short)

    elif v == "golf":
        venue = a.get("venue")
        parts.append(f"{p.name} — sân golf" + (f" tại {venue}," if venue else "") + f" {where}. Chơi golf kết hợp nghỉ dưỡng.")
        parts.append(desc_short)

    return " ".join(x for x in parts if x).strip()
