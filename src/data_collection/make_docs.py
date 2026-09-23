"""Sinh SCHEMA.md, BANGIAO.md và sample/README.md từ catalog đã chuẩn hoá: mọi con số được tính lại từ
products.jsonl (không gõ tay), nên không lệch khi catalog thay đổi.

Chạy sau normalise.py + make_template.py + make_sample.py (finalize_catalog.sh gọi tự động):
    python make_docs.py [--data-dir data]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics
from datetime import date
from pathlib import Path

from collectors.textutil import fold


def vn(x: float, d: int = 0) -> str:
    """1234.5 → '1.234,5' (định dạng số kiểu Việt Nam)."""
    return f"{x:,.{d}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def pct(a: int, b: int, d: int = 0) -> str:
    if not b:
        return "–"
    if a == b:
        return "100%"
    v = 100 * a / b
    if a and v < 1 and d == 0:
        return "<1%"
    return vn(v, d) + "%"


def has(v) -> bool:
    return v not in (None, "", [], {})


def table(header: list[str], body: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(out)


def variant(o: dict) -> str:
    level = o["attributes"].get("level")
    if o["taxonomy"] == "hotel":
        return f"hotel_{level or 'property'}"
    if o["taxonomy"] == "flight":
        return "flight_route" if level == "route" else "flight"
    return o["taxonomy"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    a = ap.parse_args()
    d = a.data_dir
    rows = [json.loads(l) for l in open(d / "products.jsonl", encoding="utf-8")]
    n = len(rows)
    today = date.today().isoformat()
    day = today[8:] + "/" + today[5:7] + "/" + today[:4]
    A = lambda o: o["attributes"]  # noqa: E731
    by_var: dict[str, list[dict]] = collections.defaultdict(list)
    for o in rows:
        by_var[variant(o)].append(o)
    src = lambda o: o["sourceRef"].split(":")[0]  # noqa: E731

    def cov(key: str, items: list[dict] | None = None) -> int:
        return sum(1 for o in (rows if items is None else items) if has(A(o).get(key)))

    def med_len(items: list[dict]) -> int:
        return int(statistics.median(len(o["description"] or "") for o in items)) if items else 0

    # ---------------------------------------------------------------- số liệu dùng chung
    priced = [o for o in rows if o["unitPrice"] is not None]
    unpriced = [o for o in rows if o["unitPrice"] is None]
    unpriced_trip = [o for o in unpriced if o["sourceRef"].startswith("trip:attraction:")]
    derived = [o for o in rows if A(o).get("descriptionSource")]
    vi = sum(1 for o in rows if A(o).get("descriptionLang") == "vi")
    coords = sum(1 for o in rows if A(o).get("latitude") is not None and A(o).get("longitude") is not None)
    with_img = sum(1 for o in rows if o["imageUrl"])
    with_range = [o for o in rows if o["availableFrom"] or o["availableTo"]]
    range_src = collections.Counter(variant(o) for o in with_range)
    avail = sum(1 for o in rows if o["available"])
    observed = sorted(A(o)["priceObservedAt"][:10] for o in rows if A(o).get("priceObservedAt"))
    price_dates = collections.Counter(A(o)["priceDate"] for o in rows if o["taxonomy"] == "hotel" and A(o).get("priceDate"))
    main_price_date, main_price_n = price_dates.most_common(1)[0] if price_dates else ("?", 0)
    other_price_dates = sorted(k for k in price_dates if k != main_price_date)
    hotel_rows = [o for o in rows if o["taxonomy"] == "hotel"]
    props, rooms = by_var["hotel_property"], by_var["hotel_room"]
    rooms_of: dict[str, int] = collections.Counter(A(o)["parentProductId"] for o in rooms)
    props_with_rooms = sum(1 for o in props if o["productId"] in rooms_of)
    flights, routes = by_var["flight"], by_var["flight_route"]
    dest_n = len({o["destination"] for o in rows})
    sources = collections.Counter(src(o) for o in rows)
    dedup = max(0, sum(1 for _ in open(d / "dedup_report.csv", encoding="utf-8")) - 1) if (d / "dedup_report.csv").exists() else 0
    manual_coords = sum(1 for o in rows if A(o).get("locationSource") == "manual")
    excluded_manual = 0
    ex_path = Path(__file__).resolve().parent / "collectors" / "excluded_products.csv"
    if ex_path.exists():
        with open(ex_path, encoding="utf-8-sig", newline="") as f:
            excluded_manual = sum(1 for r in csv.DictReader(f) if (r.get("sourceRef") or "").strip())

    # ================================================================ SCHEMA.md
    fields = [
        ("productId", "string, UUIDv5", "Khoá chính. Sinh từ `sourceRef` nên **ổn định giữa các lần chạy lại** — dùng làm khoá ngoại được, không cần lưu bảng ánh xạ"),
        ("name", "string", "Tên hiển thị. Hạng phòng theo mẫu `\"<Khách sạn> - <Hạng phòng>\"`, vé máy bay `\"Vé máy bay <A> - <B>\"`"),
        ("taxonomy", "enum", "`hotel` · `flight` · `attraction` · `combo` · `golf`"),
        ("destination", "string", "Nhãn **điểm đến du lịch**, không phải tỉnh hành chính. Tỉnh nằm ở `attributes.province`"),
        ("description", "string", "Văn bản dùng để embedding. Không chứa điều khoản vé"),
        ("attributes", "object", "Xem mục 3. Tập khoá thay đổi theo `taxonomy`"),
        ("unitPrice", "number \\| null", "Khách sạn: giá **một đêm**. Vé máy bay: giá một chiều tham khảo. `null` = chưa có giá (mục 2, điểm 2)"),
        ("currency", "string", "Luôn là `\"VND\"`"),
        ("available", "boolean", "Nguồn có trả giá tại thời điểm crawl (điểm tham quan trip.com: địa điểm có trên trip.com, có thể chưa có giá). **Không phải xác nhận còn chỗ**"),
        ("availableFrom", "date \\| null", "Vé/combo/golf Vinpearl: ngày bắt đầu bán (API Vinpearl). Vé máy bay: ngày bay sớm nhất trip.com liệt kê (giờ VN). Còn lại `null`"),
        ("availableTo", "date \\| null", "Vé/combo/golf Vinpearl: ngày hết hạn bán (API Vinpearl). Vé máy bay: ngày bay muộn nhất trip.com liệt kê (giờ VN). Còn lại `null`"),
        ("imageUrl", "URL \\| null", "Ảnh chính. Ảnh phụ ở `attributes.images`. Vé máy bay không có ảnh"),
        ("sourceRef", "string", "`\"<nguồn>:<loại>:<id>\"`, ví dụ `vinpearl:tour:VW00466`. Truy ngược về bản ghi gốc"),
    ]
    field_rows = []
    for key, typ, meaning in fields:
        c = sum(1 for o in rows if has(o.get(key)))
        field_rows.append([f"`{key}`", typ, pct(c, n, 1), meaning])

    attr_groups: list[tuple[str, str, list[tuple[str, str, str]]]] = [
        ("3.1 Định danh và liên kết", "", [
            ("level", "enum", "`property` / `room` cho khách sạn; `route` / `flight` cho vé máy bay. Điểm tham quan, combo, golf không có"),
            ("parentProductId", "string", "`productId` của khách sạn cha (hạng phòng) hoặc tuyến bay cha (chuyến cụ thể)"),
            ("url", "URL", "Trang nguồn của sản phẩm"),
            ("fieldSources", "object", "Trường nào lấy từ nguồn nào, ví dụ `{\"unitPrice\": \"booking.com\", \"description\": \"vinpearl\"}`"),
            ("sameAs", "array", "`sourceRef` của các bản ghi cùng sản phẩm ở nguồn khác đã gộp vào dòng này"),
            ("brand", "string", "Thương hiệu, chủ yếu là `Vinpearl`"),
        ]),
        ("3.2 Vị trí", "", [
            ("latitude", "number", "Vĩ độ WGS84 (kinh độ: `longitude`)"),
            ("locationSource", "enum", "Nguồn toạ độ (bảng bên dưới)"),
            ("locationPrecision", "enum", "`exact` = vị trí riêng của sản phẩm · `venue` = khu vui chơi/sân golf dùng vé · `airport` = sân bay đến · `poi` = điểm tham quan trip.com · `destination` = tâm điểm đến (combo bay+ở trip.com, KHÔNG có toạ độ khách sạn thật — không dùng để tính khoảng cách/hiển thị \"cách bạn N km\")"),
            ("address", "string", "Địa chỉ nguồn cung cấp"),
            ("province", "string", "Đơn vị hành chính (khác `destination`)"),
            ("city", "string", "Thành phố theo địa chỉ"),
            ("locationWarning", "string", "Toạ độ bất thường; chỉ còn ở sản phẩm Vinpearl được giữ lại (dòng khác có cảnh báo đã bị xoá, xem `excluded_location.csv`)"),
        ]),
        ("3.3 Mô tả", "", [
            ("descriptionLang", "enum", "Luôn là `vi` sau chuẩn hoá. Ước lượng theo tỷ lệ ký tự có dấu, không phải kiểm tra ngôn ngữ đầy đủ"),
            ("descriptionSource", "string", "**Có giá trị nghĩa là mô tả được tự sinh**, không phải văn bản gốc của nguồn. Xem mục 5"),
            ("descriptionOriginal", "string", "Văn bản gốc của nguồn khi mô tả đã được dựng lại bằng tiếng Việt"),
            ("policies", "object", "Điều khoản, chính sách hoàn huỷ, hướng dẫn sử dụng — tách khỏi `description` để không làm nhiễu embedding"),
            ("conditions", "array", "Điều kiện đặt phòng của hạng phòng OTA, mỗi phần tử một điều kiện"),
            ("highlights", "array", "Điểm nổi bật do nguồn gắn"),
        ]),
        ("3.4 Giá và tình trạng", "", [
            ("priceObservedAt", "datetime", "Thời điểm quan sát giá"),
            ("priceQuery", "object", "Khách sạn: điều kiện đã hỏi giá (ngày nhận/trả phòng, số người lớn, tiền tệ)"),
            ("priceDate", "date", "Ngày nhận phòng đã dùng để hỏi giá. **Không đồng nhất**: đọc trường này thay vì giả định một ngày"),
            ("priceNights", "int", "Số đêm của `unitPrice` — luôn là 1"),
            ("priceAdults", "int", "Số người lớn đã dùng để hỏi giá"),
            ("availabilityEvidenceKind", "enum", "`queried_stay_not_a_general_date_range` = chỉ có bằng chứng cho đúng kỳ lưu trú đã hỏi, KHÔNG phải khoảng ngày còn phòng"),
            ("availabilityDatesObserved", "array", "Các ngày nhận phòng đã có giá (chỉ khi crawl nhiều ngày)"),
            ("otaPrices", "object", "Giá cùng sản phẩm ở các OTA khác, để so sánh"),
            ("vinpearlPrice", "number", "Giá niêm yết trên vinpearl.com khi OTA thắng ở `unitPrice`"),
            ("memberPrices", "object", "Giá theo hạng thành viên VinClub: `{\"Gold\": …, \"Platinum\": …, \"Diamond\": …}`"),
            ("adultOriginalPrice", "number", "Vé Vinpearl: giá gốc người lớn trước khuyến mãi (`childPrice`: giá trẻ em)"),
            ("pricesByDate", "object", "Hạng phòng Vinpearl: giá theo từng ngày nhận phòng đã hỏi"),
            ("availabilityRangeKind", "enum", "`sale_window` = `availableFrom/To` là khoảng thời gian bán vé do Vinpearl công bố"),
        ]),
        ("3.5 Đặc tính sản phẩm", "", [
            ("starRating", "number", "Khách sạn, hạng phòng"),
            ("starRatingType", "enum", "`official` hoặc `booking_estimate` (Booking tự ước lượng)"),
            ("propertyType", "string", "Loại hình lưu trú"),
            ("amenities", "array", "Tiện ích, đã gộp từ nhiều nguồn nên có thể trùng ý"),
            ("images", "array", "Ảnh phụ"),
            ("roomName", "string", "Tên hạng phòng (`hotelName`: tên khách sạn cha)"),
            ("roomSizeM2", "int", "Diện tích hạng phòng (m²)"),
            ("maxOccupancy", "int", "Sức chứa tối đa của hạng phòng"),
            ("bed", "string", "Loại giường, chuỗi tự do của nguồn"),
            ("familyFriendly", "bool", "Suy ra từ tên, mô tả và tiện ích"),
            ("oceanView", "bool", "Suy ra từ tên, mô tả và tiện ích"),
            ("openingHours", "string", "Giờ mở cửa"),
            ("durationMinutes", "int", "Thời lượng tham quan đề xuất, hoặc thời gian bay, quy về phút"),
            ("venue", "string", "Địa điểm sử dụng vé, tra trong `collectors/venues.csv`"),
            ("ticketed", "bool", "`true` = trip.com có hiện giá vé. **Vắng mặt = chưa rõ**: trip.com không hiện giá KHÔNG có nghĩa là miễn phí hay không bán vé"),
            ("audience", "array", "Đối tượng phù hợp do nguồn gắn nhãn"),
            ("tags", "array", "Nhãn loại hình của điểm tham quan trip.com"),
        ]),
        ("3.6 Đánh giá — không có dữ liệu cá nhân", "", [
            ("reviewScore", "number", "Điểm trung bình (`reviewScoreScale`: thang 10 hoặc 5)"),
            ("reviewCount", "int", "Số lượt đánh giá"),
            ("tripAdvisorRating", "number", "Điểm TripAdvisor do vinpearl.com công bố (`tripAdvisorReviewCount`)"),
        ]),
        ("3.7 Vé máy bay", "", [
            ("originCity", "string", "Thành phố đi (`destinationCity`: thành phố đến)"),
            ("originDestination", "string", "Nhãn điểm đến của đầu đi, để lọc theo cặp điểm đến"),
            ("destinationAirportName", "string", "Tên sân bay đến"),
            ("originLatitude", "number", "Toạ độ sân bay đi (`latitude`/`longitude` là sân bay đến)"),
            ("airline", "string", "Hãng bay của chuyến (`airlines`: các hãng của tuyến)"),
            ("flightNumber", "string", "Số hiệu chuyến bay"),
            ("departureTimeLocal", "string HH:MM", "Giờ cất cánh **theo giờ Việt Nam** (`arrivalTimeLocal`: giờ hạ cánh)"),
            ("departureAt", "datetime", "Thời điểm cất cánh của chuyến rẻ nhất đã thấy, kèm múi giờ `+07:00` (`arrivalAt`: hạ cánh)"),
            ("datesSeen", "array", "Các ngày bay (giờ VN) mà trip.com liệt kê chuyến này; `availableFrom/To` là ngày nhỏ nhất/lớn nhất trong đây"),
            ("monthlyPrices", "object", "Tuyến: giá trung bình một chiều theo tháng"),
            ("roundTripFrom", "number", "Tuyến: giá khứ hồi rẻ nhất"),
        ]),
    ]
    attr_md = []
    for title, _, spec in attr_groups:
        body = []
        for key, typ, meaning in spec:
            c = cov(key)
            if c:
                body.append([f"`{key}`", typ, pct(c, n), meaning])
        attr_md.append(f"### {title}\n\n" + table(["Khoá", "Kiểu", "Độ phủ", "Ý nghĩa"], body))
    loc_src = collections.Counter(A(o).get("locationSource") for o in rows)
    loc_prec = collections.Counter(A(o).get("locationPrecision") for o in rows)
    star_dist = collections.Counter(int(A(o)["starRating"]) for o in rows if A(o).get("starRating") is not None)
    star_type = collections.Counter(A(o).get("starRatingType") or "không ghi loại" for o in rows if A(o).get("starRating") is not None)
    airline_n = collections.Counter(A(o).get("airline") for o in flights)

    var_desc = {
        "hotel_property": "Cơ sở lưu trú", "hotel_room": "Hạng phòng, luôn có `parentProductId`",
        "attraction": "Điểm tham quan và vé", "flight": "Chuyến bay cụ thể, có `parentProductId` trỏ về tuyến",
        "flight_route": "Tuyến bay giữa hai thành phố", "combo": "Combo nghỉ dưỡng và vé vui chơi", "golf": "Voucher / sân golf",
    }
    var_rows = []
    for v in ("hotel_property", "hotel_room", "attraction", "flight", "flight_route", "combo", "golf"):
        items = by_var.get(v, [])
        if not items:
            continue
        lvl = v.split("/")[1] if "/" in v else "–"
        extra = var_desc[v]
        by_src = collections.Counter(src(o) for o in items)
        if v == "hotel_property":
            extra += f". {vn(props_with_rooms)} cái có hạng phòng đi kèm (trung bình {vn(len(rooms) / max(1, props_with_rooms), 1)} hạng)"
        elif v in ("attraction", "combo", "golf"):
            extra += ": " + " · ".join(f"{vn(c)} từ {s}" for s, c in by_src.most_common())
            n_unpriced = sum(1 for o in items if o["unitPrice"] is None and o["sourceRef"].startswith("trip:attraction:"))
            if n_unpriced:
                extra += f" · {vn(n_unpriced)} điểm trip.com chưa có giá"
        var_rows.append([f"`{v}`", vn(len(items)), f"`{lvl}`" if lvl != "–" else "–", extra])

    ds = collections.Counter(A(o)["descriptionSource"] for o in derived)
    ds_meaning = (("thông tin phòng + mô tả khách sạn", "Hạng phòng OTA"), ("dữ liệu chuyến bay", "Chặng bay, hãng, giờ bay, giá"),
                  ("loại hình, địa chỉ", "Điểm tham quan thiếu phần giới thiệu"), ("mô tả gốc quá ngắn, bổ sung từ thông tin vé", "Vé Vinpearl"),
                  ("tên vé, thời lượng", "Vé Vinpearl không có phần giới thiệu"), ("dựng tiếng Việt", "Nguồn chỉ có mô tả tiếng Anh; bản gốc ở `descriptionOriginal`"),
                  ("thông tin phòng (mô tả gốc quá ngắn)", "Hạng phòng Vinpearl"))
    ds_rows = [[f"`{k}`", vn(c), next((m for kw, m in ds_meaning if kw in k), "")] for k, c in ds.most_common()]
    len_by_tax = " · ".join(f"{t} {vn(med_len([o for o in rows if o['taxonomy'] == t]))}" for t in ("hotel", "golf", "combo", "attraction", "flight")
                            if any(o["taxonomy"] == t for o in rows))

    def amen(o: dict, kws: tuple[str, ...]) -> bool:
        text = fold(" ".join(A(o).get("amenities") or []))
        return any(k in text for k in kws)

    api_keys = [
        ("wifi", ("wi-fi", "wifi", "internet"), "`amenities` khớp `wi-fi`, `wifi`, `internet`"),
        ("pool", ("ho boi", "be boi", "pool"), "`amenities` khớp `hồ bơi`, `bể bơi`, `pool`"),
        ("freeBreakfast", ("bua sang", "breakfast"), "`amenities` khớp `bữa sáng`, `breakfast` — **cần loại mục ghi có phí**"),
        ("spa", ("spa", "massage"), "`amenities` khớp `spa`, `massage`"),
        ("parking", ("cho do xe", "bai do xe", "parking"), "`amenities` khớp `chỗ đỗ xe`, `bãi đỗ xe`, `parking`"),
        ("shuttle", ("dua don", "shuttle"), "`amenities` khớp `đưa đón`, `shuttle`"),
        ("nearBeach", ("gan bien", "sat bien", "bai bien", "beachfront"), "`amenities` khớp `gần biển`, `sát biển`, `bãi biển`, `beachfront`"),
        ("privateBeach", ("bai bien rieng", "private beach"), "`amenities` khớp `bãi biển riêng`, `private beach`"),
        ("kidsClub", ("cau lac bo tre em", "kids club"), "`amenities` khớp `câu lạc bộ trẻ em`, `kids club`"),
    ]
    api_rows = [["`starRating`", "`starRating` làm tròn xuống (4,5 sao → 4)", vn(cov("starRating"))],
                ["`oceanView`, `familyFriendly`", "cùng tên, khi là `true`",
                 f"{vn(sum(1 for o in rows if A(o).get('oceanView') is True))}, {vn(sum(1 for o in rows if A(o).get('familyFriendly') is True))}"],
                ["`directFlight`", "`nonstop = true`", vn(sum(1 for o in rows if A(o).get("nonstop") is True))]]
    api_rows += [[f"`{k}`", meaning, vn(sum(1 for o in rows if amen(o, kws)))] for k, kws, meaning in api_keys]
    api_rows.append(["`kidsPool`, `nearCenter`, `baggage`, `indoor`, `outdoor`, `waterPark`, `show`, `buffet`, `seaside`, `caddie`", "chưa có nguồn", "0"])
    score10 = sum(1 for o in rows if has(A(o).get("reviewScore")) and A(o).get("reviewScoreScale") == 10)
    score_any = cov("reviewScore")
    ta = cov("tripAdvisorRating")
    count_no_score = sum(1 for o in rows if has(A(o).get("reviewCount")) and not has(A(o).get("reviewScore")) and not has(A(o).get("tripAdvisorRating")))
    null_hotels = sum(1 for o in hotel_rows if not (o["availableFrom"] or o["availableTo"]))
    null_attr = sum(1 for o in by_var["attraction"] if not (o["availableFrom"] or o["availableTo"]))
    null_golf = sum(1 for o in by_var["golf"] if not (o["availableFrom"] or o["availableTo"]))
    null_combo = sum(1 for o in by_var["combo"] if not (o["availableFrom"] or o["availableTo"]))
    null_flight = sum(1 for o in flights + routes if not (o["availableFrom"] or o["availableTo"]))

    schema_md = f"""# Schema catalog du lịch V-OTA

