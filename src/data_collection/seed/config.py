"""Tham số của pipeline seed tuần 1 — nơi DUY NHẤT chứa tỷ lệ, phân bố và danh sách (MOCK_DATA_SPEC §8).

Evaluation chỉnh phân bố ở đây mà không cần đọc code. Khoảng viết dạng (a, b) là bao gồm cả hai đầu.
Các diễn giải cho chỗ spec mơ hồ ghi ở MOCK_DATA_SPEC §0 "Điểm chốt 21/09".
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_COLLECTION_DIR = REPO_ROOT / "src" / "data_collection"
DEFAULT_DATA_DIR = DATA_COLLECTION_DIR / "data"
DEFAULT_SNAPSHOT_DIR = DATA_COLLECTION_DIR / "snapshots" / "2026-09-30"
DEFAULT_PRODUCTS_SNAPSHOT = DEFAULT_SNAPSHOT_DIR / "products.jsonl.gz"
DEFAULT_PRODUCTS_CANDIDATES = (
    DEFAULT_DATA_DIR / "products.jsonl",
    DEFAULT_PRODUCTS_SNAPSHOT,
    DATA_COLLECTION_DIR / "products.jsonl",
    DATA_COLLECTION_DIR / "products.synthetic.jsonl",
)

VOTA_URL_ENV = "SEED_DATABASE_URL"
INSIDER_URL_ENV = "INSIDER_DATABASE_URL"
DEFAULT_VOTA_URL = "postgresql://postgres:postgres@localhost:5432/vota"
DEFAULT_INSIDER_URL = "postgresql://postgres:postgres@localhost:5432/insider"

DEFAULT_SEED = 42

# ================================================================== §2 catalog: cửa sổ và lịch 30 ngày
WINDOW_DAYS = 30                          # cửa sổ đặt chỗ [as_of, as_of + 29]
# hạng phòng: cửa sổ nguyên 30 ngày, lịch mô phỏng mở đủ 30 đêm (chốt 02/10/2026; bỏ lịch kín 25–40% chốt 21/09)
TICKET_BLACKOUT_SHARE = 0.15              # attraction / golf: 15% sản phẩm có blackout …
TICKET_BLACKOUT_DAYS = (2, 3)             # … 2–3 ngày ngẫu nhiên trong cửa sổ
HOTEL_CHECK_IN = "14:00"                  # giờ mặc định cho property khi nguồn không có
HOTEL_CHECK_OUT = "12:00"

# ================================================================== §4 khách
DEFAULT_USERS = 2_000
STAGE_MIX = {"new": 0.25, "active": 0.45, "dormant": 0.20, "churned": 0.10}
STAGE_TOLERANCE = 0.05                    # lệch stage (tính lại từ event) cho phép so với STAGE_MIX
VINCLUB_TIERS = {"Member": 60, "Gold": 25, "Platinum": 10, "Diamond": 5}
HOME_CITIES = {"Hà Nội": 35, "TP. Hồ Chí Minh": 35, "Đà Nẵng": 5, "Hải Phòng": 5, "Cần Thơ": 5, "Nha Trang": 5,
               "Huế": 5, "Vinh": 5}
# Tên thành phố không trùng nhãn originDestination của catalog: sân bay Vinh nằm dưới nhãn "Nghệ An".
HOME_CITY_FLIGHT_ORIGIN = {"Vinh": "Nghệ An"}
OPTOUT_RATE = {"email": 0.05, "sms": 0.03, "push": 0.03}   # tỷ lệ opt-in = false, độc lập từng kênh
PROFILE_CREATED_BEFORE_FIRST_EVENT_DAYS = (1, 240)
PROFILE_CREATED_NO_EVENT_DAYS = (20, 900)

# ================================================================== §4 chuyến đi
# Khoảng số chuyến giữ đúng spec (active 1–4, dormant 1–2, churned 1–2); trọng số nghiêng về 1 để tổng event nằm
# trong cổng 6.000–8.000 của db/verify.sql (phân bố đều cho ~15.000). Hiệu chỉnh bằng mô phỏng trên snapshot 10.320 dòng.
TRIPS_PER_STAGE = {"active": (0.78, 0.16, 0.05, 0.01), "dormant": (0.85, 0.15), "churned": (0.85, 0.15)}
LAST_PURCHASE_DAYS_AGO = {"active": (9, 180), "dormant": (181, 365), "churned": (366, 730)}
TRIP_GAP_DAYS = (60, 240)                 # khoảng cách giữa hai lần mua liên tiếp của một khách
HISTORY_DAYS = 730                        # mọi event nằm trong 24 tháng trước as_of: lần mua cũ nhất ≤ 730 − 7 − 1 ngày
                                          # để cả product_view (≤ 7 ngày trước mua) và search cũng nằm trong cửa sổ
NEW_VIEW_TRIP_RATE = 0.20                 # new: 0–1 chuyến; tỷ lệ có 1 chuyến chỉ product_view
NEW_VIEW_DAYS_AGO = (1, 90)
NEW_VIEW_GAP_MIN = (0, 90)                # các view của chuyến chỉ-xem cách nhau 0–90 phút, cùng ngày
LEAD_DAYS = (7, 45)                       # nhận phòng = ngày mua + 7–45 ngày …
LATEST_PAST_USING_DAYS = 1                # … nhưng khách thường không có using_date sau as_of − 1 (vé bay chỉ mở 1 ngày)
TICKET_DAY_OFFSET = 1                     # attraction / combo / golf: using_date = nhận phòng + 1
MULTI_VERTICAL_RATE = 0.65                # 65% chuyến có ≥ 2 vertical
GOLF_TRIP_RATE = 0.03                     # 3% mọi chuyến có golf (luôn là chuyến nhiều vertical)
# Hai knob dưới là đòn bẩy Recall@20 của baseline popular-in-destination (DoD #5 ≤ 0,60): hạng mục bị ẩn khi đo là mục cuối
# checkout, nên càng nhiều vé bay / vé tham quan (ít sản phẩm, dễ trúng top-20) thì baseline càng mạnh. Đo trên snapshot, 62 seed:
# TB 0,540, sd 0,035 (tập ẩn chỉ ~270 khách nên dao động giữa các seed lớn), 4/62 seed vượt 0,60; seed 42 = 0,584.
# Đo lại 02/10/2026 (snapshot 11.387, lịch phòng mở đủ): MULTI_TICKET_RATE 0,35 → TB 0,515, max 0,599, 0/61 seed vượt;
# 0,10 → TB 0,514, max 0,607, 1/61 vượt; seed 42 = 0,599 ở cả hai mức.
MULTI_FLIGHT_RATE = 0.8                   # chuyến nhiều vertical: thêm vé bay nếu có tuyến từ home_city
MULTI_TICKET_RATE = 0.35                  # chuyến nhiều vertical: thêm attraction/combo nếu điểm đến có (tạo chuỗi mua chéo hợp lý)
SINGLE_VERTICAL_WEIGHTS = {"hotel": 0.85, "ticket": 0.10, "flight": 0.05}
TICKET_KIND_WEIGHTS = {"attraction": 0.7, "combo": 0.3}
DEST_REDRAWS = 30                         # số lần bốc lại điểm đến khi nó không có đủ vertical cho chuyến
ZIPF_S = 0.8                              # power-law trên thứ tự cố định crc32(product_id)
VINPEARL_BOOST = 2.0                      # brand Vinpearl nhân trọng số
VIEWS_PER_TRIP = (0.90, 0.08, 0.02)       # trọng số 1 / 2 / 3 product_view mỗi chuyến
VIEW_LEAD_DAYS = (0, 7)                   # product_view trước purchase 0–7 ngày
SEARCH_TRIP_RATE = 0.30                   # 30% chuyến mở đầu bằng 1 event search (product_id NULL)
ADD_TO_CART_TRIP_RATE = 0.40              # 40% chuyến có add_to_cart cho mọi mục, ngay trước purchase
CART_BEFORE_PURCHASE_MIN = (5, 120)       # add_to_cart trước purchase 5–120 phút
SEARCH_BEFORE_VIEW_MIN = (2, 60)          # search trước product_view đầu tiên 2–60 phút
ITEM_GAP_SECONDS = 90                     # các purchase trong một checkout cách nhau 90 giây
EVENT_HOURS = (8, 22)                     # giờ phát sinh event trong ngày
QUANTITY = {"hotel": (1, 1), "flight": (1, 3), "attraction": (2, 4), "combo": (1, 2), "golf": (1, 2)}
PRICE_NOISE = 0.05                        # unit_price = products.unit_price × U(1 − 5%, 1 + 5%) …
PRICE_ROUNDING = 1_000                    # … làm tròn nghìn
MAX_EVENTS_PER_USER = 15
EVENT_TRIM_ORDER = ("search", "add_to_cart", "product_view")   # bỏ theo thứ tự này khi vượt cap; purchase không bao giờ bị bỏ

# Cạnh lộn xộn (sau khi sinh, không áp cho persona)
MESSY_PURCHASE_BAD_PRODUCT = 0.02         # 2% purchase trỏ product_id không tồn tại
MESSY_DROP_GROUP = 0.03                   # 3% event có event_group_id (chỉ purchase mang gid) bị bỏ gid
MESSY_TWO_DEST_VIEW_USERS = 0.01          # 1% khách có product_view ở hai destination khác nhau cùng ngày …
MESSY_SECOND_VIEW_AFTER_MIN = (5, 120)    # … view thứ hai 5–120 phút sau view gốc (không qua ngày)

RECALL_K = 20                             # baseline popular-in-destination trong report …
RECALL_CEILING = 0.60                     # … vượt trần này thì report và seed_histories in cảnh báo (DoD #5)

# ================================================================== §5 persona và tài khoản app
PERSONAS = (
    # cdp_user_id, persona, tên hiển thị, email đăng nhập, home_city, vinclub_tier
    ("VP0000001", "P1_frequent", "Minh Anh", "minh.anh@example.com", "TP. Hồ Chí Minh", "Gold"),
    ("VP0000002", "P2_first_time", "Quốc Bảo", "quoc.bao@example.com", "Hà Nội", "Member"),
    ("VP0000003", "P3_dormant", "Thu Hà", "thu.ha@example.com", "Hà Nội", "Member"),
    ("VP0000004", "P4_no_history", "Khách mới", "khach.moi@example.com", "Đà Nẵng", "Member"),
)
P1 = {"destination": "Nha Trang", "past_trip_days_ago": (520, 300, 125), "past_verticals": ("hotel", "attraction"),
      "upcoming_purchase_days_ago": 3, "upcoming_using_in_days": 12, "upcoming_nights": 1, "upcoming_brand": "Vinpearl",
      "upcoming_view_days_before": 1, "upcoming_cart_minutes_before": 20, "phone": "0900000001"}
P2 = {"destination": "Phú Quốc", "view_days_ago": (2, 1)}
P3 = {"destination": "Phú Quốc", "trip_days_ago": (470, 190), "verticals": ("hotel", "ticket")}
PERSONA_LEAD_DAYS = (7, 20)               # chuyến cũ của persona: nhận phòng sau ngày mua 7–20 ngày
TEST_USERS = 50
TEST_USER_EMAIL = "test{n:02d}@vota.demo"
TEST_USER_NAME = "Khách test {n:02d}"
DEMO_PASSWORD = "Demo@2026"               # mật khẩu demo công khai, dùng chung cho 4 persona + 50 test
# Argon2id đúng tham số backend (auth §8.1) → backend không phải rehash khi đăng nhập.
ARGON2_MEMORY_KIB = 19456
ARGON2_TIME_COST = 2
ARGON2_PARALLELISM = 1
ARGON2_HASH_LEN = 32

# ================================================================== §6 Insider clone
INSIDER_PARTNER = "vota"
INSIDER_PARTNER_CREATED_DAYS_AGO = 900    # partner tạo trước mọi insider_profile (lùi thêm nếu profile cũ hơn)
INSIDER_TOKEN_DEFAULT = "dev-token"       # ghi đè bằng env INSIDER_TOKEN
INSIDER_ATTRIBUTE_KEYS = ("vinclub_tier", "home_city", "last_destination", "lifecycle_stage")
INSIDER_EMAIL = "{user}@example.com"      # {user} = cdp_user_id viết thường
INSIDER_OLD_EMAIL = "{user}.cu@example.com"
INSIDER_PHONE_PREFIX = "090"              # 09 + 8 số: "090" + 7 số thứ tự, không trùng
GDPR_RANDOM_OFF_RATE = 0.02               # gdpr_optin = false: khách tắt cả 3 kênh CỘNG 2% ngẫu nhiên
GDPR_OPTOUT_DAYS_AGO = (0, 180)           # ngày opt-out = as_of − 0…180 ngày (lưu ở updated_at)
EMAIL_HISTORY_RATE = 0.01                 # 1% profile có thêm một email cũ đã đóng …
EMAIL_HISTORY_CLOSED_DAYS_AGO = 30        # … với valid_to = as_of − 30
TTL_PURCHASE_DAYS = 730
TTL_OTHER_DAYS = 90
CHANNEL_EVENTS_PER_PROFILE = 10.0         # ~10 dòng channel_events / profile
SENDS_SPREAD = 0.5                        # độ lệch chuẩn số lần gửi / profile = 50% trung bình
CAMPAIGN_COUNT = 12
CAMPAIGN_SPAN_DAYS = 176                  # chiến dịch đầu cách as_of 176 ngày (~6 tháng) …
CAMPAIGN_LAST_DAYS_AGO = 11               # … chiến dịch cuối cách as_of 11 ngày, các chiến dịch cách đều nhau
SEND_WINDOW_HOURS = 72                    # một lần gửi rơi trong 72 giờ sau ngày chiến dịch
CHANNEL_DELAY_SECONDS = {"delivered": (1, 30), "bounce": (1, 60), "open": (300, 172_800), "click": (10, 1_800),
                         "unsubscribe": (5, 3_600)}   # độ trễ so với lần gửi (delivered, bounce, open) / bước trước (click, unsubscribe)
INSIDER_RECEIVE_DELAY_SECONDS = (1, 300)  # insider_events.received_at = event_time + 1–300 giây
CHANNEL_WEIGHTS = {"email": 55, "push": 35, "sms": 10}   # chọn kênh trong số kênh đã opt-in
# delivered = 1 − bounce − drop = 97% trên sent; open / click / unsubscribe tính trên delivered; click luôn sau open.
FUNNEL = {"bounce": 0.02, "drop": 0.01, "open": 0.35, "click": 0.08, "unsubscribe": 0.01}
BOUNCE_REASONS = ("mailbox_full", "invalid_address", "blocked")
CAMPAIGN_NAMES = ("welcome", "hotel-weekend", "flight-flash-sale", "vinwonders-combo", "golf-open", "summer-beach",
                  "dormant-winback", "tier-upgrade", "autumn-getaway", "family-trip", "last-minute", "member-perk")

# ================================================================== bộ đánh giá RecSys (KHÔNG phải seed demo)
# Chuyến bỏ giỏ: xem + add_to_cart rồi không mua (không event_group_id, như app thật). Tắt ở seed demo (0.0).
ABANDONED_CART_RATE = 0.0                 # xác suất chèn một lần bỏ giỏ trước mỗi chuyến có mua
ABANDONED_SAME_DEST_RATE = 0.5            # lần bỏ giỏ cùng điểm đến với chuyến mua kế sau nó …
ABANDONED_DAYS_BEFORE = (3, 60)           # … và xảy ra 3–60 ngày trước chuyến đó

# ================================================================== §4.3 sở thích chủ đề (g6-pref-v1, 08/10/2026)
# Gate G6 (docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md §7.1): seed demo bốc điểm đến mỗi chuyến từ phân phối TOÀN CỤC, không phụ
# thuộc khách, nên split temporal / nexttrip không thể thưởng cho việc bám sở thích. Profile `g6-pref-v1` gán cho mỗi khách thường một
# chủ đề ẨN (biển / núi / thành phố) và bốc điểm đến cùng chủ đề với xác suất THEME_PREF_RATE. Nhãn chỉ ra file sidecar
# (`user_themes.jsonl` / `themes.json`), không có cột DB, không thuật toán nào đọc. Demo / eval-v2 / append-v1: THEME_PREF_RATE = 0 → không
# tạo stream RNG nào, output không đổi byte.
THEME_PREF_RATE = 0.0                     # demo: tắt. Xác suất mỗi lần bốc điểm đến lấy trong chủ đề của khách (còn lại: bốc toàn cục)
THEME_NO_PREF_SHARE = 0.30                # 30% khách thường không có sở thích (theme None → luôn bốc toàn cục)
THEME_MIX = None                          # trọng số chọn chủ đề cho khách; None = theo khối lượng bookable của từng chủ đề trong catalog lúc sinh
# Nhãn chủ đề chép từ theme_exp.THEME (beach / mountain / city; theme_exp import lại từ đây để một nguồn). "mixed" và 7 điểm đến chưa
# nhãn của prodcopy (Quảng Ngãi, Quảng Trị, Cà Mau, Sóc Trăng, Vinpearl Onsen Resort Tuyên Quang, Tuyên Quang, Bạc Liêu) KHÔNG có ở đây
# = không chủ đề, chỉ tới được qua lần bốc toàn cục.
DEST_THEMES = {
    "beach": ["Phú Quốc", "Nha Trang", "Đà Nẵng", "Quy Nhơn", "Phan Thiết", "Côn Đảo", "Cát Bà", "Tuy Hòa", "Hạ Long",
              "Sầm Sơn", "Vũng Tàu", "Phan Rang", "Lý Sơn", "Hà Tiên", "Vân Đồn"],
    "mountain": ["Đà Lạt", "Sa Pa", "Điện Biên", "Mai Châu", "Pleiku", "Buôn Ma Thuột", "Phong Nha",
                 "Kon Tum", "Tam Đảo", "Mù Cang Chải", "Sơn La", "Mộc Châu", "Hà Giang", "Bảo Lộc", "Cao Bằng", "Lạng Sơn"],
    "city": ["Hà Nội", "TP. Hồ Chí Minh", "Huế", "Hội An", "Hải Phòng", "Cần Thơ", "Ninh Bình",
             "Mỹ Tho", "Vĩnh Long", "Đồng Tháp"],
}

# Profile `eval-v2` (05/10/2026, người dùng chốt): bộ dữ liệu sinh RIÊNG để đánh giá đủ tín hiệu RecSys — khách quay lại (CF, chuyến
# kế tiếp), bỏ giỏ, chuyến một loại đa dạng. Nạp vào database riêng, không phải demo / staging; db/verify.sql (cổng 2.000 khách,
# 6.000–8.000 event, ≤ 15 event/khách) không áp cho bộ này. Ghi đè hằng ở trên khi chạy `seed_histories --profile eval-v2`.
PROFILES = {
    "eval-v2": {
        "DEFAULT_USERS": 5_000,
        "MAX_EVENTS_PER_USER": 40,
        # hiệu chỉnh 05/10 (snapshot 30/09, as_of 05/10, seed 42): khách có mua quay lại ≥ 2 chuyến ≈ 40 %
        "TRIPS_PER_STAGE": {"active": (0.50, 0.25, 0.15, 0.10), "dormant": (0.70, 0.30), "churned": (0.70, 0.30)},
        "SINGLE_VERTICAL_WEIGHTS": {"hotel": 0.50, "ticket": 0.30, "flight": 0.20},
        "VIEWS_PER_TRIP": (0.50, 0.30, 0.20),
        "ABANDONED_CART_RATE": 0.22,      # ≈ 20 % số chuyến (lần bỏ giỏ / (lần bỏ giỏ + chuyến có mua)); 0,25 cho 22,5 %
    },
}

# Tên cũ, giữ để không vỡ import bên ngoài.
DEFAULT_ZIPF = ZIPF_S
DEFAULT_VINPEARL_BOOST = VINPEARL_BOOST
DEFAULT_MAX_EVENTS = MAX_EVENTS_PER_USER
DEFAULT_INSIDER_EVENTS_PER_PROFILE = CHANNEL_EVENTS_PER_PROFILE


def find_products(explicit: Path | None = None) -> Path | None:
    """Return the first usable real/synthetic catalog path."""
    candidates = (explicit,) if explicit else DEFAULT_PRODUCTS_CANDIDATES
    return next((path.resolve() for path in candidates if path and path.is_file()), None)

# Additive staging batch, explicitly requested 05/10: 5,000 NEW customers,
# exclude the four generated personas. Use valid catalog references/group IDs.
PROFILES["append-v1"] = {
    **PROFILES["eval-v2"],
    "DEFAULT_USERS": 5_000 + len(PERSONAS),
    "MESSY_PURCHASE_BAD_PRODUCT": 0.0,
    "MESSY_DROP_GROUP": 0.0,
}

# G6 (08/10/2026, MOCK_DATA_SPEC §4.3): append-v1 + sở thích chủ đề ẩn. Chỉ cho DB nghiên cứu RecSys (`append_histories prepare
# --profile g6-pref-v1`); demo / staging không dùng. Với THEME_PREF_RATE = 0 output trùng byte append-v1.
PROFILES["g6-pref-v1"] = {
    **PROFILES["append-v1"],
    "THEME_PREF_RATE": 0.8,
}
