#!/usr/bin/env python3
"""Monitor của job cào mới (fresh_catalog.py): xem từng lượt từ dữ liệu gốc tới dòng nạp DB, chỉnh cấu hình, chạy/dừng.

  python monitor.py                                   # http://127.0.0.1:8765 (dữ liệu: data/state, data/fresh_runs)
  python monitor.py --state-dir /data/state --run-root /data/fresh_runs --log-dir /logs   # trong container trên VM

Mặc định chỉ nghe 127.0.0.1 và từ chối Host khác localhost (chống DNS rebinding); trên máy cá nhân xem qua SSH tunnel:
  ssh -L 8765:127.0.0.1:8765 <user>@<vm>
Công khai (staging): --host 0.0.0.0 --allow-public-host chấp nhận Host public, không có đăng nhập. Thêm --read-only thì chỉ
phục vụ GET, mọi POST trả 405 (7 API điều khiển không dùng được). run_daily_docker.sh đặt các cờ này qua MONITOR_HOST, MONITOR_PUBLIC, MONITOR_READ_ONLY.

Đọc: file của các lượt (state, run-root); DB đích qua tab DB (SQL chỉ đọc trong transaction read-only, SEED_DATABASE_URL
hoặc CLOUD_SEED_DATABASE_URL theo DB_TARGET); backend qua GET /internal/calls (tab Realtime, tự làm mới).
Ghi: settings.json (Cấu hình), stop.request (Dừng), live_control.json (tạm dừng / đổi delay từng nguồn khi lượt đang chạy),
monitor-launch.log và tiến trình fresh_catalog.py khi bấm Chạy, và xoá các lượt cũ khi bấm "Xoá các lượt cũ hơn".
Gọi Weaviate chỉ khi người vận hành bấm: đọc vector và ô thử truy vấn (embed bằng e5-small, xếp hạng cosine trên vector
của collection đích). Không bao giờ trả giá trị secret: biến kết nối chỉ báo đã đặt hay chưa.
"""
from __future__ import annotations

import argparse
import ast
import csv
import fcntl
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import alerts as run_alerts
import catalog_run_lock
import fresh_settings
import pipeline_graph as graph
from collectors import live_control
from collectors.geo import normalise_destination
from normalise import STAGES as STAGE_LABELS
from fresh_run_log import HISTORY_FILE, LOG_FILE, RUN_FILE, RUNNING_FILE, STOP_FILE, prune_runs, run_dirs, write_json

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "monitor_ui"
RUN_ID = re.compile(r"^(full|daily|index)-\d{8}T\d{6}Z-\d+$")
SOURCE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
LOG_NAME = re.compile(r"^(job\.log|crawl-\d{8}\.log|fresh-catalog-[0-9-]+\.log|fresh-catalog-errors\.log)$")
MAX_TEXT = 2_000_000          # ký tự tối đa trả về cho một file raw
MAX_READ = 30_000_000         # byte tối đa giải nén một file
HEARTBEAT_STALE = 90          # giây không có nhịp sống thì coi lượt đã chết
PROGRESS_RE = re.compile(r"(\d+)/(\d+) xong · (\d+) lỗi · (\d+) bỏ qua · ([\d.]+) trang/phút · còn ~(\S+)")
AGODA_PROGRESS_RE = re.compile(r"Agoda giá: (\d+)/(\d+) \(.*?ok (\d+), lỗi (\d+)\)")  # collectors/agoda_api.py, mỗi 50 lượt
AGODA_PLAN_RE = re.compile(r"Agoda: \d+ khách sạn có hotel_id, (\d+) lượt hỏi giá cần làm")
AGODA_FINAL_RE = re.compile(r"Agoda API: \{.*'priceOk': (\d+), 'priceNone': (\d+), 'failed': (\d+).*'tasks': (\d+)")
STATE_RE = re.compile(r"\] Trạng thái: (\{.*\})\s*$")  # dòng cuối của crawl.py: {'done': 120, 'gone': 7, ...}
VINPEARL_PROGRESS_RE = re.compile(r"Vinpearl (tour: )?(\d+)/(\d+)\b")  # khách sạn rồi vé/tour (collectors/vinpearl.py)
LOG_LINE_RE = re.compile(r"^(?P<at>\d{2}:\d{2}:\d{2}) (?:\[(?P<group>[a-z]+)\] )?(?P<rest>.*)$")
LEVEL_RE = re.compile(r"^\d{2}:\d{2}:\d{2} (WARNING|ERROR|CRITICAL)\b")
INNER_RE = re.compile(r"\[([a-z][a-z_]+)\]")
BLOCK_RE = re.compile(r"bị chặn|cloudflare|captcha|challenge|xác minh bạn là con người", re.I)
HTTP_RE = re.compile(r"(?:HTTP|trả|status)\s+(\d{3})\b")
STEP_RE = re.compile(r"catalog\.step\.(start|done) name=(\S+)")
STREAM_POLL = 0.5             # giây giữa hai lần đọc log khi stream
STREAM_END_IDLE = 5.0         # lượt đã xong và log đứng yên bấy nhiêu giây thì đóng stream
SILENT_SECONDS = 180          # nguồn đang chạy mà không có dòng log mới quá lâu thì báo "im lặng"
EMBED_QUERY_MAX = 500         # ký tự tối đa của câu thử truy vấn
VECTOR_CACHE_SECONDS = 120
# Nguồn, bước và quan hệ giữa chúng khai báo ở pipeline_graph.py (P3, docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md);
# các bảng dưới chỉ đổi dạng cho monitor. Sơ đồ luồng: docs/plan/2026-09-28-monitor-so-do-luong.md — job thêm bước mới mà
# chưa khai báo thì bước đó hiện ở cột "Bước khác", không bị ẩn.
# Nguồn của lượt: khoá cấu hình bật/tắt, bước trong run.json, thư mục raw/interim, nhóm log, khoá chỉnh live.
SOURCES = tuple({"key": src.key, "label": src.label, "setting": src.setting, "steps": src.steps, "dirs": src.interim,
                 "group": src.log_group, "live": src.live, "modes": src.modes} for src in graph.SOURCES)
STEP_OWNER = {name: src.key for name, src in graph.SOURCE_BY_STEP.items()}
GRAPH_COLUMNS = graph.COLUMNS
GRAPH_SINGLE = {step.id: (step.column, step.label) for step in graph.STEPS}
GRAPH_MODES = {step.id: step.modes for step in graph.STEPS}  # None = mọi chế độ
NORMALISE_SOURCE = graph.NORMALISE_SOURCE
STREAM_STEPS = {stream.id: stream.node for stream in graph.STREAMS}  # → ô
STREAM_LIVE = {stream.id: stream.label for stream in graph.STREAMS}
NORMALISE_ALL = graph.NORMALISE_ALL  # ô chung khi lượt không chuẩn hoá theo nguồn (lượt trước CP5, lượt daily)
RESUME_STEPS = graph.RESUME_STEPS
STEP_LABELS = graph.STEP_LABELS
# Bước con bên trong Chuẩn hoá / Gộp (tên = normalise.StepClock, normalise_stream): nhãn + việc nó làm (UI2b).
SUBSTEP_INFO = {
    "đọc interim": "Đọc file interim của nguồn; bản ghi trùng khoá thì giữ bản cào mới nhất (vé máy bay: gom lịch sử giá "
                   "theo tuyến).",
    "ánh xạ nguồn": "Chuyển từng bản ghi interim sang 13 trường catalog (khách sạn + hạng phòng, vé, điểm tham quan, tuyến "
                    "bay, combo). Bản ghi lỗi bị bỏ và ghi vào errors.jsonl. Ở bước Gộp: chỉ ánh xạ lại nguồn chưa có "
                    "checkpoint còn mới.",
    "đọc checkpoint": "Đọc kết quả ánh xạ của mọi nguồn (normalised/<nguồn>.jsonl), dựng lại danh sách khách sạn, phòng, vé, "
                      "điểm tham quan theo đúng thứ tự xử lý.",
    "sửa điểm đến, toạ độ": "Sửa điểm đến theo bằng chứng (destination_overrides.csv), đánh dấu khách sạn có toạ độ đáng "
                            "ngờ, áp toạ độ sửa tay (location_overrides.csv).",
    "gộp trùng khách sạn": "Ghép cùng một khách sạn giữa Vinpearl, booking, agoda, Trip theo tên gần giống và khoảng cách; "
                           "giữ một dòng, ref của nguồn kia vào sameAs, gộp hạng phòng.",
    "vé và điểm tham quan": "Dựng vé Vinpearl và điểm tham quan trip.com / booking; ghép vé với điểm tham quan cùng địa điểm "
                            "(danh sách venues).",
    "vé máy bay, combo": "Dựng tuyến bay và chuyến bay (trip.com, booking), combo bay + ở của trip.com và combo Vinpearl.",
    "lọc": "Loại sản phẩm đã soát tay (excluded_products.csv), điểm không phải du lịch, sản phẩm không đặt được, ngoài kế "
           "hoạch điểm đến, trùng id hoặc thiếu tên / loại lạ.",
    "làm giàu": "Chuẩn hoá thuộc tính, dựng mô tả tiếng Việt từ thuộc tính, gộp biến thể giá thành viên Vinpearl vào "
                "memberPrices của vé gốc.",
    "kiểm vị trí, giá": "Chốt toạ độ; xoá dòng con mồ côi. Cảnh báo vị trí, thiếu toạ độ, giá phòng phi lý bị xoá nếu tắt "
                        "cờ giữ lại (job cào mới đang giữ lại cả ba).",
    "ghi output": "Ghi products.jsonl, báo cáo gộp trùng, dòng bị loại và số liệu từng bước.",
    # chạy liên tục (normalise_stream), một lô
    "đọc phần mới": "Đọc các dòng interim mới từ lần trước (chỉ dòng đã ghi xong; file bị ghi lại thì đọc lại từ đầu).",
    "bỏ trùng theo khoá": "Bỏ trùng trên mọi bản ghi đã đọc của nguồn: trùng khoá thì giữ bản cào mới nhất (vé máy bay: "
                          "gom lịch sử giá theo tuyến).",
    "ánh xạ bản ghi mới": "Chỉ ánh xạ bản ghi chưa gặp sang 13 trường; bản ghi đã ánh xạ ở lô trước được dùng lại.",
    "ghi checkpoint": "Ghi normalised/<nguồn>.jsonl, lỗi và meta cho bản nháp và bước Gộp chính thức dùng.",
}
# Trạng thái xấu nhất của một cột (dải bước ở Lịch sử): số lớn hơn là xấu hơn.
SEVERITY = {"notInMode": 0, "disabled": 1, "notRun": 2, "ok": 3, "skipped": 4, "waiting": 5, "draft": 6, "running": 6,
            "stopped": 7, "blocked": 8, "timeout": 8, "dead": 9, "error": 10}
RECRAWL_STATUSES = ("blocked", "timeout", "error")  # ô cào ở trạng thái này có nút "Cào lại nguồn này" (P4)
LIVE_LABELS = {"vinpearl": "Vinpearl", "trip": "trip.com vé máy bay + điểm tham quan", "booking": "booking.com",
               "agoda": "agoda.com", "tripHotels": "trip.com khách sạn (giá + thông tin)"}
# Loại sản phẩm theo (taxonomy, attributes.level) cho bảng theo thành phố.
PRODUCT_TYPES = {("hotel", "property"): "Khách sạn", ("hotel", "room"): "Hạng phòng",
                 ("attraction", None): "Điểm tham quan / vé", ("flight", "route"): "Tuyến bay",
                 ("flight", "flight"): "Chuyến bay", ("combo", None): "Combo", ("golf", None): "Golf"}
UNKNOWN_CITY = "(chưa rõ — xác định khi chuẩn hoá)"
# Số tab / worker chỉ đổi được ở Cấu hình, áp từ lượt sau (trình duyệt đã mở không đổi số tab giữa chừng).
NEXT_RUN_KEYS = ("crawl.parallelSites", "booking.tabs", "agoda.tabs", "tripHotels.httpWorkers", "tripHotels.priceTabs")
TRIP_PRICE_RE = re.compile(r"Trip (\d+)@(\d{4}-\d{2}-\d{2}): (\w+), (\d+) offers")
TRIP_META_RE = re.compile(r"Trip meta (\d+) lần \d: (HTTP \d+|lỗi)")
FAMILIES = {"vinpearl": ("vinpearl", "vinpearl_bundles"),
            "booking": ("booking_hotels", "booking_attractions", "booking_flights"),
            "agoda": ("agoda_hotels", "agoda_api"),
            "trip": ("trip_flights", "trip_attractions", "trip_hotels", "trip_combos", "trip_experiences")}
ID_KEYS = ("key", "hotelId", "poiId", "productId", "tourCode", "id", "slug", "hotelCode", "roomId", "code")
NAME_KEYS = ("name", "title", "hotelName", "productName", "tourName", "routeName")
PRICE_KEYS = ("minPrice", "price", "lowestPrice", "priceFrom", "adultPrice", "unitPrice", "amount")
SOURCE_LABELS = {
    "vinpearl": "Vinpearl", "vinpearl_bundles": "Vinpearl combo bay + ở",
    "trip_flights": "trip.com – vé máy bay", "trip_attractions": "trip.com – điểm tham quan",
    "trip_hotels": "trip.com – khách sạn", "booking_hotels": "booking.com – khách sạn",
    "agoda_hotels": "agoda.com – khách sạn", "agoda_api": "agoda.com (API)",
}
STEP_SOURCE = {"vinpearl": "vinpearl", "trip-flights": "trip_flights", "trip-attractions": "trip_attractions",
               "booking-hotels": "booking_hotels", "agoda-hotels": "agoda_hotels",
               "trip-hotels.discover": "trip_hotels", "trip-hotels.prices": "trip_hotels"}


# ---------------------------------------------------------------------------------------------------- tiện ích


def prefixed(params: dict, prefix: str) -> dict:
    """`f.cột=giá trị` → {cột: giá trị}; giá trị `\\N` = NULL (bộ lọc / khoá của tab DB)."""
    return {k[len(prefix):]: (None if v == "\\N" else v) for k, v in params.items() if k.startswith(prefix)}


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def tail_lines(path: Path, n: int, chunk: int = 256 * 1024) -> list[str]:
    """n dòng cuối của file text lớn, không đọc cả file. Dòng đầu có thể cụt nên bỏ nếu chưa đọc tới đầu file."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            data, pos = b"", size
            while pos > 0 and data.count(b"\n") <= n:
                step = min(chunk, pos)
                pos -= step
                fh.seek(pos)
                data = fh.read(step) + data
        lines = data.decode("utf-8", errors="replace").split("\n")  # không dùng splitlines(): cắt cả ở U+2028 trong JSON
        if lines and lines[-1] == "":
            lines.pop()
        if pos > 0 and lines:
            lines = lines[1:]
        return lines[-n:]
    except OSError:
        return []


def pid_alive(pid: int) -> bool:
    """os.kill(pid, 0) vẫn thành công với tiến trình zombie (cha chưa "nhận xác") — kiểm thêm /proc/{pid}/stat để không coi
    zombie là còn sống (gặp thật 22/09/2026: giao diện báo "đang chạy" mãi dù tiến trình đã chết)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform == "linux":
        try:
            stat = (Path(f"/proc/{pid}/stat")).read_text(encoding="utf-8")
            state = stat[stat.rindex(")") + 2]  # "pid (tên có thể chứa dấu ngoặc) TRẠNG_THÁI ..."
            return state != "Z"
        except (OSError, ValueError, IndexError):
            return False
    return True


def dir_size(path: Path, limit_files: int = 200_000) -> tuple[int, int]:
    """(số file, tổng byte) của một thư mục, đệ quy."""
    files = size = 0
    stack = [path]
    while stack and files < limit_files:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(Path(e.path))
                    elif e.is_file(follow_symlinks=False):
                        files += 1
                        size += e.stat(follow_symlinks=False).st_size
        except OSError:
            continue
    return files, size


def lock_busy(state_dir: Path) -> bool:
    path = catalog_run_lock.lock_file(state_dir)
    if not path.exists():
        return False
    try:
        with path.open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        return False
    return False