Tài liệu tham chiếu cho `products.jsonl` · {vn(n)} sản phẩm · bản {day} · **sinh tự động bởi `make_docs.py`, không sửa tay**

Bản máy đọc được, liệt kê **mọi** khoá `attributes` theo từng loại kèm độ phủ: **`template.json`** cùng thư mục
(sinh lại bằng `python make_template.py`). Tài liệu này giải thích các khoá quan trọng; `template.json` là danh
sách đầy đủ. Bản ghi thật để đọc và chạy thử: **`sample/`**.

---

## 1. Nguyên tắc

- Mỗi dòng của `products.jsonl` là **một sản phẩm**, gồm **đúng 13 trường** của CDP V-OTA theo §6 handbook.
- Mọi thông tin khác nằm trong `attributes`. Cố ý như vậy: thêm field cấp cao nhất mà CDP thật không có
  sẽ thành cái bẫy cho người tích hợp về sau.
- `products.csv` là cùng dữ liệu ở dạng bảng, chỉ để mở xem. **Khi viết code, đọc `products.jsonl`.**
- {vn(vi)}/{vn(n)} mô tả được nhận diện là tiếng Việt; {vn(sum(1 for o in rows if o['currency'] == 'VND'))}/{vn(n)} giá là VND; {vn(coords)}/{vn(n)} sản phẩm có toạ độ.
- Toàn bộ là dữ liệu quan sát được từ nguồn (Vinpearl, booking.com, agoda.com, trip.com, OurAirports, OpenStreetMap),
  **không có giá trị sinh ngẫu nhiên**. Phần *suy ra* (vd. `familyFriendly`, mô tả tự sinh) đều có nhãn ở `attributes`.

