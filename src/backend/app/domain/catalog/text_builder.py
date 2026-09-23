"""Text builder — template embedding chung cho catalog V-OTA. Thuần Python, test được không cần model.

Một khung 5 ô cho mọi variant: HEADLINE · FIT · FEATURES · ROLLUP · EXCERPT.
`enrich` gom dữ liệu của cha, các con (phòng / chuyến bay) và `combo_items` vào 5 ô; `build_text` ghép 5 ô thành một đoạn văn.
Chỉ search unit (hotel_property, flight_route, attraction, combo, golf) có text; phòng và chuyến bay trả "" vì dùng vector của cha.
Không đưa giá, ngày, điểm hay số lượt đánh giá vào text: chúng đổi theo từng lần crawl và làm `text_hash` đổi mà nội dung không đổi.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping, Sequence

from .models import Product

SLOTS = ("headline", "fit", "features", "rollup", "excerpt")
MAX_ROOM_NAMES, MAX_FEATURES = 5, 8

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


def _compile(pairs) -> tuple:
    return tuple((label, re.compile(rx, re.I)) for label, rx in pairs)


# --- từ vựng có kiểm soát (độ phủ đo trên snapshot 10.320 dòng) -----------------------------------------
# Thứ tự = độ hiếm tăng dần (nhãn hiếm phân biệt tốt hơn), cắt ở MAX_FEATURES. Cố định trong code, không tính IDF lúc chạy,
# để catalog đổi thì text không đổi hàng loạt. Bỏ wifi: 81% khách sạn có, không phân biệt được.
_FEATURES = _compile((
    ("cho phép thú cưng", r"thú cưng|vật nuôi|\bpets?\b"),
    ("công viên nước", r"công viên nước|water ?park"),
    ("sân golf", r"golf"),
    ("phòng hội nghị", r"hội nghị|phòng họp|hội thảo"),
    ("khu vui chơi trẻ em", r"trẻ em|\bkids?\b|khu vui chơi"),
    ("gần bãi biển", r"bãi biển|bờ biển|\bbeach"),
    ("phòng gym", r"\bgym\b|thể dục|fitness"),
    ("spa và massage", r"\bspa\b|massage|xông hơi|sauna"),
    ("quầy bar", r"\bbar\b|quầy bar"),
    ("hồ bơi", r"hồ bơi|bể bơi|\bpool"),
    ("xe đưa đón sân bay", r"đưa đón sân bay|đón sân bay|airport shuttle|xe đưa đón"),
    ("nhà hàng", r"nhà hàng|restaurant"),
    ("bữa sáng", r"bữa sáng|ăn sáng|breakfast"),
    ("phòng gia đình", r"phòng gia đình"),
    ("bãi đỗ xe", r"đỗ xe|đậu xe|parking"),
))

# Tính năng chỉ nằm ở cấp phòng, cha không nói (vd. 117 khách sạn có phòng hồ bơi riêng mà text cũ chỉ nhắc 40%).
_ROOM_FEATURES = _compile((
    ("hồ bơi riêng", r"(hồ|bể) bơi riêng|private pool"),
    ("bồn tắm", r"bồn tắm(?! hoặc vòi sen)|bathtub|jacuzzi"),
    ("ban công", r"ban công|sân hiên|balcony"),
    ("bếp riêng", r"\bbếp\b|nhà bếp|kitchen"),
    ("hướng biển", r"hướng biển|ocean ?view|sea ?view"),
))

_ROOM_CLASSES = _compile((
    ("suite", r"suite"), ("deluxe", r"deluxe"), ("superior", r"superior"), ("standard", r"standard|tiêu chuẩn"),
    ("studio", r"studio"), ("biệt thự", r"biệt thự|villa"), ("bungalow", r"bungalow"),
    ("căn hộ", r"căn hộ|apartment"), ("phòng gia đình", r"gia đình|family"), ("executive", r"executive"),
    ("premier", r"premier"), ("junior", r"junior"), ("phòng tập thể", r"dorm|tập thể"),
))

# Loại hình suy từ tên khi nguồn không khai `propertyType` (64% khách sạn thiếu). Thứ tự quan trọng.
_KIND_FROM_NAME = _compile((
    ("resort", r"resort"), ("homestay", r"homestay"), ("hostel", r"hostel"),
    ("biệt thự", r"villa|biệt thự"), ("căn hộ", r"apartment|căn hộ|\bapart"),
    ("nhà nghỉ", r"motel|nhà nghỉ|guest ?house"), ("khách sạn", r"hotel|khách sạn"),
))

_DAYPARTS = (("đêm khuya", 0, 4), ("sáng sớm", 4, 6), ("sáng", 6, 12), ("chiều", 12, 18), ("tối", 18, 24))

# --- làm sạch mô tả -------------------------------------------------------------------------------------
# Câu có nhãn do bước tự sinh mô tả thêm vào; dữ liệu đó đã có ở thuộc tính có cấu trúc.
_LABELLED = re.compile(r"^(địa chỉ|giờ mở cửa|loại hình|địa điểm|phù hợp|tiện ích|thời gian tham quan[^:]*|thời gian bay|hãng khai thác)\s*:", re.I)
# Số đổi theo từng lần crawl (giá, điểm và số lượt đánh giá).
_VOLATILE = re.compile(r"\d{1,3}(?:[.,]\d{3})+\s*(?:₫|đ\b|vnđ|vnd)|^giá (?:từ|tham khảo|một chiều|khứ hồi)"
                       r"|lượt đánh giá|\d[.,]?\d*\s*/\s*(?:10|5)\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_BULLET = re.compile(r"^[►•▪\-\*]+\s*")
# Tiêu đề SEO của agoda dính liền thân bài ("...biếtCONIHOUSE ..."); bỏ đúng cụm này, không tách theo chữ hoa.
_SEO_HEADING = "Tất cả những gì bạn cần biết"


def _clip(text: str, n: int) -> str:
    words = text.split()
    if len(words) <= n:
        return text
    cut = " ".join(words[:n])
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end >= len(cut) * 0.6 else cut


def _excerpt(description: str, name: str, n: int) -> str:
    """Mô tả rút gọn: bỏ tiêu đề mục, tiêu đề SEO, câu có nhãn, câu chứa giá/điểm đánh giá và câu chỉ lặp lại tên sản phẩm."""
    if n <= 0 or not description:
        return ""
    text = description.replace(_SEO_HEADING, ". ")
    if name:  # tiêu đề nguồn dính liền câu sau: "...ở Đà NẵngAngsana Lang Co là..."
        text = re.sub(f"(?<=[a-zà-ỹ0-9])(?={re.escape(name)})", ". ", text)
    nm, n_name = name.lower(), len(name.split())
    kept: list[str] = []
    for raw in _SENT.split(text):
        s = _BULLET.sub("", raw).strip(" .")
        if s.endswith(":"):                       # tiêu đề mục ("Chỗ nghỉ thanh lịch:")
            continue
        low, words = s.lower(), len(s.split())
        if (words < 4 or _LABELLED.match(s) or _VOLATILE.search(s) or low in nm
                or (nm in low and words <= n_name + 6) or s.isupper()
                or (low.startswith(nm) and s[len(name):len(name) + 3] == " - ")):   # dòng "Tên - khẩu hiệu" của trang nguồn
            continue
        kept.append(s if s[-1] in "!?" else s + ".")
    return _clip(" ".join(kept), n)


# --- helper nhỏ -----------------------------------------------------------------------------------------
def _where(p: Product, province: bool = False) -> str:
    """Chỉ khách sạn in tỉnh (khớp điểm đến 1.636/1.637 khách sạn); province của vé Vinpearl và golf là tỉnh bên bán, hay sai."""
    prov = (p.attributes.get("province") or "") if province else ""
    return f"tại {p.destination}" + (f" ({prov})" if prov and prov != p.destination else "")


def _join(items, sep=", ") -> str:
    return sep.join(str(x) for x in items if x)


def _blob(*parts) -> str:
    out: list[str] = []
    for x in parts:
        out.extend(map(str, x)) if isinstance(x, (list, tuple)) else out.append(str(x or ""))
    return " ".join(out).lower()


def _duration(minutes) -> str:
    if not minutes:
        return ""
    h, m = divmod(int(minutes), 60)
    return f"khoảng {h} giờ" + (f" {m} phút" if m else "") if h else f"khoảng {m} phút"


def _property_kind(p: Product) -> str:
    """propertyType của nguồn; thiếu thì suy từ tên; không suy được thì trung tính (không mặc định 'khách sạn')."""
    declared = p.attributes.get("propertyType")
    if declared:
        return declared
    for label, rx in _KIND_FROM_NAME:
        if rx.search(p.name):
            return label
    return "cơ sở lưu trú"


# --- roll-up từ con lên cha -----------------------------------------------------------------------------
def _room_rollup(rooms: Sequence[Product]) -> str:
    if not rooms:
        return ""
    rooms = sorted(rooms, key=lambda c: (c.attributes.get("roomName") or c.name, c.product_id))
    names = sorted({(c.attributes.get("roomName") or c.name.split(" - ")[-1]).strip() for c in rooms},
                   key=lambda n: (len(n.split()), n))
    freq: Counter = Counter()
    for n in names:
        freq.update(label for label, rx in _ROOM_CLASSES if rx.search(n))
    order = {label: i for i, (label, _) in enumerate(_ROOM_CLASSES)}
    classes = sorted(freq, key=lambda k: (-freq[k], order[k]))[:6]

    beds: Counter = Counter()
    for c in rooms:
        raw = re.sub(r"\s+", " ", (c.attributes.get("bed") or "")).strip().lower()
        for b in re.split(r"\s+và\s+", raw):     # "1 giường đơn và 1 giường đôi" là hai kiểu giường
            b = re.sub(r"\s*(cực lớn|siêu lớn|lớn|king|queen)\b", "", b).strip()
            if b and len(b) <= 30 and not b.startswith("chọn"):   # bỏ chuỗi tự do "chọn giường bạn muốn (tùy tình trạng...)"
                beds[b] += 1
    bed_text = _join([b for b, _ in sorted(beds.items(), key=lambda kv: (-kv[1], kv[0]))[:3]])

    cap = max((c.attributes.get("maxOccupancy") if isinstance(c.attributes.get("maxOccupancy"), (int, float)) else 0)
              for c in rooms)
    feats = [label for label, rx in _ROOM_FEATURES
             if any(rx.search(_blob(c.attributes.get("amenities") or [], c.attributes.get("roomName"))) or
                    (label == "hướng biển" and c.attributes.get("oceanView")) for c in rooms)]

    parts = []
    if classes:                       # không nêu số lượng: 24% khách sạn thiếu một phần hạng phòng trong catalog
        parts.append(f"Hạng phòng: {_join(classes)}.")
    if names:
        parts.append("Tên hạng phòng: " + "; ".join(names[:MAX_ROOM_NAMES]) + ".")
    if bed_text:
        parts.append(f"Giường: {bed_text}.")
    if cap >= 4:
        parts.append(f"Có phòng cho nhóm, tối đa {int(cap)} khách.")
    if feats:
        parts.append(f"Một số phòng có {_join(feats)}.")
    return " ".join(parts)


def _flight_rollup(route: Product, flights: Sequence[Product]) -> str:
    a = route.attributes
    parts: list[str] = []
    airlines = a.get("airlines") or sorted({c.attributes.get("airline") for c in flights if c.attributes.get("airline")})
    if airlines:
        parts.append(f"Hãng bay: {_join(airlines)}.")
    if flights:
        nonstop = {bool(c.attributes.get("nonstop")) for c in flights}
        parts.append("Bay thẳng." if nonstop == {True} else "Có chuyến nối chuyến." if nonstop == {False}
                     else "Có cả chuyến bay thẳng và nối chuyến.")
        hours = {int(str(c.attributes.get("departureTimeLocal") or "x")[:2]) for c in flights
                 if str(c.attributes.get("departureTimeLocal") or "")[:2].isdigit()}
        dayparts = [label for label, lo, hi in _DAYPARTS if any(lo <= h < hi for h in hours)]
        if dayparts:
            parts.append(f"Khung giờ khởi hành: {_join(dayparts)}.")
    if _duration(a.get("durationMinutes")):
        parts.append(f"Thời gian bay {_duration(a.get('durationMinutes'))}.")
    return " ".join(parts)


def _combo_rollup(combo_items: Sequence[Mapping[str, Any]]) -> str:
    labels = [i["label"] for i in sorted(combo_items, key=lambda i: i.get("position", 0)) if i.get("label")]
    return "Gồm: " + "; ".join(labels) + "." if labels else ""


# --- điểm vào ---------------------------------------------------------------------------------------------
def enrich(p: Product, children: Sequence[Product] = (), combo_items: Sequence[Mapping[str, Any]] = (),
           max_desc_words: int = 60) -> dict[str, str]:
    """Bước enrich: gom cha, con và combo_items vào 5 ô (ô rỗng là ""). Variant không có vector (phòng, chuyến bay) → cả 5 ô rỗng.

    children: phòng của property / chuyến bay của route. combo_items: dòng `catalog.combo_items` của combo (cần label, position).
    """
    a, v = p.attributes, p.variant
    s = dict.fromkeys(SLOTS, "")

    if v == "hotel_property":
        s["headline"] = f"{p.name} — {_property_kind(p)}{_star(a.get('starRating'))} {_where(p, province=True)}."
        fit = [t for flag, t in (("familyFriendly", "phù hợp gia đình có trẻ nhỏ"), ("oceanView", "hướng biển")) if a.get(flag)]
        s["fit"] = ", ".join(fit).capitalize() + "." if fit else ""
        feats = [label for label, rx in _FEATURES
                 if rx.search(_blob(a.get("amenities") or [], a.get("highlights") or [], p.name))][:MAX_FEATURES]
        s["features"] = f"Tiện ích: {_join(feats)}." if feats else ""
        s["rollup"] = _room_rollup(children)
        s["excerpt"] = _excerpt(p.description, p.name, max_desc_words)

    elif v == "flight_route":
        o, d, ap = a.get("originCity") or "", a.get("destinationCity") or p.destination, a.get("destinationAirportName")
        s["headline"] = f"Vé máy bay từ {o} đến {d}" + (f", hạ cánh tại {ap}" if ap else "") + "."
        s["rollup"] = _flight_rollup(p, children)
        # không lấy mô tả: 100% là văn bản tự sinh từ thuộc tính, chứa giá và tháng rẻ nhất (đổi theo từng lần crawl)

    elif v == "attraction":
        venue = a.get("venue")
        venue = venue if venue and venue.lower() not in p.name.lower() else ""
        s["headline"] = f"{p.name} — điểm tham quan" + (f" tại {venue}," if venue else "") + f" {_where(p)}."
        if a.get("ticketed") is False:   # chỉ tin cờ của nguồn: unitPrice null KHÔNG có nghĩa công cộng (trip.com: 244/299 điểm null giá có isFree=false)
            s["fit"] = "Điểm tham quan công cộng, không bán vé."
        if a.get("audience"):
            s["fit"] = (s["fit"] + " " if s["fit"] else "") + f"Phù hợp: {_join(a['audience'])}."
        tags = a.get("tags") or []
        dur = a.get("durationMinutes")
        span = "dưới 2 giờ" if dur and dur <= 120 else "nửa ngày" if dur and dur <= 300 else "cả ngày" if dur else ""
        bits = [f"loại hình {_join(tags[:4])}" if tags else "", f"thời gian tham quan {span}" if span else ""]
        s["features"] = (_join(bits, "; ").capitalize() + ".") if any(bits) else ""
        s["excerpt"] = _excerpt(p.description, p.name, max_desc_words)

    elif v == "combo":
        nights = a.get("nights")
        s["headline"] = f"{p.name} — combo" + (f" {_num_words(nights)} đêm" if nights else "") + f" {_where(p)}."
        if a.get("audience"):
            s["fit"] = f"Phù hợp: {_join(a['audience'])}."
        s["rollup"] = _combo_rollup(combo_items)
        s["excerpt"] = _excerpt(p.description, p.name, max_desc_words)

    elif v == "golf":
        venue = a.get("venue")
        venue = venue if venue and venue.lower() not in p.name.lower() else ""
        s["headline"] = f"{p.name} — sân golf" + (f" tại {venue}," if venue else "") + f" {_where(p)}."
        s["excerpt"] = _excerpt(p.description, p.name, max_desc_words)

    return s


def build_text(p: Product, children: Sequence[Product], max_desc_words: int = 60,
               combo_items: Sequence[Mapping[str, Any]] = ()) -> str:
    """Đoạn văn để embed cho một search unit; "" cho phòng và chuyến bay."""
    return " ".join(x for x in enrich(p, children, combo_items, max_desc_words).values() if x).strip()
