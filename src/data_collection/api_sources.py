"""Nguồn dữ liệu qua API: hộp thư đến (inbox) tự nhận diện file JSON, đổi về bản ghi trung gian, và tải hàng loạt về hộp thư.

Luồng: fetch (song song nhiều điểm đến) → file JSON trong `data/demo/inbox/` → `intake` nhận diện nguồn → bộ chuyển (adapter) đổi về ĐÚNG dạng bản ghi
trung gian mà normalise.py đang đọc → kho `data/demo/store/interim/` → normalise → lọc → Postgres. Bạn cũng có thể thả tay một file JSON vào inbox.

Vì sao không sửa normalise.py: dữ liệu Apify của Agoda / Booking là dữ liệu của chính hai trang đó, chỉ khác đường vận chuyển. Bản ghi được dựng với cùng
`key`/`sourceRef` như bản cào bằng trình duyệt, nên cùng mã sản phẩm: bản mới (crawledAt lớn hơn) thay bản cũ, giá được làm mới.

Bộ chuyển của Agoda/Booking dựa trên tên trường ghi ở trang mô tả của actor, CHƯA kiểm với dữ liệu thật (chưa có token). Chạy `probe-apify` hoặc `fetch` rồi
đối chiếu mục "Độ phủ trường" trên giao diện; nếu tên trường khác thì chỉ sửa hàm `adapt_*` tương ứng. Nguồn chưa có bộ chuyển (SerpApi, Travelpayouts,
Klook) được nhận diện, giữ nguyên file ở `inbox/_pending/` để viết bộ chuyển từ JSON thật, không đoán.

Token nằm ở `.env` (APIFY_TOKEN, SERPAPI_KEY, TRAVELPAYOUTS_TOKEN), chỉ đi qua header, không vào log/state/URL của lượt chạy.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import apify_source
from collectors.plan import DESTINATIONS
from collectors.textutil import fold

ApiError = apify_source.ApifyError
SETTLE_SECONDS = 1.0          # file mới ghi chưa đủ tuổi thì để vòng sau, tránh đọc file đang ghi dở
MAX_DESTINATIONS = 70
MAX_ITEMS_PER_DESTINATION = 500
MAX_USD_PER_FETCH = 5.0
SUBDIRS = ("_processed", "_pending", "_unrecognized", "_failed")


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text or "")).strip("-")


def secret(name: str) -> str:
    apify_source.load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise ApiError(f"Chưa có {name}. Điền vào file .env (xem .env.example), đừng dán vào chat hay commit.")
    return value


def has_secret(name: str) -> bool:
    apify_source.load_env()
    return bool(os.environ.get(name, "").strip())


def _num(x) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if x else None
    m = re.search(r"\d[\d.,]*", str(x))
    if not m:
        return None
    raw = m.group(0)
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", raw) else raw.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        return float(raw) or None
    except ValueError:
        return None


def _strings(x) -> list[str]:
    out = []
    for v in x or []:
        if isinstance(v, dict):
            v = v.get("name") or v.get("title") or v.get("text") or v.get("label")
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def _coord(x) -> float | None:
    try:
        return None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None


def _nights(checkin: str | None, checkout: str | None) -> int:
    try:
        return max((date.fromisoformat(checkout) - date.fromisoformat(checkin)).days, 1)
    except (TypeError, ValueError):
        return 1


# ------------------------------------------------------------------------------------------------ bộ chuyển
AGODA_URL = re.compile(r"agoda\.com/(?:[a-z]{2}-[a-z]{2}/)?([^/?#]+)/hotel/([^/?#.]+)")

# actor Booking đầy đủ ghép banner khuyến mãi vào ĐẦU description thật (đo trên probe 22/09/2026: 11/19 khách sạn Nha Trang dính,
# đối chiếu 400 dòng đầu bản cào HTML cũ: 0/400 — lỗi của actor, không phải của nguồn Booking) — lọc bỏ đoạn mở đầu khớp mẫu đã biết,
# cùng cách dự án đã lọc điều khoản khỏi mô tả vé Vinpearl (xem POLICY_BODY_RE trong normalise.py); chưa chắc bắt hết mọi biến thể.
_BOOKING_PROMO_RE = re.compile(r"^(đăng nhập để mở khóa|giảm giá genius|sign in to unlock|genius discount)", re.I)


def _strip_booking_promo(text: str | None) -> str | None:
    if not text:
        return None
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    kept = [p for p in paras if not _BOOKING_PROMO_RE.match(p)]
    return "\n\n".join(kept) or None


def adapt_agoda(item: dict, ctx: dict) -> dict | None:
    """Actor Apify `agentx/agoda-hotels-scraper` → bản ghi `agoda_hotels`. Tên trường đã KIỂM với JSON thật (probe 5 khách sạn Nha Trang, 22/09/2026,
    xem data/demo/probe/) — mọi giả định ban đầu đều đúng, không phải sửa gì (khác Booking đầy đủ, có 3 lỗi). `address` là chuỗi, `facilities` là
    danh sách tên phẳng, `latitude`/`longitude` là số thực, `currency` LÀ mã ISO thật ("USD", không phải ký hiệu như Booking).
    Mô tả/tiện nghi actor trả về tiếng Anh (không có tham số ngôn ngữ nào được actor công bố) — không cần xử lý riêng ở đây: normalise.py tự phát
    hiện descriptionLang="en" và dựng mô tả tiếng Việt từ thuộc tính (localise_descriptions), giữ bản gốc ở descriptionOriginal; đã kiểm chứng
    bằng dữ liệu thật, không chỉ đọc code.
    Giá lấy `nightly_price` (giá đang bán) để so được với giá đã cào từ trang danh sách; `nightly_inclusive` (gồm thuế phí) không dùng."""
    name = (item.get("name") or "").strip()
    if not name:
        return None
    m = AGODA_URL.search(item.get("property_url") or item.get("url") or "")
    slug = m.group(1) if m else slugify(name)
    city_part = m.group(2) if m else slugify(item.get("city") or ctx.get("destination") or "")
    city_slug = re.sub(r"-vn$", "", city_part)
    currency = str(item.get("currency") or ctx.get("currency") or "VND").upper()
    checkin = item.get("check_in") or ctx.get("checkin")
    checkout = item.get("check_out") or ctx.get("checkout")
    images = list(dict.fromkeys(u for u in [item.get("image_url"), *(item.get("gallery_urls") or [])]
                                if isinstance(u, str) and u.startswith("http")))[:20]
    city = item.get("city") or ctx.get("destination")
    return {
        "key": f"hotel:{slug}:{city_slug}", "source": "agoda_hotels", "recordType": "agoda_hotel", "slug": slug, "citySlug": city_slug,
        "url": item.get("property_url") or item.get("url"), "name": name, "nameEn": None,
        "address": {"street": item.get("address"), "locality": item.get("area") or city, "region": city,
                    "country": item.get("country"), "postalCode": item.get("postal_code")},
        "plan": {"destination": ctx.get("destination"), "via": "apify-agoda", "city": city_part},
        "priceQuery": {"checkin": checkin, "checkout": checkout, "adults": item.get("adults") or ctx.get("adults") or 2, "currency": currency},
        "minPrice": _num(item.get("nightly_price")), "currency": currency, "priceText": None,
        "starRating": _num(item.get("star_rating")), "reviewScore": _num(item.get("review_score")), "reviewScoreScale": 10.0,
        "reviewCount": int(_num(item.get("review_count")) or 0) or None,
        "description": item.get("description"), "facilities": _strings(item.get("facilities")), "images": images,
        "latitude": _coord(item.get("latitude")), "longitude": _coord(item.get("longitude")),
        "crawledAt": ctx["fetchedAt"], "transport": "apify",
    }


def adapt_booking(item: dict, ctx: dict) -> dict | None:
    """Actor Apify `makework36/fast-booking-scraper` → bản ghi `booking_hotels`. Actor không trả toạ độ, mô tả, tiện nghi và từng hạng phòng, nên:
    toạ độ để trống (được lấy từ bản Agoda cùng khách sạn khi gộp, không ghép được thì bị xoá và ghi lý do), giá dẫn đầu thành MỘT hạng phòng
    (`roomInfo`), giá chia cho số đêm của khoảng ngày hỏi."""
    name = (item.get("name") or "").strip()
    if not name:
        return None
    hotel_id = str(item.get("hotelId") or "").strip() or None
    currency = str(item.get("currency") or ctx.get("currency") or "VND").upper()
    checkin = item.get("checkin") or ctx.get("checkin")
    checkout = item.get("checkout") or ctx.get("checkout")
    total = _num(item.get("price"))
    per_night = round(total / _nights(checkin, checkout), 2) if total else None
    info = item.get("roomInfo")
    room_name = (info.get("name") or info.get("title")) if isinstance(info, dict) else info
    room_name = str(room_name).strip()[:120] if room_name else "Phòng (giá dẫn đầu)"
    dest = item.get("destination") or ctx.get("destination")
    rooms = [{"roomId": f"{hotel_id or slugify(name)}-lead", "name": room_name, "bed": None, "facilities": [], "sizeM2": None,
              "maxOccupancy": None, "conditions": [], "minPrice": per_night, "currency": currency, "rateCount": 1}] if per_night else []
    return {
        "key": f"hotel:{hotel_id or slugify(name)}", "source": "booking_hotels", "recordType": "booking_hotel", "hotelId": hotel_id,
        "url": item.get("url"), "name": name, "address": {"street": item.get("address"), "locality": None},
        "city": dest, "province": None, "breadcrumbs": [],
        "priceQuery": {"checkin": checkin, "checkout": checkout, "adults": ctx.get("adults") or 2, "currency": currency},
        "minPrice": per_night, "currency": currency, "starRating": int(_num(item.get("stars")) or 0) or None,
        "starRatingType": "official" if _num(item.get("stars")) else None,
        "reviewScore": _num(item.get("rating")), "reviewScoreScale": 10.0, "reviewCount": int(_num(item.get("reviews")) or 0) or None,
        "propertyType": None, "description": None, "descriptionShort": None, "facilities": [], "popularFacilities": [], "highlights": [],
        "images": [item["image"]] if isinstance(item.get("image"), str) and item["image"].startswith("http") else [],
        "latitude": _coord(item.get("latitude")), "longitude": _coord(item.get("longitude")), "rooms": rooms,
        "plan": {"destination": ctx.get("destination") or dest, "via": "apify-booking"},
        "crawledAt": ctx["fetchedAt"], "transport": "apify",
    }


BOOKING_URL = re.compile(r"booking\.com/hotel/[a-z]{2}/([^/?#]+?)(?:\.[a-z]{2}(?:-[a-z]{2})?)?\.html")


def _pick(d: dict, *keys):
    for k in keys:
        if d.get(k) not in (None, "", [], {}):
            return d[k]
    return None


def _room_price_usd(room: dict, nights: int) -> float | None:
    """Phòng không có giá trực tiếp: giá thật nằm trong room['options'][].price (mỗi lựa chọn = một gói giá/số khách/chính sách huỷ).
    Lấy phương án rẻ nhất, chia cho số đêm."""
    prices = [p for o in (room.get("options") or []) if isinstance(o, dict) and (p := _num(o.get("price"))) is not None]
    return round(min(prices) / nights, 2) if prices else None


def _room_beds(room: dict) -> str | None:
    beds = [b for bt in (room.get("bedTypes") or []) if isinstance(bt, dict) for b in (bt.get("beds") or []) if isinstance(b, str)]
    return "; ".join(beds) if beds else None


def _flatten_facility_groups(groups) -> list[str]:
    """facilities của khách sạn là danh sách NHÓM {"name": tên nhóm, "facilities": [{"name": tên tiện nghi}, ...]} — lấy tên tiện nghi thật bên trong,
    không phải tên nhóm."""
    out = []
    for g in groups or []:
        if not isinstance(g, dict):
            continue
        items = [f.get("name") for f in (g.get("facilities") or []) if isinstance(f, dict) and f.get("name")]
        out += items or ([g["name"]] if g.get("name") else [])  # nhóm không có mục con: dùng tạm tên nhóm
    return list(dict.fromkeys(out))


def adapt_booking_full(item: dict, ctx: dict) -> dict | None:
    """Actor Apify chính thức `voyager/booking-scraper` → bản ghi `booking_hotels`. Tên trường đã KIỂM với JSON thật (probe 5 khách sạn Nha Trang,
    22/09/2026, xem data/demo/probe/). Ba điểm khác giả định ban đầu, đã sửa ở đây:
      * `currency` của actor chỉ là ký hiệu hiển thị ("US$"), không phải mã ISO — bỏ qua, luôn dùng "USD" (đúng giá trị ta gửi lên trong APIFY_KINDS).
      * Từng hạng phòng KHÔNG có giá trực tiếp: giá nằm trong room['options'][].price (xem `_room_price_usd`).
      * `facilities` của khách sạn là danh sách nhóm lồng nhau, không phải danh sách phẳng (xem `_flatten_facility_groups`).
    Không có hotelId thì khoá lấy theo slug trong URL: khi trộn với dữ liệu cào cũ (khoá theo hotelId số) có thể trùng khách sạn, nên dùng --only-api."""
    name = (item.get("name") or "").strip()
    if not name:
        return None
    url = item.get("url") or ""
    m = BOOKING_URL.search(url)
    hotel_id = str(_pick(item, "hotelId", "hotel_id", "id") or "").strip() or None
    ident = hotel_id or (m.group(1) if m else slugify(name))
    currency = "USD"
    checkin = str(item.get("checkInDate") or ctx.get("checkin") or "")[:10] or None
    checkout = str(item.get("checkOutDate") or ctx.get("checkout") or "")[:10] or None
    nights = _nights(checkin, checkout)
    loc = item.get("location") if isinstance(item.get("location"), dict) else {}
    lat = _coord(_pick(loc, "lat", "latitude") if loc else item.get("latitude"))
    lng = _coord(_pick(loc, "lng", "lon", "longitude") if loc else item.get("longitude"))
    addr = item.get("address")
    if isinstance(addr, dict):
        street = _pick(addr, "full", "street") or None
        city = _pick(addr, "city", "region")
    else:
        street, city = (str(addr) if addr else None), None
    rooms = []
    for i, r in enumerate(item.get("rooms") or []):
        if not isinstance(r, dict):
            continue
        rooms.append({"roomId": str(_pick(r, "id", "roomId") or f"{ident}-{i}"), "name": str(_pick(r, "roomType", "name", "title") or "Phòng")[:120],
                      "bed": _room_beds(r), "facilities": _strings(r.get("facilities")), "sizeM2": _num(r.get("size")),
                      "maxOccupancy": int(_num(_pick(r, "persons", "maxOccupancy", "guests")) or 0) or None, "conditions": [],
                      "minPrice": _room_price_usd(r, nights), "currency": currency, "rateCount": len(r.get("options") or []) or 1})
    prices = [r["minPrice"] for r in rooms if r["minPrice"]]
    top = _num(item.get("price"))
    min_price = min(prices) if prices else (round(top / nights, 2) if top else None)
    images = list(dict.fromkeys(u for u in [item.get("image"), *(item.get("images") or [])] if isinstance(u, str) and u.startswith("http")))[:30]
    dest = ctx.get("destination")
    return {
        "key": f"hotel:{ident}", "source": "booking_hotels", "recordType": "booking_hotel", "hotelId": hotel_id, "url": url or None, "name": name,
        "address": {"street": street, "locality": None}, "city": city or dest, "province": None, "breadcrumbs": [],
        "priceQuery": {"checkin": checkin, "checkout": checkout, "adults": ctx.get("adults") or 2, "currency": currency},
        "minPrice": min_price, "currency": currency, "starRating": int(_num(item.get("stars")) or 0) or None,
        "starRatingType": "official" if _num(item.get("stars")) else None, "reviewScore": _num(item.get("rating")), "reviewScoreScale": 10.0,
        "reviewCount": int(_num(item.get("reviews")) or 0) or None, "propertyType": item.get("type"), "description": _strip_booking_promo(item.get("description")),
        "descriptionShort": None, "facilities": _flatten_facility_groups(item.get("facilities")), "popularFacilities": [], "highlights": [], "images": images,
        "latitude": lat, "longitude": lng, "rooms": rooms, "plan": {"destination": dest, "via": "apify-booking-full"},
        "crawledAt": ctx["fetchedAt"], "transport": "apify",
    }


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    taxonomy: str
    stem: str | None                                   # tên file interim mà normalise đọc; None = chưa có bộ chuyển
    adapt: Callable[[dict, dict], dict | None] | None
    pending: str = ""


SPECS: dict[str, Spec] = {s.key: s for s in (
    Spec("apify_agoda", "Apify → Agoda", "hotel", "agoda_hotels", adapt_agoda),
    Spec("apify_booking_full", "Apify → Booking.com (đủ phòng + toạ độ)", "hotel", "booking_hotels", adapt_booking_full),
    Spec("apify_booking", "Apify → Booking.com (bản nhanh, thiếu phòng/toạ độ)", "hotel", "booking_hotels", adapt_booking),
    Spec("serpapi_hotels", "SerpApi → Google Hotels", "hotel", None, None,
         "Google Hotels là nguồn thứ ba của bước gộp khách sạn: cần thêm vào normalise sau khi xem JSON thật"),
    Spec("travelpayouts_flights", "Travelpayouts → chuyến bay", "flight", None, None,
         "cần dạng chuyến bay thật của API để dựng tuyến + chuyến đúng schema catalog"),
    Spec("apify_klook", "Apify → Klook", "attraction", None, None,
         "JSON Klook không có toạ độ: cần thêm bước lấy toạ độ (OSM Photon) trước khi vào catalog"),
)}


# ------------------------------------------------------------------------------------------------ đọc + nhận diện
def make_envelope(source: str, items: list[dict], query: dict | None = None, cost_usd: float | None = None) -> dict:
    return {"schema": 1, "source": source, "fetchedAt": now_z(), "query": query or {}, "costUsd": cost_usd, "items": items}


def write_file_atomic(dest: Path, obj) -> Path:
    """Ghi vào file tạm rồi đổi tên: bộ theo dõi hộp thư không bao giờ thấy file ghi dở."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".tmp-{dest.name}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, dest)
    return dest