```python
import json
products = [json.loads(line) for line in open("products.jsonl", encoding="utf-8")]
```

## 2. Mười ba trường cấp cao nhất

{table(["Trường", "Kiểu", "Độ phủ", "Ý nghĩa"], field_rows)}

### Bốn chỗ dễ hiểu sai

1. **`available = true` không phải là còn phòng.** Nó chỉ nói nguồn có trả giá lúc crawl (điểm tham quan trip.com chưa có giá cũng được đánh dấu `true` để dùng trong demo; {observed[0][8:]}/{observed[0][5:7]}–{observed[-1][8:]}/{observed[-1][5:7]}/{observed[-1][:4]}).
   Với vé máy bay: trip.com liệt kê chuyến này kèm giá ở các ngày trong `datesSeen`. Luồng đặt chỗ thật phải gọi lại nguồn.
2. **`unitPrice = null` không phải là miễn phí.** {vn(len(unpriced))} sản phẩm còn `null`; {vn(len(unpriced_trip))} là điểm trip.com (tham quan, golf)
   không hiện giá — **chưa rõ có bán vé hay không** (`attributes.ticketed` vắng mặt). Web cần trạng thái hiển thị riêng, không quy về 0 đồng.
3. **Giá là một lần hỏi giá tại một thời điểm.** Khách sạn: nhận phòng {main_price_date}, 1 đêm, 2 người lớn ({vn(main_price_n)} sản phẩm{('; ngày khác: ' + ', '.join(other_price_dates)) if other_price_dates else ''}). Vé máy bay: giá tham khảo theo ngày trip.com liệt kê. Đọc `priceDate` / `datesSeen` thay vì giả định.
4. **`destination` ≠ `province`.** `destination` là nhãn du lịch dùng để lọc và gợi ý (Hội An, Sa Pa);
   `attributes.province` là đơn vị hành chính (Quảng Nam, Lào Cai).

