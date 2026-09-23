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
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import api_sources
from daily_api import DailyApi
from collectors.plan import DESTINATIONS

DEST_BY_NAME = {d.name: d for d in DESTINATIONS}

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "monitor_ui"
TARGET_ROWS = 10_000
SOURCE_ORDER = ("vinpearl", "booking_hotels", "agoda_hotels", "trip_attractions", "trip_flights", "booking_flights",
                "booking_attractions")
SOURCE_LABEL = {"vinpearl": "Vinpearl", "booking_hotels": "Booking khách sạn", "agoda_hotels": "Agoda khách sạn",
                "trip_attractions": "Trip điểm tham quan", "trip_flights": "Trip chuyến bay", "booking_flights": "Booking chuyến bay",
                "booking_attractions": "Booking vé/tour"}
JOB_ID = re.compile(r"^[0-9a-f]{20}$")
PIPELINE_RUN = re.compile(r"^\d{8}-\d{6}(-[a-z0-9]{1,12})?$")  # trùng RUN_ID trong pipeline_demo.py
LEVEL_RE = re.compile(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b")
RUNNING_STALE_SECONDS = 600


# ------------------------------------------------------------------------------------------ tiện ích nhỏ


def now() -> float:
    return time.time()


def iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else None


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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
        lines = data.decode("utf-8", errors="replace").split("\n")  # không dùng splitlines(): cắt cả ở U+0085/U+2028 trong JSON
        if lines and lines[-1] == "":
            lines.pop()
        if pos > 0 and lines:
            lines = lines[1:]
        return lines[-n:]
    except OSError:
        return []


def pid_alive(pid: int) -> bool:
    """os.kill(pid, 0) vẫn thành công với tiến trình đã chết nhưng ở trạng thái "zombie" (con của chính tiến trình này, cha chưa
    "nhận xác") — kiểm tra thêm /proc/{pid}/stat để không coi zombie là còn sống (gặp thật 22/09/2026: fetch con đã chết hẳn nhưng
    giao diện vẫn báo "đang tải" mãi)."""
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


class TTLCache:
    """Cache theo khoá + thời gian sống, tránh tính lại khi nhiều tab cùng làm mới."""

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key, ttl: float, fn):
        with self._lock:
            hit = self._data.get(key)
            if hit and now() - hit[0] < ttl:
                return hit[1]
        value = fn()
        with self._lock:
            self._data[key] = (now(), value)
        return value


CACHE = TTLCache()
_FILE_STATS: dict[tuple, dict] = {}


# ------------------------------------------------------------------------------------------ đọc bản ghi trung gian


def price_of(source: str, r: dict):
    if source == "booking_hotels" or source == "agoda_hotels":
        return r.get("minPrice")
    if source == "trip_attractions":
        return r.get("price")
    if source == "booking_attractions":
        return r.get("price") or r.get("minPrice") or r.get("fromPrice")
    if source == "trip_flights":
        return (r.get("oneWay") or {}).get("lowPrice")
    if source == "vinpearl":
        if r.get("recordType") == "vinpearl_tour":
            return r.get("adultSalePrice") or r.get("adultOriginalPrice")
        return (r.get("bestPrice") or {}).get("price")
    return None


def destination_of(r: dict) -> str | None:
    return (r.get("plan") or {}).get("destination")


def rows_estimate(source: str, r: dict) -> int:
    """Số dòng Product mà một bản ghi trung gian sinh ra (thô, chưa khử trùng giữa các nguồn)."""
    if source == "booking_hotels":
        return 1 + len(r.get("rooms") or [])
    if source == "vinpearl" and r.get("recordType") == "vinpearl_hotel":
        return 1 + len(r.get("rooms") or [])
    if source == "trip_flights":
        return 1 + len(r.get("flights") or [])
    return 1


def has_coords(r: dict) -> bool:
    return r.get("latitude") not in (None, "") and r.get("longitude") not in (None, "")


def summarize(source: str, r: dict) -> dict:
    name = r.get("name")
    extra = ""
    if source == "booking_hotels":
        extra = f"{len(r.get('rooms') or [])} phòng · {r.get('starRating') or '–'}★"
    elif source == "agoda_hotels":
        extra = f"{r.get('starRating') or '–'}★ · {r.get('reviewScore') or '–'}/10"
    elif source == "trip_attractions":
        extra = ", ".join(r.get("tags") or [])[:60] or (r.get("suggestedDuration") or "")
    elif source == "trip_flights":
        name = f"{r.get('fromCity') or r.get('fromCode')} → {r.get('toCity') or r.get('toCode')}"
        extra = f"{len(r.get('flights') or [])} chuyến · {', '.join(r.get('airlines') or [])[:40]}"
    elif source == "vinpearl":
        extra = r.get("recordType", "").replace("vinpearl_", "")
        if r.get("recordType") == "vinpearl_hotel":
            extra += f" · {len(r.get('rooms') or [])} hạng phòng"
        else:
            extra += f" · {r.get('supplierName') or ''}"
    missing = []
    if not name:
        missing.append("tên")
    if price_of(source, r) in (None, "", 0):
        missing.append("giá")
    if source != "trip_flights" and not has_coords(r):
        missing.append("toạ độ")
    desc = r.get("description") or r.get("introduction") or r.get("seoDescription")
    if source != "trip_flights" and (not desc or len(str(desc)) < 40):
        missing.append("mô tả")
    return {"name": name, "destination": destination_of(r) or r.get("destinationName") or r.get("city"),
            "price": price_of(source, r), "extra": extra, "url": r.get("url") or r.get("pageUrl"),
            "crawledAt": r.get("crawledAt"), "missing": missing}