def load_items(path: Path) -> tuple[dict, list[dict]]:
    """Nhận: phong bì của fetch, mảng JSON, {"items"|"data"|"properties"|"results"|"hotels": [...]}, JSONL, hoặc một bản ghi đơn."""
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    if path.suffix == ".jsonl":
        items = [json.loads(ln) for ln in text.split("\n") if ln.strip()]  # split("\n"): splitlines() cắt cả ở U+0085/U+2028 trong chuỗi JSON
    else:
        data = json.loads(text)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            key = next((k for k in ("items", "data", "properties", "results", "hotels") if isinstance(data.get(k), list)), None)
            items = data[key] if key else [data]
            meta = {k: v for k, v in data.items() if k != key} if key else {}
        else:
            raise ValueError("JSON phải là mảng hoặc đối tượng")
    items = [x for x in items if isinstance(x, dict)]
    if not items:
        raise ValueError("không có bản ghi nào trong file")
    return meta, items


def detect_source(meta: dict, items: list[dict]) -> str | None:
    if meta.get("source") in SPECS:
        return meta["source"]
    keys: set[str] = set()
    for it in items[:20]:
        keys |= set(it)
    if {"property_id", "star_rating"} <= keys or {"nightly_price", "property_url"} <= keys:
        return "apify_agoda"
    if any(isinstance(it.get("rooms"), list) and it["rooms"] and isinstance(it.get("location"), (dict, type(None))) and "stars" in it
           and "booking.com" in str(it.get("url")) for it in items[:20]):
        return "apify_booking_full"
    if {"hotelId", "stars"} <= keys and keys & {"priceDisplay", "unitConfig", "roomInfo"}:
        return "apify_booking"
    if "gps_coordinates" in keys and keys & {"property_token", "rate_per_night"}:
        return "serpapi_hotels"
    if {"airline", "departure_at"} <= keys or {"origin_airport", "destination_airport"} <= keys:
        return "travelpayouts_flights"
    if any("klook.com" in v for it in items[:20] for v in it.values() if isinstance(v, str)):
        return "apify_klook"
    return None