## 3. `attributes` theo nhóm

Độ phủ tính trên toàn bộ {vn(n)} sản phẩm. Chỉ liệt kê khoá quan trọng và có mặt trong catalog; đầy đủ ở `template.json`.

{(chr(10) * 2).join(attr_md)}

**Nguồn toạ độ** (`locationSource`): {" · ".join(f"`{k}` {vn(v)}" for k, v in loc_src.most_common())}.
**Độ chính xác** (`locationPrecision`): {" · ".join(f"`{k}` {vn(v)}" for k, v in loc_prec.most_common())}.
`venue` nghĩa là vé dùng chung toạ độ của khu vui chơi, không phải vị trí riêng — đúng bản chất của vé vào cửa.
{vn(manual_coords)} toạ độ `manual` được xác minh tay, ghi nguồn trong `collectors/venues.csv` và `collectors/location_overrides.csv`.

**Hạng sao** (`starRating`): {" · ".join(f"{k} sao {vn(v)}" for k, v in sorted(star_dist.items(), reverse=True))}; `starRatingType`: {" · ".join(f"`{k}` {vn(v)}" for k, v in star_type.most_common())}.
**Hãng bay** (chuyến): {" · ".join(f"{k} {vn(v)}" for k, v in airline_n.most_common())}.
**Không có nội dung review, tên hay ảnh người đánh giá** trong catalog; chỉ giữ chỉ số tổng hợp (theo §3 handbook).

