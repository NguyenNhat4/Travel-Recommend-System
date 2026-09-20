"""Mọi tỷ lệ, phân bố và danh sách từ khoá của bước seed.

MOCK_DATA_SPEC §8: "Mọi tỷ lệ ở §4–§6 nằm trong config.py để Evaluation chỉnh mà không đọc code."
Không hard-code con số nào trong logic; sửa ở đây, chạy lại cùng `--seed` là ra bộ dữ liệu mới tất định.

Không import psycopg/numpy ở module này — test đọc được config mà không cần database.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------- kết nối

#: Loader/seed cần superuser: ghi `cdp.*`, `catalog.*`, `app.*` và tạo extension pg_trgm/unaccent.
#: KHÔNG dùng DATABASE_URL — role `vota_app` không ghi được `cdp.*` và không đọc được cdp.events/profiles.
SEED_DATABASE_URL = os.environ.get(
    "SEED_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vota"
)
INSIDER_DATABASE_URL = os.environ.get(
    "INSIDER_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/insider"
)
INSIDER_TOKEN = os.environ.get("INSIDER_TOKEN", "dev-token")
INSIDER_PARTNER_NAME = "vota"  # partners.partner_name có CHECK phải lowercase

#: Số dòng mỗi lô khi insert (MOCK_DATA_SPEC §1).
BATCH_SIZE = 1000

# ---------------------------------------------------------------- cửa sổ đặt chỗ

#: Cửa sổ đặt chỗ tính từ as_of: [as_of, as_of + WINDOW_DAYS - 1]. Chuỗi calendar dài đúng WINDOW_DAYS.
WINDOW_DAYS = 30

#: Số ngày dung sai khi quyết định một purchase là "sắp tới" (phải nằm trong cửa sổ của sản phẩm).
#:
#: `db/verify.sql` so `using_date > current_date` — đồng hồ của **database**, còn seed chỉ biết `as_of`.
#: Hai mốc này lệch nhau khi container Postgres trôi giờ so với máy host, hoặc khi seed bằng `--as-of`
#: không phải hôm nay. Lệch một ngày là đủ để một chuyến bay đúng ngày `as_of` lọt qua bước kẹp rồi
#: bị verify bắt. Kẹp rộng hơn một ngày về phía quá khứ thì bất biến đúng ở cả hai mốc; event lịch sử
#: cũ hơn thế vẫn được miễn, đúng DATABASE_SCHEMA §1 mục 13.
WINDOW_CLAMP_SKEW_DAYS = 1

# ---------------------------------------------------------------- catalog tổng hợp (§1b)

#: Điểm đến Vinpearl. Thứ tự cố định để kết quả tất định.
DESTINATIONS = [
    "Nha Trang",
    "Phú Quốc",
    "Đà Nẵng",
    "Hội An",
    "Hạ Long",
    "Cửa Hội",
    "Tây Ninh",
]

#: province theo destination (destination là nhãn du lịch, province là đơn vị hành chính — SCHEMA.md §2).
DESTINATION_PROVINCE = {
    "Nha Trang": "Khánh Hòa",
    "Phú Quốc": "Kiên Giang",
    "Đà Nẵng": "Đà Nẵng",
    "Hội An": "Quảng Nam",
    "Hạ Long": "Quảng Ninh",
    "Cửa Hội": "Nghệ An",
    "Tây Ninh": "Tây Ninh",
}

#: Toạ độ tâm điểm đến; sản phẩm rải quanh đây bằng nhiễu nhỏ.
DESTINATION_LATLON = {
    "Nha Trang": (12.2388, 109.1967),
    "Phú Quốc": (10.2270, 103.9600),
    "Đà Nẵng": (16.0544, 108.2022),
    "Hội An": (15.8801, 108.3380),
    "Hạ Long": (20.9101, 107.1839),
    "Cửa Hội": (18.7967, 105.7150),
    "Tây Ninh": (11.3100, 106.0989),
}

#: Số lượng từng loại. §1b: 40 property, ~140 room, 12 route, ~150 flight, 60 attraction, 8 golf, 40 combo.
N_HOTEL_PROPERTIES = 40
ROOMS_PER_PROPERTY = (2, 5)  # inclusive
N_FLIGHT_ROUTES = 12
FLIGHTS_PER_ROUTE = (8, 15)  # inclusive
N_ATTRACTIONS = 60
N_GOLF = 8
N_COMBOS = 40

#: Tỷ lệ property mang brand Vinpearl.
VINPEARL_PROPERTY_RATE = 0.60
#: Tỷ lệ attraction là điểm công cộng: ticketed=false và unitPrice=null.
ATTRACTION_UNTICKETED_RATE = 0.15

#: Cạnh lộn xộn cố ý trong catalog (§1b).
CATALOG_MISSING_IMAGE_RATE = 0.03
CATALOG_SHORT_DESCRIPTION_RATE = 0.02
CATALOG_NEAR_DUPLICATE_PAIRS = 2  # 2 cặp property gần trùng tên, để dedupe/search có việc
CATALOG_EMPTY_ROUTES = 1  # 1 route không có chuyến nào

#: Persona cần sản phẩm neo ở hai điểm đến này, nên luôn có property Vinpearl có phòng.
ANCHOR_DESTINATIONS = ("Nha Trang", "Phú Quốc")

#: Giá (VND). (min, max) trước khi làm tròn nghìn.
PRICE_RANGE = {
    "hotel_room": (800_000, 12_000_000),
    "hotel_property": (900_000, 9_000_000),  # giá tham khảo của property
    "flight": (490_000, 3_200_000),
    "flight_route": (490_000, 2_400_000),
    "attraction": (150_000, 1_200_000),
    "golf": (900_000, 4_500_000),
    "combo": (2_500_000, 18_000_000),
}

STAR_RATINGS = [3.0, 3.5, 4.0, 4.5, 5.0]
REVIEW_SCORE_RANGE = (6.5, 9.6)
REVIEW_COUNT_RANGE = (12, 4200)
MAX_OCCUPANCY_CHOICES = [2, 2, 3, 4, 4, 6]
OCEAN_VIEW_RATE = 0.35
ROOM_SIZE_M2_RANGE = (22, 85)

#: Sân bay dùng để sinh tuyến. §1b: HAN/SGN ↔ CXR/PQC/DAD/VDO.
#: Chỉ sinh chiều **tới** điểm đến (3 origin × 4 destination = 12 tuyến), không sinh chiều về:
#: `destination` của sản phẩm phải là nhãn điểm đến du lịch có khách sạn, nếu không quy tắc
#: "mỗi chuyến một destination" ở seed_histories sẽ ghép chuyến bay về Hà Nội vào chuyến đi Nha Trang.
AIRPORT_ORIGINS = [("HAN", "Hà Nội"), ("SGN", "TP. Hồ Chí Minh"), ("HPH", "Hải Phòng")]
AIRPORT_DESTINATIONS = [
    ("CXR", "Nha Trang", "Nha Trang"),
    ("PQC", "Phú Quốc", "Phú Quốc"),
    ("DAD", "Đà Nẵng", "Đà Nẵng"),
    ("VDO", "Hạ Long", "Hạ Long"),
]
#: (mã hãng, tên hãng). Mã dùng cho attributes.airlineCode, tên cho attributes.airline
#: — contract SCHEMA.md §3.7 và sample dùng tên hãng ở `airline`, mã ở `airlineCode`.
AIRLINES = [("VN", "Vietnam Airlines"), ("VJ", "VietJet Air"), ("QH", "Bamboo Airways")]
FLIGHT_DURATION_MINUTES = {"CXR": 105, "PQC": 125, "DAD": 80, "VDO": 110}

GOLF_HOLES_CHOICES = [18, 18, 27]
GOLF_TEE_TIME_SLOTS = ["06:00", "07:30", "09:00", "10:30", "13:00", "14:30"]

ATTRACTION_OPENING_HOURS = ["08:00–17:00", "09:00–18:00", "09:00–19:30", "08:30–17:30"]
ATTRACTION_DURATION_MINUTES = [120, 180, 240, 300, 480]

HOTEL_CHECK_IN_TIME = "14:00"
HOTEL_CHECK_OUT_TIME = "12:00"

#: Tỷ lệ combo ghi giá theo khách → attributes.priceBasis = per_person.
COMBO_PER_PERSON_RATE = 0.30
#: Số đêm của combo, dùng để sinh tên "3N2Đ"/"4N3Đ".
COMBO_NIGHTS_CHOICES = [2, 3, 4]
COMBO_MIN_PAX_CHOICES = [2, 2, 2, 4]

# ---------------------------------------------------------------- lịch 30 ngày (§2.2)

#: Tổng tỷ lệ đêm kín của một hạng phòng, chọn ngẫu nhiên trong khoảng này.
ROOM_OCCUPANCY_RANGE = (0.25, 0.40)
#: Độ dài một cụm đêm kín (inclusive).
ROOM_BLOCK_NIGHTS = (1, 4)
#: Hệ số nhân xác suất kín cho thứ Sáu/Bảy và cho brand Vinpearl.
WEEKEND_OCCUPANCY_FACTOR = 1.5
VINPEARL_OCCUPANCY_FACTOR = 1.3
#: Tỷ lệ attraction/golf có blackout, và số ngày blackout (inclusive).
BLACKOUT_RATE = 0.15
BLACKOUT_DAYS = (2, 3)

# ---------------------------------------------------------------- parse combo (§3, DATABASE_SCHEMA §9)

#: item_kind → (từ khoá đã bỏ dấu, viết thường; đơn vị mặc định).
#: Thứ tự quan trọng: kind đứng trước thắng khi một đoạn khớp nhiều kind.
COMBO_ITEM_KEYWORDS = [
    ("flight", ["ve may bay", "chuyen bay", "khu hoi", "hang khong"], "khách"),
    ("golf", ["golf", "ho golf", "green fee"], "lượt"),
    (
        "meal",
        ["buffet", "an sang", "an trua", "an toi", "bua", "set menu", "tiec", "bbq", "minibar"],
        "suất",
    ),
    (
        "transfer",
        ["xe dua don", "dua don san bay", "tau cao toc", "shuttle", "xe dien", "dua don"],
        "lượt",
    ),
    (
        "attraction",
        [
            "ve",
            "vinwonders",
            "vinpearl safari",
            "grand world",
            "vinpearl land",
            "tata show",
            "thuy cung",
            "cong vien",
            "show",
        ],
        "vé",
    ),
    (
        "hotel",
        ["dem", "phong", "nghi duong", "resort", "villa", "suite", "deluxe", "bungalow", "luu tru"],
        "đêm",
    ),
    (
        "other",
        ["spa", "massage", "ho boi", "gym", "late check-out", "trang tri", "voucher"],
        "suất",
    ),
]

#: "Cáp treo" mơ hồ: đi với vé/khu vui chơi → attraction; đi với đưa đón/di chuyển → transfer.
CABLE_CAR_TERM = "cap treo"
CABLE_CAR_ATTRACTION_HINTS = ["ve", "vinwonders", "cong vien", "khu vui choi"]
CABLE_CAR_TRANSFER_HINTS = ["dua don", "di chuyen", "trung chuyen"]
#: Mơ hồ thì confidence này và ghi cả hai khả năng vào evidence.
CABLE_CAR_AMBIGUOUS_CONFIDENCE = 0.6

#: Dấu tách hạng mục trong name + description.
COMBO_SPLIT_TOKENS = ["+", ",", ";", "\n", "•", "-", " và ", " kèm ", " bao gồm ", " gồm "]

#: Ngưỡng trigram similarity khi map label → sản phẩm (§3).
COMBO_TRGM_THRESHOLD = 0.45
#: confidence theo chất lượng khớp (DATABASE_SCHEMA §9.5).
COMBO_CONFIDENCE_EXACT = 0.95  # khớp đúng tên + destination
COMBO_CONFIDENCE_DERIVED_ROOM = 0.85  # khớp resort nhưng suy hạng phòng
COMBO_CONFIDENCE_VENUE_ONLY = 0.60  # chỉ khớp venue / về property
#: Dưới ngưỡng này thì item_product_id = NULL.
COMBO_CONFIDENCE_MIN = 0.60
#: Hàng đợi soát tay: item_product_id IS NULL OR confidence < ngưỡng này.
COMBO_REVIEW_THRESHOLD = 0.80
#: Trọng số ưu tiên brand Vinpearl khi hai ứng viên điểm bằng nhau.
COMBO_VINPEARL_BONUS = 0.05

#: item_kind không phải taxonomy → FK (item_product_id, item_kind) → products(product_id, taxonomy)
#: buộc item_product_id phải NULL. Đây là ràng buộc DDL, không phải lựa chọn.
COMBO_KINDS_WITHOUT_PRODUCT = frozenset({"meal", "transfer", "other"})

# ---------------------------------------------------------------- khách và lịch sử (§4)

N_USERS = 2000
#: Tiền tố + số chữ số của cdp_user_id: VP0000001.
USER_ID_PREFIX = "VP"
USER_ID_DIGITS = 7

#: Phân bố lifecycle_stage mục tiêu. verify.sql kiểm active 45±5 và dormant 20±5.
STAGE_DISTRIBUTION = {"new": 0.25, "active": 0.45, "dormant": 0.20, "churned": 0.10}

#: Ranh giới ngày (so với as_of) để suy lifecycle_stage từ purchase gần nhất (§4).
STAGE_ACTIVE_MAX_DAYS = 180
STAGE_DORMANT_MAX_DAYS = 365

#: Khoảng ngày của chuyến cuối theo stage, tính ngược từ as_of (inclusive).
STAGE_LAST_TRIP_DAYS = {
    "active": (1, 175),
    "dormant": (185, 355),
    "churned": (375, 720),
}
#: Số chuyến mỗi khách theo stage, dạng {số chuyến: trọng số}.
#:
#: Spec §4 ghi khoảng "new 0–1 · active 1–4 · dormant 1–2 · churned 1–2". Hiểu theo nghĩa
#: **phân bố đều** trên khoảng đó thì 2.000 khách sinh ra ~15.000 event, vượt xa cổng
#: `events 6000-8000` của `db/verify.sql`. Hai con số trong cùng bộ spec mâu thuẫn nhau, nên
#: giữ đúng *khoảng* (active vẫn có thể tới 4 chuyến) và nghiêng trọng số về 1 để tổng lọt cổng —
#: `db/verify.sql` là tiêu chí nghiệm thu nên nó thắng. Evaluation chỉnh ở đây, không phải trong code.
STAGE_TRIP_WEIGHTS = {
    "new": {0: 0.50, 1: 0.50},
    "active": {1: 0.88, 2: 0.08, 3: 0.03, 4: 0.01},
    "dormant": {1: 0.92, 2: 0.08},
    "churned": {1: 0.92, 2: 0.08},
}

VINCLUB_TIERS = {"Member": 0.60, "Gold": 0.25, "Platinum": 0.10, "Diamond": 0.05}
HOME_CITIES = {
    "Hà Nội": 0.35,
    "TP. Hồ Chí Minh": 0.35,
    "Đà Nẵng": 0.05,
    "Hải Phòng": 0.05,
    "Cần Thơ": 0.05,
    "Nha Trang": 0.05,
    "Huế": 0.05,
    "Vinh": 0.05,
}

#: Tỷ lệ tắt từng kênh, độc lập nhau (§4).
EMAIL_OPTOUT_RATE = 0.05
SMS_OPTOUT_RATE = 0.03
PUSH_OPTOUT_RATE = 0.03

#: Trải chuyến trong bao nhiêu tháng trước as_of.
HISTORY_MONTHS = 24

#: Tỷ lệ chuyến có ≥ 2 vertical (§4), và xác suất có thêm vertical thứ ba.
TRIP_MULTI_VERTICAL_RATE = 0.65
TRIP_THIRD_VERTICAL_RATE = 0.10
TRIP_VERTICAL_ORDER = ["hotel", "flight", "attraction", "combo", "golf"]
#: Xác suất chuyến có golf.
TRIP_GOLF_RATE = 0.03

#: Ngày đi = ngày đặt + khoảng này (inclusive).
TRIP_LEAD_DAYS = (7, 45)
#: attraction dùng sau khi nhận phòng 1 ngày.
ATTRACTION_OFFSET_DAYS = 1

#: Power-law chọn sản phẩm phổ biến trong destination.
ZIPF_S = 1.1
#: Nhân trọng số cho brand Vinpearl.
VINPEARL_POPULARITY_FACTOR = 2.0

#: Số product_view mỗi chuyến (inclusive) và khoảng ngày trước purchase.
#: Trần trên hạ từ 3 xuống 2 cùng lý do với STAGE_TRIP_WEIGHTS: giữ tổng event trong 6.000–8.000.
VIEWS_PER_TRIP = (1, 2)
VIEW_LEAD_DAYS = (0, 7)
#: Tỷ lệ chuyến có add_to_cart, và có search event mở đầu.
ADD_TO_CART_RATE = 0.40
SEARCH_EVENT_RATE = 0.30

#: quantity của purchase theo taxonomy (inclusive).
PURCHASE_QUANTITY = {
    "hotel": (1, 1),
    "flight": (1, 3),
    "attraction": (2, 4),
    "combo": (1, 2),
    "golf": (1, 2),
}
#: Nhiễu giá ±5%, làm tròn nghìn.
PRICE_NOISE = 0.05
PRICE_ROUNDING = 1000

#: Trần event mỗi khách (verify.sql: max <= 15) và tổng mục tiêu (verify.sql: 6000–8000).
MAX_EVENTS_PER_USER = 15
TARGET_EVENT_RANGE = (6000, 8000)

#: Cạnh lộn xộn sau khi sinh (§4).
BROKEN_PRODUCT_RATE = 0.02  # purchase trỏ product_id không tồn tại
MISSING_GROUP_RATE = 0.03  # event bỏ event_group_id
TWO_DESTINATION_VIEW_RATE = 0.01  # khách xem 2 destination cùng ngày

# ---------------------------------------------------------------- persona và app (§5)

#: cdp_user_id cố định; seed_histories phải chừa 4 id này.
PERSONA_USER_IDS = {
    "P1_frequent": "VP0000001",
    "P2_first_time": "VP0000002",
    "P3_dormant": "VP0000003",
    "P4_no_history": "VP0000004",
}
PERSONA_PROFILE = {
    "P1_frequent": {
        "display_name": "Minh Anh",
        "email": "minhanh@vota.demo",
        "vinclub_tier": "Gold",
        "home_city": "Hà Nội",
        "destination": "Nha Trang",
    },
    "P2_first_time": {
        "display_name": "Quốc Bảo",
        "email": "quocbao@vota.demo",
        "vinclub_tier": "Member",
        "home_city": "TP. Hồ Chí Minh",
        "destination": "Phú Quốc",
    },
    "P3_dormant": {
        "display_name": "Thu Hà",
        "email": "thuha@vota.demo",
        "vinclub_tier": "Member",
        "home_city": "Hà Nội",
        "destination": "Phú Quốc",
    },
    "P4_no_history": {
        "display_name": "Khách mới",
        "email": "khachmoi@vota.demo",
        "vinclub_tier": "Member",
        "home_city": "Đà Nẵng",
        "destination": None,
    },
}

#: P1: 3 chuyến Nha Trang trong 18 tháng + 1 chuyến sắp tới.
P1_PAST_TRIP_DAYS = [520, 300, 120]  # ngày trước as_of
P1_UPCOMING_BOOKED_DAYS_AGO = 3  # purchase tại as_of - 3
P1_UPCOMING_USING_OFFSET = 12  # using_date = as_of + 12
#: P2: 2 product_view tại as_of - 2 và as_of - 1, không purchase.
P2_VIEW_DAYS_AGO = [2, 1]
#: P3: 2 chuyến Phú Quốc, chuyến cuối as_of - 190.
P3_TRIP_DAYS = [400, 190]

#: Tài khoản test: test01@vota.demo … testNN@vota.demo.
N_TEST_USERS = 50
TEST_USER_EMAIL_TEMPLATE = "test{:02d}@vota.demo"
DEMO_PASSWORD = "Demo@2026"
BCRYPT_COST = 10

BOOKING_REFERENCE_PREFIX = "VOTA"
BOOKING_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ I, O, 0, 1 cho dễ đọc
BOOKING_REFERENCE_LENGTH = 4

# ---------------------------------------------------------------- insider (§6)

#: Attribute copy sang Insider — cố ý chỉ là TẬP CON của CDP.
INSIDER_ATTRIBUTE_KEYS = ["vinclub_tier", "home_city", "last_destination", "lifecycle_stage"]

#: gdpr_optin=false cho khách tắt cả 3 kênh, CỘNG thêm tỷ lệ ngẫu nhiên này.
INSIDER_EXTRA_GDPR_OPTOUT_RATE = 0.02
#: Ngày opt-out = as_of - randint(khoảng này). Ghi vào insider_profiles.updated_at,
#: vì verify_insider.sql dùng updated_at làm mốc opt-out.
INSIDER_OPTOUT_DAYS_AGO = (0, 180)

#: TTL: chép event thường trong 90 ngày, purchase trong 730 ngày.
INSIDER_EVENT_TTL_DAYS = 90
INSIDER_PURCHASE_TTL_DAYS = 730

#: Email cũ đã đóng, để PATCH identity có lịch sử sẵn.
INSIDER_OLD_EMAIL_RATE = 0.01
INSIDER_OLD_EMAIL_CLOSED_DAYS_AGO = 30

#: Phễu channel_events. ~10 dòng/profile trong 6 tháng (verify: tổng 14.000–26.000).
INSIDER_CHANNEL_MONTHS = 6
INSIDER_SENDS_PER_PROFILE = (3, 5)  # inclusive; mỗi send sinh 1–4 dòng
INSIDER_DELIVERED_RATE = 0.97
INSIDER_OPEN_RATE = 0.35
INSIDER_CLICK_RATE = 0.08
INSIDER_BOUNCE_RATE = 0.02  # thay cho delivered
INSIDER_UNSUBSCRIBE_RATE = 0.01  # sau đó không còn dòng nào
INSIDER_CHANNELS = {"email": 0.70, "push": 0.20, "sms": 0.10}

# ---------------------------------------------------------------- báo cáo

#: report.py chỉ thay phần giữa hai mốc này trong src/data_collection/README.md.
REPORT_MARKER_START = "<!-- seed-report:start -->"
REPORT_MARKER_END = "<!-- seed-report:end -->"

#: Hai dòng verify.sql FAIL theo thiết kế khi dùng catalog tổng hợp (~450 dòng thay vì 2.216).
#: Ngưỡng gốc là của crawl thật; không sửa db/*.sql để lách.
EXPECTED_SYNTHETIC_FAILURES = ("products = 2216", "is_recommendable properties >= 300")

#: Baseline most-popular-in-destination phải "khó nhưng thắng được" (DATABASE_SCHEMA §8).
BASELINE_RECALL_RANGE = (0.05, 0.60)
BASELINE_K = 20