def _context(meta: dict, path: Path) -> dict:
    q = dict(meta.get("query") or {})
    sp = meta.get("search_parameters") or {}  # SerpApi ghi tham số tìm kiếm ở đây
    fetched = meta.get("fetchedAt") or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"fetchedAt": fetched, "destination": q.get("destination") or sp.get("q"), "checkin": q.get("checkin") or sp.get("check_in_date"),
            "checkout": q.get("checkout") or sp.get("check_out_date"), "adults": q.get("adults") or sp.get("adults"),
            "currency": q.get("currency") or sp.get("currency")}


def _stash(path: Path, sub: str) -> Path:
    dest_dir = path.parent / sub
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{path.name}"
    n = 1
    while dest.exists():
        n += 1
        dest = dest_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}-{path.name}"
    shutil.move(str(path), dest)
    return dest


def inbox_waiting(inbox: Path, min_age: float = SETTLE_SECONDS) -> list[Path]:
    if not inbox.is_dir():
        return []
    cutoff = time.time() - min_age
    return sorted((p for p in inbox.iterdir() if p.is_file() and p.suffix in (".json", ".jsonl") and not p.name.startswith(".")
                   and p.stat().st_mtime <= cutoff), key=lambda p: (p.stat().st_mtime, p.name))


def intake(inbox: Path, store: Path, min_age: float = SETTLE_SECONDS, log: Callable[[str], None] = lambda s: None) -> list[dict]:
    """Nhận mọi file đã 'nằm yên' trong hộp thư: nhận diện → đổi dạng → thêm vào kho. Trả kết quả từng file (để giao diện hiển thị)."""
    results = []
    for path in inbox_waiting(inbox, min_age):
        res = {"file": path.name, "source": None, "label": None, "taxonomy": None, "items": 0, "mapped": 0, "skipped": 0,
               "status": "failed", "note": "", "bytes": path.stat().st_size}
        try:
            meta, items = load_items(path)
        except (ValueError, OSError, UnicodeDecodeError) as e:
            res["note"] = f"không đọc được: {str(e)[:120]}"
            _stash(path, "_failed")
            results.append(res)
            log(f"[inbox] {path.name}: {res['note']}")
            continue
        res["items"] = len(items)
        src = detect_source(meta, items)
        spec = SPECS.get(src) if src else None
        if spec is None:
            res.update(status="unrecognized", note="không nhận ra nguồn (không thấy trường đặc trưng của Apify Agoda/Booking, SerpApi, Travelpayouts, Klook)")
            _stash(path, "_unrecognized")
        else:
            res.update(source=spec.key, label=spec.label, taxonomy=spec.taxonomy)
            if spec.adapt is None:
                res.update(status="pending", note=f"đã nhận diện, chờ bộ chuyển: {spec.pending}")
                _stash(path, "_pending")
            else:
                ctx = _context(meta, path)
                records = [r for r in (spec.adapt(it, ctx) for it in items) if r]
                target = store / "interim" / f"{spec.stem}.jsonl"
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "a", encoding="utf-8") as f:
                    for r in records:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                no_price = sum(1 for r in records if not r.get("minPrice"))
                no_coord = sum(1 for r in records if r.get("latitude") is None)
                res.update(status="done", mapped=len(records), skipped=len(items) - len(records),
                           note=(f"thiếu giá {no_price}, thiếu toạ độ {no_coord}" if (no_price or no_coord) else "đủ giá và toạ độ"))
                _stash(path, "_processed")
        results.append(res)
        log(f"[inbox] {path.name}: {res['status']} · {res['label'] or '?'} · {res['items']} mục → {res['mapped']} bản ghi · {res['note']}")
    return results