## 4. Các biến thể sản phẩm

{table(["Biến thể", "Số lượng", "`level`", "Đặc điểm"], var_rows)}

## 5. Mô tả tự sinh — đọc trước khi làm text builder

**{vn(len(derived))}/{vn(n)} mô tả ({pct(len(derived), n, 1)}) là tự sinh** từ dữ liệu có cấu trúc của nguồn (không bịa), không phải văn bản gốc.
Nhận biết bằng `attributes.descriptionSource`:

{table(["Giá trị `descriptionSource`", "Số lượng", "Dựng từ gì"], ds_rows)}

Câu mô tả khách sạn và câu mô tả vé máy bay **không nên xây theo cùng một cách** — chúng có cấu trúc khác
hẳn nhau, và điều này ảnh hưởng tới chất lượng embedding nhiều hơn cả việc chọn mô hình.
Hạng phòng cùng khách sạn có mô tả gần trùng nhau (đều ghép từ mô tả khách sạn): khi tìm kiếm nên gom kết quả theo `parentProductId`.

Độ dài mô tả trung vị theo loại (ký tự): {len_by_tax}.

## 6. Nguồn của từng trường

{table(["Trường", "Thứ tự ưu tiên", "Lý do"], [
    ["`name`, `description`", "vinpearl.com → booking.com (nếu tiếng Việt) → agoda.com", "Mô tả Vinpearl là đầu vào embedding tốt nhất"],
    ["`unitPrice`, `available`", "booking.com → agoda.com → vinpearl.com; vé máy bay và điểm tham quan: trip.com → Vinpearl", "OTA sát thực tế hơn về giá và tình trạng còn chỗ"],
    ["`availableFrom`, `availableTo`", "Vinpearl `saleStartDate`/`saleEndDate`; vé máy bay: min/max `datesSeen`", "Chỉ điền khi nguồn có bằng chứng; không sinh ngày"],
    ["toạ độ", f"Nguồn chính → OpenStreetMap; sân bay từ OurAirports; {vn(manual_coords)} điểm xác minh tay", ""],
    ["hạng sao, tiện ích", "Nguồn chính, thiếu thì nguồn khác bù", ""]])}

Mỗi sản phẩm mang `attributes.fieldSources` nên truy nguồn được từng giá trị.
Sản phẩm trùng giữa các nguồn đã gộp: {vn(dedup)} dòng trong `dedup_report.csv`.
Theo nguồn chính của dòng: {" · ".join(f"{k} {vn(v)}" for k, v in sources.most_common())}.

Ngoài các quy tắc tự động, {vn(excluded_manual)} sản phẩm bị loại sau khi soát tay (`collectors/excluded_products.csv`), và các dòng lỗi dữ liệu
(toạ độ sai/thiếu, hạng phòng giá phi lý, mồ côi) bị xoá tự động, danh sách ở `data/excluded_location.csv`.

## 7. Bắt đầu nhanh

```python
import json
from collections import Counter

products = [json.loads(l) for l in open("products.jsonl", encoding="utf-8")]

# lọc theo điểm đến và loại
hotels = [p for p in products if p["taxonomy"] == "hotel"
          and p["attributes"].get("level") == "property"
          and p["destination"] == "Nha Trang"]

# hạng phòng của một khách sạn
rooms_of = {{}}
for p in products:
    parent = p["attributes"].get("parentProductId")
    if parent:
        rooms_of.setdefault(parent, []).append(p)

# văn bản để embedding: bỏ qua hay giữ mô tả tự sinh là quyết định của bạn
texts = [p["description"] for p in products if not p["attributes"].get("descriptionSource")]

print(Counter(p["taxonomy"] for p in products))
```

Bộ mẫu để chạy thử nhanh: `sample/products-sample.jsonl`, xem `sample/README.md`.

## 8. Quy đổi sang hợp đồng API

Catalog và CDP clone giữ dữ liệu **đúng như nguồn**. `ProductSummary` của hợp đồng Backend
(`docs/spec/hop-dong-tich-hop-backend.md` §2) có vài trường dữ liệu không có sẵn ở dạng đó; tầng API quy đổi theo
các quy tắc dưới đây. Số liệu tính trên {vn(n)} sản phẩm thật.

