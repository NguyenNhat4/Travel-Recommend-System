#!/usr/bin/env python3
"""UI theo dõi cào dữ liệu V-OTA: tiến độ từng job, dữ liệu đã parse, file, nhật ký, cảnh báo.

Chỉ đọc (không ghi vào dữ liệu đang cào), chỉ nghe 127.0.0.1, không cần thư viện ngoài:

  python monitor.py                 # http://127.0.0.1:8765
  python monitor.py --port 9000 --data-dir /đường/dẫn/data
  http://127.0.0.1:8765/daily       # job hằng ngày: lượt chạy, bước đang chạy, data version, so sánh, dữ liệu qua từng bước

Nguồn số liệu: data/batches/<job>/{job.json,last-run.json,state/,interim/,raw/,logs/}, data/interim, data/products.jsonl.
Nút "Tạo bản xem trước" chuẩn hoá thử toàn bộ dữ liệu hiện có vào data/preview/ (không đụng catalog chính).
"""
from __future__ import annotations

import argparse
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

import fresh_settings
from fresh_run_log import HISTORY_FILE, LOG_FILE, RUN_FILE, RUNNING_FILE, STOP_FILE, run_dirs, write_json

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "monitor_ui"
RUN_ID = re.compile(r"^(full|daily|index)-\d{8}T\d{6}Z-\d+$")
SOURCE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
LOG_NAME = re.compile(r"^(job\.log|crawl-\d{8}\.log|fresh-catalog-[0-9-]+\.log|fresh-catalog-errors\.log)$")
MAX_TEXT = 2_000_000          # ký tự tối đa trả về cho một file raw
MAX_READ = 30_000_000         # byte tối đa giải nén một file
HEARTBEAT_STALE = 90          # giây không có nhịp sống thì coi lượt đã chết
PROGRESS_RE = re.compile(r"(\d+)/(\d+) xong · (\d+) lỗi · (\d+) bỏ qua · ([\d.]+) trang/phút · còn ~(\S+)")
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
    path = state_dir / "fresh_catalog.lock"
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
    """Kết quả đọc file lớn (interim, products) theo (đường dẫn, mtime, cỡ)."""

    def __init__(self, size: int = 24):
        self.size, self.items, self.lock = size, {}, threading.Lock()

    def get(self, path: Path, loader):
        try:
            st = path.stat()
        except OSError:
            return None
        key = (str(path), st.st_mtime_ns, st.st_size)
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