def file_stats(path: Path, source: str) -> dict:
    """Thống kê một file interim JSONL; cache theo (đường dẫn, kích thước, mtime)."""
    try:
        st = path.stat()
    except OSError:
        return {"lines": 0, "bytes": 0, "rows": 0, "noPrice": 0, "noCoords": 0, "noDesc": 0, "dest": {}, "urlRows": {}}
    key = (str(path), st.st_size, int(st.st_mtime))
    if key in _FILE_STATS:
        return _FILE_STATS[key]
    lines = rows = no_price = no_coords = no_desc = 0
    dest: Counter = Counter()
    url_rows: dict[str, int] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue  # dòng cuối đang được ghi dở
                lines += 1
                n_rows = rows_estimate(source, r)
                rows += n_rows
                ident = r.get("url") or r.get("pageUrl") or r.get("key")
                if ident:
                    url_rows[ident] = max(url_rows.get(ident, 0), n_rows)
                no_price += price_of(source, r) in (None, "", 0)
                if source != "trip_flights":
                    no_coords += not has_coords(r)
                    desc = r.get("description") or r.get("introduction") or r.get("seoDescription")
                    no_desc += not desc or len(str(desc)) < 40
                d = destination_of(r)
                if d:
                    dest[d] += 1
    except OSError:
        pass
    out = {"lines": lines, "bytes": st.st_size, "rows": rows, "noPrice": no_price, "noCoords": no_coords,
           "noDesc": no_desc, "dest": dict(dest), "mtime": st.st_mtime, "urlRows": url_rows}
    for stale in [k for k in _FILE_STATS if k[0] == key[0]]:
        _FILE_STATS.pop(stale, None)
    _FILE_STATS[key] = out
    return out


def read_records(path: Path, limit: int) -> list[dict]:
    """`limit` bản ghi cuối file (mới nhất trước). Bỏ dòng lỗi (đang ghi dở)."""
    out = []
    for line in tail_lines(path, limit + 5, chunk=1024 * 1024)[::-1]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------------------------------ job


