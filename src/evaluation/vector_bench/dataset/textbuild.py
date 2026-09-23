"""Fallback text builder (spec P1.4) — CHỈ dùng khi repo không có text builder của Search.

Repo hiện có `src/backend/app/domain/catalog/text_builder.py::build_text` → catalog.py dùng bản đó cho `--source jsonl`
để vector bench giống vector production (spec §1.1). Bản fallback này dùng cho `--source fake` (P1.5: "sinh bằng template ở P1.4")
và khi import bản backend thất bại. Không đưa giá, ngày, toạ độ, mã, review; sao viết "5 sao".
"""
from __future__ import annotations

from typing import Any


def _star(v: Any) -> str:
    if v in (None, ""):
        return ""
    s = float(v)
    return f"{int(s) if s.is_integer() else s} sao"


def _where(dest: str, prov: str) -> str:
    return f"{dest} ({prov})" if prov and prov != dest else dest


def _words(s: str, n: int) -> str:
    return " ".join((s or "").split()[:n])


def build_text(rec: dict, children: list[dict], variant: str, amenity_labels: list[str], *,
               max_amenities: int, max_rooms: int, max_desc_words: int) -> str:
    a = rec.get("attributes") or {}
    name, dest, prov = rec["name"], rec["destination"], a.get("province") or ""
    derived = bool(a.get("descriptionSource"))
    desc = _words(rec.get("description") or "", max_desc_words)
    parts: list[str] = []
    if variant == "hotel_property":
        star = _star(a.get("starRating"))
        head = f"{name} — {a.get('propertyType') or 'khách sạn'}" + (f" {star}" if star else "") + f" tại {_where(dest, prov)}."
        parts.append(head)
        if amenity_labels:
            parts.append("Tiện ích nổi bật: " + ", ".join(amenity_labels[:max_amenities]) + ".")
        rooms: list[str] = []
        for c in children:
            rn = (c.get("attributes") or {}).get("roomName") or c["name"].split(" - ")[-1]
            if rn and rn not in rooms:
                rooms.append(rn)
        if rooms:
            parts.append("Loại phòng: " + ", ".join(rooms[:max_rooms]) + ".")
        if desc and not derived:
            parts.append(desc)
    elif variant == "flight_route":
        airlines = sorted({(c.get("attributes") or {}).get("airline") for c in children} - {None, ""})
        o, d = a.get("originCity") or "", a.get("destinationCity") or dest
        s = f"Vé máy bay {o} – {d}. Chuyến bay đến {dest}" + (f", {prov}" if prov else "")
        s += (f"; hãng: {', '.join(airlines)}." if airlines else ".")
        parts.append(s)
    elif variant == "attraction":
        venue = a.get("venue")
        parts.append(f"{name} — " + (f"{venue} tại " if venue else "tại ") + f"{_where(dest, prov)}.")
        if a.get("ticketed") is False:
            parts.append("Điểm tham quan công cộng, không cần vé.")
        if a.get("audience"):
            parts.append("Phù hợp: " + ", ".join(map(str, a["audience"])) + ".")
        if a.get("highlights"):
            parts.append("Nổi bật: " + ", ".join(map(str, a["highlights"][:5])) + ".")
        if desc:
            parts.append(desc)
    elif variant == "combo":
        parts.append(f"{name} — combo tại {_where(dest, prov)}.")
        if desc:
            parts.append(desc)
    elif variant == "golf":
        parts.append(f"{name} — sân golf tại {_where(dest, prov)}.")
        if desc:
            parts.append(desc)
    else:
        raise ValueError(f"variant không phải search unit: {variant}")
    return " ".join(p for p in parts if p).strip()
