"""Cấu hình chỉnh được của job cào mới (`fresh_catalog.py`) và lịch chạy tự động.

Thứ tự ưu tiên của từng khoá: giá trị lưu từ monitor (`<CATALOG_STATE_DIR>/settings.json`) → biến môi trường cũ (nếu khoá
có biến env, vd. `TRIP_DAILY_HOTELS`) → mặc định trong code. Secret và kết nối (DB, Weaviate, Cohere) **không** nằm ở đây:
chúng chỉ ở file env của VM; monitor chỉ cho biết đã đặt hay chưa.

Giới hạn tốc độ (chỉ áp cho giá trị lưu từ monitor; env giữ hành vi cũ):
- Nguồn tuân robots.txt (Vinpearl, trip.com vé máy bay/điểm tham quan, booking.com, agoda.com): tối thiểu 2 giây giữa hai
  request tới cùng domain và tối đa 2 tab, theo `docs/spec/data-collection-spec.md` §8.
- Khách sạn trip.com: đường dẫn bị robots.txt cấm, collector giả dạng trình duyệt; giữ giới hạn đồng thời/delay hiện tại; ngân sách khách sạn mỗi lượt chỉnh riêng.

Lịch: cron gọi `run_daily_docker.sh fresh-run tick` mỗi 15 phút; `scheduled_mode()` quyết định có chạy hay không.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

SETTINGS_FILE = "settings.json"
SCHEDULE_FILE = "schedule.json"
FULL_MARKER = "full.last_success"
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Thành phố có cityId khách sạn Trip trong nhóm @deep: phạm vi tối đa của phần khách sạn Trip (không mở rộng từ monitor).
TRIP_HOTEL_CITIES = ("Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Nha Trang", "Phú Quốc", "Đà Lạt", "Hạ Long")

GROUPS = (
    ("schedule", "Lịch chạy"),
    ("sources", "Nguồn và phạm vi"),
    ("strategy", "Chiến thuật từng nguồn"),
    ("stream", "Chạy liên tục"),
    ("speed", "Tốc độ"),
    ("reliability", "Thử lại và kiểm chất lượng"),
    ("alerts", "Cảnh báo và SLA"),
    ("storage", "Lưu trữ và log"),
)


@dataclass(frozen=True)
class Field:
    key: str
    group: str
    label: str
    kind: str                      # bool | int | float | time | offsets | destinations | cities
    default: Any
    env: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    max_items: int | None = None
    help: str = ""


FIELDS: tuple[Field, ...] = (
    # ---- lịch
    Field("schedule.enabled", "schedule", "Bật lịch tự động", "bool", True,
          help="Cron gọi `fresh-run tick` mỗi 15 phút; tắt thì tick không chạy gì. Nút chạy tay vẫn dùng được."),
    Field("schedule.time", "schedule", "Giờ chạy mỗi ngày (giờ Việt Nam)", "time", "02:00",
          help="Lượt theo lịch bắt đầu ở tick đầu tiên sau giờ này, mỗi ngày tối đa một lượt."),
    Field("schedule.fullEveryDays", "schedule", "Cào lớn mỗi bao nhiêu ngày", "int", 7, env="FULL_REFRESH_DAYS",
          minimum=1, maximum=60,
          help="Tính theo ngày lịch từ ngày bắt đầu lượt cào lớn thành công gần nhất. Các ngày còn lại chạy cập nhật hằng ngày."),
    Field("schedule.dailyEnabled", "schedule", "Chạy cập nhật hằng ngày", "bool", True,
          help="Ngày không cào lớn: cuộn cửa sổ 30 ngày, hết hạn giá Trip cũ, hỏi lại giá khách sạn Trip, index. "
               "Tắt thì chỉ còn các ngày cào lớn."),
    # ---- nguồn và phạm vi
    Field("sources.vinpearl", "sources", "Vinpearl (khách sạn, vé, tour, combo, golf)", "bool", True),
    Field("sources.tripFlights", "sources", "trip.com – vé máy bay", "bool", True),
    Field("sources.tripAttractions", "sources", "trip.com – điểm tham quan", "bool", True),
    Field("sources.booking", "sources", "booking.com – khách sạn", "bool", True),
    Field("sources.agoda", "sources", "agoda.com – khách sạn", "bool", True),
    Field("sources.tripHotels", "sources", "trip.com – khách sạn và giá phòng", "bool", True,
          help="Tắt thì lượt hằng ngày chỉ còn cuộn cửa sổ, hết hạn giá và index."),
    Field("scope.destinations", "sources", "Điểm đến cào lớn", "destinations", "@deep", env="CATALOG_DESTINATIONS",
          help="Tên điểm đến hoặc nhóm (@deep, @core, @v1, @all…) trong collectors/plan.py. Áp cho booking, agoda, "
               "vé máy bay và điểm tham quan Trip. Vinpearl luôn lấy toàn bộ."),
    Field("tripHotels.cities", "sources", "Thành phố khách sạn Trip", "cities", None,
          help="Để trống: các thành phố trong phạm vi điểm đến ở trên có mã Trip. Chỉ chọn trong 7 thành phố hiện có."),
    # ---- chiến thuật
    Field("vinpearl.priceOffsets", "strategy", "Vinpearl – ngày hỏi giá phòng (số ngày từ hôm chạy)", "offsets",
          (30, 14, 60), minimum=0, maximum=365, max_items=60,
          help="Mỗi ngày là một request cho mỗi khách sạn. 0,1,…,29 = lịch 30 ngày như job cũ."),
    Field("vinpearl.tours", "strategy", "Vinpearl – lấy vé/tour/combo/golf", "bool", True),
    Field("booking.hotelsPerDestination", "strategy", "booking.com – số khách sạn mỗi điểm đến", "int", 30,
          minimum=1, maximum=500),
    Field("booking.vinpearlBrand", "strategy", "booking.com – thêm khách sạn thương hiệu Vinpearl (sitemap)", "bool", True),
    Field("booking.checkinOffsetDays", "strategy", "booking.com – ngày nhận phòng để lấy giá (+N ngày)", "int", 30,
          minimum=1, maximum=365),
    Field("agoda.hotelsPerDestination", "strategy", "agoda.com – số khách sạn mỗi điểm đến", "int", 20,
          minimum=1, maximum=500),
    Field("agoda.checkinOffsetDays", "strategy", "agoda.com – cấu hình cũ (collector API luôn hỏi giá hôm chạy)", "int", 30,
          minimum=1, maximum=365, help="Giữ để đọc settings.json cũ; fresh pipeline lấy một ngày giá thật rồi loader tạo lịch 30 ngày."),
    Field("tripAttractions.perDestination", "strategy", "trip.com – số điểm tham quan mỗi điểm đến", "int", 25,
          minimum=1, maximum=200),
    Field("tripFlights.flightsPerRoute", "strategy", "trip.com – số chuyến giữ lại mỗi tuyến (0 = tất cả)", "int", 0,
          minimum=0, maximum=100),
    Field("tripFlights.fareMinutes", "strategy", "trip.com – phút cho giá thương gia + khứ hồi 3/5/7 ngày mỗi lượt (0 = tắt)",
          "int", 30, minimum=0, maximum=600,
          help="Xoay vòng: mỗi lượt tìm các tuyến/ngày bay chưa tìm hoặc tìm lâu nhất tới khi hết số phút này; vẫn dừng "
               "trước hạn giờ trip.com vé máy bay 3 phút."),
    Field("normalise.roomsPerHotel", "strategy", "Chuẩn hoá – số hạng phòng OTA giữ mỗi khách sạn (0 = tất cả)", "int", 0,
          minimum=0, maximum=100),
    Field("normalise.maxErrorPercent", "reliability", "Chuẩn hoá – tỉ lệ bản ghi lỗi tối đa mỗi nguồn (%)", "float", 5.0,
          minimum=0, maximum=100,
          help="Bản ghi lỗi khi ánh xạ được bỏ và ghi vào errors.jsonl. Một nguồn có từ 3 bản ghi lỗi trở lên và vượt tỉ lệ "
               "này, hoặc mọi bản ghi đều lỗi, thì dừng normalize (thường là lỗi code hoặc nguồn đổi định dạng)."),
    Field("normalise.preview", "strategy", "Chuẩn hoá từng nguồn ngay khi nguồn cào xong (và bản nháp)", "bool", True,
          help="Lượt cào lớn: bước cào nào xong thì chuẩn hoá ngay file interim của bước đó, không đợi cả site (tối đa 2 "
               "tiến trình) thành checkpoint, gộp nháp để xem ở tab Chuẩn hoá / Catalog cuối trong lúc site khác còn cào. Bước normalize chính thức "
               "dùng lại checkpoint. Không nạp DB, không index. Tắt nếu máy yếu."),
    Field("stream.enabled", "stream", "Chạy liên tục – chuẩn hoá từng phần trong lúc đang cào", "bool", False,
          help="Cần bật “Chuẩn hoá từng nguồn ngay khi nguồn cào xong”. Mỗi chu kỳ đọc phần mới của từng file interim và chỉ "
               "ánh xạ bản ghi mới; nguồn cào xong thì chốt checkpoint của nó. Kết quả cuối giống hệt khi tắt. "
               "Xem docs/plan/2026-09-28-pipeline-chay-lien-tuc.md (L1)."),
    Field("stream.normaliseSeconds", "stream", "Chạy liên tục – giây giữa hai lần chuẩn hoá phần mới", "int", 15,
          minimum=2, maximum=600),
    Field("stream.mergeSeconds", "stream", "Chạy liên tục – giây giữa hai lần gộp catalog đang gộp (khi có dữ liệu mới)",
          "int", 30, minimum=5, maximum=3600),
    Field("stream.db", "stream", "Chạy liên tục – nạp DB theo phần trong lúc cào", "bool", False,
          help="Cần bật chạy liên tục. Dòng đủ điều kiện (qua kiểm tra dòng; nguồn đủ bản ghi, tỉ lệ lỗi dưới ngưỡng; cha đã "
               "nạp) được nạp vào DB đích của lượt (local hoặc cloud theo DB_TARGET). Khách sạn Trip và combo nạp ở cuối "
               "lượt. Dòng đã nạp ở lại dù cuối lượt lỗi."),
    Field("stream.dbSeconds", "stream", "Chạy liên tục – giây giữa hai lần nạp DB theo phần", "int", 60,
          minimum=10, maximum=3600),
    Field("stream.minRecords", "stream", "Chạy liên tục – số bản ghi tối thiểu của một nguồn trước khi nạp DB", "int", 20,
          minimum=1, maximum=100000,
          help="Chỉ áp khi nguồn còn đang cào: nguồn đã cào xong (checkpoint đã chốt) được nạp dù ít bản ghi hơn. "
               "Tỉ lệ bản ghi lỗi vẫn phải dưới ngưỡng của normalize."),
    Field("stream.index", "stream", "Chạy liên tục – index Weaviate theo phần (sau mỗi lần nạp DB có dòng mới)", "bool",
          False, help="Cần bật nạp DB theo phần. Chỉ nhúng dòng mới hoặc đổi text (gọi Cohere)."),
    Field("stream.indexSeconds", "stream", "Chạy liên tục – giây giữa hai lần index theo phần", "int", 300,
          minimum=30, maximum=7200),
    Field("tripHotels.initialPerCity", "strategy", "Khách sạn Trip – số ID lấy mỗi thành phố ở lượt đầu", "int", 30,
          env="TRIP_INITIAL_PER_CITY", minimum=1, maximum=500),
    Field("tripHotels.newPerCity", "strategy", "Khách sạn Trip – số ID mới mỗi thành phố ở mỗi lượt cào lớn", "int", 10,
          env="TRIP_NEW_PER_CITY", minimum=1, maximum=500),
    Field("tripHotels.scanPerCity", "strategy", "Khách sạn Trip – số thẻ quét tối đa mỗi thành phố khi tìm ID", "int", 300,
          env="TRIP_DISCOVERY_SCAN_PER_CITY", minimum=1, maximum=2000),
    Field("tripHotels.dailyHotels", "strategy", "Khách sạn Trip – số khách sạn hỏi lại giá mỗi lượt hằng ngày", "int", 180,
          env="TRIP_DAILY_HOTELS", minimum=1, maximum=2000),
    Field("tripHotels.priceOffsets", "strategy", "Khách sạn Trip – ngày nhận phòng hỏi giá (số ngày từ hôm chạy)",
          "offsets", (14, 30, 60), env="TRIP_PRICE_DATES", minimum=1, maximum=365, max_items=3),
    # ---- tốc độ
    Field("crawl.parallelSites", "speed", "Số site cào cùng lúc ở lượt cào lớn", "int", 2, env="CRAWL_PARALLEL",
          minimum=1, maximum=4, help="Song song giữa các site khác nhau; trong một site vẫn tuần tự. Mỗi site mở trình duyệt."),
    Field("vinpearl.delay", "speed", "Vinpearl – giây tối thiểu giữa hai request", "float", 2.0, minimum=2.0, maximum=120),
    Field("trip.delay", "speed", "trip.com vé máy bay/điểm tham quan – giây tối thiểu giữa hai request", "float", 2.5,
          minimum=2.0, maximum=120),
    Field("booking.delay", "speed", "booking.com – giây tối thiểu giữa hai trang", "float", 3.0, minimum=2.0, maximum=120),
    Field("booking.tabs", "speed", "booking.com – số tab", "int", 1, minimum=1, maximum=2),
    Field("booking.fast", "speed", "booking.com – chặn CSS/tracker, không chờ trang tải xong", "bool", True),
    Field("agoda.delay", "speed", "agoda.com – giây tối thiểu giữa hai request API", "float", 3.0, minimum=2.0, maximum=120),
    Field("agoda.tabs", "speed", "agoda.com – cấu hình tab cũ (API không dùng)", "int", 1, minimum=1, maximum=2),
    Field("crawl.maxBlocks", "speed", "Bị chặn liên tiếp bao nhiêu lần thì dừng một nguồn", "int", 8, minimum=1, maximum=50),
    Field("tripHotels.httpWorkers", "speed", "Khách sạn Trip – số request thông tin cùng lúc", "int", 4, env="FAST_WORKERS",
          minimum=1, maximum=4, help="Chỉ chỉnh xuống; tối đa là mức code hiện tại."),
    Field("tripHotels.priceTabs", "speed", "Khách sạn Trip – số tab hỏi giá", "int", 2, env="PRICE_WORKERS",
          minimum=1, maximum=2, help="Chỉ chỉnh xuống; tối đa là mức code hiện tại."),
    Field("tripHotels.delayMin", "speed", "Khách sạn Trip – giây chờ tối thiểu giữa hai lần mở", "float", 0.5,
          env="MIN_DELAY", minimum=0.5, maximum=120, help="Chỉ chỉnh lên; tối thiểu là mức code hiện tại."),
    Field("tripHotels.delayMax", "speed", "Khách sạn Trip – giây chờ tối đa giữa hai lần mở", "float", 1.0,
          env="MAX_DELAY", minimum=1.0, maximum=300, help="Phải ≥ giây chờ tối thiểu."),
    # ---- thử lại và kiểm chất lượng (pipeline_errors.py)
    Field("retry.transientAttempts", "reliability", "Lỗi tạm thời – số lần thử lại", "int", 2, minimum=0, maximum=5,
          help="Timeout, mất kết nối, HTTP 429/5xx, SQLite bị khoá. Áp cho từng nguồn cào và các bước nạp DB/index."),
    Field("retry.transientDelay", "reliability", "Lỗi tạm thời – giây chờ trước lần thử lại đầu", "float", 30.0,
          minimum=1, maximum=600, help="Mỗi lần sau chờ gấp đôi lần trước."),
    Field("retry.infraAttempts", "reliability", "Lỗi hạ tầng – số lần thử lại", "int", 3, minimum=0, maximum=10,
          help="Postgres, Weaviate, Cohere không kết nối được."),
    Field("retry.infraDelay", "reliability", "Lỗi hạ tầng – giây chờ trước lần thử lại đầu", "float", 60.0,
          minimum=1, maximum=1800, help="Mỗi lần sau chờ gấp đôi lần trước."),
    # ---- hạn giờ (P4, docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md): quá hạn thì dừng riêng bước đó, giữ phần đã cào,
    # nguồn khác và các bước sau cào chạy tiếp; 0 = không giới hạn
    Field("run.maxHours", "reliability", "Hạn giờ – toàn lượt gồm DB, chuẩn hoá và index", "float", 18.0,
          minimum=0.01, maximum=96, env="CATALOG_MAX_HOURS",
          help="Luôn hữu hạn. Tiến trình giám sát dừng cây tiến trình rồi ghi lỗi, giữ dữ liệu để chạy lại."),
    Field("timeout.processing", "reliability", "Hạn giờ – mỗi bước chuẩn hoá/index/DB (phút)", "int", 30,
          minimum=1, maximum=240, help="Áp cả bước cuối lượt; không chờ vô hạn khi thư viện hoặc luồng bị treo."),
    Field("crawl.maxHours", "reliability", "Hạn giờ – cả phần cào của một lượt (giờ)", "float", 16.0, env="CRAWL_MAX_HOURS",
          minimum=0, maximum=72, help="Quá hạn thì dừng mọi nguồn còn đang cào, rồi vẫn gộp, kiểm tra, nạp DB phần đã có. "
                                      "0 = không giới hạn."),
    Field("timeout.vinpearl", "reliability", "Hạn giờ – Vinpearl (phút)", "int", 90, minimum=0, maximum=1440,
          help="0 = không giới hạn."),
    Field("timeout.tripFlights", "reliability", "Hạn giờ – trip.com vé máy bay (phút)", "int", 60, minimum=0, maximum=1440),
    Field("timeout.tripAttractions", "reliability", "Hạn giờ – trip.com điểm tham quan (phút)", "int", 60, minimum=0,
          maximum=1440),
    Field("timeout.booking", "reliability", "Hạn giờ – booking.com (phút)", "int", 60, minimum=0, maximum=1440),
    Field("timeout.agoda", "reliability", "Hạn giờ – agoda.com (phút)", "int", 60, minimum=0, maximum=1440),
    Field("timeout.tripHotelsDiscover", "reliability", "Hạn giờ – khách sạn Trip: tìm ID (phút)", "int", 60, minimum=0,
          maximum=1440),
    Field("timeout.tripHotelsPrices", "reliability", "Hạn giờ – khách sạn Trip: giá phòng (phút)", "int", 480, minimum=0,
          maximum=2880, help="Quá hạn thì lượt này không có khách sạn Trip mới (giá chỉ ghi khi cả bước xong)."),
    Field("quality.maxDropPercent", "reliability", "Chặn nạp DB khi catalog giảm quá (%) so với lượt trước", "int", 50,
          minimum=0, maximum=100,
          help="So với lượt thành công gần nhất cùng chế độ, cùng phạm vi điểm đến và cùng bộ nguồn. 0 = tắt."),
    # ---- cảnh báo và SLA (CP7, CP8 docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md); chưa gửi ra ngoài, chỉ hiện trên monitor
    Field("alert.enabled", "alerts", "Ghi cảnh báo khi lượt lỗi / bị chặn / trễ SLA", "bool", True),
    Field("alert.includeWarnings", "alerts", "Cảnh báo cả mức warning (nguồn bị chặn, bản ghi lỗi lẻ, lô nạp DB lỗi)", "bool",
          True),
    Field("alert.cooldownHours", "alerts", "Không báo lại cảnh báo giống hệt trong (giờ)", "int", 6, minimum=0, maximum=168,
          help="Cùng loại + cùng bước + cùng nguồn. Cảnh báo bị chặn vẫn được ghi file."),
    Field("sla.enabled", "alerts", "Kiểm SLA ở mỗi cron tick", "bool", True),
    Field("sla.finishBy", "alerts", "SLA – hôm nay có lịch thì phải có lượt xong trước (giờ Việt Nam)", "time", "19:00"),
    Field("sla.slowFactor", "alerts", "SLA – báo bước sau cào chậm hơn N lần trung vị các lượt trước (0 = tắt)", "float", 3.0,
          minimum=0, maximum=100),
    Field("sla.maxCatalogAgeHours", "alerts", "SLA – báo khi lần nạp DB thành công gần nhất cũ hơn (giờ, 0 = tắt)", "int", 48,
          minimum=0, maximum=720),
    # ---- lưu trữ và log
    Field("runs.keep", "storage", "Số lượt giữ lại dữ liệu (raw, interim, catalog, báo cáo)", "int", 2,
          env="RUNS_KEEP", minimum=1, maximum=100,
          help="Lượt cũ hơn bị xoá đầu mỗi lượt mới (mặc định 2 lượt để tiết kiệm dung lượng VM 2 vCPU 4 GB). Tóm tắt của mọi lượt vẫn còn trong lịch sử."),
    Field("log.verbose", "storage", "Log chi tiết từng request (URL, mã HTTP, thời gian)", "bool", False),
)
BY_KEY = {f.key: f for f in FIELDS}

# Biến env chỉ báo "đã đặt hay chưa" trên monitor, không bao giờ trả giá trị (trừ DB_TARGET và WEAVIATE_VECTOR_INDEX_TYPE).
ENV_STATUS = ("DB_TARGET", "SEED_DATABASE_URL", "DATABASE_URL", "WEAVIATE_URL", "WEAVIATE_API_KEY",
              "CLOUD_SEED_DATABASE_URL", "CLOUD_DATABASE_URL", "CLOUD_WEAVIATE_URL", "CLOUD_WEAVIATE_API_KEY",
              "COHERE_API_KEY", "WEAVIATE_VECTOR_INDEX_TYPE")
ENV_PUBLIC = {"DB_TARGET", "WEAVIATE_VECTOR_INDEX_TYPE"}


class SettingsError(ValueError):
    pass


# ---------------------------------------------------------------------------------------------------- đọc / kiểm tra


def _offsets(value, field: Field) -> tuple[int, ...]:
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise SettingsError(f"{field.label}: cần danh sách số ngày")
    try:
        out = tuple(int(p) for p in parts)
    except (TypeError, ValueError):
        raise SettingsError(f"{field.label}: chỉ gồm số nguyên, cách nhau dấu phẩy") from None
    if not out:
        raise SettingsError(f"{field.label}: cần ít nhất một ngày")
    if len(set(out)) != len(out):
        raise SettingsError(f"{field.label}: có ngày trùng")
    return out


def coerce(field: Field, value, *, bounded: bool) -> Any:
    """Đổi `value` về đúng kiểu của `field`. `bounded` = áp giới hạn (giá trị lưu từ monitor)."""
    kind = field.kind
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"):
            return True
        if isinstance(value, str) and value.strip().lower() in ("0", "false", "no", "off", ""):
            return False
        raise SettingsError(f"{field.label}: cần bật/tắt")
    if kind in ("int", "float"):
        if isinstance(value, bool):
            raise SettingsError(f"{field.label}: cần một số")
        try:
            number = int(value) if kind == "int" else float(value)
        except (TypeError, ValueError, OverflowError):
            raise SettingsError(f"{field.label}: cần một số{' nguyên' if kind == 'int' else ''}") from None
        if not math.isfinite(number):
            raise SettingsError(f"{field.label}: cần số hữu hạn")
        if kind == "int" and isinstance(value, float) and not value.is_integer():
            raise SettingsError(f"{field.label}: cần số nguyên")
        if bounded:
            if field.minimum is not None and number < field.minimum:
                raise SettingsError(f"{field.label}: tối thiểu {field.minimum:g}")
            if field.maximum is not None and number > field.maximum:
                raise SettingsError(f"{field.label}: tối đa {field.maximum:g}")
        elif kind == "int" and number < 0:
            raise SettingsError(f"{field.label}: phải ≥ 0")
        return number
    if kind == "time":
        text = str(value).strip()
        if not TIME_RE.match(text):
            raise SettingsError(f"{field.label}: dạng HH:MM, vd. 02:00")
        return text
    if kind == "offsets":
        out = _offsets(value, field)
        if bounded:
            if field.max_items and len(out) > field.max_items:
                raise SettingsError(f"{field.label}: tối đa {field.max_items} ngày")
            if any(v < field.minimum or v > field.maximum for v in out):
                raise SettingsError(f"{field.label}: mỗi ngày trong khoảng {field.minimum:g}–{field.maximum:g}")
        elif any(v < 0 for v in out):
            raise SettingsError(f"{field.label}: số ngày phải ≥ 0")
        return out
    if kind == "destinations":
        text = ",".join(value) if isinstance(value, (list, tuple)) else str(value or "").strip()
        if not text:
            raise SettingsError(f"{field.label}: chọn ít nhất một điểm đến hoặc nhóm")
        from collectors.plan import select_destinations
        try:
            select_destinations(text)
        except SystemExit as exc:  # select_destinations báo tên lạ bằng SystemExit
            raise SettingsError(str(exc)) from None
        return text
    if kind == "cities":
        if value in (None, "", []):
            return None
        items = [v.strip() for v in (value.split(",") if isinstance(value, str) else value) if str(v).strip()]
        unknown = [v for v in items if v not in TRIP_HOTEL_CITIES]
        if unknown:
            raise SettingsError(f"{field.label}: chỉ chọn trong {', '.join(TRIP_HOTEL_CITIES)} (lạ: {', '.join(unknown)})")
        return tuple(dict.fromkeys(items))
    raise SettingsError(f"Kiểu cấu hình lạ: {kind}")


def settings_path(state_dir: Path) -> Path:
    return Path(state_dir) / SETTINGS_FILE


def read_saved(state_dir: Path) -> dict:
    path = settings_path(state_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SettingsError(f"Không đọc được {path}: {exc}") from None
    values = data.get("values") if isinstance(data, dict) else None
    return values if isinstance(values, dict) else {}


def resolve(state_dir: Path, env: dict | None = None) -> dict[str, dict]:
    """Mọi khoá → {value, source: file|env|default, file, env}. Khoá lạ trong file bị bỏ qua."""
    env = os.environ if env is None else env
    saved = read_saved(state_dir)
    out: dict[str, dict] = {}
    for field in FIELDS:
        entry = {"value": field.default, "source": "default", "file": None, "env": None}
        if field.env and env.get(field.env) not in (None, ""):
            entry["env"] = env[field.env]
            entry["value"] = coerce(field, env[field.env], bounded=False)
            entry["source"] = "env"
        if field.key in saved and saved[field.key] is not None:
            entry["file"] = saved[field.key]
            entry["value"] = coerce(field, saved[field.key], bounded=True)
            entry["source"] = "file"
        out[field.key] = entry
    check_consistency({k: v["value"] for k, v in out.items()})
    return out


def check_consistency(values: dict) -> None:
    if values["tripHotels.delayMax"] < values["tripHotels.delayMin"]:
        raise SettingsError("Khách sạn Trip: giây chờ tối đa phải ≥ giây chờ tối thiểu")


def load(state_dir: Path, env: dict | None = None) -> dict[str, Any]:
    """Giá trị đang có hiệu lực của mọi khoá (dict phẳng theo tên khoá)."""
    return {key: entry["value"] for key, entry in resolve(state_dir, env).items()}


def save(state_dir: Path, changes: dict, env: dict | None = None) -> dict[str, Any]:
    """Ghi thay đổi từ monitor. `None` = bỏ giá trị đã lưu (quay về env/mặc định). Kiểm tra toàn bộ trước khi ghi."""
    if not isinstance(changes, dict):
        raise SettingsError("Cần một đối tượng {khoá: giá trị}")
    saved = dict(read_saved(state_dir))
    for key, value in changes.items():
        field = BY_KEY.get(key)
        if field is None:
            raise SettingsError(f"Khoá cấu hình lạ: {key}")
        if value is None or (field.kind == "cities" and value in ("", [])):
            saved.pop(key, None)
            continue
        coerced = coerce(field, value, bounded=True)
        saved[key] = list(coerced) if isinstance(coerced, tuple) else coerced
    env = os.environ if env is None else env
    trial = {}
    for field in FIELDS:  # kiểm tra chéo trên giá trị sẽ có hiệu lực
        if field.key in saved:
            trial[field.key] = coerce(field, saved[field.key], bounded=True)
        elif field.env and env.get(field.env) not in (None, ""):
            trial[field.key] = coerce(field, env[field.env], bounded=False)
        else:
            trial[field.key] = field.default
    check_consistency(trial)
    path = settings_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "values": saved}
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".settings-", delete=False, encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=1, sort_keys=True)
        tmp.write("\n")
        name = tmp.name
    os.replace(name, path)
    return load(state_dir, env)


def describe(state_dir: Path, env: dict | None = None) -> dict:
    """Dữ liệu cho form cấu hình của monitor."""
    env = os.environ if env is None else env
    error = None
    try:
        resolved = resolve(state_dir, env)
    except SettingsError as exc:  # file hỏng: vẫn hiện form với giá trị mặc định để sửa
        error = str(exc)
        resolved = {f.key: {"value": f.default, "source": "default", "file": None, "env": env.get(f.env) if f.env else None}
                    for f in FIELDS}
    from collectors.plan import DESTINATIONS
    fields = []
    for field in FIELDS:
        entry = resolved[field.key]
        value = entry["value"]
        fields.append({
            "key": field.key, "group": field.group, "label": field.label, "kind": field.kind, "help": field.help,
            "default": list(field.default) if isinstance(field.default, tuple) else field.default,
            "env": field.env, "envValue": entry["env"], "saved": entry["file"],
            "value": list(value) if isinstance(value, tuple) else value, "source": entry["source"],
            "minimum": field.minimum, "maximum": field.maximum, "maxItems": field.max_items,
        })
    return {
        "groups": [{"id": gid, "label": label} for gid, label in GROUPS],
        "fields": fields,
        "error": error,
        "choices": {
            "destinations": ["@deep", "@core", "@new", "@extra", "@v1", "@all"] + [d.name for d in DESTINATIONS],
            "cities": list(TRIP_HOTEL_CITIES),
        },
        "env": {name: (env.get(name) or None) if name in ENV_PUBLIC else bool(env.get(name)) for name in ENV_STATUS},
    }


# ---------------------------------------------------------------------------------------------------- lịch


def local_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=7)))


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def last_full_date(state_dir: Path) -> date | None:
    """Ngày (giờ địa phương) bắt đầu lượt cào lớn thành công gần nhất. File cũ ghi giờ kết thúc hoặc nội dung lạ → dùng mtime."""
    marker = Path(state_dir) / FULL_MARKER
    if not marker.exists():
        return None
    try:
        stamp = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip().replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
    except (OSError, ValueError):
        stamp = datetime.fromtimestamp(marker.stat().st_mtime, timezone.utc)
    return stamp.astimezone(timezone(timedelta(hours=7))).date()


def full_due(values: dict, state_dir: Path, today: date) -> bool:
    last = last_full_date(state_dir)
    if last is None:
        return True
    if values["sources.tripHotels"] and not (Path(state_dir) / "trip_targets.json").is_file():
        return True
    return (today - last).days >= values["schedule.fullEveryDays"]


def auto_mode(values: dict, state_dir: Path, today: date | None = None) -> str:
    return "full" if full_due(values, state_dir, today or local_now().date()) else "daily"


def scheduled_mode(values: dict, state_dir: Path, now: datetime | None = None) -> tuple[str | None, str]:
    """(mode hoặc None, lý do) cho một tick của cron."""
    now = now or local_now()
    if not values["schedule.enabled"]:
        return None, "lịch tự động đang tắt"
    hh, mm = (int(x) for x in values["schedule.time"].split(":"))
    if now.time() < time(hh, mm):
        return None, f"chưa tới {values['schedule.time']}"
    today = now.date()
    if _read_json(Path(state_dir) / SCHEDULE_FILE).get("lastScheduledDate") == today.isoformat():
        return None, "hôm nay đã chạy lượt theo lịch"
    mode = auto_mode(values, state_dir, today)
    if mode == "daily" and not values["schedule.dailyEnabled"]:
        return None, "hôm nay không phải ngày cào lớn và cập nhật hằng ngày đang tắt"
    return mode, "đến giờ chạy"


def mark_scheduled(state_dir: Path, run_id: str, today: date | None = None) -> None:
    path = Path(state_dir) / SCHEDULE_FILE
    payload = {"lastScheduledDate": (today or local_now().date()).isoformat(), "lastScheduledRun": run_id}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    tmp.replace(path)


def next_run(values: dict, state_dir: Path, now: datetime | None = None) -> dict | None:
    """Lượt theo lịch kế tiếp: {at, mode} hoặc None nếu lịch tắt / không còn gì để chạy."""
    now = now or local_now()
    if not values["schedule.enabled"]:
        return None
    hh, mm = (int(x) for x in values["schedule.time"].split(":"))
    done_today = _read_json(Path(state_dir) / SCHEDULE_FILE).get("lastScheduledDate") == now.date().isoformat()
    for offset in range(0, 62):
        day = now.date() + timedelta(days=offset)
        if offset == 0 and done_today:
            continue
        mode = auto_mode(values, state_dir, day)
        if mode == "daily" and not values["schedule.dailyEnabled"]:
            continue
        at = datetime.combine(day, time(hh, mm), tzinfo=now.tzinfo)
        return {"at": max(at, now).isoformat(timespec="minutes"), "mode": mode,
                "pending": at <= now}  # pending: đã qua giờ nhưng tick chưa chạy (tối đa 15 phút)
    return None