class Monitor:
    def __init__(self, data: Path):
        self.data = data
        self.batches = data / "batches"
        self.preview_state = {"status": "idle", "startedAt": None, "finishedAt": None, "message": "", "summary": None}
        self.preview_lock = threading.Lock()

    # -- danh sách "gốc dữ liệu": job batch + thư mục data/ gốc + các thư mục bổ sung
    def roots(self) -> list[dict]:
        out = []
        if self.batches.is_dir():
            for job in sorted(self.batches.iterdir()):
                spec = read_json(job / "job.json")
                if spec and JOB_ID.match(job.name):
                    out.append({"id": job.name, "path": job, "kind": "batch", "spec": spec})
        main_paths = [("main", self.data, "data/ gốc (đợt cào 15–19/09)")]
        main_paths += [(p.name, p, p.name) for p in sorted(self.data.glob("enrichment-*")) if p.is_dir()]
        for rid, path, label in main_paths:
            if (path / "interim").is_dir():
                out.append({"id": rid, "path": path, "kind": "legacy",
                            "spec": {"source": "mixed", "city": label, "period": None, "args": []}})
        return out

    def root_by_id(self, rid: str) -> dict | None:
        return next((r for r in self.roots() if r["id"] == rid), None)

    # -- trạng thái SQLite của một gốc
    @staticmethod
    def state_of(path: Path) -> dict:
        db = path / "state" / "crawl_state.sqlite"
        out = {"items": {}, "discovery": [], "updatedAt": None, "errors": []}
        if not db.exists():
            return out
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)
        except sqlite3.Error:
            return out
        try:
            for src, status, n in con.execute("SELECT source, status, COUNT(*) FROM items GROUP BY source, status"):
                out["items"].setdefault(src, {})[status] = n
            out["discovery"] = [{"source": s, "key": k, "found": f, "doneAt": d}
                                for s, k, f, d in con.execute("SELECT source, key, found, done_at FROM discovery")]
            row = con.execute("SELECT MAX(updated_at) FROM items").fetchone()
            out["updatedAt"] = row[0] if row else None
            out["errors"] = [{"error": e, "count": n} for e, n in con.execute(
                "SELECT last_error, COUNT(*) FROM items WHERE status='failed' AND last_error IS NOT NULL "
                "GROUP BY last_error ORDER BY 2 DESC LIMIT 4")]
        except sqlite3.Error:
            pass
        finally:
            con.close()
        return out

    @staticmethod
    def holds_file(pid: int, target: Path) -> bool | None:
        """Tiến trình `pid` đang mở `target`? RunLock giữ file khoá mở suốt thời gian chạy, còn file cũ vẫn ghi PID của
        tiến trình đã xong (hoặc của batch.py đang chạy job khác) nên không thể tin PID. None = không kiểm tra được."""
        fd_dir = Path(f"/proc/{pid}/fd")
        if not fd_dir.is_dir():
            return None
        want = str(target.resolve())
        try:
            for fd in fd_dir.iterdir():
                try:
                    if os.readlink(fd) == want:
                        return True
                except OSError:
                    continue
        except OSError:
            return None
        return False

    @classmethod
    def running_pid(cls, path: Path) -> int | None:
        """PID tiến trình đang giữ một khoá trong state/ của job này, hoặc None."""
        for lock in (path / "state").glob("*.lock"):
            try:
                pid = int(lock.read_text().strip() or 0)
            except (OSError, ValueError):
                continue
            if not (pid and pid_alive(pid)):
                continue
            held = cls.holds_file(pid, lock)
            if held:
                return pid
            if held is None:
                # Không đọc được fd (tiến trình khác người dùng, luồng hệ thống dùng lại PID cũ trong file khoá): chỉ tin khi
                # dòng lệnh đúng là crawl/batch của chính job này.
                try:
                    cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
                except OSError:
                    continue
                if "python" not in cmd:
                    continue
                if lock.stem == "batch_job" and "batch.py" in cmd:
                    return pid
                if any(x in cmd for x in ("crawl.py", "normalise.py")) and re.search(rf"--data-dir {re.escape(str(path))}(\s|$)", cmd):
                    return pid
        return None

    def log_file(self, path: Path) -> Path | None:
        logs = sorted((path / "logs").glob("crawl-*.log"), key=lambda p: p.stat().st_mtime) if (path / "logs").is_dir() else []
        return logs[-1] if logs else None

    def job_view(self, root: dict, detail: bool = False) -> dict:
        path, spec = root["path"], root["spec"]
        source = (spec.get("source") or "").replace("-", "_")
        st = self.state_of(path)
        sources = [source] if source and source != "mixed" else sorted(st["items"])
        counts: Counter = Counter()
        for s in sources:
            counts.update(st["items"].get(s, {}))
        skipped_n = counts.get("skipped", 0) + counts.get("gone", 0)
        total = sum(counts.values()) - skipped_n  # URL đã cào ở job khác (deepen_jobs) hoặc không cào được: ngoài mẫu số
        interim_dir = path / "interim"
        files = {p.stem: file_stats(p, p.stem) for p in interim_dir.glob("*.jsonl")} if interim_dir.is_dir() else {}
        records = sum(f["lines"] for f in files.values())
        rows_est = sum(f["rows"] for f in files.values())
        last_run = read_json(path / "last-run.json")
        pid = self.running_pid(path)
        code = (last_run or {}).get("exitCode")
        pending = counts.get("pending", 0)
        if pid:
            status = "running"
        elif root["kind"] == "legacy":
            status = "done"
        elif code == 75:
            status = "blocked"
        elif code not in (None, 0):
            status = "failed"
        elif pending:
            status = "paused"
        elif code == 0:
            status = "done"
        else:
            status = "idle"
        updated = st["updatedAt"]
        log_path = self.log_file(path)
        last_activity = max([x for x in (log_path.stat().st_mtime if log_path else 0,
                                         (path / "last-run.json").stat().st_mtime if (path / "last-run.json").exists() else 0) if x] or [0])
        view = {
            "id": root["id"], "kind": root["kind"], "source": source or "mixed", "city": spec.get("city"),
            "route": spec.get("route"), "period": spec.get("period"), "once": bool(spec.get("once")),
            "status": status, "pid": pid, "exitCode": code,
            "pending": pending, "done": counts.get("done", 0), "failed": counts.get("failed", 0),
            "skipped": skipped_n, "total": total,
            "records": records, "rowsEstimate": rows_est,
            "updatedAt": updated, "lastActivity": iso(last_activity) if last_activity else None,
            "stalled": bool(pid and last_activity and now() - last_activity > RUNNING_STALE_SECONDS),
            "discoveryFound": sum((d["found"] or 0) for d in st["discovery"] if d["source"] in sources),
        }
        if detail:
            view.update({
                "spec": spec, "errors": st["errors"], "discovery": st["discovery"], "counts": dict(counts),
                "files": {k: {"lines": v["lines"], "bytes": v["bytes"], "noPrice": v["noPrice"],
                              "noCoords": v["noCoords"], "noDesc": v["noDesc"]} for k, v in files.items()},
                "log": tail_lines(log_path, 80) if log_path else [],
            })
        return view

    def jobs(self) -> list[dict]:
        return [self.job_view(r) for r in self.roots()]

    # -- tổng quan
    def overview(self) -> dict:
        jobs = self.jobs()
        by_status = Counter(j["status"] for j in jobs if j["kind"] == "batch")
        per_source: dict[str, dict] = {}
        for j in jobs:
            s = per_source.setdefault(j["source"], {"jobs": 0, "running": 0, "done": 0, "failed": 0, "pending": 0,
                                                     "urls": 0, "records": 0, "rows": 0})
            if j["kind"] != "batch":
                continue
            s["jobs"] += 1
            s["running"] += j["status"] == "running"
            s["urls"] += j["total"]
            s["done"] += j["done"]
            s["failed"] += j["failed"]
            s["pending"] += j["pending"]
            s["records"] += j["records"]
            s["rows"] += j["rowsEstimate"]
        per_source.pop("mixed", None)
        # Độ phủ: (điểm đến × nguồn) = số bản ghi đã parse, từ job batch (theo thành phố của job) + đợt cào gốc (theo plan)
        cover: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        base_urls: dict[tuple, int] = {}   # (nguồn, url) → số dòng, từ đợt cào gốc data/interim
        new_urls: dict[tuple, int] = {}    # các URL chỉ có ở job batch mới
        for root in self.roots():
            spec = root["spec"]
            interim = root["path"] / "interim"
            if not interim.is_dir():
                continue
            for f in interim.glob("*.jsonl"):
                fs = file_stats(f, f.stem)
                if root["kind"] == "legacy":
                    if root["id"] == "main":
                        for u, n in fs["urlRows"].items():
                            base_urls[(f.stem, u)] = max(base_urls.get((f.stem, u), 0), n)
                    for dest, n in fs["dest"].items():
                        cover[dest][f.stem] += n
                else:
                    for u, n in fs["urlRows"].items():
                        new_urls[(f.stem, u)] = max(new_urls.get((f.stem, u), 0), n)
                    if spec.get("city") and spec["city"] != "all":
                        cover[spec["city"]][f.stem] += fs["lines"]
        legacy_rows = sum(base_urls.values())
        fresh_rows = sum(n for k, n in new_urls.items() if k not in base_urls)
        refreshed = sum(1 for k in new_urls if k in base_urls)
        plan_names = [d.name for d in DESTINATIONS]
        coverage = [{"destination": d.name, "counts": dict(cover.get(d.name, {})), "hasAirport": bool(d.airports),
                     "configured": {"booking_hotels": True, "agoda_hotels": bool(d.agoda_city),
                                    "trip_attractions": bool(d.trip_city), "trip_flights": bool(d.airports)}}
                    for d in DESTINATIONS]
        extra = [{"destination": n, "counts": dict(c), "extra": True} for n, c in cover.items() if n not in plan_names]
        rows_batch = fresh_rows
        catalog = self.catalog_summary(self.data / "products.jsonl")
        mem = self.memory()
        return {
            "generatedAt": iso(now()), "target": TARGET_ROWS,
            "jobs": {"total": sum(1 for j in jobs if j["kind"] == "batch"), "byStatus": dict(by_status)},
            "sources": per_source, "sourceLabels": SOURCE_LABEL, "coverage": coverage + extra,
            "rowsEstimate": {"batch": rows_batch, "baseline": legacy_rows, "total": rows_batch + legacy_rows,
                             "refreshed": refreshed,
                             "note": "Ước tính thô theo URL duy nhất: 1 dòng cơ sở + số hạng phòng, 1 dòng mỗi điểm/vé/tuyến + chuyến bay. "
                                     "Trang cào lại (đã có ở đợt trước) chỉ tính một lần. Chưa khử trùng giữa Booking/Agoda/Vinpearl "
                                     "và chưa lọc sản phẩm thiếu giá, nên dùng nút “Tạo bản xem trước” để có con số thật."},
            "catalog": catalog, "preview": self.preview_view(), "resources": mem,
        }

    def catalog_summary(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        st = path.stat()

        def build():
            tax, level, dest = Counter(), Counter(), Counter()
            price = coords = desc = rows = 0
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    rows += 1
                    tax[r["taxonomy"]] += 1
                    level[f"{r['taxonomy']}:{(r.get('attributes') or {}).get('level') or '-'}"] += 1
                    dest[r["destination"] or "?"] += 1
                    price += r["unitPrice"] is not None
                    a = r.get("attributes") or {}
                    coords += a.get("latitude") is not None
                    desc += bool(r.get("description") and len(r["description"]) >= 40)
            return {"rows": rows, "byTaxonomy": dict(tax), "byLevel": dict(level),
                    "byDestination": dict(dest.most_common()), "withPrice": price, "withCoords": coords, "withDescription": desc,
                    "modified": iso(st.st_mtime)}
        return CACHE.get(("catalog", str(path), st.st_mtime, st.st_size), 3600, build)

    @staticmethod
    def memory() -> dict:
        info = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
        except (OSError, ValueError):
            pass
        chrome = [0, 0]
        crawlers = []
        try:
            for p in Path("/proc").iterdir():
                if not p.name.isdigit():
                    continue
                try:
                    cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
                    if not cmd:
                        continue
                    rss = 0
                    for line in (p / "status").read_text().splitlines():
                        if line.startswith("VmRSS:"):
                            rss = int(line.split()[1]) * 1024
                            break
                except OSError:
                    continue
                if "ms-playwright" in cmd and "chrome" in cmd:
                    chrome[0] += 1
                    chrome[1] += rss
                elif "python" in cmd and re.search(r"(crawl|batch|normalise)\.py", cmd):
                    crawlers.append({"pid": int(p.name), "rss": rss, "cmd": re.sub(r".*?(crawl|batch|normalise)\.py", r"\1.py", cmd)[:170]})
        except OSError:
            pass
        disk = shutil.disk_usage(ROOT)
        return {"memTotal": info.get("MemTotal"), "memAvailable": info.get("MemAvailable"), "chromeProcesses": chrome[0],
                "chromeRss": chrome[1], "crawlers": crawlers, "diskFree": disk.free, "diskTotal": disk.total}

    # -- dữ liệu đã parse
    def records(self, source: str, job: str, limit: int, q: str) -> dict:
        roots = [r for r in self.roots() if (job in ("all", "") or r["id"] == job)]
        files = []
        for r in roots:
            p = r["path"] / "interim" / f"{source}.jsonl"
            if p.exists() and p.stat().st_size:
                files.append((p.stat().st_mtime, r, p))
        files.sort(key=lambda x: x[0], reverse=True)
        window = 3000 if q else limit
        out, total = [], 0
        for _mtime, root, p in files:
            total += file_stats(p, source)["lines"]
            if len(out) >= limit:
                continue
            for rec in read_records(p, window):
                s = summarize(source, rec)
                if q and q.lower() not in json.dumps(s, ensure_ascii=False).lower():
                    continue
                s.update({"job": root["id"], "jobCity": root["spec"].get("city"), "key": rec.get("key")})
                out.append(s)
                if len(out) >= limit:
                    break
        return {"source": source, "total": total, "items": out}

    def record(self, job: str, source: str, key: str) -> dict | None:
        """Bản ghi đầy đủ theo key (lần xuất hiện cuối cùng trong file)."""
        root = self.root_by_id(job)
        if not root or not key:
            return None
        found = None
        try:
            with open(root["path"] / "interim" / f"{source}.jsonl", encoding="utf-8") as fh:
                for text in fh:
                    if key in text:
                        try:
                            rec = json.loads(text)
                        except ValueError:
                            continue
                        if rec.get("key") == key:
                            found = rec
        except OSError:
            return None
        return found

    # -- file
    def files(self) -> dict:
        def build():
            rows = []
            total_files = total_bytes = 0
            for r in self.roots():
                path = r["path"]
                raw_files, raw_bytes = dir_size(path / "raw")
                prof_files, prof_bytes = dir_size(path / "browser-profile")
                interim = {p.stem: file_stats(p, p.stem) for p in (path / "interim").glob("*.jsonl")} if (path / "interim").is_dir() else {}
                st = self.state_of(path)
                done = sum(c.get("done", 0) for c in st["items"].values())
                rows.append({"id": r["id"], "kind": r["kind"], "source": (r["spec"].get("source") or ""), "city": r["spec"].get("city"),
                             "rawFiles": raw_files, "rawBytes": raw_bytes, "profileBytes": prof_bytes,
                             "interimLines": sum(v["lines"] for v in interim.values()),
                             "interimBytes": sum(v["bytes"] for v in interim.values()), "doneItems": done,
                             "hasState": (path / "state" / "crawl_state.sqlite").exists()})
                total_files += raw_files
                total_bytes += raw_bytes + prof_bytes
            shared_files, shared_bytes = dir_size(self.batches / "shared")
            top = []
            for name in ("raw", "interim", "batches", "catalog", "map", "backups", "browser-profile", "preview", "logs"):
                d = self.data / name
                if d.exists():
                    n, b = dir_size(d)
                    top.append({"name": f"data/{name}", "files": n, "bytes": b})
            for f in ("products.jsonl", "products.json", "products.csv"):
                p = self.data / f
                if p.exists():
                    top.append({"name": f"data/{f}", "files": 1, "bytes": p.stat().st_size})
            return {"jobs": rows, "top": top, "shared": {"files": shared_files, "bytes": shared_bytes},
                    "totals": {"rawFiles": total_files, "bytes": total_bytes}}
        return CACHE.get("files", 30, build)

    # -- nhật ký
    def log(self, job: str, lines: int) -> dict:
        roots = self.roots()
        if job in ("running", "", "all"):
            chosen = [r for r in roots if r["kind"] == "batch" and self.running_pid(r["path"])] or \
                     sorted((r for r in roots if r["kind"] == "batch"), key=lambda r: (self.log_file(r["path"]).stat().st_mtime
                            if self.log_file(r["path"]) else 0), reverse=True)[:3]
        else:
            chosen = [r for r in roots if r["id"] == job]
        merged = []
        for r in chosen:
            lf = self.log_file(r["path"])
            if not lf:
                continue
            tag = f"{(r['spec'].get('source') or '')[:14]} {str(r['spec'].get('city') or '')[:12]}".strip()
            for line in tail_lines(lf, lines):
                m = re.match(r"^(\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2})", line)
                merged.append((m.group(2) if m else "", tag, line))
        merged.sort(key=lambda x: x[0])
        out = []
        for _t, tag, line in merged[-lines:]:
            m = LEVEL_RE.search(line)
            out.append({"job": tag, "level": m.group(1) if m else "INFO", "text": line})
        return {"jobs": [f"{r['spec'].get('source')} {r['spec'].get('city')}" for r in chosen], "lines": out}

    # -- kiểm tra hợp lý
    def health(self) -> dict:
        items = []

        def add(sev, title, detail="", job=None):
            items.append({"severity": sev, "title": title, "detail": detail, "job": job})

        jobs = [j for j in self.jobs() if j["kind"] == "batch"]
        mem = self.memory()
        if mem.get("memAvailable") is not None and mem["memAvailable"] < 1.0 * 2**30:
            add("error", "RAM khả dụng dưới 1 GB", f"Chỉ còn {mem['memAvailable'] / 2**30:.1f} GB; đóng bớt ứng dụng hoặc dừng một terminal cào.")
        elif mem.get("memAvailable") is not None and mem["memAvailable"] < 2.0 * 2**30:
            add("warn", "RAM khả dụng dưới 2 GB", f"{mem['memAvailable'] / 2**30:.1f} GB; {mem['chromeProcesses']} tiến trình Chromium đang dùng {mem['chromeRss'] / 2**30:.1f} GB.")
        if mem["diskFree"] < 20 * 2**30:
            add("warn", "Đĩa còn dưới 20 GB", f"{mem['diskFree'] / 2**30:.0f} GB trống.")
        for j in jobs:
            label = f"{j['source']} · {j['city']}"
            if j["status"] == "blocked":
                add("error", f"Bị chặn (mã 75): {label}", "Nghỉ vài giờ rồi chạy lại đúng lệnh; không giảm --delay.", j["id"])
            elif j["status"] == "failed":
                add("error", f"Job lỗi (mã {j['exitCode']}): {label}", "Xem nhật ký của job.", j["id"])
            if j["stalled"]:
                add("warn", f"Đang chạy nhưng không có hoạt động > 10 phút: {label}", "Có thể đang chờ xác minh trong cửa sổ trình duyệt.", j["id"])
            dest = DEST_BY_NAME.get(j["city"])
            unconfigured = bool(dest) and ((j["source"] == "trip_attractions" and not dest.trip_city)
                                           or (j["source"] == "agoda_hotels" and not dest.agoda_city))  # cố ý chưa có ID kiểm chứng
            if (j["status"] in ("done", "paused") and j["total"] == 0 and not unconfigured
                    and j["source"] in ("booking_hotels", "agoda_hotels", "trip_attractions") and not j["once"]):
                add("warn", f"Không tìm được URL nào: {label}", "Kiểm tra booking_query / slug Agoda / ID Trip trong collectors/plan.py.", j["id"])
            if j["done"] and j["records"] < j["done"] * 0.9 and j["source"] not in ("trip_flights", "vinpearl"):
                add("warn", f"Đã cào {j['done']} trang nhưng chỉ {j['records']} bản ghi: {label}", "Parser có thể đang bỏ sót trang; thử `crawl.py reparse`.", j["id"])
            asked = self._per_destination(j["id"])
            found = max((d["found"] or 0 for d in self.state_of(self.batches / j["id"])["discovery"]
                         if d["key"].startswith("search2:")), default=None) if asked else None
            if asked and found is not None and j["source"] == "booking_hotels" and found < asked * 0.5 and j["status"] != "running":
                add("info", f"Booking chỉ trả {found}/{asked} khách sạn: {label}",
                    "Thành phố nhỏ, hoặc cách tải thêm kết quả đã đổi; so sánh với các thành phố khác.", j["id"])
            if j["failed"] and j["total"] and j["failed"] / j["total"] > 0.2:
                add("warn", f"{j['failed']}/{j['total']} URL lỗi: {label}", "Chạy `crawl.py retry-failed <nguồn>` sau khi kiểm tra lỗi.", j["id"])
        # Chất lượng dữ liệu đã parse theo nguồn
        agg: dict[str, Counter] = defaultdict(Counter)
        for r in self.roots():
            if r["kind"] != "batch":
                continue
            for p in (r["path"] / "interim").glob("*.jsonl") if (r["path"] / "interim").is_dir() else []:
                fs = file_stats(p, p.stem)
                a = agg[p.stem]
                a["lines"] += fs["lines"]; a["noPrice"] += fs["noPrice"]; a["noCoords"] += fs["noCoords"]; a["noDesc"] += fs["noDesc"]
        for src, a in agg.items():
            if a["lines"] < 20:
                continue
            for key, label, limit in (("noPrice", "giá", 0.35), ("noCoords", "toạ độ", 0.15), ("noDesc", "mô tả", 0.4)):
                if src == "trip_attractions" and key == "noPrice":
                    continue  # điểm công cộng không bán vé
                if a[key] / a["lines"] > limit:
                    add("warn", f"{SOURCE_LABEL.get(src, src)}: {a[key]}/{a['lines']} bản ghi thiếu {label}",
                        f"Ngưỡng bình thường < {int(limit * 100)}%.")
        # URL trùng giữa các job cùng nguồn (cào lặp)
        dup = self.duplicate_urls()
        for src, n in dup.items():
            add("info", f"{SOURCE_LABEL.get(src, src)}: {n} URL xuất hiện ở nhiều job", "Cào lặp cùng một trang; chuẩn hoá sẽ gộp nhưng tốn request.")
        if not items:
            add("ok", "Không có cảnh báo", "Mọi kiểm tra hiện tại đều ổn.")
        order = {"error": 0, "warn": 1, "info": 2, "ok": 3}
        items.sort(key=lambda x: order[x["severity"]])
        return {"generatedAt": iso(now()), "items": items, "counts": dict(Counter(i["severity"] for i in items))}

    def _per_destination(self, job_id: str) -> int | None:
        spec = (read_json(self.batches / job_id / "job.json") or {}).get("args") or []
        return int(spec[spec.index("--per-destination") + 1]) if "--per-destination" in spec else None

    def duplicate_urls(self) -> dict[str, int]:
        def build():
            urls: dict[str, Counter] = defaultdict(Counter)
            for r in self.roots():
                if r["kind"] != "batch":
                    continue
                for p in (r["path"] / "interim").glob("*.jsonl") if (r["path"] / "interim").is_dir() else []:
                    try:
                        with open(p, encoding="utf-8") as fh:
                            for line in fh:
                                m = re.search(r'"url": "([^"]+)"', line)
                                if m:
                                    urls[p.stem][m.group(1)] += 1
                    except OSError:
                        continue
            return {s: sum(1 for n in c.values() if n > 1) for s, c in urls.items() if any(n > 1 for n in c.values())}
        return CACHE.get("dups", 60, build)

    # -- xem trước catalog chuẩn hoá
    def preview_view(self) -> dict:
        with self.preview_lock:
            view = dict(self.preview_state)
        return view

    def start_preview(self) -> dict:
        with self.preview_lock:
            if self.preview_state["status"] == "running":
                return dict(self.preview_state)
            self.preview_state = {"status": "running", "startedAt": iso(now()), "finishedAt": None,
                                  "message": "Đang gộp dữ liệu...", "summary": None}
        threading.Thread(target=self._preview_worker, daemon=True).start()
        return self.preview_view()

    def _set_preview(self, **kw):
        with self.preview_lock:
            self.preview_state.update(kw)

    def _preview_worker(self):
        prev = self.data / "preview"
        try:
            shutil.rmtree(prev, ignore_errors=True)
            (prev / "interim").mkdir(parents=True)
            seen: dict[str, set] = defaultdict(set)
            lines: dict[str, list] = defaultdict(list)

            def add_lines(path: Path, source: str, raw_archive: str | None):
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    return
                for line in text.split("\n"):
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue  # dòng cuối đang được ghi dở
                    if raw_archive:
                        rec["rawArchive"] = raw_archive
                    canon = json.dumps(rec, sort_keys=True, ensure_ascii=False)
                    if canon not in seen[source]:
                        seen[source].add(canon)
                        lines[source].append(canon)

            for f in sorted((self.data / "interim").glob("*.jsonl")):
                add_lines(f, f.stem, None)
            for r in self.roots():
                if r["kind"] != "batch":
                    continue
                for f in (r["path"] / "interim").glob("*.jsonl") if (r["path"] / "interim").is_dir() else []:
                    add_lines(f, f.stem, str((r["path"] / "raw").resolve()))
            for source, ls in lines.items():
                (prev / "interim" / f"{source}.jsonl").write_text("\n".join(ls) + "\n", encoding="utf-8")
            self._set_preview(message="Đang chuẩn hoá (khử trùng, gộp nguồn)...")
            cmd = [sys.executable, str(ROOT / "normalise.py"), "--data-dir", str(prev), "--no-plan",
                   "--rooms-per-hotel", "0", "--flights-per-route", "0"]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
            if proc.returncode != 0:
                self._set_preview(status="error", finishedAt=iso(now()),
                                  message=(proc.stderr or proc.stdout)[-600:] or f"normalise thoát mã {proc.returncode}")
                return
            summary = self.catalog_summary(prev / "products.jsonl")
            self._set_preview(status="done", finishedAt=iso(now()), message="Xong. Đây chỉ là bản xem trước, catalog chính chưa đổi.",
                              summary=summary)
        except Exception as e:  # noqa: BLE001 - báo lỗi lên UI thay vì làm chết luồng
            self._set_preview(status="error", finishedAt=iso(now()), message=f"{type(e).__name__}: {e}")

    # -- luồng demo (pipeline_demo.py): trang /pipeline chỉ đọc state.json và khởi chạy tiến trình con với tham số đã kiểm tra
    def pipeline_state(self, run: str) -> dict:
        demo = self.data / "demo"
        rid = run
        if run == "latest":
            try:
                rid = (demo / "latest.txt").read_text(encoding="utf-8").strip()
            except OSError:
                return {"empty": True}
        if not PIPELINE_RUN.match(rid):
            raise ValueError("lượt chạy không hợp lệ")
        st = read_json(demo / "runs" / rid / "state.json")
        if not st:
            return {"empty": True}
        if st.get("status") == "running" and not pid_alive(int(st.get("pid") or 0)):
            st["status"], st["stale"] = "stopped", True  # tiến trình đã chết giữa chừng
        return st

    def pipeline_runs(self) -> list[dict]:
        runs = self.data / "demo" / "runs"
        out = []
        if runs.is_dir():
            for p in sorted((x for x in runs.iterdir() if x.is_dir() and PIPELINE_RUN.match(x.name)), reverse=True)[:12]:
                st = read_json(p / "state.json") or {}
                out.append({"id": p.name, "status": st.get("status", "?"), "startedAt": st.get("startedAt")})
        return out

    def pipeline_config(self) -> dict:
        return {"tokens": api_sources.token_status(), "kinds": list(api_sources.FETCH_KINDS),
                "defaultDestinations": [d.name for d in DESTINATIONS[:15]]}

    def pipeline_inbox(self) -> dict:
        return api_sources.inbox_overview(self.data / "demo" / "inbox")

    def save_token(self, key: str, value: str) -> dict:
        api_sources.save_env_var(key, value)
        return api_sources.token_status()

    def clear_token(self, key: str) -> dict:
        api_sources.clear_env_var(key)
        return api_sources.token_status()

    def run_probe(self, kind: str, destination: str, limit, max_usd) -> dict:
        destination = str(destination or "").strip() or "Nha Trang"
        if len(destination) > 60 or not re.fullmatch(r"[\w ,.\-]+", destination):
            raise ValueError("điểm đến không hợp lệ")
        try:
            limit = min(max(int(limit), 1), 10)
            max_usd = min(max(float(max_usd), 0.01), 0.5)
        except (TypeError, ValueError):
            raise ValueError("limit/maxUsd phải là số") from None
        return api_sources.probe_kind(kind, destination, limit, max_usd, self.data / "demo" / "probe")

    def pipeline_fetch(self) -> dict:
        st = read_json(self.data / "demo" / "fetch.json") or {"status": "idle"}
        if st.get("status") == "fetching" and not pid_alive(int(st.get("pid") or 0)):
            st["status"], st["stale"] = "failed", True
        return st

    def start_pull(self, opts: dict) -> tuple[int, dict]:
        """Tải hàng loạt từ API rồi tự xử lý hết. Chi tiêu bị chặn cứng ở phía này (≤ $5, ≤ 500 mục/điểm đến), token chỉ đọc từ .env."""
        kind = str(opts.get("source") or "")
        if kind not in api_sources.FETCH_KINDS:
            raise ValueError("nguồn không hợp lệ")
        need = {"apify-agoda": "apify", "apify-booking": "apify", "apify-booking-full": "apify", "serpapi": "serpapi", "travelpayouts": "travelpayouts"}[kind]
        if not api_sources.token_status()[need]:
            return 400, {"error": "Chưa có token cho nguồn này trong file .env (xem README, mục Nguồn API). Điền xong tải lại trang."}
        if self.pipeline_state("latest").get("status") == "running" or self.pipeline_fetch().get("status") == "fetching":
            return 409, {"error": "Đang có một lượt tải hoặc lượt chạy, đợi nó xong."}

        def num(key: str, lo: float, hi: float, default: float, cast=int):
            try:
                v = cast(opts.get(key) if opts.get(key) not in (None, "") else default)
            except (TypeError, ValueError):
                raise ValueError(f"{key} phải là số") from None
            return min(max(v, lo), hi)

        dests = str(opts.get("destinations") or "").strip()
        if dests and (len(dests) > 300 or not re.fullmatch(r"[\w ,.\-]+", dests)):
            raise ValueError("điểm đến chỉ gồm chữ, số, dấu cách và dấu phẩy")
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        argv = [sys.executable, str(ROOT / "pipeline_demo.py"), "pull", kind, "--run-id", run_id, "--source-data-dir", str(self.data),
                "--max-items", str(num("maxItems", 1, api_sources.MAX_ITEMS_PER_DESTINATION, 50)),
                "--max-usd", str(num("maxUsd", 0.01, api_sources.MAX_USD_PER_FETCH, 1.0, float)),
                "--pages", str(num("pages", 1, 5, 1)), "--replay-delay-ms", str(num("delayMs", 0, 2000, 300))]
        if dests:
            argv += ["--destinations", dests]
        if opts.get("onlyApi", True):
            argv.append("--only-api")
        if opts.get("noDb"):
            argv.append("--no-db")
        (self.data / "demo").mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "VOTA_DATA_DIR": str(self.data)}
        with open(self.data / "demo" / f"launcher-{run_id}.log", "w", encoding="utf-8") as log:
            subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        return 200, {"runId": run_id}

    def start_pipeline(self, opts: dict) -> tuple[int, dict]:
        if self.pipeline_state("latest").get("status") == "running":
            return 409, {"error": "Đang có một lượt chạy, đợi nó xong."}

        def num(key: str, lo: int, hi: int, default: int) -> int:
            try:
                v = int(opts.get(key) if opts.get(key) not in (None, "") else default)
            except (TypeError, ValueError):
                raise ValueError(f"{key} phải là số") from None
            return min(max(v, lo), hi)

        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        argv = [sys.executable, str(ROOT / "pipeline_demo.py"), "run", "--run-id", run_id, "--source-data-dir", str(self.data),
                "--replay-delay-ms", str(num("delayMs", 0, 2000, 300))]
        dests = str(opts.get("destinations") or "").strip()
        if dests:
            if len(dests) > 200 or not re.fullmatch(r"[\w ,.\-]+", dests):
                raise ValueError("điểm đến chỉ gồm chữ, số, dấu cách và dấu phẩy")
            argv += ["--destinations", dests]
        if opts.get("maxHotels") not in (None, "", 0, "0"):
            argv += ["--max-hotels", str(num("maxHotels", 1, 20000, 2000))]
        if opts.get("liveVinpearl"):  # HTTP thường, không mở trình duyệt; vé/tour Vinpearl cần Chromium nên giao diện không có
            argv.append("--live-vinpearl")
        if opts.get("onlyApi"):
            argv.append("--only-api")
        if opts.get("noDb"):
            argv.append("--no-db")
        (self.data / "demo").mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "VOTA_DATA_DIR": str(self.data)}
        with open(self.data / "demo" / f"launcher-{run_id}.log", "w", encoding="utf-8") as log:
            subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        return 200, {"runId": run_id}