def inbox_overview(inbox: Path) -> dict:
    out = {"waiting": [], "counts": {s: 0 for s in SUBDIRS}}
    if not inbox.is_dir():
        return out
    for p in sorted(inbox.iterdir()):
        if p.is_file() and p.suffix in (".json", ".jsonl") and not p.name.startswith("."):
            out["waiting"].append({"file": p.name, "bytes": p.stat().st_size})
        elif p.is_dir() and p.name in SUBDIRS:
            out["counts"][p.name] = sum(1 for x in p.iterdir() if x.is_file())
    return out


# ------------------------------------------------------------------------------------------------ tải hàng loạt
@dataclass
class FetchOptions:
    destinations: list[str]
    max_items: int = 50
    max_usd: float = 1.0
    checkin: str = ""
    checkout: str = ""
    adults: int = 2
    currency: str = "VND"
    concurrency: int = 3
    pages: int = 1
    routes: list[str] = field(default_factory=list)
    month: str = ""

    def __post_init__(self):
        if not self.checkin:
            d = date.today() + timedelta(days=30)
            self.checkin, self.checkout = d.isoformat(), (d + timedelta(days=1)).isoformat()
        if not self.month:
            self.month = (date.today() + timedelta(days=30)).strftime("%Y-%m")

    def validate(self) -> None:
        if not 1 <= len(self.destinations) <= MAX_DESTINATIONS:
            raise ApiError(f"số điểm đến phải trong 1..{MAX_DESTINATIONS}")
        if not 1 <= self.max_items <= MAX_ITEMS_PER_DESTINATION:
            raise ApiError(f"--max-items phải trong 1..{MAX_ITEMS_PER_DESTINATION}")
        if not 0 < self.max_usd <= MAX_USD_PER_FETCH:
            raise ApiError(f"--max-usd phải trong (0, {MAX_USD_PER_FETCH}]")
        for d in self.destinations:
            if not re.fullmatch(r"[\w .,\-]{1,60}", d):
                raise ApiError(f"tên điểm đến không hợp lệ: {d!r}")