### 8.1 `rating` và `reviewCount`

Hợp đồng dùng thang 0–5, một chữ số thập phân; `reviewCount` là `null` khi `rating` là `null`.

{table(["Thứ tự", "Nguồn", "Có ở", "Quy đổi"], [
    ["1", "`reviewScore`, `reviewScoreScale`", f"{vn(score_any)} sản phẩm ({vn(score10)} thang 10)", "`rating = round(reviewScore / reviewScoreScale × 5, 1)`, `reviewCount = reviewCount`"],
    ["2", "`tripAdvisorRating`, `tripAdvisorReviewCount`", f"{vn(ta)} khách sạn Vinpearl, thang 5", "giữ nguyên"],
    ["—", "không có điểm", "còn lại", f"`rating = null`, `reviewCount = null` — kể cả {vn(count_no_score)} sản phẩm có `reviewCount` mà không có điểm"]])}

### 8.2 `attributes`

Hợp đồng chỉ nhận một bộ khoá cố định, giá trị là `true` hoặc vắng mặt, riêng `starRating` là số nguyên. API
**chỉ trả các khoá trong bảng này**; mọi khoá khác trong `attributes` của catalog (mảng `amenities`, `nonstop: false`…) không đi ra ngoài.

{table(["Khoá hợp đồng", "Lấy từ", "Số sản phẩm"], api_rows)}

So khớp trên chuỗi đã bỏ dấu và viết thường. Đây là suy luận từ từ khoá, không phải dữ liệu nguồn gắn nhãn sẵn.

### 8.3 `availableFrom`, `availableTo`

Hợp đồng bắt buộc cả hai để kiểm tra `DATE_OUT_OF_RANGE`. Hiện có {vn(len(with_range))}/{vn(n)} sản phẩm có giá trị
({" · ".join(f"{k} {vn(v)}" for k, v in range_src.most_common())}). **Không có** ở {vn(null_hotels)} khách sạn/hạng phòng, {vn(null_attr)} điểm tham quan,
{vn(null_combo)} combo, {vn(null_golf)} sân golf, {vn(null_flight)} vé máy bay. Nguồn không công bố khoảng bán cho khách sạn và điểm trip.com,
nên không có giá trị đúng để điền — catalog để `null` thay vì bịa.
Đề xuất cho Backend: khi `null`, dùng cửa sổ đặt chỗ cấu hình được, từ hôm nay đến hôm nay + N ngày, và ghi rõ đây là giả định của bản demo.
Lưu ý khoảng của vé/combo/golf Vinpearl là **thời gian bán**, có thể hết hạn sớm hơn ngày demo: lọc `availableTo >= hôm nay`.
Khoảng của vé máy bay là **các ngày bay trip.com đã liệt kê** (cửa sổ quan sát), không phải lịch khai thác đầy đủ.

### 8.4 `unitPrice`

Hợp đồng ghi `unitPrice` bắt buộc là số nguyên, nhưng {vn(len(unpriced))} sản phẩm có `unitPrice = null` ({vn(len(unpriced_trip))} là điểm trip.com
không hiện giá, chưa rõ có bán vé không). Cần Backend chọn: cho phép `null` trong hợp đồng và hiển thị "chưa có giá", hoặc không trả các sản phẩm này ra API.
"""
    (d / "SCHEMA.md").write_text(schema_md, encoding="utf-8")

    # ================================================================ BANGIAO.md
    cov_rows = []
    for v in ("hotel_property", "hotel_room", "attraction", "flight", "flight_route", "combo", "golf"):
        items = [o for o in rows if (variant(o) == v or (v == "flight" and o["taxonomy"] == "flight"))]
        if not items:
            continue
        m = len(items)
        p_ok = sum(1 for o in items if o["unitPrice"] is not None)
        img = sum(1 for o in items if o["imageUrl"])
        d200 = sum(1 for o in items if len(o["description"] or "") >= 200)
        star = sum(1 for o in items if any(A(o).get(k) is not None for k in (
            "starRating", "reviewScore", "rating", "tripRating", "bookingReviewScore", "agodaReviewScore", "tripAdvisorRating")))
        oh = sum(1 for o in items if has(A(o).get("openingHours")))
        cov_rows.append([v, vn(m), pct(p_ok, m), "**" + pct(img, m) + "**" if img == 0 else pct(img, m), pct(d200, m),
                         pct(star, m) if v not in ("flight",) else "–", pct(sum(1 for o in items if A(o).get("latitude") is not None), m),
                         pct(oh, m) if v in ("attraction", "combo", "golf") else "–"])
    att_all = by_var["attraction"] + by_var["combo"]
    open_att = sum(1 for o in by_var["attraction"] if has(A(o).get("openingHours")))
    open_combo = sum(1 for o in by_var["combo"] if has(A(o).get("openingHours")))
    dur_att = sum(1 for o in by_var["attraction"] if has(A(o).get("durationMinutes")))
    venue_n = sum(1 for o in rows if A(o).get("locationPrecision") == "venue")
    warn_n = sum(1 for o in rows if A(o).get("locationWarning"))
    imgs_n = cov("images")
    imgs_med = int(statistics.median(len(A(o)["images"]) for o in rows if has(A(o).get("images")))) if imgs_n else 0
    places = 0
    gj = d / "map" / "places.geojson"
    if gj.exists():
        try:
            places = len(json.load(open(gj, encoding="utf-8")).get("features", []))
        except (ValueError, OSError):
            places = 0
    tax_n = collections.Counter(o["taxonomy"] for o in rows)
    no_flight = sorted({o["destination"] for o in props} - {o["destination"] for o in routes})
    dest_flight = {o["destination"] for o in routes}
    hotel_dest = collections.Counter(o["destination"] for o in props)
    hotel_dest_set = set(hotel_dest)

    bangiao = f"""# Bàn giao catalog du lịch V-OTA — {day}

Dữ liệu sản phẩm du lịch thật, thu thập theo §3 handbook RecSys internship v3. Người thu thập: mảng Data.
**Sinh tự động bởi `make_docs.py`, không sửa tay.** Giá quan sát {observed[0][8:]}/{observed[0][5:7]}–{observed[-1][8:]}/{observed[-1][5:7]}/{observed[-1][:4]}.

