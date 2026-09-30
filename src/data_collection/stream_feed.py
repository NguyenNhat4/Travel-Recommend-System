"""Chạy liên tục sau chuẩn hoá: gộp nháp (L3), nạp DB theo phần (L4), index theo phần (L5).

docs/plan/2026-09-28-pipeline-chay-lien-tuc.md. Mỗi việc là một `Ticker`: luồng riêng, chạy `work()` mỗi `interval` giây.
Chu kỳ và cờ tạm dừng đọc lại mỗi nửa giây từ `live_control` (monitor chỉnh khi lượt đang chạy, L6): lô đang chạy dở không
bị đổi, giá trị mới áp từ lô sau; tạm dừng thì dữ liệu dồn sang lô sau, không mất. Lỗi một lô chỉ ghi log và thử lại ở
chu kỳ sau, không làm hỏng lượt: bước gộp / nạp DB / index chính thức cuối lượt vẫn chạy như khi tắt chạy liên tục.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from collectors.common import read_jsonl

TICK = 0.5
TRIP_HOTEL = re.compile(r"^trip:hotel:")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_jsonl(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


class Ticker:
    """`work()` mỗi `interval` giây (hoặc ngay khi `kick()`), trong luồng `name`.

    `control()` trả dict của live_control cho việc này: `interval` (giây) thay cho mặc định, `paused` (bool).
    `work()` trả dict (số liệu lô) hoặc None (không có gì để làm)."""

    def __init__(self, name: str, work: Callable[[], dict | None], interval: float,
                 control: Callable[[], dict] | None = None, log: Callable[[str], None] = print):
        self.name, self.work, self.interval, self.control, self.log = name, work, interval, control, log
        self.stop = threading.Event()
        self.kicked = threading.Event()
        self.thread: threading.Thread | None = None
        self.last: dict | None = None
        self.runs = 0
        self.kick_seen: str | None = None
        self.on_result: Callable[[dict], None] | None = None

    def settings(self) -> tuple[float, bool]:
        entry = (self.control() if self.control else None) or {}
        kick = entry.get("kickAt")
        if kick and kick != self.kick_seen:  # monitor bấm "chạy ngay"
            self.kick_seen = kick
            self.kicked.set()
        interval = entry.get("interval")
        return (float(interval) if interval else self.interval), bool(entry.get("paused"))

    def kick(self) -> None:
        self.kicked.set()

    def run_once(self) -> dict | None:
        try:
            result = self.work()
        except Exception as exc:  # lô sau thử lại; bước chính thức cuối lượt vẫn chạy
            self.log(f"[{self.name}] stream.{self.name}.failed {type(exc).__name__}: {exc}")
            return None
        if result is not None:
            self.runs += 1
            self.last = result
            if self.on_result is not None:
                self.on_result(result)
        return result

    def loop(self) -> None:
        last = time.monotonic()
        while not self.stop.wait(TICK):
            interval, paused = self.settings()
            if paused:
                continue
            if time.monotonic() - last < interval and not self.kicked.is_set():
                continue
            self.kicked.clear()
            last = time.monotonic()
            self.run_once()

    def start(self, target: Callable[[], None] | None = None) -> "Ticker":
        """`target`: bọc vòng lặp (vd. trong một bước của run.json); mặc định chạy thẳng `loop`."""
        self.thread = threading.Thread(target=target or self.loop, name=f"stream-{self.name}", daemon=True)
        self.thread.start()
        return self

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join()


# ---------------------------------------------------------------------------------------------------- L3 gộp nháp


def checkpoint_signature(checkpoints: Path) -> tuple:
    """Dấu vân tay của các checkpoint theo nguồn: đổi khi có nguồn được chuẩn hoá thêm."""
    if not checkpoints.is_dir():
        return ()
    out = []
    for meta in sorted(checkpoints.glob("*.meta.json")):
        try:
            st = meta.stat()
        except FileNotFoundError:
            continue
        out.append((meta.name, st.st_mtime_ns, st.st_size))
    return tuple(out)


class DraftMerger:
    """L3: gộp nháp khi checkpoint đổi. `request()` là `Previewer._request_merge` (không chạy chồng, tự gộp lại một lần
    nếu có nguồn mới trong lúc đang gộp)."""

    def __init__(self, checkpoints: Path, request: Callable[[], None]):
        self.checkpoints, self.request = checkpoints, request
        self.seen: tuple = ()

    def __call__(self) -> dict | None:
        signature = checkpoint_signature(self.checkpoints)
        if not signature or signature == self.seen:
            return None
        self.request()
        self.seen = signature
        return {"at": now_iso(), "sources": len(signature)}


# ---------------------------------------------------------------------------------------------------- L4 nạp DB


def row_hash(row: dict) -> str:
    return hashlib.blake2b(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                           digest_size=16).hexdigest()


def source_health(checkpoints: Path) -> dict[str, dict]:
    """Số bản ghi / lỗi / trạng thái theo checkpoint (nguồn interim)."""
    out = {}
    for meta in sorted(checkpoints.glob("*.meta.json")) if checkpoints.is_dir() else []:
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out[meta.name[:-len(".meta.json")]] = data
    return out


def select_ready(products: list[dict], metas: dict[str, dict], loaded: set[str], *, min_records: int,
                 max_error_percent: float, validate: Callable[[list[dict]], None]) -> tuple[list[dict], dict[str, int]]:
    """Dòng "đủ" để nạp giữa lượt (Đã chốt 1 của plan). Trả (dòng, số dòng bị giữ lại theo lý do).

    - qua kiểm tra từng dòng (`validate([row])`, cho phép cha ở ngoài);
    - site của dòng (phần đầu sourceRef) có ≥ `min_records` bản ghi, hoặc mọi checkpoint của site đã chốt `ok` (nguồn cào
      xong thì cỡ mẫu không còn là rủi ro — quyết định 2026-09-29, P2 của docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md);
      tỉ lệ lỗi ≤ ngưỡng, không checkpoint nào `failed`;
    - không phải khách sạn Trip (cần đủ giá mọi mốc ngày, chỉ biết ở cuối) và không phải combo (thành phần có thể chưa
      có trong DB; FK của catalog.combo_items) — cả hai nạp ở bước chính thức;
    - dòng con (phòng, chuyến bay) chỉ nạp khi cha đã nạp trong lượt hoặc cùng lô."""
    held: dict[str, int] = {}

    def hold(reason: str) -> None:
        held[reason] = held.get(reason, 0) + 1

    site_ok: dict[str, bool] = {}
    for site in {row["sourceRef"].split(":")[0] for row in products}:
        stems = [m for stem, m in metas.items() if stem.split("_")[0] == site]
        records = sum(m.get("records") or 0 for m in stems)
        errors = sum(m.get("errors") or 0 for m in stems)
        finished = bool(stems) and all(m.get("status") == "ok" for m in stems)
        site_ok[site] = bool(stems) and (records >= min_records or finished) \
            and errors * 100 <= max_error_percent * records and not any(m.get("status") == "failed" for m in stems)
    candidates: dict[str, dict] = {}
    for row in products:
        ref = row["sourceRef"]
        if TRIP_HOTEL.match(ref):
            hold("khách sạn Trip: nạp ở cuối lượt (cần đủ giá mọi mốc ngày)")
            continue
        if row["taxonomy"] == "combo":
            hold("combo: nạp ở cuối lượt (thành phần phải có trong DB)")
            continue
        if not site_ok.get(ref.split(":")[0]):
            hold(f"nguồn {ref.split(':')[0]}: đang cào mà chưa đủ {min_records} bản ghi, hoặc tỉ lệ lỗi vượt ngưỡng")
            continue
        try:
            validate([row])
        except ValueError as exc:
            hold(f"kiểm tra dòng: {exc}")
            continue
        candidates[row["productId"]] = row
    changed = True
    while changed:  # bỏ dòng con có cha không nạp được (lặp vì chuyến bay → tuyến, phòng → khách sạn)
        changed = False
        for pid, row in list(candidates.items()):
            parent = (row.get("attributes") or {}).get("parentProductId")
            if parent and parent not in candidates and parent not in loaded:
                del candidates[pid]
                hold("dòng con: cha chưa nạp")
                changed = True
    return list(candidates.values()), held


class DbFeeder:
    """L4: mỗi chu kỳ lấy catalog đang gộp (`preview/products.jsonl`), chọn dòng "đủ" mới hoặc đổi so với lần nạp trước,
    nạp bằng đúng hàm nạp của bước chính thức (`load(products_path, None, db_url, root, report_path=...)`: upsert, advisory
    lock, không xoá). Mỗi lô ghi `<lượt>/db_batches/<n>/` và một dòng `<lượt>/db_batches.jsonl`."""

    def __init__(self, run_dir: Path, db_url: str, root: Path, load: Callable, validate: Callable, *,
                 min_records: int, max_error_percent: float, log: Callable[[str], None] = print):
        self.run_dir, self.db_url, self.root, self.load, self.validate = Path(run_dir), db_url, root, load, validate
        self.min_records, self.max_error_percent, self.log = min_records, max_error_percent, log
        self.loaded: dict[str, str] = {}  # productId → hash nội dung đã nạp
        self.batches = 0
        self.written = 0

    def __call__(self) -> dict | None:
        draft = self.run_dir / "preview" / "products.jsonl"
        if not draft.is_file():
            return None
        products = list(read_jsonl(draft))
        ready, held = select_ready(products, source_health(self.run_dir / "normalised"), set(self.loaded),
                                   min_records=self.min_records, max_error_percent=self.max_error_percent,
                                   validate=self.validate)
        batch = [row for row in ready if self.loaded.get(row["productId"]) != row_hash(row)]
        if not batch:
            return None
        number = self.batches + 1
        folder = self.run_dir / "db_batches" / f"{number:04d}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "products.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in batch),
                                               encoding="utf-8")
        started = time.monotonic()
        entry = {"n": number, "at": now_iso(), "draftRows": len(products), "ready": len(ready), "rows": len(batch),
                 "held": held}
        try:
            counts = self.load(folder / "products.jsonl", None, self.db_url, self.root,
                               report_path=folder / "db_load.jsonl") or {}
        except Exception as exc:
            entry.update(error=f"{type(exc).__name__}: {exc}"[:500], seconds=round(time.monotonic() - started, 2))
            append_jsonl(self.run_dir / "db_batches.jsonl", entry)
            raise
        self.batches = number
        self.loaded.update((row["productId"], row_hash(row)) for row in batch)
        self.written += counts.get("dbRowsWritten") or 0
        entry.update(counts=counts, written=counts.get("dbRowsWritten"), seconds=round(time.monotonic() - started, 2))
        append_jsonl(self.run_dir / "db_batches.jsonl", entry)
        self.log(f"[stream-db] stream.db.batch n={number} rows={len(batch)} written={entry['written']} "
                 f"held={sum(held.values())}")
        return entry


# ---------------------------------------------------------------------------------------------------- L5 index


class IndexFeeder:
    """L5: khi DB có dòng ghi mới từ lần index trước thì chạy đúng hàm index của bước chính thức (tăng dần theo textHash:
    chỉ nhúng dòng mới / đổi text). Mỗi lần ghi một dòng `<lượt>/index_batches.jsonl`."""

    def __init__(self, run_dir: Path, feeder: DbFeeder, index: Callable[[Path], dict], log: Callable[[str], None] = print):
        self.run_dir, self.feeder, self.index, self.log = Path(run_dir), feeder, index, log
        self.indexed_at_written = 0
        self.batches = 0

    def __call__(self) -> dict | None:
        written = self.feeder.written
        if written <= self.indexed_at_written:
            return None
        started = time.monotonic()
        entry = {"n": self.batches + 1, "at": now_iso(), "newDbRows": written - self.indexed_at_written}
        try:
            report = self.index(self.run_dir / "index_detail.stream.jsonl") or {}
        except Exception as exc:
            entry.update(error=f"{type(exc).__name__}: {exc}"[:500], seconds=round(time.monotonic() - started, 2))
            append_jsonl(self.run_dir / "index_batches.jsonl", entry)
            raise
        self.batches += 1
        if not report.get('deferred'):
            self.indexed_at_written = written
        entry.update(report={k: report.get(k) for k in ("embedded", "unchanged", "searchUnits", "deletedOrphans", "deferred", "reason", "retryAfter")},
                     seconds=round(time.monotonic() - started, 2))
        append_jsonl(self.run_dir / "index_batches.jsonl", entry)
        self.log(f"[stream-index] stream.index.batch n={entry['n']} embedded={report.get('embedded')}")
        return entry