def destination_query(name: str) -> str:
    by_name = {d.name: d for d in DESTINATIONS}
    d = by_name.get(name)
    return f"{d.booking_query if d else name}, Vietnam"


APIFY_KINDS = {
    # Actor này không nhận VND (danh sách tiền tệ cố định, kiểm ngày 22/09/2026 qua lỗi thật từ Apify) → luôn hỏi USD,
    # adapt_booking_full/to_vnd() tự quy đổi sang VND như các nguồn khác.
    "apify-booking-full": {"actor": "voyager/booking-scraper", "source": "apify_booking_full", "usd_item": 0.002, "usd_run": 0.0,
                           "input": lambda q, o: {"search": q, "maxItems": o.max_items, "checkIn": o.checkin, "checkOut": o.checkout, "currency": "USD",
                                                  "language": "vi", "adults": o.adults, "rooms": 1, "children": 0}},
    "apify-agoda": {"actor": "agentx/agoda-hotels-scraper", "source": "apify_agoda", "usd_item": 0.004, "usd_run": 0.02,
                    "input": lambda q, o: {"location": q, "max_results": o.max_items, "check_in": o.checkin, "check_out": o.checkout}},
    "apify-booking": {"actor": "makework36/fast-booking-scraper", "source": "apify_booking", "usd_item": 0.0018, "usd_run": 0.0,
                      "input": lambda q, o: {"destinations": [q], "maxResults": o.max_items, "checkin": o.checkin, "checkout": o.checkout,
                                             "adults": o.adults, "currency": o.currency}},
    # golf ngoài Vinpearl (xem SPECS: apify_klook, adapt=None — chỉ xem thử/tải thô, CHƯA vào catalog cho tới khi có JSON thật để viết bộ chuyển
    # và ghép toạ độ từ OpenStreetMap, vì Klook không trả toạ độ theo trang mô tả actor).
    "apify-klook-golf": {"actor": "dariomory/klook-activities-scraper", "source": "apify_klook", "usd_item": 0.005, "usd_run": 0.0,
                         "input": lambda q, o: {"searchKeywords": [f"golf {q}"], "maxItemsPerKeyword": o.max_items}},
}
FETCH_KINDS = tuple(APIFY_KINDS) + ("serpapi", "travelpayouts")
DEFAULT_ROUTES = ["HAN-SGN", "SGN-HAN", "HAN-DAD", "DAD-HAN", "SGN-DAD", "DAD-SGN", "SGN-CXR", "CXR-SGN", "SGN-PQC", "PQC-SGN", "HAN-CXR", "HAN-PQC"]