## 1. Đọc gì trước

{table(["Nếu bạn định…", "Đọc file này"], [
    ["Viết code đọc catalog", "**`SCHEMA.md`** — 13 trường, toàn bộ `attributes`, ngữ nghĩa và bẫy thường gặp"],
    ["Thử nhanh không muốn tải cả catalog", "**`sample/`** — bộ mẫu, liên kết cha–con toàn vẹn, có README riêng"],
    ["Tra một khoá cụ thể bằng code", "**`template.json`** — bản máy đọc được, mọi khoá `attributes` theo loại kèm độ phủ"],
    ["Biết dữ liệu tới đâu, thiếu gì", "**`stats.md`** (thống kê) và `quality_review.csv` (danh sách cần soát)"]])}

## 2. Gói này có gì

{table(["File", "Nội dung"], [
    ["`products.jsonl`", f"**Bản chuẩn.** {vn(n)} sản phẩm, mỗi dòng 1 JSON đúng 13 trường §6"],
    ["`products.csv`, `products.json`", "Cùng dữ liệu ở dạng bảng / mảng JSON, để mở xem. Khi viết code đọc JSONL"],
    ["`catalog/*.json`", "Tách theo loại (hotel, flight, attraction, combo, golf)"],
    ["`SCHEMA.md`, `template.json`", "Schema dạng người đọc và dạng máy đọc"],
    ["`sample/`", "Bộ mẫu chạy thử, liên kết cha–con toàn vẹn"],
    ["`combo_items.jsonl`/`.csv`, `combo_items_review.csv`, `combo_attributes.json`", "Thành phần của combo (parse từ tên + mô tả bằng `parse_combos.py`) và `priceBasis`; để loader nạp vào `catalog.combo_items`. `products.jsonl` không đổi"],
    ["`map/`", "Ghim bản đồ: CSV cho Google My Maps + `places.geojson`"],
    ["`stats.md`, `quality_review.csv`, `dedup_report.csv`", "Thống kê, danh sách cần soát, các cặp trùng đã gộp"],
    ["`excluded_location.csv`, `excluded_auto.csv`", "Dòng đã xoá vì lỗi dữ liệu / không phải điểm du lịch, để truy vết"]])}

```python
import pandas as pd
df = pd.read_json("products.jsonl", lines=True)
```

## 3. Số liệu nhanh

- **{vn(n)} sản phẩm** · {vn(dest_n)} điểm đến có dữ liệu · {vn(len(props))} khách sạn riêng biệt (+ {vn(len(rooms))} hạng phòng)
- Theo loại: {" · ".join(f"{k} {vn(v)}" for k, v in tax_n.most_common())} (vé máy bay: {vn(len(routes))} tuyến + {vn(len(flights))} chuyến)
- Theo nguồn chính: {" · ".join(f"{k} {vn(v)}" for k, v in sources.most_common())}
- **{pct(vi, n)} mô tả tiếng Việt · {pct(coords, n)} có toạ độ** · {pct(len(priced), n, 1)} có giá · {pct(with_img, n, 1)} có ảnh (vé máy bay không có ảnh)
- {vn(avail)}/{vn(n)} đánh dấu `available` ({pct(avail, n, 1)}); {vn(len(with_range))} có `availableFrom/To`

Catalog chỉ giữ sản phẩm hoàn chỉnh: sản phẩm mà nguồn không cung cấp được giá, dòng có toạ độ sai/thiếu và hạng phòng giá phi lý
đã bị loại, ghi rõ trong mục "Bị loại" của `stats.md`.

## 4. Những điều phải biết trước khi dùng

1. **`available = true` không phải là còn phòng/vé/chỗ.** Nó chỉ nói nguồn có trả giá lúc crawl (riêng điểm tham quan trip.com chưa có giá cũng là `true`, để dùng trong demo). Đừng hiển thị như xác nhận đặt được; luồng đặt thật phải gọi lại nguồn.
2. **`unitPrice = null` không phải là miễn phí.** {vn(len(unpriced))} sản phẩm còn `null`, {vn(len(unpriced_trip))} là điểm tham quan trip.com không hiện giá
   (chưa rõ có bán vé không). Web cần trạng thái hiển thị riêng, không quy về 0 đồng.
3. **{pct(len(derived), n, 1)} mô tả là tự sinh** từ dữ liệu có cấu trúc, nhận biết qua `attributes.descriptionSource`. Điều khoản vé đã được tách khỏi `description` sang `attributes.policies`.
4. **Giá là một lần hỏi giá:** khách sạn nhận phòng {main_price_date}, 1 đêm, 2 người lớn; sau ngày đó giá là của quá khứ. Vé máy bay là giá tham khảo theo ngày bay trip.com liệt kê.
5. **`availableFrom/To` chỉ có ở {vn(len(with_range))} sản phẩm** (vé/combo/golf Vinpearl = thời gian bán, vé máy bay = các ngày bay đã liệt kê). Khách sạn và điểm trip.com để `null` vì nguồn không công bố.
   Giờ bay (`departureTimeLocal`) là **giờ Việt Nam**.

## 5. Độ phủ từng trường — đọc trước khi code

{table(["Loại", "n", "có giá", "ảnh", "mô tả ≥200 ký tự", "sao/điểm", "toạ độ", "giờ mở cửa"], cov_rows)}

Chỗ dưới 100% đều thuộc về bản chất dữ liệu: điểm tham quan thiếu giá là điểm trip.com không hiện giá; vé máy bay không có ảnh vì một chuyến bay không có ảnh sản phẩm.

## 6. Ghi chú theo đội

**Web** — `imageUrl` phủ {pct(with_img, n, 1)}; chỉ {vn(len(flights) + len(routes))} vé máy bay không có ảnh (dùng placeholder hoặc logo hãng qua `airlineCode`/`airlines`).
Cần trạng thái hiển thị riêng cho {vn(len(unpriced_trip))} điểm chưa có giá so với sản phẩm có giá — đừng quy về 0 đồng. Ảnh phụ nằm trong `attributes.images` ({vn(imgs_n)} sản phẩm, trung vị {imgs_med} ảnh).

