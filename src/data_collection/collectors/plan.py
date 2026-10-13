"""Kế hoạch thu thập theo handbook §3: 2.000–5.000 sản phẩm, 10–15 điểm đến, đủ hotel/flight/attraction/combo.

Chọn điểm đến có Vinpearl trước, rồi thêm các điểm du lịch lớn. Slug/mã từng nguồn đã được kiểm tra thủ công
(15/09/2026); nếu website đổi URL, sửa ở đây.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Destination:
    name: str                        # tên chuẩn, trùng với geo.py
    booking_query: str               # ô tìm kiếm booking.com
    agoda_city: str | None           # https://www.agoda.com/vi-vn/city/<slug>.html
    trip_city: str | None            # https://vn.trip.com/travel-guide/attraction/<slug>/tourist-attractions/
    airports: tuple[str, ...] = ()   # IATA – trang https://vn.trip.com/flights/airport-<iata>/
    vinpearl: bool = False
    trip_hotel_city_id: str | None = None
    # ID thành phố nội bộ của trip.com (khác slug trip_city ở trên) — dùng cho CẢ /hotels/list?city=<id> lẫn
    # /packages/list?hCity=<id> (đã xác nhận cùng namespace: city=6942 vào /hotels/list trả về đúng Hải Phòng,
    # và hCity=6942 trên /packages/list cũng vậy — kiểm tra thật qua browser 23/09/2026).
    # Chỉ ghi ID ĐÃ KIỂM CHỨNG (mở /hotels/list?city=<id>&locale=vi-VN, xem tiêu đề trang khớp tên); không có thì
    # None, không đoán — đúng quy ước của agoda_city/trip_city ở trên. Dùng `trip-hotels --discover-city-ids` để
    # tìm thêm (collectors/trip_hotels.py), rồi dán tay vào đây.


# trip_city của Bạc Liêu, Tam Đảo, Cà Mau, Lạng Sơn, Sơn La, Bắc Ninh, Sóc Trăng thêm 12/10/2026 (mở
# vn.trip.com/travel-guide/attraction/<slug>/tourist-attractions/ bằng crawler, tiêu đề trang khớp tên). Cà Mau, Lạng Sơn,
# Sơn La, Bắc Ninh dùng mã cấp tỉnh vì mã thành phố (Cà Mau 24733, Lạng Sơn 1447671, Sơn La 24744, Bắc Ninh 1447661) chỉ có
# ở www.trip.com, vn.trip.com báo 404; Sóc Trăng dùng 2186660 (24740, 1524648 báo 404). Nhóm @extra giữ trip_city = None
# theo quy ước chỉ cào Booking; mã đã kiểm cho lượt cào tay: Sầm Sơn sam-son-1525754, Hà Tiên ha-tien-24758, Vân Đồn
# van-don-district-1542075, Lý Sơn ly-son-1526936; Tuyên Quang (chưa có trong kế hoạch) tuyen-quang-province-1524609.
# vn.trip.com báo 404 cho Côn Đảo 24761, Mộc Châu 1540494 / 2133290, Tuyên Quang 24760, Bảo Lộc 121753.
DESTINATIONS: tuple[Destination, ...] = (
    Destination("Nha Trang", "Nha Trang", "nha-trang-vn", "nha-trang-670", ("CXR",), vinpearl=True, trip_hotel_city_id="1777"),
    Destination("Phú Quốc", "Phu Quoc", "phu-quoc-island-vn", "phu-quoc-island-24779", ("PQC",), vinpearl=True, trip_hotel_city_id="5649"),
    # trip_city cũ "hoi-an-668" trả 404 (kiểm 19/09/2026) nên Hội An chưa từng có điểm tham quan Trip; Trip không có
    # trang danh sách riêng cho Hội An (không thấy trong dải ID Việt Nam 24722–24782). Tìm theo tên trên
    # /hotels/list cũng chỉ trả "Phố cổ Hội An" xếp dưới Đà Nẵng (kiểm 23/09/2026) — không có cityId khách sạn
    # riêng, để None thay vì đoán trùng cityId của Đà Nẵng (sẽ gán nhầm khách sạn Đà Nẵng vào điểm đến này).
    Destination("Hội An", "Hoi An", "hoi-an-vn", None, (), vinpearl=True),                # bay tới Đà Nẵng
    Destination("Đà Nẵng", "Da Nang", "da-nang-vn", "da-nang-669", ("DAD",), trip_hotel_city_id="1356"),
    Destination("Hạ Long", "Ha Long", "h-long-vn", "ha-long-city-1524623", ("VDO",), vinpearl=True, trip_hotel_city_id="1390"),
    Destination("Hà Nội", "Hanoi", "hanoi-vn", "hanoi-181", ("HAN",), vinpearl=True, trip_hotel_city_id="286"),
    Destination("TP. Hồ Chí Minh", "Ho Chi Minh City", "ho-chi-minh-city-vn", "ho-chi-minh-city-434", ("SGN",), trip_hotel_city_id="301"),
    Destination("Hải Phòng", "Hai Phong", "haiphong-vn", "haiphong-180", ("HPH",), vinpearl=True, trip_hotel_city_id="6942"),
    Destination("Nghệ An", "Cua Lo", "vinh-vn", "vinh-city-24768", ("VII",), vinpearl=True),
    Destination("Hà Tĩnh", "Ha Tinh", "ha-tinh-vn", None, (), vinpearl=True),                # bay tới Vinh
    Destination("Đà Lạt", "Da Lat", "dalat-vn", "dalat-1393", ("DLI",), trip_hotel_city_id="5204"),
    Destination("Huế", "Hue", "hue-vn", "hue-667", ("HUI",), trip_hotel_city_id="1776"),
    Destination("Quy Nhơn", "Quy Nhon", "quy-nhon-binh-dinh-vn", "quy-nhon-24728", ("UIH",), trip_hotel_city_id="6172"),
    Destination("Sa Pa", "Sa Pa", "sapa-vn", "sapa-24736", ()),
    Destination("Phan Thiết", "Mui Ne", "phan-thiet-vn", "phan-thiet-1218", (), trip_hotel_city_id="4134"),
    # ---- Mở rộng 19/09/2026 (33 điểm đến, nhóm `@new`). Chỉ ghi ID/slug ĐÃ KIỂM CHỨNG; không có thì None, không đoán.
    #   agoda_city: trang https://www.agoda.com/vi-vn/city/<slug>.html trả 200 (hoặc 301 sang slug chuẩn); slug lạ bị
    #               chuyển 302 sang pagenotfound. Pleiku/Phan Rang chỉ có trang "region" nên bỏ.
    #   trip_city : https://vn.trip.com/travel-guide/attraction/<slug>-<id>/tourist-attractions/ trả 200, tên trong
    #               tiêu đề khớp (quét ID 24700–24800). Slug tuỳ ý, ID mới quyết định.
    #   airports  : chỉ sân bay nằm trong địa phương đó, không gán sân bay "gần nhất".
    Destination("Ninh Bình", "Ninh Binh", "ninh-binh-vn", None, ()),
    Destination("Vũng Tàu", "Vung Tau", "vung-tau-vn", None, ()),
    Destination("Côn Đảo", "Con Dao", "con-o-islands-vn", None, ("VCS",)),
    Destination("Cần Thơ", "Can Tho", "c-n-tho-vn", "can-tho-24737", ("VCA",), trip_hotel_city_id="36145"),
    Destination("Hà Giang", "Ha Giang", "ha-giang-vn", None, ()),
    Destination("Cao Bằng", "Cao Bang", "cao-bang-vn", "cao-bang-24741", ()),
    Destination("Mộc Châu", "Moc Chau", "moc-chau-vn", None, ()),
    Destination("Buôn Ma Thuột", "Buon Ma Thuot", "buon-ma-thuot-vn", "dak-lak-24724", ("BMV",)),
    Destination("Pleiku", "Pleiku", None, "gia-lai-24722", ("PXU",)),
    Destination("Tuy Hòa", "Tuy Hoa", None, "tuy-hoa-24764", ("TBB",)),
    Destination("Châu Đốc", "Chau Doc", None, "chau-doc-24757", ()),
    Destination("Bắc Ninh", "Bac Ninh", "bac-ninh-vn", "bac-ninh-province-1445852", ()),
    Destination("Thanh Hóa", "Thanh Hoa", "thanh-hoa-vn", None, ("THD",)),
    Destination("Quảng Bình", "Quang Binh", None, "dong-hoi-24726", ("VDH",)),
    Destination("Tây Ninh", "Tay Ninh", "tay-ninh-vn", None, ()),
    Destination("Kon Tum", "Kon Tum", "kon-tum-vn", "kon-tum-24782", ()),
    Destination("Cà Mau", "Ca Mau", "ca-mau-vn", "ca-mau-province-1524647", ("CAH",)),
    Destination("Bến Tre", "Ben Tre", "ben-tre-vn", "ben-tre-24725", ()),
    Destination("Mỹ Tho", "My Tho", None, "my-tho-24763", ()),
    Destination("Sóc Trăng", "Soc Trang", "soc-trang-vn", "soc-trang-2186660", ()),
    Destination("Bạc Liêu", "Bac Lieu", "bac-lieu-vn", "bac-lieu-2044758", ()),
    Destination("Điện Biên", "Dien Bien Phu", "dien-bien-phu-vn", "dien-bien-phu-24777", ("DIN",)),
    Destination("Lạng Sơn", "Lang Son", "lang-son-vn", "lang-son-province-1445821", ()),
    Destination("Sơn La", "Son La", "son-la-vn", "son-la-province-1524635", ()),
    Destination("Biên Hòa", "Bien Hoa", None, "bien-hoa-24729", ()),
    Destination("Vĩnh Long", "Vinh Long", "vinh-long-vn", None, ()),
    Destination("Đồng Tháp", "Dong Thap", "sa-dec-vn", None, ()),
    Destination("Quảng Trị", "Dong Ha", "dong-ha-vn", "dong-ha-24781", ()),
    Destination("Quảng Ngãi", "Quang Ngai", "quang-ngai-vn", None, ()),
    Destination("Phan Rang", "Phan Rang", None, None, ()),
    Destination("Tam Đảo", "Tam Dao", "tam-dao-vn", "tam-dao-1447662", ()),
    Destination("Mai Châu", "Mai Chau", None, None, ()),
    Destination("Rạch Giá", "Rach Gia", None, "rach-gia-24732", ("VKG",)),
    # ---- Điểm đến nhỏ chỉ cào từ Booking (chỉ cần tên tìm kiếm; chưa có slug Agoda / ID Trip đã kiểm chứng).
    #      Nhóm `@extra`. Cát Bà, Lý Sơn, Sầm Sơn, Hà Tiên, Phong Nha trước đây là địa danh con của Hải Phòng, Quảng Ngãi,
    #      Thanh Hóa, Rạch Giá, Quảng Bình; nay là điểm đến riêng nên bản ghi cũ ở đó được gán lại khi chuẩn hoá.
    Destination("Cát Bà", "Cat Ba", None, None, ()),
    Destination("Lý Sơn", "Ly Son", None, None, ()),
    Destination("Sầm Sơn", "Sam Son", None, None, ()),
    Destination("Hà Tiên", "Ha Tien", None, None, ()),
    Destination("Bảo Lộc", "Bao Loc", None, None, ()),
    Destination("Phong Nha", "Phong Nha", None, None, ()),
    Destination("Vân Đồn", "Van Don", None, None, ()),
    Destination("Mù Cang Chải", "Mu Cang Chai", None, None, ()),
    Destination("Thái Nguyên", "Thai Nguyen", None, None, ()),
    Destination("Nam Định", "Nam Dinh", None, None, ()),
    Destination("Vĩnh Phúc", "Vinh Phuc", None, None, ()),
    Destination("Móng Cái", "Mong Cai", None, None, ()),
    Destination("Long Xuyên", "Long Xuyen", None, None, ()),
    Destination("Bắc Kạn", "Bac Kan", None, None, ()),
    Destination("Hà Nam", "Ha Nam", None, None, ()),
    Destination("Trà Vinh", "Tra Vinh", None, None, ()),
    Destination("Tam Kỳ", "Tam Ky", None, None, ()),
    Destination("Gia Nghĩa", "Gia Nghia", None, None, ()),
    Destination("Thái Bình", "Thai Binh", None, None, ()),
)

# 15 điểm đến gốc của handbook (đợt cào đầu, dữ liệu 15–19/09/2026) và phần mở rộng sau đó.
CORE_DESTINATIONS: tuple[str, ...] = tuple(d.name for d in DESTINATIONS[:15])
# 19 điểm đến nhỏ thêm ngày 19/09/2026, chỉ cào từ Booking. (Lai Châu bị gỡ: địa chỉ Phan Xi Păng, Ô Quy Hồ, Cầu kính Rồng Mây
# ghi Lai Châu nên lấy mất điểm tham quan nổi bật nhất của Sa Pa.)
EXTRA_DESTINATIONS: tuple[str, ...] = tuple(d.name for d in DESTINATIONS[-19:])
# 8 thị trường lớn nhất, cào sâu hơn (200 khách sạn Booking thay vì 100).
DEEP_DESTINATIONS: tuple[str, ...] = ("Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Nha Trang", "Phú Quốc", "Hội An", "Đà Lạt", "Hạ Long")
# Phạm vi cố định của catalog v1 (job hằng ngày daily.py, chốt 23/09/2026): đúng 38 điểm đến có trong catalog 11.387 sản phẩm.
V1_DESTINATIONS: tuple[str, ...] = (
    "Đà Nẵng", "Nha Trang", "Phú Quốc", "TP. Hồ Chí Minh", "Hà Nội", "Hội An", "Phan Thiết", "Đà Lạt", "Huế", "Quy Nhơn",
    "Hải Phòng", "Sa Pa", "Hạ Long", "Côn Đảo", "Cần Thơ", "Ninh Bình", "Nghệ An", "Pleiku", "Tuy Hòa", "Buôn Ma Thuột",
    "Rạch Giá", "Cát Bà", "Điện Biên", "Quảng Bình", "Hà Tĩnh", "Thanh Hóa", "Phong Nha", "Châu Đốc", "Cao Bằng", "Kon Tum",
    "Quảng Trị", "Bắc Ninh", "Tây Ninh", "Sầm Sơn", "Mỹ Tho", "Biên Hòa", "Bến Tre", "Mai Châu",
)


@dataclass(frozen=True)
class Budget:
    """Số lượng lấy MỖI điểm đến (trừ flight). Mặc định cho catalog cuối ~3.000–4.000 sản phẩm."""

    booking_hotels: int = 30          # khách sạn phổ biến nhất trên booking.com
    agoda_hotels: int = 20            # khách sạn phổ biến nhất trên agoda.com (trùng booking sẽ được gộp)
    trip_hotels: int = 15             # khách sạn trip.com (nguồn mới 23/09/2026, robots.txt cấm — xem collectors/trip_hotels.py); thấp hơn booking/agoda vì chưa kiểm chứng ở quy mô lớn
    trip_attractions: int = 25        # điểm tham quan trip.com
    trip_experiences: int = 30        # tour/hoạt động trip.com (things-to-do); 1 trang/điểm đến trả tối đa ~12, chưa có cách phân trang hợp lệ
    trip_combos: int = 3              # gói combo bay+ở trip.com/packages mỗi điểm đến (mỗi điểm đến có sân bay riêng)
    ota_rooms_per_hotel: int = 3      # hạng phòng OTA giữ lại mỗi khách sạn (Vinpearl giữ hết)
    flights_per_route: int = 5        # số hiệu chuyến bay giữ lại mỗi tuyến (ngoài sản phẩm cấp tuyến)


DEFAULT_BUDGET = Budget()
TARGET_MIN, TARGET_MAX = 2000, 5000


def select_destinations(names: str | None) -> tuple[Destination, ...]:
    """Chọn điểm đến theo tên (có hoặc không dấu). Nhóm: @core = 15 điểm gốc, @new = 33 điểm mở rộng, @extra = 20 điểm nhỏ
    chỉ Booking, @deep = 8 thị trường lớn, @v1 = 38 điểm của catalog v1, @all = tất cả."""
    if not names:
        return DESTINATIONS
    from .textutil import fold

    core, extra, deep = set(CORE_DESTINATIONS), set(EXTRA_DESTINATIONS), set(DEEP_DESTINATIONS)
    groups = {"@core": tuple(d for d in DESTINATIONS if d.name in core),
              "@new": tuple(d for d in DESTINATIONS if d.name not in core and d.name not in extra),
              "@extra": tuple(d for d in DESTINATIONS if d.name in extra),
              "@deep": tuple(d for d in DESTINATIONS if d.name in deep),
              "@v1": tuple(d for d in DESTINATIONS if d.name in set(V1_DESTINATIONS)),
              "@all": DESTINATIONS}
    tokens = [n.strip() for n in names.split(",") if n.strip()]
    picked = {d.name for t in tokens if t.lower() in groups for d in groups[t.lower()]}
    wanted = {fold(t) for t in tokens if t.lower() not in groups}
    chosen = tuple(d for d in DESTINATIONS if d.name in picked or fold(d.name) in wanted)
    unknown = wanted - {fold(d.name) for d in chosen}
    if unknown:
        raise SystemExit(
            f"Điểm đến không có trong kế hoạch: {', '.join(sorted(unknown))}. "
            f"Có: {', '.join(d.name for d in DESTINATIONS)} (hoặc @core, @new, @extra, @deep, @v1, @all)"
        )
    return chosen


def budget_with(per_destination: int | None, **overrides) -> Budget:
    b = DEFAULT_BUDGET
    if per_destination:
        b = replace(b, booking_hotels=per_destination, agoda_hotels=max(1, per_destination * 2 // 3),
                    trip_attractions=per_destination)
    return replace(b, **{k: v for k, v in overrides.items() if v is not None})


def plan_destination_names() -> set[str]:
    return {d.name for d in DESTINATIONS}