# ------------------------------------------------------------------------------------------ HTTP


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
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost", "[::1]")  # chống DNS rebinding

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._json({"error": "host không hợp lệ"}, 403)
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        m = self.monitor
        try:
            if url.path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/overview":
                return self._json(CACHE.get("overview", 2.5, m.overview))
            if url.path == "/api/jobs":
                return self._json(CACHE.get("jobs", 2.5, m.jobs))
            if url.path == "/api/job":
                root = m.root_by_id(q.get("id", ""))
                return self._json(m.job_view(root, detail=True)) if root else self._json({"error": "không có job"}, 404)
            if url.path == "/api/records":
                source = q.get("source", "booking_hotels")
                if source not in SOURCE_ORDER:
                    return self._json({"error": "nguồn không hợp lệ"}, 400)
                job = q.get("job", "all")
                if job != "all" and not (JOB_ID.match(job) or job == "main" or job.startswith("enrichment-")):
                    return self._json({"error": "job không hợp lệ"}, 400)
                return self._json(m.records(source, job, min(int(q.get("limit", 40)), 200), q.get("q", "")))
            if url.path == "/api/record":
                source = q.get("source", "")
                if source not in SOURCE_ORDER:
                    return self._json({"error": "nguồn không hợp lệ"}, 400)
                rec = m.record(q.get("job", ""), source, q.get("key", ""))
                return self._json(rec) if rec is not None else self._json({"error": "không thấy bản ghi"}, 404)
            if url.path == "/api/files":
                return self._json(m.files())
            if url.path == "/api/log":
                return self._json(m.log(q.get("job", "running"), min(int(q.get("lines", 150)), 500)))
            if url.path == "/api/health":
                return self._json(CACHE.get("health", 5, m.health))
            if url.path == "/api/preview":
                return self._json(m.preview_view())
            if url.path == "/pipeline":
                return self._send(200, (STATIC / "pipeline.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/pipeline/state":
                return self._json(m.pipeline_state(q.get("run", "latest")))
            if url.path == "/api/pipeline/runs":
                return self._json(m.pipeline_runs())
            if url.path == "/api/pipeline/config":
                return self._json(m.pipeline_config())
            if url.path == "/api/pipeline/inbox":
                return self._json(m.pipeline_inbox())
            if url.path == "/api/pipeline/fetch":
                return self._json(m.pipeline_fetch())
            if url.path == "/daily":
                return self._send(200, (STATIC / "daily.html").read_bytes(), "text/html; charset=utf-8")
            if url.path.startswith("/api/daily/"):
                d, name = self.daily, url.path.rsplit("/", 1)[1]
                routes = {
                    "overview": lambda: d.overview(),
                    "run": lambda: d.run(q.get("id", "latest")),
                    "log": lambda: d.log(q.get("run", "latest"), q.get("name", ""), min(int(q.get("lines", 200)), 2000)),
                    "versions": lambda: d.versions(),
                    "version": lambda: d.version(q.get("v", "")),
                    "diff": lambda: d.diff(q.get("a", ""), q.get("b") or None),
                    "search": lambda: d.search(q.get("q", "")),
                    "trace": lambda: d.trace(q.get("id", "")),
                    "raw": lambda: d.raw(q.get("path", "")),
                }
                if name in routes:
                    return self._json(routes[name]())
        except (ValueError, KeyError) as e:
            return self._json({"error": str(e)}, 400)
        return self._json({"error": "không tìm thấy"}, 404)

    def do_POST(self):  # noqa: N802
        if not self._host_ok() or self.headers.get("X-Requested-With") != "vota-monitor":
            return self._json({"error": "bị từ chối"}, 403)
        path = urlparse(self.path).path
        if path == "/api/preview":
            return self._json(self.monitor.start_preview())
        if path.startswith("/api/daily/"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 4096:
                    raise ValueError("nội dung quá lớn")
                body = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("cần một đối tượng JSON")
                return self._json(self.daily.act(path.rsplit("/", 1)[1], body), 202)
            except (ValueError, UnicodeDecodeError) as e:
                return self._json({"error": str(e)}, 400)
        if path in ("/api/pipeline/run", "/api/pipeline/pull"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 4096:
                    raise ValueError("nội dung quá lớn")
                opts = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8"))
                if not isinstance(opts, dict):
                    raise ValueError("cần một đối tượng JSON")
                code, body = (self.monitor.start_pull if path.endswith("/pull") else self.monitor.start_pipeline)(opts)
            except (ValueError, UnicodeDecodeError) as e:
                return self._json({"error": str(e)}, 400)
            return self._json(body, code)
        if path in ("/api/pipeline/token", "/api/pipeline/token/clear", "/api/pipeline/probe"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 2048:
                    raise ValueError("nội dung quá lớn")
                body = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("cần một đối tượng JSON")
                if path == "/api/pipeline/token":
                    out = {"tokens": self.monitor.save_token(str(body.get("key") or ""), str(body.get("value") or ""))}
                elif path == "/api/pipeline/token/clear":
                    out = {"tokens": self.monitor.clear_token(str(body.get("key") or ""))}
                else:
                    out = self.monitor.run_probe(str(body.get("kind") or ""), body.get("destination"), body.get("limit", 5), body.get("maxUsd", 0.1))
            except (ValueError, UnicodeDecodeError, api_sources.ApiError) as e:
                return self._json({"error": str(e)}, 400)
            return self._json(out)
        return self._json({"error": "không tìm thấy"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