def estimate_cost(kind: str, n_destinations: int, max_items: int, pages: int = 1, n_routes: int = 0) -> dict:
    """Ước tính theo giá niêm yết đã đọc ngày 21/09/2026 (có thể đổi). Trần chi tiêu thật do --max-usd/maxTotalChargeUsd đảm bảo."""
    if kind in APIFY_KINDS:
        k = APIFY_KINDS[kind]
        return {"usd": round(n_destinations * (max_items * k["usd_item"] + k["usd_run"]), 4), "unit": "USD (Apify, trả theo kết quả)"}
    if kind == "serpapi":
        n = n_destinations * pages
        return {"usd": 0.0, "unit": f"{n} lượt tìm kiếm (gói free 250 lượt/tháng, sau đó ~$0,025/lượt)"}
    return {"usd": 0.0, "unit": f"{n_routes or len(DEFAULT_ROUTES)} lượt gọi (token miễn phí)"}


def _slug_file(kind: str, part: str) -> str:
    return f"{kind}-{slugify(part)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"


def fetch_apify(kind: str, opts: FetchOptions, inbox: Path, *, client: apify_source.Apify | None = None,
                on_event: Callable[[dict], None] = lambda e: None) -> list[dict]:
    """Mỗi điểm đến một lượt chạy actor, chạy song song (gói Free của Apify cho tối đa 5 run cùng lúc). Trần chi tiêu chia đều cho các điểm đến."""
    opts.validate()
    k = APIFY_KINDS[kind]
    client = client or apify_source.Apify(apify_source.get_token())
    per_run = round(opts.max_usd / len(opts.destinations), 4)
    if per_run < k["usd_run"] + k["usd_item"]:
        raise ApiError(f"Ngân sách ${opts.max_usd} quá nhỏ cho {len(opts.destinations)} điểm đến (mỗi lượt chạy tối thiểu ~${k['usd_run'] + k['usd_item']:.3f}).")

    def one(dest: str) -> dict:
        res = {"destination": dest, "items": 0, "costUsd": None, "file": None, "error": None}
        try:
            out = client.run_and_collect(k["actor"], k["input"](destination_query(dest), opts), max_items=opts.max_items, max_usd=per_run,
                                         wait_timeout_s=600)
            query = {"destination": dest, "checkin": opts.checkin, "checkout": opts.checkout, "adults": opts.adults, "currency": opts.currency}
            env = make_envelope(k["source"], out["items"], query, out["costUsd"])
            res.update(items=len(out["items"]), costUsd=out["costUsd"], file=write_file_atomic(inbox / _slug_file(kind, dest), env).name)
        except ApiError as e:
            res["error"] = str(e)
        on_event(res)
        return res

    with ThreadPoolExecutor(max_workers=max(1, min(opts.concurrency, 5))) as pool:
        return list(pool.map(one, opts.destinations))