**Agent (trợ lý lịch trình)** — `products.jsonl` có `latitude`/`longitude` cho {pct(coords, n)} sản phẩm, dùng thẳng là đủ.
`map/places.geojson` là bản gom theo địa điểm ({vn(places)} điểm thay vì {vn(n)} sản phẩm, mỗi điểm kèm `items` có `productId`).
`openingHours` chỉ có ở {pct(open_att, len(by_var['attraction']))} điểm tham quan và {pct(open_combo, len(by_var['combo']))} combo, `durationMinutes` {pct(dur_att, len(by_var['attraction']))} điểm tham quan
→ chưa đủ xếp lịch theo giờ cho mọi sản phẩm. `locationPrecision = venue` ({vn(venue_n)} sản phẩm) là vị trí khu vui chơi chứ không phải vị trí riêng của vé.
Còn {vn(warn_n)} sản phẩm mang `locationWarning` (Vinpearl được giữ), xem `quality_review.csv`.

**RecSys** — {vn(len(derived))} mô tả tự sinh; kiểm tra `attributes.descriptionSource` trước khi đưa vào text builder. Câu mô tả khách sạn và câu mô tả vé máy bay không nên xây cùng một cách.
Hạng phòng cùng khách sạn có mô tả gần trùng nhau: nên gom kết quả theo `parentProductId` (hoặc embed cấp khách sạn) để top-k không bị một khách sạn chiếm hết.
Toàn bộ catalog là tiếng Việt, nên `all-MiniLM-L6-v2` — mô hình chỉ hỗ trợ tiếng Anh mà mọi tutorial đều dùng — sẽ cho kết quả gần như ngẫu nhiên; cần mô hình đa ngôn ngữ.
**Gợi ý chéo danh mục:** {vn(len(hotel_dest_set & dest_flight))}/{vn(len(hotel_dest_set))} điểm đến có khách sạn có tuyến bay *đến* nó. Điểm đến có khách sạn nhưng không có sân bay riêng
({", ".join(f"{k} ({vn(hotel_dest[k])})" for k in no_flight if hotel_dest[k] >= 20)}) cần ánh xạ sang sân bay gần nhất khi gợi ý vé máy bay.

## 7. Pháp lý và dữ liệu cá nhân

- **Không có dữ liệu cá nhân.** Review, tên và ảnh người đánh giá bị xoá trước khi ghi đĩa. Chỉ giữ điểm trung bình và số lượt.
- Điều khoản booking.com và agoda.com không cho phép thu thập tự động. **Dữ liệu chỉ dùng nội bộ cho demo thực tập, không phân phối lại, không đưa lên repo hay trang công khai.**
- Toạ độ OpenStreetMap theo giấy phép ODbL: khi hiển thị bản đồ phải ghi "© OpenStreetMap contributors". Toạ độ sân bay từ OurAirports (public domain).
- Không ghi gì vào CDP hay Insider production.

## 8. Tái tạo bộ dữ liệu

Code và hướng dẫn đầy đủ: `src/data_collection/README.md` trong monorepo. Sau khi cào xong và dừng các tiến trình cào, chạy một lệnh:

```
./finalize_catalog.sh     # sao lưu → gộp batch → chuẩn hoá → catalog → template.json + sample/ + SCHEMA.md + BANGIAO.md
```

Kiểm tra hồi quy: `python -m unittest discover -s . -p "test_*.py"` (không cần mạng).
"""
    (d / "BANGIAO.md").write_text(bangiao, encoding="utf-8")

    # ================================================================ sample/README.md
    sample_path = d / "sample" / "products-sample.jsonl"
    if sample_path.exists():
        sample = [json.loads(l) for l in open(sample_path, encoding="utf-8")]
        sv = collections.Counter(variant(o) for o in sample)
        size = lambda p: f"{p.stat().st_size // 1024} KB"  # noqa: E731
        csv_path = d / "sample" / "products-sample.csv"
        parents_ok = all(A(o).get("parentProductId") in {x["productId"] for x in sample} for o in sample if A(o).get("parentProductId"))
        unpriced_s = [o for o in sample if o["unitPrice"] is None]
        readme = f"""# Bộ dữ liệu mẫu — {len(sample)} sản phẩm

Cắt ra từ catalog đầy đủ {vn(n)} sản phẩm để chạy thử nhanh. Cùng schema, cùng giá trị thật — không phải dữ liệu giả.
**Sinh tự động bởi `make_sample.py` + `make_docs.py`.**

{table(["File", "Kích thước", "Dùng khi nào"], [
    ["`products-sample.jsonl`", size(sample_path), "Viết code. Đầy đủ 13 trường và toàn bộ `attributes`"],
    ["`products-sample.csv`", size(csv_path) if csv_path.exists() else "–", "Mở xem bằng Excel/Sheets. Chỉ có các trường hay dùng, đã làm phẳng"]])}

## Mẫu này phủ những gì

{len(sample)} sản phẩm trên {len({o['destination'] for o in sample})} điểm đến, đủ **{len(sv)} biến thể**:

{table(["Biến thể", "Số lượng"], [[f"`{k}`", v] for k, v in sorted(sv.items())])}

Và các trường hợp đặc biệt mà code của bạn cần xử lý đúng:

- **Liên kết cha–con {'toàn vẹn' if parents_ok else 'CHƯA toàn vẹn'}**: mọi hạng phòng đều có khách sạn cha trong mẫu, mọi chuyến bay đều có tuyến cha, nên thử `parentProductId` được ngay.
- **{len(unpriced_s)} sản phẩm không có giá** — `unitPrice = null` nghĩa là *chưa có giá* (trip.com không hiện giá, chưa rõ có bán vé không), không phải miễn phí.
- Vé có giá theo hạng thành viên (`memberPrices`), sản phẩm có điều khoản tách riêng (`policies`), sản phẩm có mô tả gốc tiếng Anh (`descriptionOriginal`).
- Vé máy bay có `availableFrom/To` (các ngày bay trip.com liệt kê) và giờ bay theo giờ Việt Nam.

```python
import json
sample = [json.loads(l) for l in open("products-sample.jsonl", encoding="utf-8")]
```
"""
        (d / "sample" / "README.md").write_text(readme, encoding="utf-8")

    print(f"đã ghi {d}/SCHEMA.md, {d}/BANGIAO.md" + (f", {d}/sample/README.md" if sample_path.exists() else ""))


if __name__ == "__main__":
    main()