def age_seconds(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


def read_text(path: Path, limit: int = MAX_READ) -> tuple[str, bool]:
    """Nội dung file (tự giải nén .gz), cắt ở `limit` byte. → (text, bị cắt?)"""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:
        data = fh.read(limit + 1)
    return data[:limit].decode("utf-8", errors="replace"), len(data) > limit


def iter_jsonl(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            for index, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield index, json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def first_value(record: dict, keys) -> object:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def record_ids(record: dict) -> set[str]:
    ids = {str(record[k]) for k in ID_KEYS if record.get(k) not in (None, "", [], {}) and not isinstance(record[k], (dict, list))}
    if record.get("fromCode") and record.get("toCode"):
        ids.add(f"{record['fromCode']}-{record['toCode']}")
    return ids


def ref_parts(ref: str) -> tuple[str, str, str]:
    """`booking:hotel:123:room:abc` → (booking, hotel, 123). Combo Trip: `trip:combo:…` giữ phần sau `trip:`."""
    parts = ref.split(":")
    family = parts[0] if parts else ""
    kind = parts[1] if len(parts) > 1 else ""
    if family == "trip" and kind == "combo":
        return family, kind, ref[len("trip:"):]
    return family, kind, parts[2] if len(parts) > 2 else ""


def safe_name(name: str, pattern: re.Pattern, what: str) -> str:
    if not name or not pattern.match(name):
        raise ValueError(f"{what} không hợp lệ")
    return name


def brief_record(record: dict) -> dict:
    rooms = record.get("rooms")
    return {
        "name": first_value(record, NAME_KEYS),
        "id": first_value(record, ID_KEYS),
        "recordType": record.get("recordType"),
        "destination": record.get("destination") or (record.get("plan") or {}).get("destination"),
        "price": first_value(record, PRICE_KEYS),
        "currency": record.get("currency"),
        "rooms": len(rooms) if isinstance(rooms, list) else None,
        "url": record.get("url") or record.get("detailUrl"),
        "crawledAt": record.get("crawledAt"),
    }


def brief_product(row: dict) -> dict:
    attrs = row.get("attributes") or {}
    return {
        "productId": row.get("productId"), "name": row.get("name"), "taxonomy": row.get("taxonomy"),
        "level": attrs.get("level"), "destination": row.get("destination"), "unitPrice": row.get("unitPrice"),
        "available": row.get("available"), "availableFrom": row.get("availableFrom"), "availableTo": row.get("availableTo"),
        "sourceRef": row.get("sourceRef"), "sameAs": len(attrs.get("sameAs") or []),
        "priceSource": (attrs.get("fieldSources") or {}).get("unitPrice"),
        "hasImage": bool(row.get("imageUrl")), "descriptionChars": len(row.get("description") or ""),
    }


def page(rows: list, offset: int, limit: int) -> dict:
    offset = max(0, offset)
    limit = max(1, min(limit, 500))
    return {"total": len(rows), "offset": offset, "limit": limit, "rows": rows[offset:offset + limit]}


class FileCache:
    """Kết quả đọc file lớn (interim, products) theo (đường dẫn, mtime, cỡ, kiểu đọc). `kind` phân biệt các cách đọc khác
    nhau của cùng một file (vd. đếm dòng interim cho bảng nguồn và đọc bản ghi interim để truy vết)."""

    def __init__(self, size: int = 24):
        self.size, self.items, self.lock = size, {}, threading.Lock()

    def get(self, path: Path, loader, kind: str = "rows"):
        try:
            st = path.stat()
        except OSError:
            return None
        key = (str(path), st.st_mtime_ns, st.st_size, kind)
        with self.lock:
            if key in self.items:
                return self.items[key]
        value = loader(path)
        with self.lock:
            if len(self.items) >= self.size:
                self.items.pop(next(iter(self.items)))
            self.items[key] = value
        return value


# ---------------------------------------------------------------------------------------------------- dữ liệu


def _new_stat() -> dict:
    return {"lines": 0, "warnings": 0, "errors": 0, "blocks": 0, "http": Counter(), "lastAt": None, "lastLine": None,
            "progress": None, "result": None, "live": None, "tripPrices": Counter(), "tripMeta": Counter()}


def _age_of_clock(clock: str | None) -> float | None:
    """Tuổi (giây) của mốc HH:MM:SS giờ máy trong log; qua nửa đêm thì cộng một ngày."""
    if not clock:
        return None
    try:
        hh, mm, ss = (int(x) for x in clock.split(":"))
    except ValueError:
        return None
    now = datetime.now()
    age = (now.hour * 3600 + now.minute * 60 + now.second) - (hh * 3600 + mm * 60 + ss)
    return age + 86400 if age < 0 else age


class LogScan:
    """Quét job.log của một lượt theo kiểu tăng dần (nhớ vị trí đã đọc) → số liệu theo nguồn cho bảng tình trạng.

    Dòng của tiến trình crawl.py có tiền tố [nhóm] (fresh_catalog.run_source); nhóm trip chạy tuần tự vé máy bay rồi điểm
    tham quan nên dòng không có tag nguồn bên trong được gán cho bước trip đang chạy. Dòng khách sạn Trip (chạy trong tiến
    trình chính) nhận ra qua "Trip meta …" / "Trip <id>@<ngày>: …"."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self._reset(None)

    def _reset(self, inode) -> None:
        self.offset = 0
        self.inode = inode
        self.partial = b""
        self.stats = {src["key"]: _new_stat() for src in SOURCES}
        self.current: dict[str, str] = {}
        self.groups: dict[str, dict] = {}

    def update(self) -> "LogScan":
        with self.lock:
            try:
                st = self.path.stat()
            except OSError:
                return self
            if st.st_ino != self.inode or st.st_size < self.offset:
                self._reset(st.st_ino)
            if st.st_size == self.offset:
                return self
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = self.partial + fh.read(st.st_size - self.offset)
                self.offset = fh.tell()
            lines = data.split(b"\n")
            self.partial = lines.pop()
            for raw in lines:
                self._line(raw.decode("utf-8", errors="replace"))
            return self

    def _owner(self, group: str | None, rest: str) -> str | None:
        if group == "trip":
            inner = INNER_RE.search(rest)
            if inner and inner.group(1) in ("trip_flights", "trip_attractions"):
                return "tripFlights" if inner.group(1) == "trip_flights" else "tripAttractions"
            return self.current.get("trip", "tripFlights")
        if group:
            return next((src["key"] for src in SOURCES if src["group"] == group), None)
        if rest.startswith("Trip meta ") or TRIP_PRICE_RE.search(rest) or "[trip_hotels" in rest:
            return "tripHotels"
        return None

    def _line(self, line: str) -> None:
        match = LOG_LINE_RE.match(line)
        if not match:
            return
        at, group, rest = match.group("at"), match.group("group"), match.group("rest")
        if not group:
            step = STEP_RE.search(rest)
            if step and step.group(2) in ("trip-flights", "trip-attractions") and step.group(1) == "start":
                self.current["trip"] = STEP_OWNER[step.group(2)]
            event = re.match(r"catalog\.group\.(start|done|skip) name=(\w+)(?: status=(\w+))?", rest)
            if event:
                kind, name, status = event.groups()
                self.groups[name] = {"event": kind, "status": status or kind, "at": at}
                return
        owner = self._owner(group, rest)
        if owner is None:
            return
        stat = self.stats[owner]
        stat["lines"] += 1
        stat["lastAt"], stat["lastLine"] = at, rest[-400:]
        level = LEVEL_RE.match(rest)
        if level:
            stat["warnings" if level.group(1) == "WARNING" else "errors"] += 1
        elif rest.startswith("Traceback") or " Error: " in rest:
            stat["errors"] += 1
        if BLOCK_RE.search(rest):
            stat["blocks"] += 1
        for code in HTTP_RE.findall(rest):
            stat["http"][code] += 1
        progress = PROGRESS_RE.search(rest)
        if progress:
            done, total, failed, skipped, rate, eta = progress.groups()
            stat["progress"] = {"done": int(done), "total": int(total), "failed": int(failed), "skipped": int(skipped),
                                "perMinute": float(rate), "eta": eta,
                                "processed": int(done) + int(failed) + int(skipped)}
        plan = AGODA_PLAN_RE.search(rest)
        if plan:  # tổng lượt hỏi giá biết trước; dòng tiến độ chỉ ghi mỗi 50 lượt
            stat["progress"] = {"done": 0, "total": int(plan.group(1)), "failed": 0, "skipped": 0, "processed": 0}
        agoda = AGODA_PROGRESS_RE.search(rest)
        if agoda:
            processed, total, ok, failed = map(int, agoda.groups())
            stat["progress"] = {"done": ok, "total": total, "failed": failed, "skipped": max(processed - ok - failed, 0),
                                "processed": processed}
        state = STATE_RE.search(rest)
        if state:  # tổng theo URL duy nhất (dòng tiến độ cộng cả lượt thử lại vào tổng)
            try:
                counts = {k: v for k, v in ast.literal_eval(state.group(1)).items() if isinstance(v, int)}
            except (ValueError, SyntaxError):
                counts = {}
            if sum(counts.values()):
                stat["result"] = {"ok": counts.get("done", 0), "total": sum(counts.values()),
                                  "failed": counts.get("failed", 0) + counts.get("blocked", 0)}
        final = AGODA_FINAL_RE.search(rest)
        if final:  # hết hàng (priceNone) là kết quả hợp lệ, không phải lỗi
            ok, none, failed, tasks = map(int, final.groups())
            stat["result"] = {"ok": ok + none, "total": tasks, "failed": failed}
        vinpearl = VINPEARL_PROGRESS_RE.search(rest) if owner == "vinpearl" else None
        if vinpearl:
            done, total = int(vinpearl.group(2)), int(vinpearl.group(3))
            stat["progress"] = {"done": done, "total": total, "failed": 0, "skipped": 0, "processed": done,
                                "phase": "vé/tour" if vinpearl.group(1) else "khách sạn"}
        if "live.control" in rest:
            stat["live"] = rest[rest.index("live.control"):][:200]
        price = TRIP_PRICE_RE.search(rest)
        if price:
            stat["tripPrices"][price.group(3)] += 1
        meta = TRIP_META_RE.search(rest)
        if meta:
            stat["tripMeta"]["ok" if meta.group(2) == "HTTP 200" else "failed"] += 1


def product_type(row: dict) -> str:
    taxonomy, level = row.get("taxonomy"), (row.get("attributes") or {}).get("level")
    return PRODUCT_TYPES.get((taxonomy, level)) or PRODUCT_TYPES.get((taxonomy, None)) or f"{taxonomy}/{level or '-'}"


def interim_city(record: dict) -> str:
    """Thành phố của một bản ghi interim khi đang cào: điểm đến trong kế hoạch cào (booking, agoda, điểm tham quan Trip),
    thành phố đến (vé máy bay), tên địa điểm (vé Vinpearl), thành phố (khách sạn Trip). Khách sạn Vinpearl không có trường
    nào: thành phố chỉ xác định ở bước chuẩn hoá (địa chỉ, toạ độ)."""
    plan = record.get("plan") or {}
    return normalise_destination(plan.get("destination"), record.get("destination"), record.get("toCity"),
                                 record.get("destinationName"), record.get("city")) or UNKNOWN_CITY


class InterimTally:
    """Đếm bản ghi interim theo thành phố, đọc tăng dần (nhớ vị trí); file bị ghi lại từ đầu (đổi inode/nhỏ đi) thì đếm lại."""

    def __init__(self, path: Path):
        self.path, self.lock = path, threading.Lock()
        self.inode, self.offset, self.partial, self.counts = None, 0, b"", Counter()

    def update(self) -> Counter:
        with self.lock:
            try:
                st = self.path.stat()
            except OSError:
                return Counter()
            if st.st_ino != self.inode or st.st_size < self.offset:
                self.inode, self.offset, self.partial, self.counts = st.st_ino, 0, b"", Counter()
            if st.st_size > self.offset:
                with open(self.path, "rb") as fh:
                    fh.seek(self.offset)
                    data = self.partial + fh.read(st.st_size - self.offset)
                    self.offset = fh.tell()
                lines = data.split(b"\n")
                self.partial = lines.pop()
                for raw in lines:
                    try:
                        record = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(record, dict):
                        self.counts[interim_city(record)] += 1
            return Counter(self.counts)


def stem_lanes(stem: str, group: str | None = None) -> list[str]:
    """Làn (nguồn cào trong SOURCES) sinh ra file interim `stem`: khớp thư mục trước, không có thì theo họ nguồn."""
    exact = [s["key"] for s in SOURCES if stem in s["dirs"]]
    if exact:
        return exact
    family = group or next((f for f, stems in FAMILIES.items() if stem in stems), None)
    return [s["key"] for s in SOURCES
            if family and (s["group"] == family or any(d in FAMILIES.get(family, ()) for d in s["dirs"]))]


def graph_focus(nodes: list[dict], data: dict) -> tuple[str | None, dict | None]:
    """UI3: ô chọn sẵn khi mở lượt + lỗi cho dải báo ở đầu sơ đồ.

    Có ô lỗi / mất tiến trình → ô đầu tiên theo thứ tự cột (bị chặn xếp sau lỗi); lượt đang chạy → ô đang chạy xa nhất;
    còn lại → ô cuối cùng đã chạy. Dải báo: ô lỗi đầu tiên, hoặc lỗi của cả lượt nếu không ô nào mang lỗi."""
    bad = [n for n in nodes if n["status"] in ("error", "dead")] or [n for n in nodes if n["status"] == "blocked"]
    problem = None
    if bad:
        focus = bad[0]["id"]
        problem = {k: bad[0].get(k) for k in ("id", "label", "status", "errorKind", "error")}
    elif data.get("status") == "running":
        live = [n for n in nodes if n["status"] in ("running", "draft")]
        focus = live[-1]["id"] if live else None
    else:
        ran = [n for n in nodes if n["status"] not in ("notInMode", "disabled", "notRun", "waiting")]
        focus = ran[-1]["id"] if ran else None
    if problem is None and data.get("error") and data.get("status") in ("failed", "dead", "partial"):
        problem = {"id": None, "label": "Cả lượt", "status": data.get("status"), "errorKind": data.get("errorKind"),
                   "error": data.get("error")}
    return focus, problem


def graph_strip_detail(nodes: list[dict]) -> dict[str, list[list[str]]]:
    """UI4: từng ô (nhãn, trạng thái) của mỗi cột, trừ ô mờ, để di chuột trên dải bước ở Lịch sử."""
    out: dict[str, list[list[str]]] = {}
    for node in nodes:
        if node["col"] != "other" and node["status"] not in ("notInMode", "disabled"):
            out.setdefault(node["col"], []).append([node["label"], node["status"]])
    return out


# Số bước con của các bước lớn khi đang chạy (để tô tiến độ = số bước con đã xong / tổng), theo danh sách khai báo ở
# pipeline_graph.SUBSTEPS. Vé thương gia mô phỏng / dữ liệu demo không phải bước xử lý nên không có bước con.
EXPECTED_SUBSTEPS = {name: len(plan) for name, plan in graph.SUBSTEPS.items()}
GOOD_STATUSES = ("ok", "partial", "skipped")
PENDING_STATUSES = ("waiting", "notRun", "notInMode", "disabled")  # ô chưa chạy / không chạy ở lượt này


def percent(ok, total) -> float | None:
    return round(100 * ok / total, 1) if isinstance(ok, (int, float)) and isinstance(total, (int, float)) and total > 0 \
        else None


def substep_view(entry: dict) -> dict:
    """Một bước con cho sơ đồ: vào → ra, đạt/tổng và % tô màu. Bước có đạt/tổng (vd. dòng ghép được với DB) tô theo tỉ lệ đó;
    bước biến đổi (lọc, gộp trùng: ra ít hơn vào là bình thường) xong thì tô đủ; đang chạy thì chưa có %."""
    status = entry.get("status") or "unknown"
    pct = percent(entry.get("ok"), entry.get("total"))
    if pct is None and status in GOOD_STATUSES:
        pct = 100.0
    # normalise.StepClock ghi rowsIn/rowsOut/peakRssMb; stage_log.Stages ghi in/out
    return {"name": entry.get("name"), "status": status, "seconds": entry.get("seconds"),
            "in": entry.get("in", entry.get("rowsIn")), "out": entry.get("out", entry.get("rowsOut")),
            "changed": entry.get("changed"),
            "ok": entry.get("ok"), "total": entry.get("total"), "note": entry.get("note"), "error": entry.get("error"),
            "ramMb": entry.get("peakRssMb"), "percent": pct, "description": SUBSTEP_INFO.get(entry.get("name"))}


def with_plan(views: list[dict], plan: tuple[str, ...], node_status: str) -> list[dict]:
    """Chuỗi bước con theo thứ tự `plan` (pipeline_graph.SUBSTEPS) để bước chưa chạy không bị ẩn: bước đã chạy giữ số liệu
    thật; bước chưa có số liệu là ô mờ (`planned`) mang trạng thái của ô lớn nếu ô chưa chạy (Chờ tới lượt / Không chạy /
    Không thuộc lượt / Đã tắt), "waiting" nếu nằm sau bước con mới nhất của ô đang chạy, "noData" nếu ô đã xong (ok /
    partial) mà không ghi bước con nào (lượt trước khi job ghi số liệu bước con: bước con đã chạy, chỉ thiếu số liệu), còn
    lại "notRun" (lượt này không chạy bước con đó). Bước con ngoài kế hoạch (vd. index bị hoãn) giữ ở cuối."""
    if not plan:
        return views
    unrecorded = not views and node_status in ("ok", "partial")
    done = {v["name"] for v in views}
    reached = max((plan.index(v["name"]) for v in views if v["name"] in plan), default=-1)
    out = []
    for index, name in enumerate(plan):
        if name in done:
            out.extend(v for v in views if v["name"] == name)
            continue
        if node_status in PENDING_STATUSES:
            status = node_status
        elif unrecorded:
            status = "noData"
        else:
            status = "waiting" if node_status in ("running", "draft") and index > reached else "notRun"
        out.append({**substep_view({"name": name, "status": status}), "planned": True})
    return out + [v for v in views if v["name"] not in plan]


def node_progress(node: dict, *, done=None, total=None, running: bool = False) -> None:
    """`node.progress`: đang chạy → đã làm / tổng (kind progress); xong → phần thành công / tổng (kind result). Không có số
    thì ô xong tô đủ, ô lỗi không tô; ô đang chạy không biết tổng thì để trống (giao diện hiện sọc chạy)."""
    pct = percent(done, total)
    if pct is None and not running:
        pct = 100.0 if node["status"] in GOOD_STATUSES else (0.0 if node["status"] in ("error", "dead", "failed") else None)
    node["progress"] = {"done": done, "total": total, "percent": pct, "kind": "progress" if running else "result"}


def running_substep(steps_file: Path) -> str | None:
    """Tên bước con đang chạy trong steps.json của normalise.StepClock (None nếu không có)."""
    steps = (read_json(steps_file) or {}).get("steps") or []
    return next((st.get("name") for st in reversed(steps) if st.get("status") == "running"), None)


def graph_strip(nodes: list[dict]) -> dict[str, str | None]:
    """Trạng thái xấu nhất của từng cột sơ đồ (dải bước ở Lịch sử); cột "Bước khác" không nằm trong dải."""
    worst: dict[str, str] = {}
    for node in nodes:
        current = worst.get(node["col"])
        if current is None or SEVERITY.get(node["status"], SEVERITY["running"]) > SEVERITY.get(current, SEVERITY["running"]):
            worst[node["col"]] = node["status"]
    return {col: worst.get(col) for col, _ in GRAPH_COLUMNS}


class FreshMonitor:
    def __init__(self, state_dir: Path, run_root: Path, log_dir: Path | None = None):
        self.state_dir, self.run_root = Path(state_dir), Path(run_root)
        self.log_dir = Path(log_dir) if log_dir else None
        self.cache = FileCache()
        self.spawn_lock = threading.Lock()
        self.spawned: dict | None = None
        self._disk = (0.0, None)
        self._scans: dict[str, LogScan] = {}
        self._tallies: dict[str, InterimTally] = {}
        self._vectors: dict = {}
        self._vector_lock = threading.Lock()

    # -- lượt đang chạy
    def running(self) -> dict | None:
        info = read_json(self.state_dir / RUNNING_FILE) or {}
        busy = lock_busy(self.state_dir)
        spawned = self.spawned
        if not busy:
            if spawned and spawned.get("returncode") is None and pid_alive(spawned["pid"]):
                return {"starting": True, "mode": spawned["mode"], "startedAt": spawned["startedAt"], "trigger": "monitor"}
            return None
        heartbeat = age_seconds(info.get("heartbeatAt"))
        out = dict(info)
        out["heartbeatAgeSeconds"] = None if heartbeat is None else round(heartbeat)
        out["stale"] = heartbeat is not None and heartbeat > HEARTBEAT_STALE
        if info.get("runId"):
            out["progress"] = self.progress(info["runId"])
        return out

    def progress(self, run_id: str) -> dict:
        """Tiến độ từ log của lượt: dòng x/y mới nhất của từng nhóm, số lần hỏi giá / thông tin Trip."""
        path = self.run_path(run_id) / LOG_FILE
        groups: dict[str, dict] = {}
        trip = Counter()
        meta = Counter()
        for line in tail_lines(path, 4000):
            group = re.search(r"\[([a-z]+)\]", line)
            match = PROGRESS_RE.search(line)
            if match:
                done, total, failed, skipped, rate, eta = match.groups()
                groups[group.group(1) if group else "-"] = {
                    "done": int(done), "total": int(total), "failed": int(failed), "skipped": int(skipped),
                    "perMinute": float(rate), "eta": eta, "line": line[-300:]}
            price = TRIP_PRICE_RE.search(line)
            if price:
                trip[price.group(3)] += 1
            info = TRIP_META_RE.search(line)
            if info:
                meta["ok" if info.group(2) == "HTTP 200" else "failed"] += 1
        return {"groups": groups, "tripPrices": dict(trip), "tripMeta": dict(meta)}

    # -- tổng quan
    def overview(self) -> dict:
        described = fresh_settings.describe(self.state_dir)
        values = {f["key"]: f["value"] for f in described["fields"]}
        try:
            upcoming = fresh_settings.next_run(values, self.state_dir) if not described["error"] else None
        except (KeyError, ValueError):
            upcoming = None
        targets = read_json(self.state_dir / "trip_targets.json", {}) or {}
        now = time.monotonic()
        if now - self._disk[0] > 60 or self._disk[1] is None:
            self._disk = (now, dir_size(self.run_root)[1] if self.run_root.is_dir() else 0)
        spawned = dict(self.spawned) if self.spawned else None
        if spawned and spawned.get("returncode") not in (None, 0):
            spawned["launchLog"] = tail_lines(self.state_dir / "monitor-launch.log", 12)
        return {
            "now": datetime.now().astimezone().isoformat(timespec="seconds"),
            "running": self.running(),
            "nextRun": upcoming,
            "settingsError": described["error"],
            "schedule": {k: values.get(k) for k in ("schedule.enabled", "schedule.time", "schedule.fullEveryDays",
                                                     "schedule.dailyEnabled")},
            "lastFull": str(fresh_settings.last_full_date(self.state_dir) or "") or None,
            "tripHotelIds": len(targets.get("hotels") or []),
            "runs": self.runs(limit=12),
            "diskBytes": self._disk[1],
            "env": described["env"],
            "targets": self.targets(),
            "spawned": spawned,
            "runnerLogs": self.runner_logs()[:8],
            "alerts": self.alerts(limit=30),
            "stream": {k: values.get(k) for k in ("stream.enabled", "stream.db", "stream.index")},
            "sla": self.sla(values),
        }

    # -- cảnh báo và SLA (CP7, CP8)
    def alerts(self, limit: int = 200, include_suppressed: bool = False) -> list[dict]:
        """Cảnh báo mới nhất trước, từ <state>/alerts.jsonl (bỏ cảnh báo bị chặn vì trùng trong thời gian chờ)."""
        items = run_alerts.read_alerts(self.state_dir / run_alerts.ALERTS)
        if not include_suppressed:
            items = [a for a in items if not a.get("suppressed")]
        return items[::-1][:limit]

    def sla(self, values: dict | None = None) -> dict:
        try:
            if values is None:
                values = {f["key"]: f["value"] for f in fresh_settings.describe(self.state_dir)["fields"]}
            return run_alerts.sla_status(self.state_dir, self.run_root, values)
        except Exception as exc:  # cấu hình lỗi, file hỏng: vẫn hiện phần còn lại của trang
            return {"enabled": False, "error": f"{type(exc).__name__}: {exc}"[:300], "rules": []}

    def dbx(self):
        """Tab "DB": xem toàn bộ database đích (chỉ đọc; docs/prd/deployment-plan.md §5)."""
        from db_browser import DbBrowser
        db_target = os.environ.get("DB_TARGET", "local")
        url = os.environ.get("SEED_DATABASE_URL" if db_target == "local" else "CLOUD_SEED_DATABASE_URL") or ""
        if not url:
            raise ValueError("Monitor chưa có kết nối DB (SEED_DATABASE_URL / CLOUD_SEED_DATABASE_URL)")
        if getattr(self, "_dbx", None) is None or self._dbx.url != url:
            self._dbx = DbBrowser(url)
        return self._dbx

    def backend_calls(self, after: int = 0, limit: int = 200) -> dict:
        """Lần gọi web / agent gần nhất từ backend (`GET /internal/calls`, docs/prd/deployment-plan.md §5)."""
        import urllib.error
        import urllib.parse
        import urllib.request
        raw = os.environ.get("BACKEND_URL")
        if raw is not None and not raw.strip():  # BACKEND_URL được đặt nhưng trống: tắt realtime (staging-ha, không gọi gì)
            return {"disabled": True, "reason": "BACKEND_URL trống: monitor này không đọc realtime từ backend",
                    "lastSeq": 0, "startedAt": None, "catalog": {}, "summary": [], "events": [], "backend": None}
        base = (raw or "http://127.0.0.1:8000").rstrip("/")
        query = urllib.parse.urlencode({"after": max(0, int(after)), "limit": max(1, min(int(limit), 1000))})
        try:
            with urllib.request.urlopen(f"{base}/internal/calls?{query}", timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ValueError(f"Backend trả HTTP {exc.code} cho /internal/calls (bản backend chưa có đo lần gọi?)") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ValueError(f"Không gọi được backend {base}: {getattr(exc, 'reason', exc)}") from None
        return {**data, "backend": base}

    def targets(self) -> dict:
        """Nơi lượt kế tiếp sẽ ghi (host/database/collection, không có tài khoản hay mật khẩu)."""
        db_target = os.environ.get("DB_TARGET", "local")
        url = os.environ.get("SEED_DATABASE_URL" if db_target == "local" else "CLOUD_SEED_DATABASE_URL") or ""
        out = {"dbTarget": db_target, "localOnly": os.environ.get("CATALOG_LOCAL_ONLY") == "1",
               "db": _where(url) if url else None, "weaviate": None, "collection": None, "error": None}
        try:
            settings = self._index_settings()
            out.update(weaviate=_where(settings.weaviate_url), collection=settings.vector_collection)
        except Exception as exc:  # thiếu env, backend chưa cài…: vẫn hiện phần còn lại
            out["error"] = str(exc)[:300]
        return out

    # -- danh sách lượt
    def run_path(self, run_id: str) -> Path:
        safe_name(run_id, RUN_ID, "Mã lượt")
        path = self.run_root / run_id
        if not path.is_dir():
            raise ValueError(f"Không còn dữ liệu của lượt {run_id} (đã quá số lượt giữ lại)")
        if path.is_symlink() or self.run_root.resolve() not in path.resolve().parents:
            raise ValueError("Đường dẫn lượt không hợp lệ")
        return path

    def runs(self, limit: int = 60) -> list[dict]:
        retained = {p.name: p for p in run_dirs(self.run_root)}
        out: dict[str, dict] = {}
        for _, summary in iter_jsonl(self.state_dir / HISTORY_FILE):
            if isinstance(summary, dict) and summary.get("id"):
                out[summary["id"]] = dict(summary, retained=False)
        running = read_json(self.state_dir / RUNNING_FILE) or {}
        busy = lock_busy(self.state_dir)
        for name, path in retained.items():
            data = read_json(path / RUN_FILE) or {"id": name, "status": "unknown"}
            entry = {k: data.get(k) for k in ("id", "mode", "trigger", "status", "startedAt", "finishedAt", "seconds",
                                               "exitCode", "error", "counts", "diskBytes")}
            entry["id"] = entry["id"] or name
            entry["retained"] = True
            entry["steps"] = [{k: s.get(k) for k in ("name", "group", "status", "seconds")} for s in data.get("steps") or []]
            if entry["status"] == "running" and not (busy and running.get("runId") == name):
                entry["status"] = "dead"  # tiến trình bị kill, không kịp ghi kết thúc
            nodes = self._graph_nodes(dict(data, status=entry["status"]), path)[0]
            entry["strip"], entry["stripDetail"] = graph_strip(nodes), graph_strip_detail(nodes)
            out[entry["id"]] = entry
        rows = sorted(out.values(), key=lambda r: r.get("startedAt") or "", reverse=True)
        previous: dict[str | None, int] = {}  # số sản phẩm của lượt trước cùng chế độ (duyệt từ cũ tới mới)
        for row in reversed(rows):
            products = ((row.get("counts") or {}).get("catalog") or {}).get("products")
            row["products"] = products
            before = previous.get(row.get("mode"))
            row["productsDelta"] = products - before if products is not None and before is not None else None
            if products is not None:
                previous[row.get("mode")] = products
        return rows[:limit]

    def run(self, run_id: str) -> dict:
        path = self.run_path(run_id)
        data = read_json(path / RUN_FILE) or {"id": run_id}
        if data.get("status") == "running":
            running = read_json(self.state_dir / RUNNING_FILE) or {}
            if not (lock_busy(self.state_dir) and running.get("runId") == run_id):
                data["status"] = "dead"
            else:
                data["progress"] = self.progress(run_id)
        data["sourcesData"] = self.sources(path)
        data["normalise"] = read_json(path / "normalise_report.json")
        data["artifacts"] = self.artifacts(path)
        data["logs"] = sorted(p.name for p in [path / LOG_FILE, *sorted((path / "logs").glob("crawl-*.log"))] if p.is_file())
        data["hasProducts"] = (path / "products.jsonl").is_file()
        data["hasDbReport"] = (path / "db_load.jsonl").is_file()
        data["hasStages"] = (path / "normalise_stages" / "stages.json").is_file()
        data["normaliseSteps"] = (read_json(path / "normalise_stages" / "steps.json") or {}).get("steps")
        data["preview"] = read_json(path / "preview" / "preview.json")
        data["hasEmbed"] = (path / "index_detail.jsonl").is_file()
        data["alerts"] = run_alerts.read_alerts(path / run_alerts.ALERTS)[::-1]
        data["index"] = read_json(path / "index_report.json")
        return data

    # -- sơ đồ luồng
    def graph(self, run_id: str) -> dict:
        """Ô và đường nối của một lượt, tính từ run.json + checkpoint chuẩn hoá (chỉ đọc)."""
        path = self.run_path(run_id)
        data = read_json(path / RUN_FILE) or {"id": run_id}
        if data.get("status") == "running" and not self._is_running(run_id):
            data["status"] = "dead"
        nodes, edges = self._graph_nodes(data, path, counts=True)
        columns = [{"id": col, "label": label} for col, label in GRAPH_COLUMNS]
        if any(n["col"] == "other" for n in nodes):
            columns.append({"id": "other", "label": "Bước khác"})
        if data.get("status") != "running":  # lượt đã kết thúc: ô sau bước cào chạy lại được (CP6)
            for node in nodes:
                options = graph.resume_options(node["id"])  # ô → các bước chạy lại được từ ô đó (CP6)
                src = graph.SOURCE_BY_STEP.get(node["id"])
                if src is not None and not (node["status"] in RECRAWL_STATUSES and data.get("mode") in src.modes
                                            and (not src.in_process or (path / "trip_targets.run.json").is_file())):
                    continue  # cào lại một nguồn (P4): chỉ bước cào hỏng; khách sạn Trip cần ID đã lưu của lượt
                if options and (data.get("mode") != "index" or node["id"] == "index"):
                    node["resume"] = list(options)
        focus, problem = graph_focus(nodes, data)
        return {"run": data.get("id") or run_id, "mode": data.get("mode"), "status": data.get("status"),
                "focus": focus, "problem": problem, "resumes": data.get("resumes") or [], "columns": columns, "lanes": [{"id": s["key"], "label": s["label"], "dirs": list(s["dirs"])} for s in SOURCES],
                "nodes": nodes, "edges": edges, "strip": graph_strip(nodes)}

    def substeps(self, run_id: str, node: str, variant: str = "") -> dict:
        """Bước con bên trong một ô Chuẩn hoá / Gộp (UI2b), kèm mô tả việc từng bước làm.

        `variant` của ô Gộp: "official" (normalise_stages/steps.json) hoặc "draft" (bản nháp mới nhất ở preview/);
        mặc định bản chính thức nếu đã có. Ô chuẩn hoá theo nguồn: "stream" (meta của chạy liên tục, kèm các lô) hoặc
        "process" (normalised/steps/<nguồn>/steps.json của tiến trình con)."""
        path = self.run_path(run_id)
        out: dict = {"node": node, "variant": None, "variants": [], "steps": [], "drafts": [], "batches": []}
        if node.startswith(NORMALISE_SOURCE):
            stem = safe_name(node[len(NORMALISE_SOURCE):], SOURCE_NAME, "Nguồn")
            meta = read_json(path / "normalised" / f"{stem}.meta.json") or {}
            if meta.get("batches"):
                out.update(variant="stream", steps=meta.get("steps") or [], batches=meta.get("history") or [])
            else:
                out.update(variant="process",
                           steps=(read_json(path / "normalised" / "steps" / stem / "steps.json") or {}).get("steps") or [])
        elif node in ("normalise", NORMALISE_ALL):
            data = read_json(path / RUN_FILE) or {}
            previews = [st for st in data.get("steps") or [] if st.get("name") == "normalise.preview"]
            out["drafts"] = [{"n": i + 1, "status": st.get("status"), "startedAt": st.get("startedAt"),
                              "seconds": st.get("seconds"), **{k: (st.get("detail") or {}).get(k)
                                                               for k in ("rows", "sources", "groups", "exitCode")}}
                             for i, st in enumerate(previews)]
            found = {}
            official = (read_json(path / "normalise_stages" / "steps.json") or {}).get("steps")
            if official:
                found["official"] = official
            draft = None
            if previews and previews[-1].get("status") == "running":
                draft = (read_json(path / "preview.next" / "normalise_stages" / "steps.json") or {}).get("steps")
            draft = draft or (read_json(path / "preview" / "normalise_stages" / "steps.json") or {}).get("steps")
            if draft:
                found["draft"] = draft
            out["variants"] = list(found)
            chosen = variant if variant in found else ("official" if "official" in found else next(iter(found), None))
            out.update(variant=chosen, steps=found.get(chosen) or [])
            if not out["steps"]:  # chưa gộp lần nào: hiện sẵn các bước con sẽ chạy (mờ), kèm mô tả
                status = ("notInMode" if data.get("mode") not in (GRAPH_MODES["normalise"] or (data.get("mode"),))
                          else "waiting" if data.get("status") == "running" else "notRun")
                out["steps"] = [{"name": name, "status": status, "planned": True}
                                for name in graph.planned_substeps("normalise")]
        else:
            raise ValueError("Ô này không có bước con")
        out["steps"] = [dict(st, description=SUBSTEP_INFO.get(st.get("name"))) for st in out["steps"]]
        return out

    def feed(self, run_id: str, kind: str) -> dict:
        """Các lô nạp DB / index theo phần của lượt (`db_batches.jsonl`, `index_batches.jsonl`), mới nhất trước."""
        name = {"db": "db_batches.jsonl", "index": "index_batches.jsonl"}.get(kind)
        if not name:
            raise ValueError("kind phải là db hoặc index")
        rows = [r for _, r in iter_jsonl(self.run_path(run_id) / name)]
        return {"kind": kind, "total": len(rows), "rows": rows[::-1][:200]}

    def _graph_nodes(self, data: dict, path: Path, counts: bool = False) -> tuple[list[dict], list[list[str]]]:
        """`counts=False` (dải bước ở Lịch sử): bỏ phần đếm interim, chỉ cần trạng thái."""
        mode, settings = data.get("mode"), data.get("settings") or {}
        dead = data.get("status") == "dead"
        pending = "waiting" if data.get("status") == "running" else "notRun"
        steps: dict[str, dict] = {}
        drafts = 0
        for st in data.get("steps") or []:
            name = st.get("name") or ""
            if name == "normalise.preview":
                drafts += 1
            else:
                steps[name] = st  # một bước chạy nhiều lần: lấy lần cuối
        nodes: list[dict] = []
        edges: list[list[str]] = []

        def absent(modes, setting: str | None = None) -> str:
            if modes is not None and mode not in modes:
                return "notInMode"
            if setting and settings.get(setting) is False:
                return "disabled"
            return pending

        def add(node_id: str, col: str, lane: str | None, label: str, st: dict | None, fallback: str) -> dict:
            node = {"id": node_id, "col": col, "lane": lane, "label": label, "status": fallback, "seconds": None,
                    "startedAt": None, "finishedAt": None, "in": None, "out": None, "errors": None, "retries": 0,
                    "errorKind": None, "error": None}
            if st:
                detail = st.get("detail") or {}
                status = st.get("status") or "unknown"
                node.update(status="dead" if status == "running" and dead else status, seconds=st.get("seconds"),
                            startedAt=st.get("startedAt"), finishedAt=st.get("finishedAt"), error=st.get("error"),
                            errorKind=st.get("errorKind") or detail.get("errorKind"),
                            retries=len(detail.get("attempts") or []))
            nodes.append(node)
            return node

        def single(name: str) -> dict:
            col, label = GRAPH_SINGLE[name]
            st = steps.get(name)
            return add(name, col, None, label, st, absent(GRAPH_MODES[name]))  # nhãn dài của bước: panel/Chi tiết bước

        def detail(name: str) -> dict:
            return (steps.get(name) or {}).get("detail") or {}

        prepare = single("maintain")
        prepare["out"] = detail("maintain").get("windowRows")

        tails: dict[str, str] = {}  # làn → ô cào cuối của làn
        for src in SOURCES:
            previous = prepare["id"]
            for name in src["steps"]:
                add(name, "crawl", src["key"], STEP_LABELS.get(name, name), steps.get(name),
                    absent(src["modes"], src["setting"]))
                edges.append([previous, name])
                previous = name
            tails[src["key"]] = previous
            if counts:
                files = [path / "interim" / f"{d}.jsonl" for d in src["dirs"]]
                files = [f for f in files if f.is_file()]
                if files:
                    nodes[-1]["out"] = sum(self._interim_count(f) for f in files)

        metas = {}
        folder = path / "normalised"
        for meta in sorted(folder.glob("*.meta.json")) if folder.is_dir() else []:
            metas[meta.name[:-len(".meta.json")]] = read_json(meta) or {}
        stems = [n[len(NORMALISE_SOURCE):] for n in steps if n.startswith(NORMALISE_SOURCE)]
        stems += [s for s in metas if s not in stems]
        merge_id = "normalise"
        for stem in stems:
            st = steps.get(NORMALISE_SOURCE + stem)
            lanes = stem_lanes(stem, (st or {}).get("group"))
            node = add(NORMALISE_SOURCE + stem, "normalise", lanes[0] if lanes else None,
                       SOURCE_LABELS.get(stem, stem), st, absent(GRAPH_MODES["normalise"]))
            meta, info = metas.get(stem) or {}, (st or {}).get("detail") or {}
            if not st and meta:  # "streaming": đang chuẩn hoá dần trong lúc cào (normalise_stream)
                streaming = "running" if data.get("status") == "running" else "stopped"
                node.update(status={"failed": "error", "streaming": streaming}.get(meta.get("status"), meta.get("status") or "unknown"),
                            seconds=meta.get("seconds"), error=meta.get("error"))
            node.update({"in": info.get("records", meta.get("records")), "out": info.get("rows", meta.get("rows")),
                         "errors": info.get("errors", meta.get("errors"))})
            edges.extend([tails[lane], node["id"]] for lane in lanes)
            edges.append([node["id"], merge_id])
        if not stems:
            merge_step = steps.get("normalise")
            node = add(NORMALISE_ALL, "normalise", None, "Chuẩn hoá (chung trong bước Gộp)", None,
                       (merge_step or {}).get("status") or absent(GRAPH_MODES["normalise"]))
            if node["status"] == "running" and dead:
                node["status"] = "dead"
            edges.extend([tail, NORMALISE_ALL] for tail in tails.values())
            edges.append([NORMALISE_ALL, merge_id])

        merge = single("normalise")
        previews = [st for st in data.get("steps") or [] if st.get("name") == "normalise.preview"]
        if previews:
            last = previews[-1]
            info = last.get("detail") or {}
            merge["draft"] = {"n": len(previews), "status": last.get("status"), "rows": info.get("rows"),
                              "groups": sorted(info.get("groups") or {}), "sources": info.get("sources") or [],
                              "at": last.get("finishedAt") or last.get("startedAt")}
            if not steps.get("normalise") and data.get("status") == "running":
                merge["status"] = "draft"  # chưa tới bản chính thức nhưng đã gộp nháp
        if counts:
            if merge["status"] == "running":
                merge["substep"] = running_substep(path / "normalise_stages" / "steps.json")
            elif previews and previews[-1].get("status") == "running":
                merge["substep"] = running_substep(path / "preview.next" / "normalise_stages" / "steps.json")
            for node in nodes:
                if node["id"].startswith(NORMALISE_SOURCE) and node["status"] == "running":
                    node["substep"] = running_substep(path / "normalised" / "steps" / node["id"][len(NORMALISE_SOURCE):]
                                                      / "steps.json")
        read = detail("normalise").get("recordsRead")  # normalise_report: số bản ghi theo từng nguồn
        merge.update({"in": sum(read.values()) if isinstance(read, dict) else read, "out": detail("normalise").get("rowsFinal"),
                      "drafts": drafts})
        single("validate")["out"] = detail("validate").get("products")
        single("db")["out"] = detail("db").get("dbRowsWritten")
        index = single("index")
        index.update({"in": detail("index").get("searchUnits"), "out": detail("index").get("embedded")})
        edges += [[dep, step.id] for step in graph.STEPS if step.id not in ("maintain", "normalise") for dep in step.deps]
        by_id = {n["id"]: n for n in nodes}
        for name, target in STREAM_STEPS.items():  # chạy liên tục (L6): lô của việc chạy suốt phần cào, gắn vào ô tương ứng
            st = steps.get(name)
            if not st or target is None:
                continue
            info = st.get("detail") or {}
            status = "dead" if st.get("status") == "running" and dead else st.get("status")
            node = by_id[target]
            node["stream"] = {"status": status, "batches": info.get("batches") or 0, "at": info.get("at"),
                              "dbRowsWritten": info.get("dbRowsWritten")}
            if status == "running" and not steps.get(target) and node["status"] in ("waiting", "notRun", "draft"):
                node["status"] = "draft" if target == "normalise" else "running"
            if name == "stream.db" and status == "running" and not steps.get("validate"):
                # nạp theo phần kiểm từng dòng trước mỗi lô; kiểm cả catalog vẫn chạy ở cuối lượt
                by_id["validate"].update(status="running", note="kiểm từng dòng theo lô nạp DB; kiểm cả catalog ở cuối lượt")

        if counts:
            self._progress(nodes, steps, data, path)
        known = set(GRAPH_SINGLE) | set(STEP_OWNER) | set(STREAM_STEPS)
        for name, st in steps.items():
            if name not in known and not name.startswith(NORMALISE_SOURCE):
                add(name, "other", None, st.get("label") or name, st, pending)
        return nodes, edges

    def _progress(self, nodes: list[dict], steps: dict[str, dict], data: dict, path: Path) -> None:
        """% hoàn thành của từng ô (tô màu trên sơ đồ) và bước con của các ô lớn (bấm để bung)."""
        scan = self._scan(path / LOG_FILE)
        refresh = ((data.get("counts") or {}).get("refresh")) or {}
        settings = data.get("settings") or {}
        for node in nodes:
            st = steps.get(node["id"]) or {}
            info = st.get("detail") or {}
            running = node["status"] == "running"
            if node["col"] == "crawl":
                stat = scan.stats.get(node["lane"]) or {}
                if node["id"] == "trip-hotels.prices":
                    if running:
                        targets = (read_json(path / "trip_targets.run.json") or {}).get("hotels") or []
                        dates = len(settings.get("tripHotels.priceOffsets") or (14, 30, 60))
                        node_progress(node, done=sum((stat.get("tripPrices") or {}).values()),
                                      total=len(targets) * dates or None, running=True)
                    else:
                        node_progress(node, done=info.get("completed"), total=info.get("requested"))
                elif node["id"] == "trip-hotels.discover":
                    node_progress(node, running=running)
                else:
                    progress, result = stat.get("progress") or {}, stat.get("result") or {}
                    if running:
                        node_progress(node, done=progress.get("processed"), total=progress.get("total"), running=True)
                        if progress.get("phase"):
                            node["substep"] = progress["phase"]
                    elif result:
                        node_progress(node, done=result["ok"], total=result["total"])
                    elif progress and progress.get("phase") is None:
                        node_progress(node, done=progress.get("done"), total=progress.get("total"))
                    else:
                        node_progress(node)
                item = refresh.get(node["id"])
                if isinstance(item, dict) and item.get("requested"):
                    node["refresh"] = {k: item.get(k) for k in ("requested", "refreshed", "percent")}
            elif node["id"].startswith(NORMALISE_SOURCE):
                records, errors = node.get("in"), node.get("errors") or 0
                node_progress(node, done=(records - errors) if records else None, total=records, running=running)
                stem = node["id"][len(NORMALISE_SOURCE):]
                sub = (read_json(path / "normalised" / "steps" / stem / "steps.json") or {}).get("steps") or []
                if sub:
                    node["substeps"] = [substep_view(e) for e in sub]
            elif node["id"] == "normalise":
                sub = (read_json(path / "normalise_stages" / "steps.json") or {}).get("steps") or []
                draft = not sub and node["status"] in ("running", "draft")
                if draft:  # bản nháp chỉ gộp từ checkpoint: không có bước đọc interim / ánh xạ nguồn
                    folder = "preview.next" if (path / "preview.next").is_dir() else "preview"
                    sub = (read_json(path / folder / "normalise_stages" / "steps.json") or {}).get("steps") or []
                self._big(node, sub, running, graph.planned_substeps("normalise", merge_only=draft))
            elif node["id"] in ("maintain", "validate", "db", "index"):
                self._big(node, info.get("substeps") or [], running, graph.planned_substeps(node["id"]))
            else:
                node_progress(node, running=running)

    @staticmethod
    def _big(node: dict, sub: list[dict], running: bool, plan: tuple[str, ...] = ()) -> None:
        """Ô lớn có bước con: đang chạy tô theo số bước con đã xong; xong thì tô theo luật/tỉ lệ của bước con chính. Chuỗi
        bước con hiện đủ `plan` (kể cả bước chưa / không chạy, with_plan); % chỉ tính trên bước con đã có số liệu."""
        views = [substep_view(e) for e in sub]
        chain = with_plan(views, plan, node["status"])
        if chain:
            node["substeps"] = chain
        finished = [v for v in views if v["status"] != "running"]
        if running:
            expected = max(EXPECTED_SUBSTEPS.get(node["id"], len(views) or 1), len(views))
            node_progress(node, done=len(finished), total=expected if views else None, running=True)
            return
        if node["id"] == "validate" and views:
            checked = [v for v in views if v["status"] != "skipped"]
            node_progress(node, done=sum(v["status"] == "ok" for v in checked), total=len(checked))
        elif node["id"] == "db":
            main = next((v for v in views if v["name"] == "ghép với DB"), None)
            node_progress(node, done=(main or {}).get("ok"), total=(main or {}).get("total"))
        elif node["id"] == "index":
            main = next((v for v in views if (v["name"] or "").startswith("embed")), None)
            node_progress(node, done=(main or {}).get("ok"), total=(main or {}).get("total") or None)
        else:
            node_progress(node)

    def sources(self, path: Path) -> list[dict]:
        names = set()
        if (path / "raw").is_dir():
            names |= {p.name for p in (path / "raw").iterdir() if p.is_dir() and SOURCE_NAME.match(p.name)}
        if (path / "interim").is_dir():
            names |= {p.stem for p in (path / "interim").glob("*.jsonl") if SOURCE_NAME.match(p.stem)}
        out = []
        for name in sorted(names):
            files, size = dir_size(path / "raw" / name) if (path / "raw" / name).is_dir() else (0, 0)
            interim = path / "interim" / f"{name}.jsonl"
            count = sum(1 for _ in iter_jsonl(interim)) if interim.is_file() else 0
            out.append({"source": name, "label": SOURCE_LABELS.get(name, name), "rawFiles": files, "rawBytes": size,
                        "interimRecords": count})
        return out

    def artifacts(self, path: Path) -> list[dict]:
        skip = {RUN_FILE, LOG_FILE, "products.jsonl", "db_load.jsonl", "index_detail.jsonl"}
        out = []
        for p in sorted(list(path.glob("*")) + list((path / "map").glob("*"))):
            if p.is_file() and p.name not in skip and not p.name.startswith("."):
                out.append({"name": str(p.relative_to(path)), "bytes": p.stat().st_size})
        return out

    # -- dung lượng: theo dõi đĩa VM và dọn lượt cào cũ (người dùng yêu cầu 06/10)
    def _storage_root(self) -> Path:
        """Thư mục dữ liệu gắn vào container (`/data` trên VM): cha chung của state và các lượt cào."""
        return self.run_root.parent if self.run_root.parent == self.state_dir.parent else self.run_root

    def _running_dir(self) -> Path | None:
        info = read_json(self.state_dir / RUNNING_FILE) or {}
        if lock_busy(self.state_dir) and info.get("runId"):
            return self.run_root / str(info["runId"])
        return None

    def storage(self) -> dict:
        """Đĩa của VM (filesystem chứa thư mục dữ liệu), từng thư mục con và từng lượt cào còn giữ."""
        root = self._storage_root()
        usage = shutil.disk_usage(root if root.exists() else Path("/"))
        dirs = []
        if root.is_dir():
            for entry in sorted(root.iterdir()):
                if entry.is_symlink():
                    continue
                files, size = dir_size(entry) if entry.is_dir() else (1, entry.stat().st_size)
                dirs.append({"name": entry.name, "bytes": size, "files": files})
        dirs.sort(key=lambda d: d["bytes"], reverse=True)
        running = self._running_dir()
        keep = None
        described = fresh_settings.describe(self.state_dir)
        if not described["error"]:
            keep = next((f["value"] for f in described["fields"] if f["key"] == "runs.keep"), None)
        runs = []
        for index, path in enumerate(run_dirs(self.run_root)):
            files, size = dir_size(path)
            runs.append({"runId": path.name, "bytes": size, "files": files,
                         "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                         "running": running is not None and path.resolve() == running.resolve()})
        return {"path": str(root), "disk": {"total": usage.total, "used": usage.used, "free": usage.free},
                "dirs": dirs, "runs": runs, "runsKeep": keep,
                "note": "Image Docker cũ không xoá được từ monitor (container không có quyền Docker); "
                        "bước deploy job cào tự xoá image cũ, giữ bản đang chạy và một bản trước."}

    def storage_cleanup(self, keep_runs) -> dict:
        """Xoá các lượt cào cũ, giữ `keep_runs` lượt mới nhất; lượt đang chạy luôn được giữ."""
        if isinstance(keep_runs, bool) or not isinstance(keep_runs, int) or not 1 <= keep_runs <= 100:
            raise ValueError("Số lượt giữ lại phải là số nguyên 1–100")
        root = self._storage_root()
        before = shutil.disk_usage(root if root.exists() else Path("/")).free
        attempted = prune_runs(self.run_root, keep_runs, protect=self._running_dir())
        # prune_runs bỏ qua lỗi filesystem (thiếu quyền, file đang mở): chỉ báo "đã xoá" khi thư mục thật sự đã mất.
        removed = [name for name in attempted if not (self.run_root / name).exists()]
        failed = [name for name in attempted if (self.run_root / name).exists()]
        self._disk = (0.0, None)
        after = shutil.disk_usage(root if root.exists() else Path("/")).free
        return {"removed": removed, "failed": failed, "freedBytes": max(0, after - before), "kept": keep_runs}

    # -- log
    def runner_logs(self) -> list[dict]:
        if not self.log_dir or not self.log_dir.is_dir():
            return []
        files = sorted(self.log_dir.glob("fresh-catalog-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        out = []
        for p in files[:40]:
            last = tail_lines(p, 3)
            code = next((m.group(1) for line in reversed(last) if (m := re.search(r"fresh-catalog\.exit=(\d+)", line))), None)
            out.append({"name": p.name, "bytes": p.stat().st_size,
                        "modifiedAt": datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                        "exitCode": code})
        return out

    def log(self, run_id: str | None, name: str, lines: int = 400, grep: str = "", runner: bool = False) -> dict:
        name = safe_name(name, LOG_NAME, "Tên log")
        if runner:
            if not self.log_dir:
                raise ValueError("Monitor chưa được chạy với --log-dir")
            path = self.log_dir / name
        else:
            base = self.run_path(run_id or "")
            path = base / name if name == LOG_FILE else base / "logs" / name
        if not path.is_file():
            raise ValueError("Không có file log này")
        lines = max(10, min(int(lines), 20000))
        if grep:
            needle = grep.lower()
            matched = [line for line in tail_lines(path, 200_000) if needle in line.lower()]
            content = matched[-lines:]
        else:
            content = tail_lines(path, lines)
        return {"name": name, "bytes": path.stat().st_size, "lines": content}

    # -- dữ liệu gốc
    def raw_dir(self, run_id: str, source: str) -> Path:
        return self.run_path(run_id) / "raw" / safe_name(source, SOURCE_NAME, "Nguồn")

    def raw_list(self, run_id: str, source: str, q: str = "", offset: int = 0, limit: int = 100) -> dict:
        base = self.raw_dir(run_id, source)
        rows = []
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(base))
                    if q and q.lower() not in rel.lower():
                        continue
                    st = p.stat()
                    rows.append({"path": rel, "bytes": st.st_size, "kind": raw_kind(p),
                                 "modifiedAt": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")})
        rows.sort(key=lambda r: r["path"])
        return page(rows, offset, limit)

    def raw_file(self, run_id: str, source: str, rel: str) -> dict:
        base = self.raw_dir(run_id, source).resolve()
        path = (base / rel).resolve()
        if base not in path.parents or not path.is_file():
            raise ValueError("Đường dẫn file raw không hợp lệ")
        text, cut = read_text(path)
        kind = raw_kind(path)
        out = {"path": rel, "bytes": path.stat().st_size, "kind": kind, "truncated": cut, "chars": len(text)}
        if kind == "json":
            try:
                data = json.loads(text)
                pretty = json.dumps(data, ensure_ascii=False, indent=1)
                out["json"] = pretty[:MAX_TEXT]
                out["truncated"] = cut or len(pretty) > MAX_TEXT
                out["summary"] = json_summary(data)
            except ValueError:
                out["text"] = text[:MAX_TEXT]
        elif kind == "html":
            out.update(html_views(text))
            out["text"] = text[:MAX_TEXT]
        else:
            out["text"] = text[:MAX_TEXT]
        return out

    # -- interim
    def _interim_rows(self, run_id: str, source: str) -> list[dict]:
        path = self.run_path(run_id) / "interim" / f"{safe_name(source, SOURCE_NAME, 'Nguồn')}.jsonl"
        rows = self.cache.get(path, lambda p: [(i, r) for i, r in iter_jsonl(p)], "indexed")
        if rows is None:
            raise ValueError("Nguồn này không có interim trong lượt")
        return rows

    def interim(self, run_id: str, source: str, q: str = "", offset: int = 0, limit: int = 100) -> dict:
        rows = self._interim_rows(run_id, source)
        needle = q.lower().strip()
        out = []
        for index, record in rows:
            if needle and needle not in json.dumps(record, ensure_ascii=False).lower():
                continue
            out.append(dict(brief_record(record), index=index))
        result = page(out, offset, limit)
        result["fields"] = sorted({k for _, r in rows[:200] for k in r})
        return result

    def interim_record(self, run_id: str, source: str, index: int) -> dict:
        for i, record in self._interim_rows(run_id, source):
            if i == index:
                return {"index": i, "record": record}
        raise ValueError("Không có bản ghi này")

    # -- catalog chuẩn hoá
    def _data_dir(self, run_id: str, preview: bool = False) -> Path:
        """Thư mục kết quả chuẩn hoá: của lượt, hoặc bản nháp `<lượt>/preview/` (fresh_catalog.Previewer)."""
        path = self.run_path(run_id)
        if not preview:
            return path
        if not (path / "preview" / "preview.json").is_file():
            raise ValueError("Lượt này chưa có bản chuẩn hoá nháp")
        return path / "preview"

    def _products(self, run_id: str, preview: bool = False) -> list[dict]:
        path = self._data_dir(run_id, preview) / "products.jsonl"
        rows = self.cache.get(path, lambda p: [r for _, r in iter_jsonl(p)])
        if rows is None:
            raise ValueError("Lượt này chưa tới bước chuẩn hoá")
        return rows

    def products(self, run_id: str, q: str = "", taxonomy: str = "", level: str = "", source: str = "",
                 destination: str = "", flag: str = "", offset: int = 0, limit: int = 100, preview: bool = False) -> dict:
        rows = self._products(run_id, preview)
        facets = {"taxonomy": Counter(), "level": Counter(), "source": Counter(), "destination": Counter()}
        out = []
        needle = q.lower().strip()
        for row in rows:
            b = brief_product(row)
            src = (b["sourceRef"] or "").split(":")[0]
            for key, value in (("taxonomy", b["taxonomy"]), ("level", b["level"] or "-"), ("source", src),
                               ("destination", b["destination"])):
                facets[key][value] += 1
            if taxonomy and b["taxonomy"] != taxonomy:
                continue
            if level and (b["level"] or "-") != level:
                continue
            if source and src != source:
                continue
            if destination and b["destination"] != destination:
                continue
            if flag == "noPrice" and b["unitPrice"] is not None:
                continue
            if flag == "unavailable" and b["available"]:
                continue
            if flag == "noImage" and b["hasImage"]:
                continue
            if needle and needle not in f"{b['name']} {b['sourceRef']} {b['productId']}".lower():
                continue
            out.append(b)
        result = page(out, offset, limit)
        result["facets"] = {k: dict(v.most_common()) for k, v in facets.items()}
        return result

    def product(self, run_id: str, product_id: str, preview: bool = False) -> dict:
        path = self.run_path(run_id)  # interim của bản nháp là hard link của interim lượt: cùng nội dung, cùng chỉ số dòng
        row = next((r for r in self._products(run_id, preview) if r.get("productId") == product_id), None)
        if row is None:
            raise ValueError("Không có sản phẩm này trong catalog của lượt")
        attrs = row.get("attributes") or {}
        refs = [row.get("sourceRef")] + list(attrs.get("sameAs") or [])
        trace = []
        for ref in [r for r in refs if r]:
            family, kind, ident = ref_parts(ref)
            for source in FAMILIES.get(family, ()):
                interim = path / "interim" / f"{source}.jsonl"
                if not interim.is_file():
                    continue
                matches = []
                for index, record in self.cache.get(interim, lambda p: [(i, r) for i, r in iter_jsonl(p)], "indexed") or []:
                    if ident and ident in record_ids(record):
                        matches.append(dict(brief_record(record), index=index))
                    elif kind == "route" and ident and ident == f"{record.get('fromCode')}-{record.get('toCode')}":
                        matches.append(dict(brief_record(record), index=index))
                    if len(matches) >= 5:
                        break
                for match in matches:
                    trace.append({"ref": ref, "source": source, "interim": match,
                                  "raw": self.raw_for(path, source, ident, match.get("url"))})
        db = None if preview else next((r for _, r in iter_jsonl(path / "db_load.jsonl")
                                        if r.get("productId") == product_id), None)
        return {"product": row, "trace": trace, "db": db}

    def raw_for(self, path: Path, source: str, ident: str, url: str | None) -> list[str]:
        base = path / "raw" / source
        if not base.is_dir():
            return []
        found = []
        if source == "trip_hotels" and ident and (base / ident).is_dir():
            return sorted(str(p.relative_to(base)) for p in (base / ident).iterdir() if p.is_file())[:20]
        tokens = [t for t in {ident, re.sub(r"[^A-Za-z0-9._-]+", "_", url or "")[:60]} if t and len(t) >= 3]
        if url:
            from collectors.common import Paths, RawCache
            cache = RawCache(Paths(path), source)
            for ext in ("html", "json"):
                candidate = cache.path(url, ext)
                if candidate.is_file():
                    found.append(str(candidate.relative_to(base)))
        if not found and tokens:
            for p in base.rglob("*"):
                if p.is_file() and any(t in p.name for t in tokens):
                    found.append(str(p.relative_to(base)))
                    if len(found) >= 20:
                        break
        return sorted(set(found))

    # -- nạp DB
    def db_rows(self, run_id: str, action: str = "", q: str = "", written: str = "", offset: int = 0,
                limit: int = 100) -> dict:
        path = self.run_path(run_id) / "db_load.jsonl"
        rows = self.cache.get(path, lambda p: [r for _, r in iter_jsonl(p)])
        if rows is None:
            raise ValueError("Lượt này chưa nạp DB")
        counts = Counter(r.get("action") for r in rows)
        written_count = sum(1 for r in rows if r.get("written"))
        needle = q.lower().strip()
        out = [r for r in rows
               if (not action or r.get("action") == action)
               and (not written or (written == "yes") == bool(r.get("written")))
               and (not needle or needle in f"{r.get('name')} {r.get('sourceRef')} {r.get('productId')}".lower())]
        result = page(out, offset, limit)
        result.update(actions=dict(counts), written=written_count)
        return result

    # -- báo cáo khác của lượt
    def artifact(self, run_id: str, name: str) -> dict:
        base = self.run_path(run_id).resolve()
        if name not in {item["name"] for item in self.artifacts(base)}:
            raise ValueError("Không có báo cáo này trong lượt")
        path = (base / name).resolve()
        if base not in path.parents or not path.is_file():
            raise ValueError("Không có file này trong lượt")
        text, cut = read_text(path, 8_000_000)
        out = {"name": name, "bytes": path.stat().st_size, "truncated": cut}
        if path.suffix == ".csv":
            reader = csv.reader(io.StringIO(text.lstrip("﻿")))
            rows = list(reader)
            out.update(kind="table", header=rows[0] if rows else [], rows=rows[1:2001], total=max(0, len(rows) - 1))
        elif path.suffix in (".json", ".geojson"):
            try:
                out.update(kind="json", json=json.dumps(json.loads(text), ensure_ascii=False, indent=1)[:MAX_TEXT])
            except ValueError:
                out.update(kind="text", text=text[:MAX_TEXT])
        elif path.suffix == ".jsonl":
            rows = [json.loads(line) for line in text.splitlines()[:500] if line.strip()]
            out.update(kind="json", json=json.dumps(rows, ensure_ascii=False, indent=1)[:MAX_TEXT])
        else:
            out.update(kind="text", text=text[:MAX_TEXT])
        return out

    # -- khách sạn Trip
    def trip_hotels(self) -> dict:
        from fresh_catalog_schedule import select_batch
        targets = (read_json(self.state_dir / "trip_targets.json", {}) or {}).get("hotels") or []
        schedule = (read_json(self.state_dir / "trip_schedule.json", {}) or {}).get("hotels") or {}
        order = {row["trip_hotel_id"]: i + 1 for i, row in enumerate(select_batch(targets, schedule, max(1, len(targets))))} \
            if targets else {}
        values = fresh_settings.load(self.state_dir) if not fresh_settings.describe(self.state_dir)["error"] else {}
        batch = values.get("tripHotels.dailyHotels", 60)
        coverage, coverage_run = {}, None
        for path in run_dirs(self.run_root):
            report = read_json(path / "trip_price_coverage.json")
            if report:
                coverage_run = path.name
                for row in report.get("results") or []:
                    coverage.setdefault(str(row.get("hotelId")), {})[row.get("checkin")] = row.get("status")
                break
        rows = []
        for row in targets:
            hid = row["trip_hotel_id"]
            entry = schedule.get(hid) or {}
            rows.append({"hotelId": hid, "cityId": row.get("city_id"), "destination": row.get("destination"),
                         "lastAttemptAt": entry.get("lastAttemptAt"), "lastSuccessAt": entry.get("lastSuccessAt"),
                         "queue": order.get(hid), "nextBatch": order.get(hid, 10**9) <= batch,
                         "lastCoverage": coverage.get(hid)})
        rows.sort(key=lambda r: r["queue"] or 10**9)
        return {"hotels": rows, "dailyBatch": batch, "coverageRun": coverage_run,
                "cities": dict(Counter(r["destination"] for r in rows))}

    # -- cấu hình
    def settings(self) -> dict:
        return fresh_settings.describe(self.state_dir)

    def save_settings(self, changes: dict) -> dict:
        fresh_settings.save(self.state_dir, changes)
        return fresh_settings.describe(self.state_dir)

    # -- chạy / dừng
    def start(self, mode: str) -> tuple[int, dict]:
        if mode not in ("auto", "full", "daily", "index"):
            raise ValueError("Chế độ chạy không hợp lệ")
        with self.spawn_lock:
            if self.running():
                return 409, {"error": "Đang có lượt chạy; đợi xong hoặc bấm Dừng"}
            cmd = [sys.executable, str(ROOT / "fresh_catalog.py"), mode, "--trigger", "monitor"]
            if mode != "index" and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
                cmd = ["xvfb-run", "-a", "-s", "-screen 0 1366x768x24"] + cmd
            env = dict(os.environ, CATALOG_STATE_DIR=str(self.state_dir), CATALOG_RUN_ROOT=str(self.run_root),
                       PYTHONUNBUFFERED="1")
            self.state_dir.mkdir(parents=True, exist_ok=True)
            with open(self.state_dir / "monitor-launch.log", "a", encoding="utf-8") as log:
                log.write(f"\n=== {datetime.now().astimezone().isoformat(timespec='seconds')} {' '.join(cmd)}\n")
                log.flush()
                proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, start_new_session=True)
            self.spawned = {"pid": proc.pid, "mode": mode, "returncode": None,
                            "startedAt": datetime.now().astimezone().isoformat(timespec="seconds")}

            def reap(p=proc, info=self.spawned):
                info["returncode"] = p.wait()

            threading.Thread(target=reap, daemon=True).start()
            return 202, {"started": True, "mode": mode, "pid": proc.pid}

    def resume(self, run_id: str, from_step: str, source: str | None = None) -> tuple[int, dict]:
        """CP6: chạy lại lượt đã kết thúc từ một bước sau cào (`fresh_catalog.py resume <lượt> --from <bước>`).
        P4: `from_step` = crawl + `source` → cào lại riêng nguồn đó rồi chạy tiếp tới index."""
        if from_step not in RESUME_STEPS:
            raise ValueError("Bước chạy lại không hợp lệ")
        recrawl = from_step == graph.RECRAWL
        if recrawl != bool(source) or (recrawl and source not in graph.SOURCE_BY_KEY):
            raise ValueError("Cào lại cần đúng một nguồn hợp lệ (và chỉ khi chạy lại từ bước cào)")
        path = self.run_path(run_id)
        data = read_json(path / RUN_FILE) or {}
        if data.get("status") == "running" and self._is_running(run_id):
            return 409, {"error": "Lượt này đang chạy"}
        with self.spawn_lock:
            if self.running():
                return 409, {"error": "Đang có lượt chạy; đợi xong hoặc bấm Dừng"}
            cmd = [sys.executable, str(ROOT / "fresh_catalog.py"), "resume", run_id, "--from", from_step,
                   "--trigger", "monitor", *(["--source", source] if recrawl else [])]
            if recrawl and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):  # cào cần trình duyệt, như start()
                cmd = ["xvfb-run", "-a", "-s", "-screen 0 1366x768x24"] + cmd
            env = dict(os.environ, CATALOG_STATE_DIR=str(self.state_dir), CATALOG_RUN_ROOT=str(self.run_root),
                       PYTHONUNBUFFERED="1")
            with open(self.state_dir / "monitor-launch.log", "a", encoding="utf-8") as log:
                log.write(f"\n=== {datetime.now().astimezone().isoformat(timespec='seconds')} {' '.join(cmd)}\n")
                log.flush()
                proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, start_new_session=True)
            self.spawned = {"pid": proc.pid, "mode": f"resume:{from_step}" + (f":{source}" if recrawl else ""),
                            "returncode": None,
                            "startedAt": datetime.now().astimezone().isoformat(timespec="seconds")}

            def reap(p=proc, info=self.spawned):
                info["returncode"] = p.wait()

            threading.Thread(target=reap, daemon=True).start()
            return 202, {"started": True, "run": run_id, "from": from_step, "source": source, "pid": proc.pid}

    def stop(self) -> tuple[int, dict]:
        info = read_json(self.state_dir / RUNNING_FILE) or {}
        if not lock_busy(self.state_dir) or not info.get("runId"):
            return 409, {"error": "Không có lượt nào đang chạy"}
        write_json(self.state_dir / STOP_FILE, {"runId": info["runId"],
                                                "requestedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        return 202, {"stopping": info["runId"],
                     "message": "Đã gửi yêu cầu dừng; crawler sẽ dừng ở điểm kiểm tra tiếp theo. Bước DB đã bắt đầu có thể hoàn tất; dữ liệu đã commit được giữ lại."}

    # -- tình trạng từng nguồn của một lượt
    def _scan(self, path: Path) -> LogScan:
        key = str(path)
        scan = self._scans.get(key)
        if scan is None:
            if len(self._scans) > 20:
                self._scans.pop(next(iter(self._scans)))
            scan = self._scans[key] = LogScan(path)
        return scan.update()

    def _interim_count(self, path: Path) -> int:
        return self.cache.get(path, lambda p: sum(1 for _ in iter_jsonl(p)), "count") or 0

    def _is_running(self, run_id: str) -> bool:
        running = read_json(self.state_dir / RUNNING_FILE) or {}
        return lock_busy(self.state_dir) and running.get("runId") == run_id

    def _previous_counts(self, run_id: str, mode: str | None) -> tuple[str | None, dict[str, int]]:
        """Số bản ghi interim theo thư mục của lượt cùng chế độ gần nhất trước lượt này (để báo nguồn tụt mạnh)."""
        for path in run_dirs(self.run_root):
            if path.name == run_id or not path.name.startswith(f"{mode}-"):
                continue
            if path.name.split("-")[1] >= run_id.split("-")[1]:  # chỉ lượt bắt đầu trước (mốc UTC trong tên)
                continue
            counts = {p.stem: self._interim_count(p) for p in (path / "interim").glob("*.jsonl")}
            if counts:
                return path.name, counts
        return None, {}

    def health(self, run_id: str) -> dict:
        path = self.run_path(run_id)
        data = read_json(path / RUN_FILE) or {"id": run_id}
        running = data.get("status") == "running" and self._is_running(run_id)
        settings = data.get("settings") or {}
        scan = self._scan(path / LOG_FILE)
        control = live_control.read(self.state_dir / live_control.FILE_NAME) if running else {}
        live = (control.get("sources") or {}) if control.get("runId") == run_id else {}
        prev_run, prev = self._previous_counts(run_id, data.get("mode"))
        rows = []
        for src in SOURCES:
            stat = scan.stats[src["key"]]
            steps = [st for st in data.get("steps") or [] if st.get("name") in src["steps"]]
            raw_files = raw_bytes = interim = 0
            prev_interim = 0
            for name in src["dirs"]:
                if (path / "raw" / name).is_dir():
                    files, size = dir_size(path / "raw" / name)
                    raw_files += files
                    raw_bytes += size
                interim += self._interim_count(path / "interim" / f"{name}.jsonl")
                prev_interim += prev.get(name, 0)
            state, notes = self._source_state(src, data, settings, steps, running, scan, interim)
            if state == "ok" and prev_interim and interim < prev_interim / 2:
                notes.append(f"giảm mạnh: {interim} bản ghi, lượt trước {prev_interim}")
            age = _age_of_clock(stat["lastAt"])
            if state == "running" and age is not None and age > SILENT_SECONDS:
                notes.append(f"im lặng {round(age / 60)} phút (không có dòng log mới)")
            if stat["blocks"]:
                notes.append(f"{stat['blocks']} dòng log báo bị chặn / challenge")
            bad = {code: n for code, n in stat["http"].items() if code >= "400"}
            if bad:
                notes.append("HTTP lỗi: " + ", ".join(f"{code}×{n}" for code, n in sorted(bad.items())))
            entry = live.get(src["live"]) or {}
            if entry.get("paused"):
                notes.append("đang tạm dừng trên monitor")
            rows.append({
                "key": src["key"], "label": src["label"], "state": state, "notes": notes,
                "lost": state in ("error", "blocked", "skipped", "notRun", "empty"),
                "steps": [{k: st.get(k) for k in ("name", "status", "seconds", "startedAt", "error", "errorKind", "detail")}
                          for st in steps],
                "rawFiles": raw_files, "rawBytes": raw_bytes, "interim": interim, "prevInterim": prev_interim or None,
                "dirs": [d for d in src["dirs"] if (path / "raw" / d).is_dir() or (path / "interim" / f"{d}.jsonl").is_file()],
                "log": {k: stat[k] for k in ("lines", "warnings", "errors", "blocks", "lastAt", "lastLine", "progress", "live")}
                | {"http": dict(stat["http"]), "ageSeconds": age, "tripPrices": dict(stat["tripPrices"]),
                   "tripMeta": dict(stat["tripMeta"])},
                "liveKey": src["live"], "paused": bool(entry.get("paused")),
            })
        return {"runId": run_id, "mode": data.get("mode"), "status": "running" if running else data.get("status"),
                "running": running, "groups": scan.groups, "previousRun": prev_run, "sources": rows}

    @staticmethod
    def _source_state(src, data, settings, steps, running, scan, interim) -> tuple[str, list[str]]:
        mode = data.get("mode")
        if mode not in src["modes"]:
            return "notInMode", [f"lượt {mode} không chạy nguồn này"]
        if settings and settings.get(src["setting"]) is False:
            return "disabled", ["đang tắt trong cấu hình của lượt"]
        notes = []
        if steps:
            statuses = [st.get("status") for st in steps]
            for st in steps:
                if st.get("error"):
                    notes.append(f"{st['name']}: {st['error']}")
                tries = (st.get("detail") or {}).get("attempts") or []
                if tries:
                    notes.append(f"{st['name']}: đã thử lại {len(tries)} lần ({', '.join(t['kind'] for t in tries)})")
            for state in ("running", "error", "blocked", "stopped"):
                if state in statuses:
                    if state == "blocked":
                        notes.append("nguồn trả mã 75: bị chặn liên tiếp, đã lưu tiến độ")
                    return state, notes
            if interim == 0:
                return "empty", notes + ["chạy xong nhưng không có bản ghi interim nào"]
            return "ok", notes
        group = scan.groups.get(src["group"] or "trip") or {}
        if group.get("event") == "skip":
            return "skipped", ["bị bỏ vì nguồn khác lỗi trước khi tới lượt"]
        if running:
            return "waiting", ["chưa tới lượt (đang chờ site khác hoặc bước trước)"]
        return "notRun", ["không chạy: lượt dừng trước bước này" + (f" ({data.get('error')})" if data.get("error") else "")]

    # -- số lượng theo thành phố
    def cities(self, run_id: str, preview: bool = False) -> dict:
        """Thành phố × loại × nguồn của catalog (chính thức hoặc nháp) và thành phố × nguồn của interim (khi đang cào)."""
        path = self.run_path(run_id)
        catalog, catalog_error = None, None
        try:
            rows = self._products(run_id, preview)
        except ValueError as exc:
            rows, catalog_error = None, str(exc)
        if rows is not None:
            table: dict[str, dict] = {}
            sources, types = Counter(), Counter()
            for row in rows:
                city = row.get("destination") or "(trống)"
                entry = table.setdefault(city, {"destination": city, "total": 0, "bySource": Counter(),
                                                "byType": Counter(), "merged": 0})
                family = (row.get("sourceRef") or "-").split(":")[0]
                kind = product_type(row)
                entry["total"] += 1
                entry["bySource"][family] += 1
                entry["byType"][kind] += 1
                entry["merged"] += bool((row.get("attributes") or {}).get("sameAs"))
                sources[family] += 1
                types[kind] += 1
            order = [label for label in PRODUCT_TYPES.values() if label in types] + \
                    sorted(t for t in types if t not in PRODUCT_TYPES.values())
            catalog = {"rows": len(rows), "sources": [k for k, _ in sources.most_common()], "types": order,
                       "destinations": sorted(({**e, "bySource": dict(e["bySource"]), "byType": dict(e["byType"])}
                                               for e in table.values()), key=lambda e: (-e["total"], e["destination"]))}
        per_file: dict[str, Counter] = {}
        for file in sorted((path / "interim").glob("*.jsonl")):
            if SOURCE_NAME.match(file.stem):
                tally = self._tallies.get(str(file))
                if tally is None:
                    tally = self._tallies[str(file)] = InterimTally(file)
                per_file[file.stem] = tally.update()
        cities: dict[str, dict] = {}
        for stem, counts in per_file.items():
            for city, n in counts.items():
                entry = cities.setdefault(city, {"destination": city, "total": 0, "bySource": {}})
                entry["total"] += n
                entry["bySource"][stem] = n
        interim = {"sources": [{"source": stem, "label": SOURCE_LABELS.get(stem, stem), "total": sum(c.values())}
                               for stem, c in per_file.items()],
                   "destinations": sorted(cities.values(), key=lambda e: (e["destination"] == UNKNOWN_CITY,
                                                                          -e["total"], e["destination"]))}
        return {"runId": run_id, "preview": preview, "catalog": catalog, "catalogError": catalog_error,
                "interim": interim, "running": self._is_running(run_id)}

    # -- chỉnh tốc độ khi đang chạy
    def live(self) -> dict:
        info = read_json(self.state_dir / RUNNING_FILE) or {}
        run_id = info.get("runId") if lock_busy(self.state_dir) else None
        values = {}
        if run_id:
            try:
                values = (read_json(self.run_path(run_id) / RUN_FILE) or {}).get("settings") or {}
            except ValueError:
                values = {}
        described = fresh_settings.describe(self.state_dir)
        current = {f["key"]: f["value"] for f in described["fields"]}
        values = values or current
        control = live_control.read(self.state_dir / live_control.FILE_NAME)
        sources = (control.get("sources") or {}) if run_id and control.get("runId") == run_id else {}
        rows = []
        for key, limits in live_control.LIMITS.items():
            entry = sources.get(key) or {}
            fields = []
            for name, floor in limits.items():
                base = values.get(live_control.SETTING_KEYS[key][name])
                override = entry.get(name)
                fields.append({"name": name, "base": base, "override": override,
                               "value": override if override is not None else base,
                               "minimum": floor, "maximum": live_control.MAX_DELAY})
            rows.append({"key": key, "label": LIVE_LABELS[key], "paused": bool(entry.get("paused")), "fields": fields,
                         "updatedAt": entry.get("updatedAt")})
        next_run = [{k: f[k] for k in ("key", "label", "value", "minimum", "maximum", "source")}
                    for f in described["fields"] if f["key"] in NEXT_RUN_KEYS]
        enabled = {"stream.normalise": values.get("stream.enabled"), "stream.merge": values.get("stream.enabled"),
                   "stream.db": values.get("stream.enabled") and values.get("stream.db"),
                   "stream.index": values.get("stream.enabled") and values.get("stream.db") and values.get("stream.index")}
        stream = []
        for key, (low, high, setting) in live_control.STREAM.items():
            entry = sources.get(key) or {}
            base = values.get(setting)
            stream.append({"key": key, "label": STREAM_LIVE[key], "enabled": bool(enabled[key]),
                           "paused": bool(entry.get("paused")), "base": base, "override": entry.get("interval"),
                           "value": entry.get("interval") or base, "minimum": low, "maximum": high,
                           "kickAt": entry.get("kickAt"), "updatedAt": entry.get("updatedAt")})
        return {"runId": run_id, "running": bool(run_id), "sources": rows, "nextRun": next_run, "stream": stream}

    def set_live(self, key: str, changes: dict) -> tuple[int, dict]:
        info = read_json(self.state_dir / RUNNING_FILE) or {}
        if not lock_busy(self.state_dir) or not info.get("runId"):
            return 409, {"error": "Không có lượt nào đang chạy; delay cho lượt sau chỉnh ở trang Cấu hình"}
        live_control.write(self.state_dir / live_control.FILE_NAME, info["runId"], key, changes)
        return 200, self.live()

    # -- các bước chuẩn hoá
    def _stages_dir(self, run_id: str, preview: bool = False) -> Path:
        path = self._data_dir(run_id, preview) / "normalise_stages"
        if not (path / "stages.json").is_file():
            raise ValueError("Lượt này chưa có ảnh chụp các bước chuẩn hoá (chưa tới bước normalise, hoặc chạy bản cũ)")
        return path

    def _stage_entries(self, run_id: str, stage: str, preview: bool = False) -> list[dict]:
        if stage == "final":
            # products.jsonl không còn `_meta`: lấy nhãn nguồn của cùng dòng ở bước "enriched" cho khớp các bước khác
            try:
                source_of = {e["product"].get("productId"): e.get("source")
                             for e in self._stage_entries(run_id, "enriched", preview)}
            except ValueError:
                source_of = {}
            return [{"source": source_of.get(r.get("productId")) or (r.get("sourceRef") or "").split(":")[0], "product": r}
                    for r in self._products(run_id, preview)]
        if stage == "errors":  # bản ghi lỗi khi ánh xạ (normalise.RecordGuard); có cả khi normalize dừng giữa chừng
            path = self._data_dir(run_id, preview) / "normalise_stages" / "errors.jsonl"
            if path.is_file():
                return self.cache.get(path, lambda p: [r for _, r in iter_jsonl(p)]) or []
            # chưa tới bước gộp: lấy từ checkpoint chuẩn hoá theo nguồn (normalised/<nguồn>.errors.jsonl)
            folder = self.run_path(run_id) / "normalised"
            out: list[dict] = []
            for part in sorted(folder.glob("*.errors.jsonl")) if folder.is_dir() else []:
                out += self.cache.get(part, lambda p: [r for _, r in iter_jsonl(p)]) or []
            return out
        base = self._stages_dir(run_id, preview)
        if stage == "merges":
            return self.cache.get(base / "merges.jsonl", lambda p: [r for _, r in iter_jsonl(p)]) or []
        if stage not in ("mapped", "merged", "filtered", "enriched", "dropped"):
            raise ValueError("Bước chuẩn hoá không hợp lệ")
        path = base / f"{stage}.jsonl.gz"

        def load(p: Path) -> list[dict]:
            out = []
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        try:
                            out.append(json.loads(line))
                        except ValueError:
                            continue
            return out
        return self.cache.get(path, load) or []

    def checkpoints(self, run_id: str) -> list[dict]:
        """Chuẩn hoá theo nguồn của lượt (`<lượt>/normalised/*.meta.json`, normalise.write_checkpoint); bản nháp và bản
        chính thức cùng dùng các checkpoint này."""
        folder = self.run_path(run_id) / "normalised"
        out = []
        for meta in sorted(folder.glob("*.meta.json")) if folder.is_dir() else []:
            data = read_json(meta) or {}
            out.append({k: data.get(k) for k in ("source", "status", "error", "records", "rows", "errors", "seconds",
                                                  "today", "batches")}
                       | {"writtenAt": datetime.fromtimestamp(meta.stat().st_mtime).astimezone().isoformat(timespec="seconds")})
        return out

    def normalise(self, run_id: str, preview: bool = False) -> dict:
        folder = self._data_dir(run_id, preview) / "normalise_stages"
        steps = (read_json(folder / "steps.json") or {}).get("steps")
        errors = Counter(e.get("source") for e in self._stage_entries(run_id, "errors", preview))
        checkpoints = self.checkpoints(run_id)
        if (steps or checkpoints) and not (folder / "stages.json").is_file():  # đang chạy hoặc đã chết: vẫn cho xem
            return {"stages": [], "steps": steps or [], "dropped": {}, "merges": 0, "dropReasons": [], "report": None,
                    "recordErrors": dict(errors), "checkpoints": checkpoints,
                    "incomplete": True, "preview": read_json(self._data_dir(run_id, True) / "preview.json") if preview else None}
        base = self._stages_dir(run_id, preview)
        summary = read_json(base / "stages.json") or {}
        summary["steps"] = steps
        summary["recordErrors"] = dict(errors)
        summary["checkpoints"] = checkpoints
        reasons = Counter((e.get("step"), e.get("reason")) for e in self._stage_entries(run_id, "dropped", preview))
        summary["dropReasons"] = [{"step": step, "reason": reason, "rows": n} for (step, reason), n in reasons.most_common(60)]
        summary["report"] = read_json(self._data_dir(run_id, preview) / "normalise_report.json")
        summary["preview"] = read_json(self._data_dir(run_id, True) / "preview.json") if preview else None
        return summary

    def normalise_rows(self, run_id: str, stage: str, q: str = "", source: str = "", taxonomy: str = "",
                       step: str = "", offset: int = 0, limit: int = 100, preview: bool = False) -> dict:
        entries = self._stage_entries(run_id, stage, preview)
        needle = q.lower().strip()
        if stage == "errors":
            rows = [{"index": i, "source": e.get("source"), "function": e.get("function"), "input": e.get("input"),
                     "error": e.get("error")}
                    for i, e in enumerate(entries)
                    if (not source or e.get("source") == source)
                    and (not needle or needle in json.dumps(e, ensure_ascii=False).lower())]
            result = page(rows, offset, limit)
            result["facets"] = {"source": dict(Counter(e.get("source") for e in entries).most_common())}
            return result
        facets = {"source": Counter(), "taxonomy": Counter(), "step": Counter()}
        out = []
        for index, entry in enumerate(entries):
            if stage == "merges":
                if needle and needle not in json.dumps(entry, ensure_ascii=False).lower():
                    continue
                out.append(dict(entry, index=index))
                continue
            product = entry.get("product") or {}
            attrs = product.get("attributes") or {}
            src = entry.get("source") or "-"
            facets["source"][src] += 1
            facets["taxonomy"][product.get("taxonomy") or "-"] += 1
            if entry.get("step"):
                facets["step"][entry["step"]] += 1
            if source and src != source or taxonomy and product.get("taxonomy") != taxonomy:
                continue
            if step and entry.get("step") != step:
                continue
            if needle and needle not in f"{product.get('name')} {product.get('sourceRef')} {product.get('productId')} " \
                                       f"{entry.get('reason') or ''}".lower():
                continue
            out.append({"index": index, "source": src, "step": entry.get("step"), "reason": entry.get("reason"),
                        "productId": product.get("productId"), "name": product.get("name"),
                        "taxonomy": product.get("taxonomy"), "level": attrs.get("level"),
                        "destination": product.get("destination"), "unitPrice": product.get("unitPrice"),
                        "sourceRef": product.get("sourceRef"), "sameAs": len(attrs.get("sameAs") or []),
                        "input": entry.get("input")})
        result = page(out, offset, limit)
        result["facets"] = {k: dict(v.most_common()) for k, v in facets.items() if v}
        return result

    def normalise_row(self, run_id: str, stage: str, index: int, preview: bool = False) -> dict:
        entries = self._stage_entries(run_id, stage, preview)
        if not 0 <= index < len(entries):
            raise ValueError("Không có dòng này")
        return {"stage": stage, "index": index, "entry": entries[index]}

    def normalise_trace(self, run_id: str, ident: str, preview: bool = False) -> dict:
        """Một sản phẩm qua từng bước: dòng khớp theo productId / sourceRef / sameAs và trường đã đổi so với bước trước."""
        ident = ident.strip()
        if not ident:
            raise ValueError("Nhập productId hoặc sourceRef")
        refs, ids = {ident}, {ident}
        for stage in ("final", "enriched", "filtered", "merged"):
            try:
                entries = self._stage_entries(run_id, stage, preview)
            except ValueError:
                continue
            for entry in entries:
                product = entry.get("product") or {}
                same = set((product.get("attributes") or {}).get("sameAs") or [])
                if ident in (product.get("productId"), product.get("sourceRef")) or ident in same:
                    ids.add(product.get("productId"))
                    refs |= {product.get("sourceRef")} | same
            if len(ids) > 1:
                break
        out, previous = [], None
        for stage, label, _help in STAGE_LABELS:
            try:
                entries = self._stage_entries(run_id, stage, preview)
            except ValueError:
                continue
            matches = [dict(e, index=i) for i, e in enumerate(entries)
                       if (e.get("product") or {}).get("productId") in ids or (e.get("product") or {}).get("sourceRef") in refs][:12]
            primary = next((m["product"] for m in matches if m["product"].get("productId") in ids), None) \
                or (matches[0]["product"] if matches else None)
            out.append({"id": stage, "label": label, "rows": matches,
                        "diff": product_diff(previous, primary) if previous is not None and primary is not None else None})
            previous = primary if primary is not None else previous
        dropped = [dict(e, index=i) for i, e in enumerate(self._stage_entries(run_id, "dropped", preview))
                   if (e.get("product") or {}).get("productId") in ids or (e.get("product") or {}).get("sourceRef") in refs]
        merges = [m for m in self._stage_entries(run_id, "merges", preview) if m.get("keptRef") in refs or m.get("mergedRef") in refs]
        return {"ident": ident, "refs": sorted(r for r in refs if r), "stages": out, "dropped": dropped[:20], "merges": merges}

    # -- embedding
    def _embed_rows(self, run_id: str) -> list[dict]:
        path = self.run_path(run_id) / "index_detail.jsonl"
        rows = self.cache.get(path, lambda p: [r for _, r in iter_jsonl(p)])
        if rows is None:
            raise ValueError("Lượt này chưa có chi tiết index (bước index chưa chạy, lỗi trước khi đọc catalog, hoặc chạy bản cũ)")
        return rows

    def embed(self, run_id: str, action: str = "", taxonomy: str = "", q: str = "", offset: int = 0,
              limit: int = 100) -> dict:
        rows = self._embed_rows(run_id)
        actions, reasons, taxonomies = Counter(), Counter(), Counter()
        chars = []
        needle = q.lower().strip()
        out = []
        for row in rows:
            actions[row.get("action")] += 1
            if row.get("reason"):
                reasons[row["reason"]] += 1
            if row.get("taxonomy"):
                taxonomies[row["taxonomy"]] += 1
            if row.get("chars") is not None:
                chars.append(row["chars"])
            if action and row.get("action") != action or taxonomy and row.get("taxonomy") != taxonomy:
                continue
            if needle and needle not in f"{row.get('name')} {row.get('productId')} {row.get('text') or ''}".lower():
                continue
            out.append({k: row.get(k) for k in ("productId", "name", "taxonomy", "destination", "action", "reason",
                                                 "chars", "words", "textHash")}
                       | {"norm": (row.get("vector") or {}).get("norm"), "preview": (row.get("text") or "")[:160]})
        result = page(out, offset, limit)
        chars.sort()
        result.update(actions=dict(actions), reasons=dict(reasons), taxonomy=dict(taxonomies.most_common()),
                      chars={"min": chars[0], "median": chars[len(chars) // 2], "max": chars[-1]} if chars else None,
                      report=read_json(self.run_path(run_id) / "index_report.json"))
        return result

    def embed_row(self, run_id: str, product_id: str) -> dict:
        row = next((r for r in self._embed_rows(run_id) if r.get("productId") == product_id), None)
        if row is None:
            raise ValueError("Không có sản phẩm này trong chi tiết index của lượt")
        return row

    def _index_settings(self):
        ensure_backend_path()
        from fresh_catalog import index_settings  # nạp muộn: kéo theo backend
        try:
            return index_settings(os.environ.get("DB_TARGET", "local"))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Monitor chưa có cấu hình index ({exc}); chạy monitor cùng env với job") from None

    def _weaviate_http(self, settings):
        import httpx
        ensure_backend_path()
        from src.backend.app.infrastructure.vectors.weaviate_store import normalize_weaviate_url
        headers = {"Authorization": f"Bearer {settings.weaviate_api_key}"} if settings.weaviate_api_key else {}
        return httpx.Client(base_url=normalize_weaviate_url(settings.weaviate_url), headers=headers,
                            timeout=settings.weaviate_timeout_seconds)

    def embed_vector(self, product_id: str) -> dict:
        """Vector đang lưu trong collection đích cho một sản phẩm (cả sản phẩm giữ nguyên, không nhúng lại ở lượt này)."""
        ensure_backend_path()
        from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient
        from src.backend.jobs.embed_products import vector_preview
        settings = self._index_settings()
        with self._weaviate_http(settings) as client:
            response = client.get(f"/v1/objects/{settings.vector_collection}/{WeaviateClient.object_uuid(product_id)}",
                                  params={"include": "vector"})
            if response.status_code == 404:
                raise ValueError(f"Collection {settings.vector_collection} không có vector của sản phẩm này")
            response.raise_for_status()
            obj = response.json()
        return {"productId": product_id, "collection": settings.vector_collection,
                "properties": obj.get("properties"), "vector": vector_preview(obj.get("vector") or [])}

    def _collection_vectors(self, settings, refresh: bool):
        ensure_backend_path()
        from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient
        import numpy as np
        key = (settings.weaviate_url, settings.vector_collection)
        with self._vector_lock:
            cached = self._vectors.get(key)
            if cached and not refresh and time.monotonic() - cached["at"] < VECTOR_CACHE_SECONDS:
                return cached
            client = WeaviateClient(settings.weaviate_url, collection=settings.vector_collection,
                                    vector_index_type=settings.weaviate_vector_index_type,
                                    api_key=settings.weaviate_api_key, timeout_seconds=settings.weaviate_timeout_seconds)
            try:
                meta, vectors = client.fetch(include_vectors=True)
            finally:
                client.close()
            ids = [pid for pid, vec in vectors.items() if vec.size]
            matrix = np.vstack([vectors[pid] for pid in ids]).astype(np.float32) if ids else np.zeros((0, 0), np.float32)
            norms = np.linalg.norm(matrix, axis=1) if ids else np.zeros(0)
            cached = {"at": time.monotonic(), "ids": ids, "matrix": matrix, "norms": norms,
                      "models": Counter(m.model_version for m in meta.values())}
            self._vectors = {key: cached}
            return cached

    def embed_query(self, run_id: str, query: str, k: int = 10, refresh: bool = False) -> dict:
        """Thử truy vấn: e5-small (tiền tố `query: `) → xếp hạng cosine trên mọi vector của collection đích (đọc qua REST).
        Model nạp một lần ở lần bấm đầu (vài giây), giữ cho các lần sau."""
        ensure_backend_path()
        import numpy as np
        from src.backend.app.infrastructure.embeddings.factory import build_embedder
        from src.backend.jobs.embed_products import vector_preview
        query = (query or "").strip()
        if not query or len(query) > EMBED_QUERY_MAX:
            raise ValueError(f"Câu truy vấn cần 1–{EMBED_QUERY_MAX} ký tự")
        k = max(1, min(int(k), 50))
        settings = self._index_settings()
        started = time.monotonic()
        if getattr(self, "_query_embedder", None) is None:
            self._query_embedder = build_embedder(settings)
        vector = np.asarray(self._query_embedder.embed_query(query), dtype=np.float32).reshape(-1)
        embed_ms = round((time.monotonic() - started) * 1000)
        data = self._collection_vectors(settings, refresh)
        if not data["ids"]:
            raise ValueError(f"Collection {settings.vector_collection} chưa có vector nào")
        scores = data["matrix"] @ vector / np.maximum(data["norms"] * float(np.linalg.norm(vector)), 1e-12)
        order = np.argsort(-scores)[:k]
        names: dict[str, dict] = {}
        try:
            names = {r["productId"]: r for r in self._embed_rows(run_id) if r.get("productId")}
        except ValueError:
            pass
        if not names:
            try:
                names = {r["productId"]: r for r in self._products(run_id)}
            except ValueError:
                names = {}
        hits = []
        for rank, i in enumerate(order, start=1):
            pid = data["ids"][i]
            info = names.get(pid) or {}
            hits.append({"rank": rank, "productId": pid, "cosine": round(float(scores[i]), 5),
                         "name": info.get("name"), "taxonomy": info.get("taxonomy"), "destination": info.get("destination"),
                         "text": (info.get("text") or info.get("description") or "")[:300], "inRun": pid in names})
        return {"query": query, "k": k, "collection": settings.vector_collection, "vectors": len(data["ids"]),
                "models": dict(data["models"]), "embedMs": embed_ms, "queryVector": vector_preview(vector),
                "hits": hits}


def ensure_backend_path() -> None:
    """Bước index và ô thử truy vấn dùng code backend (`src.backend…`): cần gốc repo trong sys.path như fresh_catalog."""
    repo = str(ROOT.parent.parent)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def _where(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return f"{parsed.hostname or '?'}{':' + str(parsed.port) if parsed.port else ''}{parsed.path or ''}"


def _short(value, limit: int = 300):
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit] + "…"


def product_diff(before: dict, after: dict) -> dict:
    """Trường đổi giữa hai ảnh chụp của cùng sản phẩm: trường cấp 1 (trừ attributes) và từng khoá của attributes."""
    changed = {}
    for key in sorted(set(before) | set(after)):
        if key == "attributes":
            continue
        if before.get(key) != after.get(key):
            changed[key] = {"before": _short(before.get(key)), "after": _short(after.get(key))}
    a, b = before.get("attributes") or {}, after.get("attributes") or {}
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            changed[f"attributes.{key}"] = {"before": _short(a.get(key)), "after": _short(b.get(key))}
    return changed


def raw_kind(path: Path) -> str:
    name = path.name[:-3] if path.name.endswith(".gz") else path.name
    for ext, kind in ((".json", "json"), (".html", "html"), (".htm", "html"), (".xml", "xml")):
        if name.endswith(ext):
            return kind
    parent = path.parent.name
    return {"json": "json", "html": "html", "xmlgz": "xml"}.get(parent, "text")


def json_summary(data) -> dict:
    if isinstance(data, dict):
        return {"type": "object", "keys": list(data)[:60]}
    if isinstance(data, list):
        return {"type": "array", "length": len(data)}
    return {"type": type(data).__name__}


def html_views(html: str) -> dict:
    """Các khối có cấu trúc trong HTML (JSON-LD, __NEXT_DATA__, hotelDetailResponse) và văn bản hiển thị."""
    out: dict = {}
    title = re.search(r"<title[^>]*>(.*?)</title>", html[:20000], re.S | re.I)
    out["title"] = re.sub(r"\s+", " ", title.group(1)).strip() if title else None
    blocks = []
    for match in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            blocks.append(json.loads(match.group(1).strip()))
        except ValueError:
            continue
    out["jsonLd"] = json.dumps(blocks, ensure_ascii=False, indent=1)[:MAX_TEXT] if blocks else None
    nxt = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if nxt:
        try:
            out["nextData"] = json.dumps(json.loads(nxt.group(1)), ensure_ascii=False, indent=1)[:MAX_TEXT]
        except ValueError:
            out["nextData"] = None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html[:5_000_000], "lxml")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n"))
        out["visibleText"] = text.strip()[:60000]
    except Exception:  # bs4/lxml thiếu hoặc HTML hỏng: vẫn trả mã nguồn
        out["visibleText"] = None
    return out


# ---------------------------------------------------------------------------------------------------- HTTP


def host_allowed(host_header: str, allow_public: bool = False) -> bool:
    """Kiểm tra Host HTTP (chống DNS rebinding); public mode là opt-in cho dashboard vận hành tạm thời."""
    raw = (host_header or "").strip()
    if allow_public:
        return bool(raw)
    host = raw.split("]")[0] + "]" if raw.startswith("[") else raw.split(":")[0]
    return host in ("127.0.0.1", "localhost", "[::1]")


class Handler(BaseHTTPRequestHandler):
    monitor: FreshMonitor
    allow_public_host = False
    read_only = False  # --read-only: chỉ GET; mọi POST (điều khiển job, đổi cấu hình, xoá lượt) trả 405
    server_version = "VotaMonitor/2"

    def log_message(self, fmt, *args):  # im lặng: đây là công cụ nền
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        return host_allowed(self.headers.get("Host") or "", self.allow_public_host)

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._json({"error": "host không hợp lệ"}, 403)
        url = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        m = self.monitor
        num = lambda key, default: int(q.get(key) or default)  # noqa: E731
        pv = q.get("preview") == "1"  # bản chuẩn hoá nháp của lượt
        try:
            if url.path in ("/daily", "/pipeline"):
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if url.path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/log/stream":
                return self._stream_log(q.get("run", ""), num("lines", 300))
            routes = {
                "/api/overview": lambda: m.overview(),
                "/api/storage": lambda: m.storage(),
                "/api/runs": lambda: m.runs(limit=num("limit", 60)),
                "/api/run": lambda: m.run(q.get("id", "")),
                "/api/graph": lambda: m.graph(q.get("run", "")),
                "/api/alerts": lambda: m.alerts(limit=num("limit", 200), include_suppressed=q.get("all") == "1"),
                "/api/feed": lambda: m.feed(q.get("run", ""), q.get("kind", "")),
                "/api/substeps": lambda: m.substeps(q.get("run", ""), q.get("node", ""), q.get("variant", "")),
                "/api/log": lambda: m.log(q.get("run"), q.get("name", LOG_FILE), num("lines", 400), q.get("grep", ""),
                                          runner=q.get("runner") == "1"),
                "/api/raw": lambda: m.raw_list(q.get("run", ""), q.get("source", ""), q.get("q", ""),
                                               num("offset", 0), num("limit", 100)),
                "/api/raw/file": lambda: m.raw_file(q.get("run", ""), q.get("source", ""), q.get("path", "")),
                "/api/interim": lambda: m.interim(q.get("run", ""), q.get("source", ""), q.get("q", ""),
                                                  num("offset", 0), num("limit", 100)),
                "/api/interim/record": lambda: m.interim_record(q.get("run", ""), q.get("source", ""), num("index", -1)),
                "/api/products": lambda: m.products(q.get("run", ""), q.get("q", ""), q.get("taxonomy", ""),
                                                    q.get("level", ""), q.get("source", ""), q.get("destination", ""),
                                                    q.get("flag", ""), num("offset", 0), num("limit", 100), pv),
                "/api/product": lambda: m.product(q.get("run", ""), q.get("id", ""), pv),
                "/api/db": lambda: m.db_rows(q.get("run", ""), q.get("action", ""), q.get("q", ""), q.get("written", ""),
                                             num("offset", 0), num("limit", 100)),
                "/api/artifact": lambda: m.artifact(q.get("run", ""), q.get("name", "")),
                "/api/trip-hotels": lambda: m.trip_hotels(),
                "/api/settings": lambda: m.settings(),
                "/api/health": lambda: m.health(q.get("run", "")),
                "/api/cities": lambda: m.cities(q.get("run", ""), pv),
                "/api/live": lambda: m.live(),
                "/api/normalise": lambda: m.normalise(q.get("run", ""), pv),
                "/api/normalise/rows": lambda: m.normalise_rows(q.get("run", ""), q.get("stage", ""), q.get("q", ""),
                                                                q.get("source", ""), q.get("taxonomy", ""),
                                                                q.get("step", ""), num("offset", 0), num("limit", 100),
                                                                pv),
                "/api/normalise/row": lambda: m.normalise_row(q.get("run", ""), q.get("stage", ""), num("index", -1), pv),
                "/api/normalise/trace": lambda: m.normalise_trace(q.get("run", ""), q.get("id", ""), pv),
                "/api/embed": lambda: m.embed(q.get("run", ""), q.get("action", ""), q.get("taxonomy", ""),
                                              q.get("q", ""), num("offset", 0), num("limit", 100)),
                "/api/embed/row": lambda: m.embed_row(q.get("run", ""), q.get("id", "")),
                "/api/embed/vector": lambda: m.embed_vector(q.get("id", "")),
                "/api/calls": lambda: m.backend_calls(num("after", 0), num("limit", 200)),
                "/api/dbx/tables": lambda: m.dbx().tables(),
                "/api/dbx/graph": lambda: m.dbx().graph(),
                "/api/dbx/rows": lambda: m.dbx().rows(q.get("table", ""), prefixed(q, "f."), q.get("q", ""),
                                                      q.get("sort", ""), q.get("desc") == "1", num("offset", 0),
                                                      num("limit", 50)),
                "/api/dbx/row": lambda: m.dbx().row(q.get("table", ""), prefixed(q, "k.")),
                "/api/dbx/children": lambda: m.dbx().children(q.get("id", ""), num("offset", 0), num("limit", 50)),
            }
            if url.path in routes:
                return self._json(routes[url.path]())
        except (ValueError, KeyError, fresh_settings.SettingsError) as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:  # lỗi gọi Weaviate/model…: báo gọn thay vì đóng kết nối
            return self._json({"error": f"{type(e).__name__}: {str(e)[:300]}"}, 502)
        return self._json({"error": "không tìm thấy"}, 404)

    def _stream_log(self, run_id: str, lines: int) -> None:
        """Server-sent events: `init` (N dòng cuối), `lines` (dòng mới mỗi 0,5 giây), `end` khi lượt không còn chạy."""
        path = self.monitor.run_path(run_id) / LOG_FILE
        lines = max(10, min(lines, 5000))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def send(event: str, payload) -> None:
            self.wfile.write(f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            offset = path.stat().st_size if path.is_file() else 0
            send("init", {"lines": tail_lines(path, lines) if offset else []})
            partial, idle, ping = b"", 0.0, time.monotonic()
            while True:
                time.sleep(STREAM_POLL)
                size = path.stat().st_size if path.is_file() else 0
                if size < offset:
                    offset, partial = 0, b""
                if size > offset:
                    with open(path, "rb") as fh:
                        fh.seek(offset)
                        data = partial + fh.read(min(size - offset, 2_000_000))
                        offset = fh.tell()
                    parts = data.split(b"\n")
                    partial = parts.pop()
                    if parts:
                        send("lines", {"lines": [part.decode("utf-8", errors="replace") for part in parts]})
                    idle = 0.0
                else:
                    idle += STREAM_POLL
                if time.monotonic() - ping > 15:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    ping = time.monotonic()
                if idle >= STREAM_END_IDLE and not self.monitor._is_running(run_id):
                    send("end", {"offset": offset})
                    return
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_POST(self):  # noqa: N802
        if self.read_only:
            return self._json({"error": "monitor đang chạy chỉ đọc"}, 405)
        if not self._host_ok() or self.headers.get("X-Requested-With") != "vota-monitor":
            return self._json({"error": "bị từ chối"}, 403)
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 <= length <= 64_000:
                raise ValueError("nội dung quá lớn")
            body = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("cần một đối tượng JSON")
            if path == "/api/settings":
                return self._json(self.monitor.save_settings(body.get("values") or {}))
            if path == "/api/run":
                code, out = self.monitor.start(str(body.get("mode") or ""))
                return self._json(out, code)
            if path == "/api/resume":
                code, out = self.monitor.resume(str(body.get("run") or ""), str(body.get("from") or ""),
                                                body.get("source") or None)
                return self._json(out, code)
            if path == "/api/stop":
                code, out = self.monitor.stop()
                return self._json(out, code)
            if path == "/api/live":
                code, out = self.monitor.set_live(str(body.get("key") or ""), body.get("changes") or {})
                return self._json(out, code)
            if path == "/api/storage/cleanup":
                return self._json(self.monitor.storage_cleanup(body.get("keepRuns")))
            if path == "/api/embed/query":
                return self._json(self.monitor.embed_query(str(body.get("run") or ""), str(body.get("q") or ""),
                                                           int(body.get("k") or 10), bool(body.get("refresh"))))
        except (ValueError, UnicodeDecodeError, fresh_settings.SettingsError) as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:  # lỗi model/Weaviate: báo gọn
            return self._json({"error": f"{type(e).__name__}: {str(e)[:300]}"}, 502)
        return self._json({"error": "không tìm thấy"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1", help="địa chỉ bind; mặc định chỉ nghe loopback")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--allow-public-host", action="store_true",
                    help="chấp nhận Host public; chỉ bật tạm thời vì UI có POST endpoint điều khiển job")
    ap.add_argument("--read-only", action="store_true",
                    help="chỉ phục vụ GET; từ chối mọi POST (dashboard công khai, không điều khiển được job)")
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="thư mục dữ liệu chung chứa state/, fresh_runs/, logs/ (mặc định VOTA_DATA_DIR nếu có)")
    ap.add_argument("--state-dir", type=Path, default=None, help="mặc định CATALOG_STATE_DIR, rồi <data-dir>/state")
    ap.add_argument("--run-root", type=Path, default=None, help="mặc định CATALOG_RUN_ROOT, rồi <data-dir>/fresh_runs")
    ap.add_argument("--log-dir", type=Path, default=None,
                    help="thư mục log của runner (fresh-catalog-*.log) để xem lỗi xảy ra trước khi lượt tạo thư mục riêng; "
                         "mặc định CATALOG_LOG_DIR, rồi <data-dir>/logs nếu có")
    a = ap.parse_args(argv)
    # Thư mục: tham số > CATALOG_* > --data-dir / VOTA_DATA_DIR (<dữ liệu>/state, /fresh_runs, /logs — cách CD của
    # release-mvp-v2 gọi monitor trong image daily) > data/ cạnh file này.
    data_dir = a.data_dir or (Path(os.environ["VOTA_DATA_DIR"]) if os.environ.get("VOTA_DATA_DIR") else None)
    state_dir = a.state_dir or (Path(os.environ["CATALOG_STATE_DIR"]) if os.environ.get("CATALOG_STATE_DIR")
                                else data_dir / "state" if data_dir else ROOT / "data" / "state")
    run_root = a.run_root or (Path(os.environ["CATALOG_RUN_ROOT"]) if os.environ.get("CATALOG_RUN_ROOT")
                              else data_dir / "fresh_runs" if data_dir else ROOT / "data" / "fresh_runs")
    log_dir = a.log_dir or (Path(os.environ["CATALOG_LOG_DIR"]) if os.environ.get("CATALOG_LOG_DIR")
                            else data_dir / "logs" if data_dir and (data_dir / "logs").is_dir() else None)
    Handler.monitor = FreshMonitor(state_dir.resolve(), run_root.resolve(), log_dir.resolve() if log_dir else None)
    Handler.allow_public_host = a.allow_public_host
    Handler.read_only = a.read_only
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Monitor job cào: http://{a.host}:{a.port}  (state: {state_dir.resolve()}, lượt: {run_root.resolve()})"
          + (" [chỉ đọc]" if a.read_only else "") + " — Ctrl+C để dừng", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