def _get_json(url: str, headers: dict | None = None, timeout: float = 60.0, redact: tuple[str, ...] = ()) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "vota-pipeline-demo/1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code} từ {urllib.parse.urlsplit(url).netloc}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        msg = f"không gọi được {urllib.parse.urlsplit(url).netloc}: {e}"
    for s in redact:
        msg = msg.replace(s, "***")
    raise ApiError(msg)


def fetch_serpapi(opts: FetchOptions, inbox: Path, *, api_key: str | None = None, base: str = "https://serpapi.com",
                  on_event: Callable[[dict], None] = lambda e: None) -> list[dict]:
    """Google Hotels qua SerpApi: mỗi điểm đến 1..pages trang (~20 khách sạn/trang, mỗi trang tính 1 lượt tìm kiếm). Khoá nằm trong query string
    theo cách SerpApi yêu cầu, nên lỗi luôn được che khoá trước khi hiện ra."""
    opts.validate()
    key = api_key or secret("SERPAPI_KEY")
    results = []
    for dest in opts.destinations:
        res = {"destination": dest, "items": 0, "costUsd": None, "file": None, "error": None}
        items: list[dict] = []
        token = None
        try:
            for _ in range(max(1, opts.pages)):
                params = {"engine": "google_hotels", "q": f"khách sạn {dest}", "check_in_date": opts.checkin, "check_out_date": opts.checkout,
                          "adults": opts.adults, "currency": opts.currency, "gl": "vn", "hl": "vi", "api_key": key}
                if token:
                    params["next_page_token"] = token
                page = _get_json(f"{base}/search.json?" + urllib.parse.urlencode(params), redact=(key,))
                if page.get("error"):
                    raise ApiError(f"SerpApi: {str(page['error'])[:160]}")
                items += [p for p in page.get("properties") or [] if isinstance(p, dict)]
                token = (page.get("serpapi_pagination") or {}).get("next_page_token")
                if not token:
                    break
            query = {"destination": dest, "checkin": opts.checkin, "checkout": opts.checkout, "adults": opts.adults, "currency": opts.currency}
            res.update(items=len(items), file=write_file_atomic(inbox / _slug_file("serpapi", dest), make_envelope("serpapi_hotels", items, query)).name)
        except ApiError as e:
            res["error"] = str(e)
        on_event(res)
        results.append(res)
    return results


def fetch_travelpayouts(opts: FetchOptions, inbox: Path, *, token: str | None = None, base: str = "https://api.travelpayouts.com",
                        on_event: Callable[[dict], None] = lambda e: None) -> list[dict]:
    """Giá vé máy bay tham khảo (cache của Aviasales) theo tuyến trong một tháng. Token qua header X-Access-Token."""
    tok = token or secret("TRAVELPAYOUTS_TOKEN")
    routes = opts.routes or DEFAULT_ROUTES
    results = []
    for route in routes:
        res = {"destination": route, "items": 0, "costUsd": 0.0, "file": None, "error": None}
        try:
            o, d = route.split("-")
            if not (re.fullmatch(r"[A-Z]{3}", o) and re.fullmatch(r"[A-Z]{3}", d)):
                raise ApiError(f"tuyến không hợp lệ: {route!r} (dạng HAN-SGN)")
            q = urllib.parse.urlencode({"origin": o, "destination": d, "departure_at": opts.month, "currency": "vnd", "limit": 200,
                                        "sorting": "price", "unique": "false", "one_way": "true"})
            data = _get_json(f"{base}/aviasales/v3/prices_for_dates?{q}", headers={"X-Access-Token": tok}, redact=(tok,))
            items = [x for x in data.get("data") or [] if isinstance(x, dict)]
            env = make_envelope("travelpayouts_flights", items, {"origin": o, "destination": d, "month": opts.month, "currency": "vnd"})
            res.update(items=len(items), file=write_file_atomic(inbox / _slug_file("travelpayouts", route), env).name)
        except (ApiError, ValueError) as e:
            res["error"] = str(e)
        on_event(res)
        results.append(res)
    return results


