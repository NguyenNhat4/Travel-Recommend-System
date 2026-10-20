"""Đồ thị bước của job cào: nguồn cào, bước sau cào và quan hệ giữa chúng (P3, docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md).

Khai báo ở một chỗ để `fresh_catalog.py` (job, chạy lại) và `monitor.py` (sơ đồ, nút chạy lại) cùng đọc. Module chỉ có
dữ liệu và hàm suy ra, không chạy bước nào: job vẫn gọi các bước theo thứ tự trong code, và
`tests/test_pipeline_graph.py` kiểm thứ tự đó khớp `deps` ở đây (tương tự định nghĩa DAG tách khỏi executor của Airflow).

Thêm một nguồn: một dòng trong SOURCES (+ collector / hàm chạy của nó). Thêm một bước sau cào: một dòng trong STEPS và
hàm chạy trong fresh_catalog.py. Tên bước là khoá trong run.json của các lượt cũ — không đổi tên bước đã có.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """Một nguồn cào = một làn trên sơ đồ."""
    key: str                      # làn trên sơ đồ, khoá thống kê của monitor
    label: str
    setting: str                  # công tắc bật/tắt trong Cấu hình (fresh_settings)
    site: str                     # nhóm site của crawl_sites: các bước cùng site chạy tuần tự (cùng một site, tránh bị chặn)
    steps: tuple[str, ...]        # tên bước cào trong run.json, theo thứ tự; bước sau phụ thuộc bước trước
    step_labels: tuple[str, ...]  # nhãn ngắn của từng bước trên sơ đồ
    interim: tuple[str, ...]      # file interim/<tên>.jsonl nguồn ghi; bước cuối của nguồn ghi xong các file này
    live: str                     # khoá chỉnh tốc độ sống (collectors/live_control.py)
    modes: tuple[str, ...]        # chế độ lượt có các bước cào này
    in_process: bool = False      # True: bước là hàm trong fresh_catalog.py; False: tiến trình `crawl.py <bước>`
    step_titles: tuple[str, ...] = ()  # nhãn dài trong run.json (chỉ bước trong tiến trình; crawl.py không có nhãn)
    timeouts: tuple[str, ...] = ()     # khoá Cấu hình hạn giờ (phút) của từng bước (P4); 0 = không giới hạn

    @property
    def log_group(self) -> str | None:
        """Tiền tố `[site]` của dòng log: chỉ tiến trình crawl.py; bước trong tiến trình log không có tiền tố."""
        return None if self.in_process else self.site


SOURCES: tuple[Source, ...] = (
    Source("vinpearl", "Vinpearl (khách sạn, vé, tour, combo)", "sources.vinpearl", "vinpearl",
           ("vinpearl",), ("Vinpearl",), ("vinpearl", "vinpearl_bundles"), "vinpearl", ("full",),
           timeouts=("timeout.vinpearl",)),
    Source("tripFlights", "trip.com – vé máy bay", "sources.tripFlights", "trip",
           ("trip-flights",), ("Trip vé máy bay",), ("trip_flights",), "trip", ("full",), timeouts=("timeout.tripFlights",)),
    Source("tripAttractions", "trip.com – điểm tham quan", "sources.tripAttractions", "trip",
           ("trip-attractions",), ("Trip điểm tham quan",), ("trip_attractions",), "trip", ("full",),
           timeouts=("timeout.tripAttractions",)),
    Source("booking", "booking.com – khách sạn", "sources.booking", "booking",
           ("booking-hotels",), ("booking.com",), ("booking_hotels",), "booking", ("full",), timeouts=("timeout.booking",)),
    Source("agoda", "agoda.com – khách sạn", "sources.agoda", "agoda",
           ("agoda-hotels",), ("agoda.com",), ("agoda_api",), "agoda", ("full",), timeouts=("timeout.agoda",)),
    Source("tripHotels", "trip.com – khách sạn + giá phòng", "sources.tripHotels", "trip",
           ("trip-hotels.discover", "trip-hotels.prices"), ("Trip KS: tìm ID", "Trip KS: giá phòng"), ("trip_hotels",),
           "tripHotels", ("full", "daily"), in_process=True,
           step_titles=("Khách sạn Trip: tìm ID mới", "Khách sạn Trip: thông tin + giá phòng"),
           timeouts=("timeout.tripHotelsDiscover", "timeout.tripHotelsPrices")),
)
# Thứ tự các site được giao cho pool cào (crawl.parallelSites site cùng lúc): site đứng trước bắt đầu trước. Booking cuối:
# làm mới ~1.800 khách sạn mất nhiều giờ nhất, nếu đứng trước sẽ ăn hết `crawl.maxHours` của Agoda khi chạy tuần tự.
SITE_ORDER = ("trip", "vinpearl", "agoda", "booking")
# File interim một site có thể có mà không bước nào của job này ghi (lệnh crawl.py riêng): vẫn được chuẩn hoá khi cả site
# xong.
SITE_EXTRA_INTERIM = {"trip": ("trip_combos",), "booking": ("booking_attractions", "booking_flights"),
                      "agoda": ("agoda_hotels",)}  # bản cào bằng trình duyệt cũ (bước agoda-hotels nay chạy collector API)


@dataclass(frozen=True)
class Step:
    """Một bước ngoài phần cào (một ô riêng trên sơ đồ)."""
    id: str                       # tên bước trong run.json = id ô trên sơ đồ
    column: str
    label: str                    # nhãn ngắn trên sơ đồ
    title: str                    # nhãn dài trong run.json / log
    deps: tuple[str, ...]         # bước phải xong trước; CRAWL = mọi bước cào của lượt
    modes: tuple[str, ...] | None  # chế độ lượt có bước này; None = mọi chế độ
    resume: tuple[str, ...] = field(default=())  # tên dùng cho `resume --from` bắt đầu từ bước này (rỗng: không chạy lại được)


CRAWL = "crawl"  # dep giả: mọi bước cào của lượt (và chuẩn hoá theo nguồn của chúng)
COLUMNS = (("prepare", "Chuẩn bị"), ("crawl", "Cào"), ("normalise", "Chuẩn hoá"), ("merge", "Gộp"),
           ("validate", "Kiểm tra"), ("db", "Nạp DB"), ("index", "Index"))
STEPS: tuple[Step, ...] = (
    Step("maintain", "prepare", "Bảo trì DB", "Bảo trì DB: hết hạn giá Trip cũ, cuộn cửa sổ 30 ngày, parse lại thành phần combo", (), None),
    # `merge`: chạy lại chỉ bước gộp từ checkpoint (không ánh xạ lại interim)
    Step("normalise", "merge", "Gộp catalog", "Chuẩn hoá 13 trường, gộp trùng", (CRAWL,), ("full", "daily"),
         resume=("normalise", "merge")),
    Step("validate", "validate", "Kiểm tra catalog", "Kiểm tra catalog trước khi nạp", ("normalise",), ("full", "daily"),
         resume=("validate",)),
    Step("db", "db", "Nạp Postgres", "Nạp cdp.products / catalog.combo_items", ("validate",), ("full", "daily"),
         resume=("db",)),
    Step("index", "index", "Embed + index Weaviate", "Index vector vào Weaviate", ("db",), None, resume=("index",)),
)


@dataclass(frozen=True)
class Stream:
    """Việc chạy liên tục suốt phần cào (docs/plan/2026-09-28-pipeline-chay-lien-tuc.md), gắn vào một ô của sơ đồ."""
    id: str                       # tên bước trong run.json (`stream.<việc>`) = khoá chỉnh sống
    node: str | None              # ô trên sơ đồ nhận các lô; None: hiện trên từng ô chuẩn hoá theo nguồn
    label: str                    # nhãn ngắn (hàng điều khiển trên monitor)
    title: str                    # nhãn dài trong run.json

    @property
    def name(self) -> str:        # tên việc trong fresh_catalog (Ticker)
        return self.id.split(".", 1)[1]


STREAMS: tuple[Stream, ...] = (
    Stream("stream.normalise", None, "Chuẩn hoá từng phần", "Chạy liên tục: chuẩn hoá từng phần trong lúc cào"),
    Stream("stream.merge", "normalise", "Gộp catalog đang gộp", "Chạy liên tục: gộp catalog đang gộp khi có dữ liệu mới"),
    Stream("stream.db", "db", "Nạp DB theo phần", "Chạy liên tục: nạp DB theo phần"),
    Stream("stream.index", "index", "Index theo phần", "Chạy liên tục: index theo phần"),
)
# Bước con của các bước lớn, theo thứ tự chạy: stage_log.Stages (maintain, validate, db, index) và normalise.StepClock
# (normalise). Monitor hiện đủ danh sách này cả khi bước chưa chạy hoặc bước con không chạy ở lượt này;
# tests/test_pipeline_graph.py đối chiếu tên với code. Thêm / đổi tên bước con thì sửa cả ở đây.
SUBSTEPS: dict[str, tuple[str, ...]] = {
    "maintain": ("đọc catalog", "danh sách làm mới", "hết hạn giá Trip", "cuộn cửa sổ 30 ngày", "ghi DB",
                 "parse thành phần combo"),
    "normalise": ("đọc interim", "ánh xạ nguồn", "đọc checkpoint", "sửa điểm đến, toạ độ", "gộp trùng khách sạn",
                  "vé và điểm tham quan", "vé máy bay, combo", "lọc", "làm giàu", "kiểm vị trí, giá", "ghi output"),
    "validate": ("khách sạn Trip đủ mốc ngày giá", "13 trường đúng thứ tự", "id, sourceRef, thông tin hiển thị",
                 "đủ nhóm sản phẩm", "catalog không giảm quá ngưỡng", "độ phủ làm mới khách sạn đang có"),
    "db": ("đọc catalog lượt này", "thuộc tính combo", "đọc DB", "ghép với DB", "cửa sổ 30 ngày", "ghi cdp.products",
           "parse thành phần combo"),
    "index": ("đọc search unit từ DB", "giữ vector không đổi text", "embed mới / đổi text + ghi Weaviate",
              "xoá vector mồ côi", "chỉ mục từ khoá (lexical)"),
}
# Bước con chỉ có ở trường hợp đặc biệt nên không hiện sẵn: index bị hoãn (hết quota) thay cả chuỗi bằng một bước.
SUBSTEP_EXTRAS: dict[str, tuple[str, ...]] = {"index": ("embed + ghi Weaviate",)}
MERGE_ONLY_FROM = "đọc checkpoint"  # gộp nháp / chạy lại chỉ gộp (--merge-only) bắt đầu từ bước con này
NORMALISE_SOURCE = "normalise.source:"   # tiền tố bước chuẩn hoá một file interim: normalise.source:<file>
NORMALISE_ALL = "normalise.sources"      # ô chung của sơ đồ khi lượt không chuẩn hoá theo nguồn (lượt daily, lượt cũ)
# `resume --from crawl --source <nguồn>` (P4): cào lại riêng một nguồn của lượt rồi chạy tiếp mọi bước sau cào.
RECRAWL = "crawl"


# ---------------------------------------------------------------------------------------------------- suy ra

BY_ID = {step.id: step for step in STEPS}
SOURCE_BY_STEP = {name: src for src in SOURCES for name in src.steps}
SOURCE_BY_KEY = {src.key: src for src in SOURCES}
CRAWL_STEPS = tuple(SOURCE_BY_STEP)
# bước cuối của nguồn → file interim nó ghi: bước đó xong thì chuẩn hoá ngay các file này (P1)
STEP_INTERIM = {src.steps[-1]: src.interim for src in SOURCES}
# nhóm site → các bước crawl.py của site, theo SITE_ORDER (bước trong tiến trình được crawl_and_load chèn vào nhóm trip)
SITE_GROUPS = tuple((site, tuple(name for src in SOURCES if src.site == site and not src.in_process for name in src.steps))
                    for site in SITE_ORDER)
SITE_INTERIM = {site: tuple(stem for src in SOURCES if src.site == site for stem in src.interim)
                + SITE_EXTRA_INTERIM.get(site, ()) for site in SITE_ORDER}
SOURCE_SWITCH = {name: src.setting for src in SOURCES if not src.in_process for name in src.steps}
LIVE_KEYS = {name: src.live for src in SOURCES if not src.in_process for name in src.steps}
STEP_TITLES = {name: title for src in SOURCES for name, title in zip(src.steps, src.step_titles)}
STEP_LABELS = {name: label for src in SOURCES for name, label in zip(src.steps, src.step_labels)}
STEP_TIMEOUT = {name: key for src in SOURCES for name, key in zip(src.steps, src.timeouts)}
RESUME_STEPS = (RECRAWL, *(name for step in STEPS for name in step.resume))


def deps_of(name: str) -> tuple[str, ...]:
    """Bước phải xong trước `name` (tên bước trong run.json). Bước cào: bước trước cùng nguồn, bước đầu thì `maintain`;
    bước chuẩn hoá theo nguồn: mọi bước cào; bước sau cào: `deps` đã khai báo, CRAWL = mọi bước cào."""
    if name in SOURCE_BY_STEP:
        steps = SOURCE_BY_STEP[name].steps
        index = steps.index(name)
        return (steps[index - 1],) if index else ("maintain",)
    if name.startswith(NORMALISE_SOURCE):
        return ()  # chạy ngay khi bước cào ghi file của nó xong (P1): không đợi bước nào khác
    step = BY_ID.get(name)
    if step is None:
        return ()
    return tuple(dep for d in step.deps for dep in (CRAWL_STEPS if d == CRAWL else (d,)))


def planned_substeps(name: str, merge_only: bool = False) -> tuple[str, ...]:
    """Bước con dự kiến của bước lớn `name` (rỗng: bước không có bước con). `merge_only`: bước Gộp chỉ gộp từ checkpoint
    (bản nháp trong lúc cào, chạy lại từ bước gộp) nên không đọc interim / ánh xạ nguồn."""
    plan = SUBSTEPS.get(name, ())
    return plan[plan.index(MERGE_ONLY_FROM):] if merge_only and MERGE_ONLY_FROM in plan else plan


def downstream(name: str) -> tuple[str, ...]:
    """Các bước sau cào phụ thuộc (trực tiếp hoặc gián tiếp) vào `name`, theo thứ tự STEPS."""
    found: set[str] = {name}
    out = []
    for step in STEPS:
        if step.id != name and any(dep in found for dep in deps_of(step.id)):
            found.add(step.id)
            out.append(step.id)
    return tuple(out)


def resume_plan(from_step: str) -> tuple[str, ...]:
    """Các bước `resume --from <from_step>` chạy, theo thứ tự (CP6). `merge` = bước normalize chỉ gộp từ checkpoint;
    `crawl` = cào lại một nguồn rồi chuẩn hoá (dùng lại checkpoint của nguồn khác) và chạy tiếp như bình thường."""
    if from_step == RECRAWL:
        return (RECRAWL, *resume_plan("normalise"))
    step = next((s for s in STEPS if from_step in s.resume), None)
    if step is None:
        raise ValueError(f'Bước chạy lại phải là một trong: {", ".join(RESUME_STEPS)}')
    return (step.id, *downstream(step.id))


def resume_options(node: str) -> tuple[str, ...]:
    """Tên chạy lại được từ một ô của sơ đồ: ô bước sau cào → tên của nó; ô chuẩn hoá chung → chuẩn hoá lại từ đầu."""
    if node == NORMALISE_ALL:
        return BY_ID["normalise"].resume[:1]
    if node in SOURCE_BY_STEP:
        return (RECRAWL,)  # monitor chỉ hiện nút khi bước cào đó bị chặn / lỗi / quá giờ
    step = BY_ID.get(node)
    return step.resume if step else ()
