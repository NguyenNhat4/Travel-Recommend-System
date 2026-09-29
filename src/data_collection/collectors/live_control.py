"""Chỉnh tốc độ cào khi lượt đang chạy: monitor ghi một file, crawler đọc lại trước mỗi request.

Monitor ghi `<CATALOG_STATE_DIR>/live_control.json`. `fresh_catalog.py` truyền đường dẫn file qua env `CRAWL_LIVE_FILE`,
mã lượt qua `CRAWL_RUN_ID` và khoá nguồn qua `CRAWL_LIVE_KEY` cho từng tiến trình `crawl.py`. `HostRateLimiter.wait()` và
vòng hỏi giá khách sạn Trip đọc file trước mỗi request (stat tối đa 2 lần/giây, chỉ parse lại khi file đổi):
- `paused`: giữ request lại cho tới khi bấm chạy tiếp; tiến độ và trình duyệt giữ nguyên.
- `delay` (vinpearl, trip, booking, agoda): khoảng cách tối thiểu giữa hai request tới cùng host, thay cho `--delay` của lượt.
  Crawl-delay của robots.txt vẫn thắng nếu lớn hơn.
- `delayMin`/`delayMax` (khách sạn Trip): khoảng chờ ngẫu nhiên giữa hai lần mở trang giá/thông tin.
Mức tối thiểu bằng mức tối thiểu của trang Cấu hình (`fresh_settings.py`): 2 giây cho nguồn tuân robots.txt
(`docs/spec/data-collection-spec.md` §8), 0,5 giây cho khách sạn Trip (mức code hiện tại). File bị xoá đầu và cuối mỗi lượt,
nên chỉnh live không kéo sang lượt sau; số tab/worker chỉ đổi được ở trang Cấu hình, áp từ lượt sau.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

FILE_NAME = "live_control.json"
MAX_DELAY = 300.0
# khoá → trường số chỉnh được và mức tối thiểu của từng trường
LIMITS: dict[str, dict[str, float]] = {
    "vinpearl": {"delay": 2.0},
    "trip": {"delay": 2.0},
    "booking": {"delay": 2.0},
    "agoda": {"delay": 2.0},
    "tripHotels": {"delayMin": 0.5, "delayMax": 1.0},
}
# khoá live → khoá cấu hình của lượt (giá trị đang dùng khi chưa chỉnh live)
SETTING_KEYS: dict[str, dict[str, str]] = {
    "vinpearl": {"delay": "vinpearl.delay"},
    "trip": {"delay": "trip.delay"},
    "booking": {"delay": "booking.delay"},
    "agoda": {"delay": "agoda.delay"},
    "tripHotels": {"delayMin": "tripHotels.delayMin", "delayMax": "tripHotels.delayMax"},
}
# Chạy liên tục (docs/plan/2026-09-28-pipeline-chay-lien-tuc.md, L6): mỗi việc có chu kỳ (giây, tối thiểu, tối đa, khoá
# cấu hình của lượt), `paused`, và `kick` (monitor bấm "chạy ngay" → ghi `kickAt`; vòng lặp thấy mốc mới thì chạy ngay).
STREAM: dict[str, tuple[float, float, str]] = {
    "stream.normalise": (2.0, 600.0, "stream.normaliseSeconds"),
    "stream.merge": (5.0, 3600.0, "stream.mergeSeconds"),
    "stream.db": (10.0, 3600.0, "stream.dbSeconds"),
    "stream.index": (30.0, 7200.0, "stream.indexSeconds"),
}
CHECK_EVERY = 0.5     # giây giữa hai lần stat file
PAUSE_POLL = 1.0      # giây giữa hai lần kiểm khi đang tạm dừng


class LiveControlError(ValueError):
    pass


def read(path: Path | str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def validate(key: str, changes: dict, current: dict | None = None) -> dict:
    """Kiểm một thay đổi từ monitor. `None` ở một trường số = bỏ chỉnh live, quay về cấu hình của lượt."""
    if key in STREAM:
        return _validate_stream(key, changes)
    if key not in LIMITS:
        raise LiveControlError(f"Nguồn lạ: {key}")
    if not isinstance(changes, dict) or not changes:
        raise LiveControlError("Cần ít nhất một thay đổi")
    out: dict = {}
    for name, value in changes.items():
        if name == "paused":
            if not isinstance(value, bool):
                raise LiveControlError("paused phải là true/false")
            out[name] = value
            continue
        if name not in LIMITS[key]:
            raise LiveControlError(f"{key} không chỉnh được {name}")
        if value is None:
            out[name] = None
            continue
        if isinstance(value, bool):
            raise LiveControlError(f"{name}: cần một số")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise LiveControlError(f"{name}: cần một số") from None
        if not math.isfinite(number):
            raise LiveControlError(f"{name}: cần số hữu hạn")
        floor = LIMITS[key][name]
        if number < floor or number > MAX_DELAY:
            raise LiveControlError(f"{name}: trong khoảng {floor:g}–{MAX_DELAY:g} giây")
        out[name] = number
    merged = {**(current or {}), **out}
    low, high = merged.get("delayMin"), merged.get("delayMax")
    if low is not None and high is not None and high < low:
        raise LiveControlError("delayMax phải ≥ delayMin")
    return out


def _validate_stream(key: str, changes: dict) -> dict:
    if not isinstance(changes, dict) or not changes:
        raise LiveControlError("Cần ít nhất một thay đổi")
    low, high, _setting = STREAM[key]
    out: dict = {}
    for name, value in changes.items():
        if name == "paused":
            if not isinstance(value, bool):
                raise LiveControlError("paused phải là true/false")
            out[name] = value
        elif name == "kick":
            if value is not True:
                raise LiveControlError("kick phải là true")
            out["kickAt"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        elif name == "interval":
            if value is None:
                out[name] = None
                continue
            if isinstance(value, bool):
                raise LiveControlError("interval: cần một số")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise LiveControlError("interval: cần một số") from None
            if not math.isfinite(number) or number < low or number > high:
                raise LiveControlError(f"interval: trong khoảng {low:g}–{high:g} giây")
            out[name] = number
        else:
            raise LiveControlError(f"{key} không chỉnh được {name}")
    return out


def write(path: Path | str, run_id: str, key: str, changes: dict) -> dict:
    """Ghi thay đổi đã kiểm vào file (ghi đè nguyên tử). Trả trạng thái mới của cả file."""
    path = Path(path)
    data = read(path)
    if data.get("runId") != run_id:
        data = {"runId": run_id, "sources": {}}
    sources = data.setdefault("sources", {})
    entry = dict(sources.get(key) or {})
    for name, value in validate(key, changes, entry).items():
        if value is None:
            entry.pop(name, None)
        else:
            entry[name] = value
    entry["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sources[key] = entry
    data["updatedAt"] = entry["updatedAt"]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    return data


class Reader:
    """Đọc file điều khiển của lượt `run_id`; parse lại khi mtime/cỡ đổi, stat tối đa mỗi `CHECK_EVERY` giây."""

    def __init__(self, path: Path | str | None, run_id: str | None):
        self.path = Path(path) if path else None
        self.run_id = run_id
        self.lock = threading.Lock()
        self._checked = 0.0
        self._stamp = None
        self._data: dict = {}
        self._seen: dict[str, dict] = {}

    def get(self, key: str | None) -> dict:
        if not key or self.path is None:
            return {}
        with self.lock:
            now = time.monotonic()
            if now - self._checked >= CHECK_EVERY:
                self._checked = now
                try:
                    st = self.path.stat()
                    stamp = (st.st_mtime_ns, st.st_size)
                except OSError:
                    stamp = None
                if stamp != self._stamp:
                    self._stamp = stamp
                    data = read(self.path) if stamp else {}
                    self._data = data if not self.run_id or data.get("runId") in (None, self.run_id) else {}
            entry = dict((self._data.get("sources") or {}).get(key) or {})
            entry.pop("updatedAt", None)
            if entry != self._seen.get(key, {}):
                self._seen[key] = entry
                shown = " ".join(f"{k}={v}" for k, v in sorted(entry.items())) or "về cấu hình của lượt"
                print(f"live.control key={key} {shown}", flush=True)
            return entry


_reader: Reader | None = None
_reader_lock = threading.Lock()


def reader() -> Reader:
    """Reader theo env của tiến trình (`CRAWL_LIVE_FILE`, `CRAWL_RUN_ID`); tạo lại nếu env đổi (test, lượt mới)."""
    global _reader
    path, run_id = os.environ.get("CRAWL_LIVE_FILE") or None, os.environ.get("CRAWL_RUN_ID") or None
    with _reader_lock:
        if _reader is None or str(_reader.path or "") != str(path or "") or _reader.run_id != run_id:
            _reader = Reader(path, run_id)
        return _reader


def current(key: str | None = None) -> dict:
    return reader().get(key if key is not None else os.environ.get("CRAWL_LIVE_KEY"))


async def hold_while_paused(key: str | None = None) -> dict:
    """Chờ tới khi nguồn không còn bị tạm dừng; trả điều khiển đang có hiệu lực."""
    control = current(key)
    if control.get("paused"):
        started = time.monotonic()
        while control.get("paused"):
            await asyncio.sleep(PAUSE_POLL)
            control = current(key)
        print(f"live.control key={key or os.environ.get('CRAWL_LIVE_KEY')} resumed after "
              f"{round(time.monotonic() - started)}s", flush=True)
    return control