def fetch(kind: str, opts: FetchOptions, inbox: Path, *, on_event: Callable[[dict], None] = lambda e: None, **kw) -> list[dict]:
    if kind in APIFY_KINDS:
        return fetch_apify(kind, opts, inbox, on_event=on_event, **kw)
    if kind == "serpapi":
        return fetch_serpapi(opts, inbox, on_event=on_event, **kw)
    if kind == "travelpayouts":
        return fetch_travelpayouts(opts, inbox, on_event=on_event, **kw)
    raise ApiError(f"nguồn không hỗ trợ: {kind!r} (chọn một trong {', '.join(FETCH_KINDS)})")


def token_status() -> dict:
    return {"apify": has_secret("APIFY_TOKEN"), "serpapi": has_secret("SERPAPI_KEY"), "travelpayouts": has_secret("TRAVELPAYOUTS_TOKEN")}


# ------------------------------------------------------------------------------------------------ lưu token từ giao diện (.env)
ENV_KEYS = ("APIFY_TOKEN", "SERPAPI_KEY", "TRAVELPAYOUTS_TOKEN")
ENV_PATH = apify_source.ROOT / ".env"


def _rewrite_env(transform) -> None:
    """Đọc .env (hoặc .env.example nếu chưa có .env, để giữ chú thích), đổi các dòng khớp `transform`, ghi đè nguyên tử. Không bao giờ log giá trị."""
    src = ENV_PATH if ENV_PATH.exists() else apify_source.ROOT / ".env.example"
    lines = src.read_text(encoding="utf-8").split("\n") if src.exists() else []
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line and not line.lstrip().startswith("#") else None
        if key in ENV_KEYS:
            seen.add(key)
            new = transform(key, line)
            if new is not None:
                out.append(new)
        else:
            out.append(line)
    for key in set(ENV_KEYS) - seen:
        new = transform(key, f"{key}=")
        if new is not None:
            out.append(new)
    tmp = ENV_PATH.with_suffix(".tmp")
    tmp.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    os.replace(tmp, ENV_PATH)
    try:
        os.chmod(ENV_PATH, 0o600)  # chỉ chủ file đọc được; bỏ qua nếu hệ điều hành không hỗ trợ (vd. Windows)
    except OSError:
        pass


def save_env_var(key: str, value: str) -> None:
    """Ghi một token vào .env từ giao diện. Không bao giờ trả giá trị ngược lại, không ghi vào log/state."""
    if key not in ENV_KEYS:
        raise ApiError(f"khoá không hợp lệ: {key!r}")
    value = value.strip().strip("'\"")
    if not value:
        raise ApiError("chưa nhập giá trị")
    if len(value) > 300 or re.search(r"[\r\n]", value):
        raise ApiError("giá trị không hợp lệ (quá dài hoặc chứa dòng mới)")
    _rewrite_env(lambda k, line: f"{key}={value}" if k == key else line)
    os.environ[key] = value  # để tiến trình monitor.py hiện tại dùng ngay, không cần khởi động lại


def clear_env_var(key: str) -> None:
    if key not in ENV_KEYS:
        raise ApiError(f"khoá không hợp lệ: {key!r}")
    _rewrite_env(lambda k, line: f"{key}=" if k == key else line)
    os.environ.pop(key, None)


def probe_kind(kind: str, destination: str, limit: int, max_usd: float, out_dir: Path) -> dict:
    """Xem thử N mục thật của một actor Apify (dùng chung bảng APIFY_KINDS với fetch/pull) — để nhìn JSON trước khi viết/sửa bộ chuyển."""
    if kind not in APIFY_KINDS:
        raise ApiError(f"nguồn không xem thử được: {kind!r}")
    k = APIFY_KINDS[kind]
    opts = FetchOptions(destinations=[destination], max_items=limit)
    input_ = k["input"](destination_query(destination), opts)
    res = apify_source.probe(k["actor"], input_, limit=limit, max_usd=max_usd, out_dir=out_dir)
    saved = json.loads(res["path"].read_text(encoding="utf-8"))
    return {"kind": kind, "actor": k["actor"], "path": str(res["path"]), "count": res["count"], "costUsd": res["costUsd"],
            "fields": res["fields"], "items": saved["items"]}
