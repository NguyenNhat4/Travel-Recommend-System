"""Chuẩn hoá từng phần trong lúc đang cào (L1 của docs/plan/2026-09-28-pipeline-chay-lien-tuc.md).

Collector ghi interim nối tiếp từng bản ghi (`JsonlWriter`, flush ngay). Mỗi chu kỳ, `SourceFollower` của một nguồn:

1. đọc phần mới của `interim/<nguồn>.jsonl` từ byte đã đọc lần trước, chỉ lấy dòng đã có `\\n`;
   file bị ghi lại (inode khác hoặc ngắn hơn, vd. collector ghi lại cả file cuối nguồn) thì đọc lại từ đầu;
2. bỏ trùng trên MỌI bản ghi đã đọc bằng đúng `normalise.dedupe_source` của bản theo lô;
3. chỉ ánh xạ bản ghi chưa gặp (`normalise.map_source`), nhớ kết quả theo nội dung bản ghi;
4. ghi checkpoint `normalised/<nguồn>.*` như `normalise.py --only-source` (meta `status: streaming` cho tới lần cuối).

Collector ghi vào `<nguồn>.jsonl.tmp` rồi mới đổi tên ở cuối nguồn (Vinpearl: từng khách sạn/tour flush ngay vào file tạm):
khi chưa có `<nguồn>.jsonl` thì đọc file tạm (L2). Đổi tên giữ nguyên inode và nội dung nên không phải đọc lại từ đầu.
Nguồn dừng giữa chừng không đổi tên file tạm: lúc chốt hoặc lúc dừng luồng, checkpoint của nguồn không có file chính bị
xoá, vì bản theo lô không bao giờ có nguồn đó (bản nháp trong lúc cào thì vẫn thấy).

Cùng hàm, cùng bản ghi, cùng thứ tự nên checkpoint lần cuối giống hệt bản theo lô; fingerprint (mtime, cỡ file interim)
khớp thì bước normalize chính thức dùng lại (`--reuse-checkpoints`), không khớp thì nó tự ánh xạ lại.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import normalise as N
from stream_feed import Ticker

STREAMING = "streaming"
HISTORY = 40  # số lô gần nhất giữ trong meta cho monitor
PARTIAL = ".jsonl.tmp"  # file tạm collector đang ghi (JsonlWriter(out.with_suffix(".jsonl.tmp")))


def _write_meta(directory: Path, stem: str, meta: dict) -> None:
    tmp = directory / f".{stem}.meta.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(directory / f"{stem}.meta.json")


def _digest(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()


class SourceFollower:
    """Ánh xạ dần một file interim. Mọi lời gọi `poll` giữ khoá riêng của nguồn."""

    def __init__(self, stem: str, interim: Path, checkpoints: Path, args, log: Callable[[str], None] = print):
        self.stem, self.path, self.checkpoints, self.args, self.log = stem, Path(interim), Path(checkpoints), args, log
        self.rates = {"USD": args.usd_vnd, "EUR": args.eur_vnd}
        self.budget = N.budget_with(args.per_destination, ota_rooms_per_hotel=args.rooms_per_hotel,
                                    flights_per_route=args.flights_per_route)
        self.lock = threading.Lock()
        self.inode: int | None = None
        self.offset = 0
        self.records: list[dict] = []
        self.hashes: dict[int, str] = {}      # id(bản ghi) → hash dòng interim (bản ghi sống cùng self.records)
        self.memo: dict[str, tuple] = {}      # hash nội dung → (mục checkpoint, lỗi, số lần gọi, số lỗi)
        self.today: date | None = None
        self.batches = 0
        self.meta: dict | None = None
        self.history: list[dict] = []
        self.read_count = 0  # số bản ghi đọc được ở lần _read gần nhất

    # -- đọc phần mới
    def _open(self):
        """File chính; chưa có thì file tạm đang ghi. Thử lại file chính một lần vì collector có thể vừa đổi tên."""
        for path in (self.path, self.path.with_suffix(PARTIAL), self.path):
            try:
                return open(path, "rb")
            except FileNotFoundError:
                continue
        return None

    def _read(self, final: bool) -> tuple[bool, os.stat_result | None]:
        self.read_count = 0
        handle = self._open()
        if handle is None:
            return False, None
        with handle:
            st = os.fstat(handle.fileno())
            reset = st.st_ino != self.inode or st.st_size < self.offset
            if reset:
                self.inode, self.offset, self.records, self.hashes = st.st_ino, 0, [], {}
            handle.seek(self.offset)
            data = handle.read(max(0, st.st_size - self.offset))
        end = len(data) if final else data.rfind(b"\n") + 1  # lần cuối: như read_jsonl, lấy cả dòng cuối thiếu \n
        for number, line in enumerate(data[:end].decode("utf-8").split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                N.log.warning("Bỏ dòng JSON hỏng %s (byte %d, dòng %d của lô)", self.path.name, self.offset, number)
                continue
            self.records.append(record)
            self.hashes[id(record)] = _digest(line)
            self.read_count += 1
        self.offset += end
        return reset or end > 0, st

    def _key(self, record: dict) -> str:
        known = self.hashes.get(id(record))
        # vé máy bay: bản ghi sau bỏ trùng là tuyến gộp lịch sử (đối tượng mới mỗi lần) → hash theo nội dung
        return known or _digest(json.dumps(record, sort_keys=True, ensure_ascii=False))

    # -- một lô
    def poll(self, final: bool = False) -> dict | None:
        """Ánh xạ phần mới và ghi checkpoint. Trả meta khi có ghi, None khi không có gì mới (và không phải lần cuối)."""
        with self.lock:
            today = self.args.today or date.today()
            day_changed = today != self.today
            if day_changed:  # ánh xạ phụ thuộc ngày (tour, giá theo ngày): qua ngày thì ánh xạ lại
                self.today, self.memo = today, {}
            started = clock = time.monotonic()
            changed, st = self._read(final)
            if st is None:
                return None
            if not (changed or day_changed or final or self.meta is None):
                return None
            new = self.read_count
            timings = {"đọc phần mới": time.monotonic() - clock}
            clock = time.monotonic()
            deduped = N.dedupe_source(self.stem, self.records)
            timings["bỏ trùng theo khoá"] = time.monotonic() - clock
            clock = time.monotonic()
            entries, errors, total, failed, mapped = [], [], 0, 0, 0
            for record in deduped:
                key = self._key(record)
                hit = self.memo.get(key)
                if hit is None:
                    guard = N.RecordGuard(None, self.args.max_error_percent)
                    out = N.map_source(self.stem, [copy.deepcopy(record)], today=today, rates=self.rates,
                                       budget=self.budget, guard=guard)
                    hit = self.memo[key] = (out, guard.errors, guard.total[self.stem], guard.failed[self.stem])
                    mapped += 1
                entries += hit[0]
                errors += hit[1]
                total += hit[2]
                failed += hit[3]
            timings["ánh xạ bản ghi mới"] = time.monotonic() - clock
            clock = time.monotonic()
            judge = N.RecordGuard(None, self.args.max_error_percent)
            judge.errors, judge.total[self.stem], judge.failed[self.stem] = errors, total, failed
            verdict = judge.verdict(self.stem)
            self.batches += 1
            rows = sum(len(N.entry_rows(e)) for e in entries)
            meta = {"source": self.stem, "status": ("failed" if verdict else "ok") if final else STREAMING,
                    "error": verdict, "records": len(deduped), "entries": len(entries), "rows": rows, "errors": failed,
                    "seconds": round(time.monotonic() - started, 3),
                    # như normalise.checkpoint_fingerprint, nhưng lấy từ lần đọc này (file có thể đã dài thêm)
                    "mapperVersion": N.MAPPER_VERSION, "interimMtimeNs": st.st_mtime_ns, "interimBytes": st.st_size, "today": today.isoformat(),
                    "rates": self.rates, "flightsPerRoute": self.budget.flights_per_route,
                    "batches": self.batches, "offset": self.offset, "mappedThisBatch": mapped}
            # bước con của lô này + lịch sử các lô (monitor: ô chuẩn hoá theo nguồn → "Các bước bên trong")
            counts = {"đọc phần mới": (None, new), "bỏ trùng theo khoá": (len(self.records), len(deduped)),
                      "ánh xạ bản ghi mới": (mapped, rows)}
            meta["steps"] = [{"name": name, "status": "ok", "seconds": round(sec, 4), "rowsIn": counts[name][0],
                              "rowsOut": counts[name][1]} for name, sec in timings.items()]
            self.history = (self.history + [{"n": self.batches, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                             "newRecords": new, "records": len(deduped), "mapped": mapped, "rows": rows,
                                             "errors": failed, "seconds": meta["seconds"], "final": final}])[-HISTORY:]
            meta["history"] = self.history
            clock = time.monotonic()
            N.write_checkpoint(self.checkpoints, self.stem, entries, meta, errors)
            meta["steps"].append({"name": "ghi checkpoint", "status": "ok", "seconds": round(time.monotonic() - clock, 4),
                                  "rowsIn": rows, "rowsOut": rows})
            _write_meta(self.checkpoints, self.stem, meta)  # ghi lại riêng meta (nhỏ) để có thời gian của chính bước ghi
            self.meta = meta
            self.log(f"[normalise:{self.stem}] normalise.stream.batch n={self.batches} records={len(deduped)} "
                     f"rows={rows} errors={failed} mapped={mapped} offset={self.offset}"
                     + (f" final status={meta['status']}" if final else ""))
            return meta


class StreamNormaliser:
    """Một luồng chạy `SourceFollower.poll` cho mọi file interim mỗi `interval` giây, trong lúc các site còn cào.

    `finish_source(nguồn)`: site của nguồn đã cào xong → đọc lần cuối, checkpoint `ok`/`failed`, không theo dõi nữa.
    Lỗi ở đây không làm hỏng lượt: bước normalize chính thức ánh xạ lại nguồn nào không có checkpoint `ok` còn mới."""

    def __init__(self, run_dir: Path, normalise_argv: list[str], interval: float,
                 log: Callable[[str], None] = print):
        self.args = N.build_parser().parse_args(normalise_argv)
        self.interim = Path(run_dir) / "interim"
        self.checkpoints = Path(run_dir) / N.CHECKPOINT_DIR
        self.interval, self.log = interval, log
        self.followers: dict[str, SourceFollower] = {}
        self.finished: set[str] = set()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.ticker: Ticker | None = None

    def follower(self, stem: str) -> SourceFollower:
        with self.lock:
            if stem not in self.followers:
                self.followers[stem] = SourceFollower(stem, self.interim / f"{stem}.jsonl", self.checkpoints, self.args,
                                                      self.log)
            return self.followers[stem]

    def poll_all(self) -> int:
        """Một chu kỳ trên mọi nguồn chưa xong; trả số nguồn có ghi checkpoint."""
        written = 0
        names = [p.name for p in self.interim.iterdir()] if self.interim.is_dir() else []
        stems = sorted({n[:-len(PARTIAL)] if n.endswith(PARTIAL) else n[:-len(".jsonl")]
                        for n in names if n.endswith((".jsonl", PARTIAL)) and not n.startswith(".")})
        for stem in stems:
            if self.stop.is_set():
                break
            with self.lock:
                if stem in self.finished:
                    continue
            try:
                written += self.follower(stem).poll() is not None
            except Exception as exc:  # một nguồn lỗi không chặn nguồn khác; bản chính thức sẽ ánh xạ lại
                self.log(f"[normalise:{stem}] normalise.stream.failed {type(exc).__name__}: {exc}")
        return written

    def finish_source(self, stem: str) -> dict | None:
        with self.lock:
            self.finished.add(stem)
        follower = self.follower(stem)
        meta = follower.poll(final=True) if follower.path.is_file() else self._drop(stem)
        with follower.lock:  # đã chốt, không đọc nữa: trả bộ nhớ (bản ghi + kết quả ánh xạ ~ vài lần cỡ interim)
            follower.records, follower.hashes, follower.memo = [], {}, {}
        return meta

    def _drop(self, stem: str) -> None:
        """Nguồn chỉ có file tạm (collector dừng trước khi đổi tên): bỏ checkpoint để khớp bản theo lô."""
        for name in (f"{stem}.jsonl", f"{stem}.errors.jsonl", f"{stem}.meta.json"):
            (self.checkpoints / name).unlink(missing_ok=True)
        self.log(f"[normalise:{stem}] normalise.stream.dropped không có interim/{stem}.jsonl (chỉ có file tạm)")
        return None

    def start(self, control: Callable[[], dict] | None = None,
              target: Callable[[Ticker], Callable[[], None]] | None = None) -> "StreamNormaliser":
        """`control`: live_control của "stream.normalise" (chu kỳ, tạm dừng, chạy ngay). `target(ticker)`: bọc vòng lặp."""
        self.ticker = Ticker("normalise", lambda: {"written": n} if (n := self.poll_all()) else None, self.interval,
                             control, self.log)
        self.ticker.start(target(self.ticker) if target else None)
        return self

    @property
    def thread(self):
        return self.ticker.thread if self.ticker else None

    def close(self) -> None:
        self.stop.set()
        if self.ticker is not None:
            self.ticker.close()
        with self.lock:
            unfinished = [stem for stem in self.followers if stem not in self.finished]
        for stem in unfinished:
            with self.followers[stem].lock:
                if not self.followers[stem].path.is_file():
                    self._drop(stem)