class FreshMonitor:
    def __init__(self, state_dir: Path, run_root: Path, log_dir: Path | None = None):
        self.state_dir, self.run_root = Path(state_dir), Path(run_root)
        self.log_dir = Path(log_dir) if log_dir else None
        self.cache = FileCache()
        self.spawn_lock = threading.Lock()
        self.spawned: dict | None = None
        self._disk = (0.0, None)

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
            "spawned": spawned,
            "runnerLogs": self.runner_logs()[:8],
        }

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
            out[entry["id"]] = entry
        rows = sorted(out.values(), key=lambda r: r.get("startedAt") or "", reverse=True)
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
        return data

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
        skip = {RUN_FILE, LOG_FILE, "products.jsonl", "db_load.jsonl"}
        out = []
        for p in sorted(list(path.glob("*")) + list((path / "map").glob("*"))):
            if p.is_file() and p.name not in skip and not p.name.startswith("."):
                out.append({"name": str(p.relative_to(path)), "bytes": p.stat().st_size})
        return out

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
        rows = self.cache.get(path, lambda p: [(i, r) for i, r in iter_jsonl(p)])
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
    def _products(self, run_id: str) -> list[dict]:
        path = self.run_path(run_id) / "products.jsonl"
        rows = self.cache.get(path, lambda p: [r for _, r in iter_jsonl(p)])
        if rows is None:
            raise ValueError("Lượt này chưa tới bước chuẩn hoá")
        return rows

    def products(self, run_id: str, q: str = "", taxonomy: str = "", level: str = "", source: str = "",
                 destination: str = "", flag: str = "", offset: int = 0, limit: int = 100) -> dict:
        rows = self._products(run_id)
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

    def product(self, run_id: str, product_id: str) -> dict:
        path = self.run_path(run_id)
        row = next((r for r in self._products(run_id) if r.get("productId") == product_id), None)
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
                for index, record in self.cache.get(interim, lambda p: [(i, r) for i, r in iter_jsonl(p)]) or []:
                    if ident and ident in record_ids(record):
                        matches.append(dict(brief_record(record), index=index))
                    elif kind == "route" and ident and ident == f"{record.get('fromCode')}-{record.get('toCode')}":
                        matches.append(dict(brief_record(record), index=index))
                    if len(matches) >= 5:
                        break
                for match in matches:
                    trace.append({"ref": ref, "source": source, "interim": match,
                                  "raw": self.raw_for(path, source, ident, match.get("url"))})
        db = next((r for _, r in iter_jsonl(path / "db_load.jsonl") if r.get("productId") == product_id), None)
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

    def stop(self) -> tuple[int, dict]:
        info = read_json(self.state_dir / RUNNING_FILE) or {}
        if not lock_busy(self.state_dir) or not info.get("runId"):
            return 409, {"error": "Không có lượt nào đang chạy"}
        write_json(self.state_dir / STOP_FILE, {"runId": info["runId"],
                                                "requestedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        return 202, {"stopping": info["runId"],
                     "message": "Đã gửi yêu cầu dừng; crawler sẽ dừng ở điểm kiểm tra tiếp theo. Bước DB đã bắt đầu có thể hoàn tất; dữ liệu đã commit được giữ lại."}


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
    """Kiểm tra Host HTTP; public mode là opt-in cho dashboard vận hành tạm thời."""
    if allow_public:
        return bool((host_header or "").strip())
    host = (host_header or "").split(":")[0]
    return host in ("127.0.0.1", "localhost", "[::1]")


class Handler(BaseHTTPRequestHandler):
    monitor: Monitor
    daily: DailyApi
    server_version = "VotaMonitor/1"

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
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost", "[::1]")  # chống DNS rebinding

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._json({"error": "host không hợp lệ"}, 403)
        url = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        m = self.monitor
        num = lambda key, default: int(q.get(key) or default)  # noqa: E731
        try:
            if url.path in ("/daily", "/pipeline"):
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if url.path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            routes = {
                "/api/overview": lambda: m.overview(),
                "/api/runs": lambda: m.runs(limit=num("limit", 60)),
                "/api/run": lambda: m.run(q.get("id", "")),
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
                                                    q.get("flag", ""), num("offset", 0), num("limit", 100)),
                "/api/product": lambda: m.product(q.get("run", ""), q.get("id", "")),
                "/api/db": lambda: m.db_rows(q.get("run", ""), q.get("action", ""), q.get("q", ""), q.get("written", ""),
                                             num("offset", 0), num("limit", 100)),
                "/api/artifact": lambda: m.artifact(q.get("run", ""), q.get("name", "")),
                "/api/trip-hotels": lambda: m.trip_hotels(),
                "/api/settings": lambda: m.settings(),
            }
            if url.path in routes:
                return self._json(routes[url.path]())
        except (ValueError, KeyError, fresh_settings.SettingsError) as e:
            return self._json({"error": str(e)}, 400)
        return self._json({"error": "không tìm thấy"}, 404)

    def do_POST(self):  # noqa: N802
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
            if path == "/api/stop":
                code, out = self.monitor.stop()
                return self._json(out, code)
        except (ValueError, UnicodeDecodeError, fresh_settings.SettingsError) as e:
            return self._json({"error": str(e)}, 400)
        return self._json({"error": "không tìm thấy"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1", help="địa chỉ bind; mặc định chỉ nghe loopback")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data-dir", type=Path, default=Path(os.environ.get("VOTA_DATA_DIR", ROOT / "data")))
    a = ap.parse_args(argv)
    Handler.monitor = Monitor(a.data_dir.resolve())
    Handler.daily = DailyApi(a.data_dir.resolve())
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Theo dõi cào dữ liệu: http://127.0.0.1:{a.port}  (dữ liệu: {a.data_dir.resolve()}) — Ctrl+C để dừng", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
