#!/usr/bin/env python3
"""Luồng dữ liệu tự động cho buổi demo: thu thập → chuẩn hoá → nạp Postgres, có số liệu từng bước.

  python pipeline_demo.py run                                 # phát lại toàn bộ dữ liệu thô đã cào → DB riêng vota_demo
  python pipeline_demo.py run --destinations "Nha Trang,Phú Quốc" --max-hotels 400
  python pipeline_demo.py run --live-vinpearl                 # gọi API Vinpearl thật cho khách sạn + phòng (miễn phí, không cần key)
  python pipeline_demo.py run --live-vinpearl --calendar-days 30 --live-trip --no-db   # MIỄN PHÍ, không trình duyệt: lịch trống 30 ngày thật
                                                              # (Vinpearl) + điểm tham quan/chuyến bay thật (Trip.com) — hợp để chạy định kỳ
  python pipeline_demo.py run --live-tours --tour-limit 10    # thêm vé/tour/combo/golf thật (mở cửa sổ Chromium vì Cloudflare)
  python pipeline_demo.py run --no-db                         # không cần Postgres
  python pipeline_demo.py pull apify-booking-full --only-api  # CHẾ ĐỘ API: tải hàng loạt → hộp thư → tự xử lý hết (không mở trình duyệt)
  python pipeline_demo.py fetch apify-agoda --max-usd 2       # chỉ tải về hộp thư đến; các nguồn: apify-booking-full, apify-agoda, apify-booking, serpapi, travelpayouts
  python pipeline_demo.py auto --only-api                     # theo dõi hộp thư đến, có file mới tự chạy
  python pipeline_demo.py status                              # trạng thái lượt chạy mới nhất
  python pipeline_demo.py probe-apify --actor user/actor --input @input.json --limit 5 --max-usd 0.10

Xem trực quan (có nút chạy): `python monitor.py` → http://127.0.0.1:8765/pipeline

Các bước dùng đúng code xử lý thật (`normalise.py`, `data_collection.seed.parse_combos`,
`data_collection.seed.load_products`, `db/vota_schema.sql`), chỉ đổi thư mục dữ liệu:
mỗi lượt chạy có thư mục riêng `data/demo/runs/<lượt>/`. Nguồn "phát lại" đọc lại bản ghi thô đã cào trong `data/interim/`; nguồn "live"
gọi API thật. Giao diện luôn ghi rõ nguồn nào là live, nguồn nào là phát lại — không giả vờ.

Cô lập với database ứng dụng (kiểm tra bằng code, xem `check_db_target` / `check_run_dir`):
  * chỉ ghi vào `data/demo/`; `data/products.jsonl` (catalog đóng băng) chỉ được đọc, sha256 được so lúc bắt đầu và lúc kết thúc;
  * Postgres: chỉ database `vota_demo*` trên máy này; database này tự tạo lại mỗi lượt (chỉ nó), không chạm `vota`/`insider`;
  * không commit/push gì lên repo nhóm.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from itertools import zip_longest
from pathlib import Path

import api_sources
import apify_source
from collectors.common import default_data_dir
from collectors.plan import DESTINATIONS
from collectors.textutil import fold

ROOT = Path(__file__).resolve().parent
SRC_ROOT = ROOT.parent
REPO_ROOT = SRC_ROOT.parent
RUN_ID = re.compile(r"^\d{8}-\d{6}(-[a-z0-9]{1,12})?$")
DB_NAME = re.compile(r"^vota_demo[a-z0-9_]{0,20}$")
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
KEEP_RUNS = 6
LOG_KEEP = 150
FROZEN_NAME = "products.jsonl"
INBOX, STORE = "inbox", "store"  # dưới data/demo/: hộp thư đến (file JSON từ API) và kho tích luỹ (bản ghi trung gian đã đổi dạng)
SAMPLE_DESTINATIONS = ("Nha Trang", "Phú Quốc", "Đà Nẵng", "Hà Nội", "Hội An", "Hồ Chí Minh")

# Thứ tự theo handbook §3: Vinpearl trước, rồi các OTA. (khoá luồng, tên hiển thị, sinh ra taxonomy nào, file interim, recordType lọc, nguồn)
# nguồn "cache" = bản ghi thô đã cào trước đó (data/interim); "store" = kho tích luỹ từ hộp thư đến (dữ liệu API)
FEEDS = (
    ("vinpearl_hotels", "Vinpearl khách sạn (API)", "hotel + hạng phòng", "vinpearl", "vinpearl_hotel", "cache"),
    ("vinpearl_tours", "Vinpearl vé / combo / golf (API sau Cloudflare)", "attraction (vé), combo, golf", "vinpearl", "vinpearl_tour", "cache"),
    ("booking_hotels", "Booking.com", "hotel + hạng phòng", "booking_hotels", None, "cache"),
    ("agoda_hotels", "Agoda", "hotel", "agoda_hotels", None, "cache"),
    ("trip_attractions", "Trip.com điểm tham quan", "attraction", "trip_attractions", None, "cache"),
    ("trip_flights", "Trip.com chuyến bay", "flight", "trip_flights", None, "cache"),
    ("api_agoda", "Agoda qua API (Apify)", "hotel", "agoda_hotels", None, "store"),
    ("api_booking", "Booking.com qua API (Apify)", "hotel + 1 hạng phòng (giá dẫn đầu)", "booking_hotels", None, "store"),
)
FEED_SOURCE = {f[0]: f[3] for f in FEEDS}
STAGES = (
    ("trigger", "1 · Kích hoạt", "Nhận lệnh và kiểm tra các rào an toàn: DB riêng, không sửa catalog đóng băng."),
    ("ingest", "2 · Thu thập", "Dữ liệu thô đổ về từng nguồn dưới dạng JSON (gọi API thật hoặc phát lại bản đã cào)."),
    ("normalise", "3 · Chuẩn hoá", "Đổi mọi nguồn về 13 trường catalog, gộp trùng giữa nguồn, áp luật giá, xoá dòng lỗi."),
    ("loader", "4 · Chuẩn bị nạp", "Tách thành phần combo, áp cửa sổ đặt chỗ 30 ngày và lịch phòng trống."),
    ("database", "5 · Nạp Postgres", "Nạp vào database demo riêng bằng đúng DDL của nhóm rồi chạy các phép kiểm tra."),
    ("report", "6 · Báo cáo", "Độ phủ trường, so với catalog đóng băng, một khách sạn đi qua luồng ra sao."),
)
FUNNEL = (
    ("rowsBuilt", "Sản phẩm dựng từ bản ghi thô (khách sạn, phòng, vé, chuyến bay…)"),
    ("rowsAfterExclusions", "Sau khi loại điểm không phải du lịch / đã soát tay"),
    ("rowsAfterUnsellable", "Sau khi loại sản phẩm không có giá"),
    ("rowsAfterValidation", "Sau khi khử trùng và kiểm tra loại hợp lệ"),
    ("rowsAfterMemberMerge", "Sau khi gộp biến thể giá thành viên"),
    ("rowsFinal", "Sau khi xoá dòng lỗi (toạ độ, giá phi lý, mồ côi)"),
)


class GuardrailError(RuntimeError):
    pass


def iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def demo_dir(data_dir: Path | None = None) -> Path:
    return (data_dir or default_data_dir()) / "demo"


# ---------------------------------------------------------------------------------------------- rào an toàn
def check_db_target(host: str, port: int, dbname: str) -> None:
    if host not in LOOPBACK:
        raise GuardrailError(f"Chỉ nạp vào Postgres trên máy này (127.0.0.1), không phải {host!r}.")
    if not DB_NAME.match(dbname):
        raise GuardrailError(f"Tên database phải bắt đầu bằng 'vota_demo' (nhận {dbname!r}) để không trùng 'vota'/'insider' của nhóm.")


def check_run_dir(run_dir: Path, demo: Path) -> None:
    runs = (demo / "runs").resolve()
    if run_dir.resolve().parent != runs or not RUN_ID.match(run_dir.name):
        raise GuardrailError(f"Thư mục lượt chạy phải nằm trực tiếp trong {runs} (nhận {run_dir}).")


def sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(demo: Path) -> Path:
    demo.mkdir(parents=True, exist_ok=True)
    lock = demo / "run.lock"
    if lock.exists():
        try:
            other = int(lock.read_text().strip())
        except ValueError:
            other = 0
        if other and other != os.getpid() and pid_alive(other):
            raise GuardrailError(f"Đang có lượt chạy khác (pid {other}). Đợi nó xong rồi chạy lại.")
    lock.write_text(str(os.getpid()))
    return lock


def prune_runs(demo: Path, keep: int = KEEP_RUNS) -> None:
    """Giữ KEEP_RUNS lượt mới nhất; chỉ xoá thư mục con hợp lệ (đúng mẫu tên) của data/demo/runs."""
    runs = demo / "runs"
    if not runs.is_dir():
        return
    olds = sorted((p for p in runs.iterdir() if p.is_dir() and RUN_ID.match(p.name)), key=lambda p: p.name)
    for p in olds[: max(len(olds) - keep, 0)]:
        shutil.rmtree(p, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- trạng thái
class RunState:
    """Toàn bộ những gì giao diện cần, ghi nguyên tử vào state.json sau mỗi thay đổi (giới hạn ~7 lần/giây)."""

    def __init__(self, run_dir: Path, params: dict):
        self.dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self.path = run_dir / "state.json"
        self._last = 0.0
        self.d = {
            "schema": 1, "runId": run_dir.name, "pid": os.getpid(), "status": "running", "startedAt": iso(), "finishedAt": None,
            "params": params, "guardrails": [], "feeds": {}, "funnel": [], "dropped": {}, "composition": {}, "coverage": {},
            "sample": None, "compare": None, "database": None, "inbox": None, "changes": None,
            "stages": [{"id": i, "title": t, "about": a, "status": "pending", "startedAt": None, "finishedAt": None,
                        "metrics": {}, "notes": []} for i, t, a in STAGES],
            "log": [],
        }
        self.save(force=True)

    def stage(self, sid: str) -> dict:
        return next(s for s in self.d["stages"] if s["id"] == sid)

    def start(self, sid: str) -> None:
        s = self.stage(sid)
        s.update(status="running", startedAt=iso())
        self.save(force=True)

    def done(self, sid: str, status: str = "done", **metrics) -> None:
        s = self.stage(sid)
        s["metrics"].update(metrics)
        s.update(status=status, finishedAt=iso())
        self.save(force=True)

    def metrics(self, sid: str, **kw) -> None:
        self.stage(sid)["metrics"].update(kw)
        self.save()

    def note(self, sid: str, text: str) -> None:
        self.stage(sid)["notes"].append(text)
        self.save()

    def log(self, text: str) -> None:
        line = f"{datetime.now().strftime('%H:%M:%S')} {text}"
        print(line, flush=True)
        self.d["log"] = (self.d["log"] + [line])[-LOG_KEEP:]
        with open(self.dir / "pipeline.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self.save()

    def save(self, force: bool = False) -> None:
        if not force and time.monotonic() - self._last < 0.15:
            return
        self._last = time.monotonic()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def finish(self, status: str) -> None:
        self.d.update(status=status, finishedAt=iso())
        self.save(force=True)


# ---------------------------------------------------------------------------------------------- thu thập
def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln.strip()]  # split("\n"), không splitlines (U+0085/U+2028)


def dest_of(r: dict) -> str:
    return (r.get("plan") or {}).get("destination") or r.get("city") or r.get("province") or (r.get("citySlug") or "").replace("-", " ") or "?"


def matches_destination(r: dict, wanted: set[str]) -> bool:
    names = ((r.get("plan") or {}).get("destination"), r.get("city"), r.get("province"), (r.get("citySlug") or "").replace("-", " "))
    return any(fold(n or "") in wanted for n in names)


def cap_hotels(parsed: dict[str, list[tuple[str, dict]]], max_hotels: int) -> None:
    """Giữ tối đa max_hotels bản ghi Booking+Agoda, chia đều theo điểm đến (vòng tròn), xen kẽ hai nguồn. Xác định, không ngẫu nhiên."""
    groups: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for s in ("booking_hotels", "agoda_hotels"):
        for i, (_, r) in enumerate(parsed.get(s, [])):
            groups[dest_of(r)][s].append(i)
    order = sorted(groups, key=lambda d: (-sum(len(v) for v in groups[d].values()), d))
    queues = {d: [(s, i) for pair in zip_longest(groups[d]["booking_hotels"], groups[d]["agoda_hotels"])
                  for s, i in zip(("booking_hotels", "agoda_hotels"), pair) if i is not None] for d in order}
    chosen: set[tuple[str, int]] = set()
    cursor = dict.fromkeys(order, 0)
    while len(chosen) < max_hotels:
        moved = False
        for d in order:
            if cursor[d] < len(queues[d]) and len(chosen) < max_hotels:
                chosen.add(queues[d][cursor[d]])
                cursor[d] += 1
                moved = True
        if not moved:
            break
    for s in ("booking_hotels", "agoda_hotels"):
        if s in parsed:
            parsed[s] = [x for i, x in enumerate(parsed[s]) if (s, i) in chosen]


def select_feeds(src_dir: Path, destinations: list[str], max_hotels: int | None, store_dir: Path | None = None,
                 use_cache: bool = True) -> dict[str, list[str]]:
    loaded: dict[tuple[str, str], list[tuple[str, dict]]] = {}

    def load(origin: str, source: str) -> list[tuple[str, dict]]:
        if (origin, source) not in loaded:
            base = src_dir if origin == "cache" else store_dir
            recs = []
            for ln in read_lines(base / "interim" / f"{source}.jsonl"):
                try:
                    recs.append((ln, json.loads(ln)))
                except ValueError:
                    continue  # dòng cuối đang được ghi dở
            loaded[(origin, source)] = recs
        return loaded[(origin, source)]

    parsed = {}
    for key, _, _, source, rtype, origin in FEEDS:
        if (origin == "cache" and not use_cache) or (origin == "store" and store_dir is None):
            parsed[key] = []
        else:
            parsed[key] = [(ln, r) for ln, r in load(origin, source) if rtype is None or r.get("recordType") == rtype]
    wanted = {fold(d) for d in destinations} or None
    if wanted:  # Vinpearl luôn giữ (handbook §3); lọc điểm đến cho OTA, điểm tham quan và tuyến bay
        for s in ("booking_hotels", "agoda_hotels", "trip_attractions"):
            parsed[s] = [(ln, r) for ln, r in parsed[s] if matches_destination(r, wanted)]
        parsed["trip_flights"] = [(ln, r) for ln, r in parsed["trip_flights"]
                                  if {fold(r.get("fromCity") or ""), fold(r.get("toCity") or "")} & wanted]
    if max_hotels:
        cap_hotels(parsed, max_hotels)
    return {s: [ln for ln, _ in v] for s, v in parsed.items()}


def run_child(state: RunState, sid: str, argv: list[str], on_line=None) -> int:
    """Chạy tiến trình con, đưa từng dòng output vào nhật ký của luồng."""
    env = {k: v for k, v in os.environ.items() if k != "CRAWL_SHARED_CACHE"}
    env["PYTHONUNBUFFERED"] = "1"  # để dòng nhật ký hiện ngay, không dồn đến cuối
    env["PYTHONPATH"] = str(SRC_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            state.log(f"[{sid}] {line[:300]}")
        if on_line:
            on_line(line)
    return proc.wait()


def stage_trigger(state: RunState, args, run_dir: Path) -> str:
    demo = demo_dir()
    check_run_dir(run_dir, demo)
    frozen = Path(args.source_data_dir) / FROZEN_NAME
    state.d["frozenSha256"] = sha256_of(frozen)
    g = state.d["guardrails"]
    g.append({"name": "Chỉ ghi vào data/demo", "ok": True, "detail": f"lượt này: {run_dir.name}; thư mục cũ tự dọn (giữ {KEEP_RUNS})"})
    g.append({"name": "Catalog đóng băng chỉ đọc", "ok": True,
              "detail": f"{FROZEN_NAME} sha256 {(state.d['frozenSha256'] or 'không có')[:12]}… — so lại khi kết thúc"})
    if args.no_db:
        g.append({"name": "Không nạp DB", "ok": True, "detail": "--no-db"})
    else:
        check_db_target(args.db_host, args.db_port, args.db_name)
        g.append({"name": "DB riêng, không phải DB nhóm", "ok": True,
                  "detail": f"{args.db_host}:{args.db_port}/{args.db_name} — cổng 5432 (BE/FE) bị chặn, chỉ tạo lại database này"})
    tok = api_sources.token_status()
    g.append({"name": "API key", "ok": True, "detail": " · ".join(f"{n} {'có' if tok[k] else 'chưa có'}" for n, k in
                                                                     (("Apify", "apify"), ("SerpApi", "serpapi"), ("Travelpayouts", "travelpayouts")))
                                                       + " — chỉ đọc từ .env, không ghi vào state hay log"})
    state.log("Rào an toàn đã qua: " + "; ".join(x["name"] for x in g))
    return "done"


def live_vinpearl(state: RunState, args, run_dir: Path, sel: dict[str, list[str]]) -> str:
    """Gọi Vinpearl thật. Khách sạn + hạng phòng là HTTP thường; vé/tour/combo/golf nằm sau Cloudflare nên chỉ live khi --live-tours
    (mở một cửa sổ Chromium, chờ tối đa vài chục giây). Luồng nào lỗi thì quay về bản đã cào và ghi rõ trên giao diện."""
    feeds = state.d["feeds"]
    vin = run_dir / "interim" / "vinpearl.jsonl"
    tours = args.live_tours
    days = min(max(getattr(args, "calendar_days", 1) or 1, 1), 30)
    price_dates = ",".join(str(d) for d in range(days))  # "0,1,2,...": hỏi giá từng ngày liên tiếp, dựng lịch trống thật thay vì 1 ngày mẫu
    cal_note = f" · lịch trống {days} ngày thật" if days > 1 else ""
    feeds["vinpearl_hotels"].update(mode="live", total=None,
                                    note=f"gọi API booking.vinpearl.com bằng HTTP (không cần key, không cần trình duyệt){cal_note}")
    if tours:
        feeds["vinpearl_tours"].update(mode="live", total=None, note="API vé/tour nằm sau Cloudflare nên được gọi từ trong một cửa sổ Chromium")
    else:
        feeds["vinpearl_tours"]["note"] = "phát lại: API vé/tour cần trình duyệt (dùng --live-tours để gọi thật)"
    argv = [sys.executable, "crawl.py", "--data-dir", str(run_dir), "vinpearl", "--price-dates", price_dates, "--tour-limit", str(args.tour_limit)]
    argv += ["--manual-wait", "20", "--challenge-timeout", "30", "--max-blocks", "2"] if tours else ["--headless", "--skip-tours"]

    def on_line(line: str) -> None:
        m = re.search(r"Vinpearl (\d+)/(\d+):", line)
        if m:
            feeds["vinpearl_hotels"].update(received=int(m[1]), total=int(m[2]))
            state.save()

    state.log("Vinpearl: gọi API thật…")
    code = run_child(state, "vinpearl", argv, on_line=on_line)
    recs = [r for r in (json.loads(ln) for ln in read_lines(vin))]
    hotels = sum(1 for r in recs if r.get("recordType") == "vinpearl_hotel")
    tour_recs = sum(1 for r in recs if r.get("recordType") == "vinpearl_tour")
    status = "done"
    if code != 0 or not hotels:
        if args.no_fallback:
            raise RuntimeError(f"crawl.py vinpearl thất bại (mã {code}, {hotels} khách sạn)")
        vin.unlink(missing_ok=True)
        for k in ("vinpearl_hotels", "vinpearl_tours"):
            feeds[k].update(mode="replay", total=len(sel[k]), received=0, note=f"API live lỗi (mã {code}) → dùng bản đã cào")
        state.note("ingest", "Vinpearl live lỗi, đã chuyển sang phát lại bản đã cào")
        return "warn"
    feeds["vinpearl_hotels"].update(total=hotels, received=hotels)
    sel["vinpearl_hotels"] = []
    if tours:
        if tour_recs:
            feeds["vinpearl_tours"].update(total=tour_recs, received=tour_recs)
            sel["vinpearl_tours"] = []
        else:
            feeds["vinpearl_tours"].update(mode="replay", total=len(sel["vinpearl_tours"]), received=0,
                                           note="API vé/tour không trả dữ liệu (Cloudflare?) → dùng bản đã cào")
            state.note("ingest", "Vinpearl vé/tour live không lấy được, đã phát lại bản đã cào")
            status = "warn"
    return status


def live_trip(state: RunState, args, run_dir: Path, sel: dict[str, list[str]]) -> str:
    """Gọi Trip.com thật: HTTP thường, không cần trình duyệt (collectors/trip.py đọc JSON-LD/__NEXT_DATA__ nhúng sẵn trong trang, miễn phí).
    Lỗi nguồn nào thì nguồn đó quay về bản đã cào, ghi rõ trên giao diện."""
    feeds = state.d["feeds"]
    status = "done"
    for key, cmd in (("trip_attractions", "trip-attractions"), ("trip_flights", "trip-flights")):
        path = run_dir / "interim" / f"{key}.jsonl"
        feeds[key].update(mode="live", total=None, note="gọi trip.com bằng HTTP thường (không cần trình duyệt)")
        state.log(f"{cmd}: gọi Trip.com thật…")
        code = run_child(state, key, [sys.executable, "crawl.py", "--data-dir", str(run_dir), cmd])
        n = len(read_lines(path))
        if code != 0 or not n:
            if args.no_fallback:
                raise RuntimeError(f"crawl.py {cmd} thất bại (mã {code}, {n} bản ghi)")
            path.unlink(missing_ok=True)
            feeds[key].update(mode="replay", total=len(sel[key]), received=0, note=f"Trip.com live lỗi (mã {code}) → dùng bản đã cào")
            state.note("ingest", f"{cmd} live lỗi, đã chuyển sang phát lại bản đã cào")
            status = "warn"
        else:
            feeds[key].update(total=n, received=n)
            sel[key] = []
    return status


def stage_ingest(state: RunState, args, run_dir: Path) -> str:
    src = Path(args.source_data_dir)
    interim = run_dir / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    demo = demo_dir()
    api_mode = args.api or args.only_api
    if api_mode:  # hộp thư đến → nhận diện → đổi dạng → kho; xong mới chọn dữ liệu của lượt này
        results = api_sources.intake(demo / INBOX, demo / STORE, log=state.log)
        state.d["inbox"] = {"results": results, "overview": api_sources.inbox_overview(demo / INBOX)}
        got = sum(r["mapped"] for r in results if r["status"] == "done")
        state.stage("ingest")["metrics"].update(inboxFiles=len(results), inboxRecords=got)
        state.log(f"Hộp thư đến: {len(results)} file mới → {got} bản ghi vào kho")
    dests = [d.strip() for d in (args.destinations or "").split(",") if d.strip()]
    sel = select_feeds(src, dests, args.max_hotels, store_dir=(demo / STORE) if api_mode else None, use_cache=not args.only_api)
    feeds = state.d["feeds"]
    for key, label, about, _, _, origin in FEEDS:
        feeds[key] = {"label": label, "about": about, "mode": "api" if origin == "store" else "replay", "total": len(sel[key]), "received": 0,
                      "note": "kho tích luỹ từ hộp thư đến (dữ liệu API)" if origin == "store" else ("không dùng (--only-api)" if args.only_api else None)}
    state.stage("ingest")["metrics"].update(total=sum(len(v) for v in sel.values()), received=0)
    statuses = []
    if args.live_vinpearl or args.live_tours:
        statuses.append(live_vinpearl(state, args, run_dir, sel))
    if args.live_trip:
        statuses.append(live_trip(state, args, run_dir, sel))
    status = "warn" if "warn" in statuses else "done"
    if not any(sel.values()) and not any(f["mode"] == "live" and f["received"] for f in feeds.values()):
        raise RuntimeError("Không có dữ liệu để xử lý: hộp thư đến và kho API đều trống. Chạy `python pipeline_demo.py fetch <nguồn>` hoặc thả file JSON "
                           f"vào {demo / INBOX}.")

    manual = src / "combo_items_manual.jsonl"
    if manual.exists() and not args.only_api:
        shutil.copyfile(manual, run_dir / "combo_items_manual.jsonl")
        state.note("ingest", "Kèm combo_items_manual.jsonl (bản duyệt tay) làm đầu vào của bước tách combo")

    order = [f[0] for f in FEEDS]
    pos = dict.fromkeys(order, 0)
    handles: dict = {}
    delay = max(args.replay_delay_ms, 0) / 1000
    sent = 0
    total = sum(len(v) for v in sel.values())
    try:
        while any(pos[k] < len(sel[k]) for k in order):
            for k in order:
                chunk = sel[k][pos[k]:pos[k] + args.batch]
                if not chunk:
                    continue
                f = handles.get(FEED_SOURCE[k]) or handles.setdefault(FEED_SOURCE[k], open(interim / f"{FEED_SOURCE[k]}.jsonl", "a", encoding="utf-8"))
                f.write("\n".join(chunk) + "\n")
                f.flush()
                pos[k] += len(chunk)
                sent += len(chunk)
                feeds[k]["received"] = pos[k]
            state.stage("ingest")["metrics"].update(received=sent, total=total)
            state.save()
            time.sleep(delay)
    finally:
        for f in handles.values():
            f.close()
    live_total = sum(f["received"] for f in feeds.values() if f["mode"] == "live")
    api_total = sum(f["received"] for f in feeds.values() if f["mode"] == "api")
    state.stage("ingest")["metrics"].update(received=sent + live_total, total=total + live_total)
    state.log(f"Thu thập xong: {sent + live_total} bản ghi thô ({api_total} từ API, {sent - api_total} phát lại, {live_total} live)")
    return status


# ---------------------------------------------------------------------------------------------- chuẩn hoá
def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in read_lines(path)]


def composition_of(rows: list[dict]) -> dict:
    c: Counter = Counter()
    for r in rows:
        lvl = (r.get("attributes") or {}).get("level")
        c[f"{r['taxonomy']}/{lvl}" if lvl else r["taxonomy"]] += 1
    return dict(sorted(c.items()))


def stage_normalise(state: RunState, args, run_dir: Path) -> str:
    report = run_dir / "normalise_report.json"
    argv = [sys.executable, "normalise.py", "--data-dir", str(run_dir), "--no-plan", "--rooms-per-hotel", "0", "--flights-per-route", "0",
            "--report-json", str(report)]
    code = run_child(state, "normalise", argv)
    if code != 0 or not report.exists():
        raise RuntimeError(f"normalise.py thất bại (mã {code})")
    rep = json.loads(report.read_text(encoding="utf-8"))
    rows = read_jsonl(run_dir / "products.jsonl")
    read = rep.get("recordsRead", {})
    funnel = [{"label": "Bản ghi thô đọc vào (mới nhất theo từng khoá)", "rows": sum(read.values()), "unit": "bản ghi"}]
    if rep.get("hotelRecords") is not None:
        funnel.append({"label": "Khách sạn: bản ghi các nguồn → cụm sau khi gộp trùng", "rows": rep["hotelClusters"],
                       "unit": "khách sạn", "from": rep["hotelRecords"]})
    funnel += [{"label": label, "rows": rep[k], "unit": "dòng"} for k, label in FUNNEL if k in rep]
    state.d["funnel"] = funnel
    state.d["dropped"] = dict(sorted(rep.get("dropped", {}).items(), key=lambda kv: -kv[1]))
    state.d["composition"] = composition_of(rows)
    state.done("normalise", recordsRead=read, rowsFinal=len(rows), locationStats=rep.get("locationStats", {}))
    state.log(f"Chuẩn hoá xong: {sum(read.values())} bản ghi thô → {len(rows)} dòng Product")
    return "done"


def stage_loader(state: RunState, args, run_dir: Path) -> str:
    as_of = args.as_of
    for name, argv in (("parse_combos", [sys.executable, "parse_combos.py", "--data-dir", str(run_dir)]),
                       ("load_catalog", [sys.executable, "load_catalog.py", "--data-dir", str(run_dir), "--out-dir", str(run_dir / "loader"),
                                         "--as-of", as_of])):
        code = run_child(state, "loader", argv)
        if code != 0:
            raise RuntimeError(f"{name}.py thất bại (mã {code})")
    products = read_lines(run_dir / "loader" / "cdp_products.jsonl")
    combos = read_lines(run_dir / "loader" / "catalog_combo_items.jsonl")
    state.done("loader", rowsForDb=len(products), comboItems=len(combos), asOf=as_of)
    state.log(f"Chuẩn bị nạp xong: {len(products)} dòng cdp.products, {len(combos)} thành phần combo (cửa sổ 30 ngày từ {as_of})")
    return "done"


# ---------------------------------------------------------------------------------------------- Postgres
def load_db_modules():
    """Import loader/meta chính thức của monorepo, không giữ một implementation DB thứ hai."""
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    from data_collection.seed import catalog_meta, database
    return database, catalog_meta


def stage_database(state: RunState, args, run_dir: Path) -> str:
    if args.no_db:
        state.done("database", status="skipped", note="--no-db")
        return "skipped"
    check_db_target(args.db_host, args.db_port, args.db_name)  # kiểm lần nữa ngay trước khi chạm DB
    import psycopg

    ld, catalog_meta = load_db_modules()
    conn_args = dict(host=args.db_host, port=args.db_port, user=args.db_user, password=args.db_password, connect_timeout=5, autocommit=True)
    try:
        admin = psycopg.connect(dbname="postgres", **conn_args)
    except psycopg.OperationalError as e:
        raise RuntimeError(f"Không nối được Postgres {args.db_host}:{args.db_port} ({' '.join(str(e).split())[:140]}). "
                           f"Bật Postgres của repo: docker compose up -d --wait postgres") from None
    with admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{args.db_name}" WITH (FORCE)')  # chỉ database demo (đã qua check_db_target)
        admin.execute(f'CREATE DATABASE "{args.db_name}"')
    products = read_jsonl(run_dir / "loader" / "cdp_products.jsonl")
    combos = read_jsonl(run_dir / "loader" / "catalog_combo_items.jsonl")
    ids = {p["product_id"] for p in products}
    kept = [c for c in combos if c["combo_product_id"] in ids and (not c["item_product_id"] or c["item_product_id"] in ids)]
    checks: list[dict] = []
    with psycopg.connect(dbname=args.db_name, **conn_args) as conn:
        conn.execute((REPO_ROOT / "db" / "vota_schema.sql").read_text(encoding="utf-8"))
        n = ld.copy_rows(conn, "cdp.products", ld.PRODUCT, products)
        m = ld.copy_rows(conn, "catalog.combo_items", ld.COMBO, kept)
        conn.execute("ANALYZE")
        db_n = conn.execute("SELECT count(*) FROM cdp.products").fetchone()[0]
        checks.append({"name": "Số dòng trong cdp.products khớp file loader", "ok": db_n == n == len(products), "detail": f"file {n} · DB {db_n}"})
        no_coord = conn.execute("SELECT count(*) FROM catalog.product_meta WHERE latitude IS NULL OR longitude IS NULL").fetchone()[0]
        checks.append({"name": "Mọi dòng có toạ độ", "ok": no_coord == 0, "detail": f"thiếu toạ độ: {no_coord}"})
        orphan = conn.execute("SELECT count(*) FROM catalog.product_meta m WHERE m.variant = 'hotel_room' AND NOT EXISTS "
                              "(SELECT 1 FROM cdp.products p WHERE p.product_id = m.parent_product_id)").fetchone()[0]
        checks.append({"name": "Mọi hạng phòng trỏ về khách sạn cha có trong DB", "ok": orphan == 0, "detail": f"mồ côi: {orphan}"})
        no_item = conn.execute("SELECT count(*) FROM cdp.products p WHERE p.taxonomy = 'combo' AND NOT EXISTS "
                               "(SELECT 1 FROM catalog.combo_items i WHERE i.combo_product_id = p.product_id)").fetchone()[0]
        checks.append({"name": "Mọi combo có ít nhất một thành phần", "ok": no_item == 0, "detail": f"combo trống: {no_item}"})
        meta = catalog_meta.build_meta(read_jsonl(run_dir / "products.jsonl"))
        db = {str(r[0]): (r[1], r[2], r[3], r[4], str(r[5]) if r[5] else None) for r in conn.execute(
            "SELECT product_id, variant, is_bookable, is_search_unit, is_recommendable, parent_product_id FROM catalog.product_meta")}
        diff = sum(1 for pid, x in meta.items()
                   if db.get(pid) != (x["variant"], x["is_bookable"], x["is_search_unit"], x["is_recommendable"], x["parent_product_id"]))
        checks.append({"name": "3 cờ (bookable / search unit / recommendable): view SQL khớp code Python", "ok": diff == 0 and len(db) == len(meta),
                       "detail": f"lệch {diff}/{len(meta)}"})
        flags = conn.execute("SELECT count(*) FILTER (WHERE is_bookable), count(*) FILTER (WHERE is_search_unit), "
                             "count(*) FILTER (WHERE is_recommendable) FROM catalog.product_meta").fetchone()
        variants = dict(conn.execute("SELECT variant, count(*) FROM catalog.product_meta GROUP BY 1 ORDER BY 2 DESC").fetchall())
    state.d["database"] = {"target": f"{args.db_host}:{args.db_port}/{args.db_name}", "rowsLoaded": n, "comboItemsLoaded": m,
                           "comboItemsSkipped": len(combos) - len(kept), "checks": checks, "variants": variants,
                           "isBookable": flags[0], "isSearchUnit": flags[1], "isRecommendable": flags[2]}
    bad = [c for c in checks if not c["ok"]]
    state.done("database", rowsLoaded=n, comboItems=m, checksPassed=len(checks) - len(bad), checksTotal=len(checks))
    for c in checks:
        state.log(f"[database] {'PASS' if c['ok'] else 'FAIL'} {c['name']} — {c['detail']}")
    if bad:
        raise RuntimeError(f"{len(bad)} phép kiểm tra DB không đạt")
    return "done"


# ---------------------------------------------------------------------------------------------- báo cáo
COVER = (
    ("description", lambda r, a: bool(r.get("description"))),
    ("imageUrl", lambda r, a: bool(r.get("imageUrl"))),
    ("unitPrice", lambda r, a: r.get("unitPrice") is not None),
    ("toạ độ", lambda r, a: a.get("latitude") is not None and a.get("longitude") is not None),
    ("address", lambda r, a: bool(a.get("address"))),
    ("amenities", lambda r, a: bool(a.get("amenities"))),
    ("starRating", lambda r, a: a.get("starRating") is not None),
    ("reviewScore", lambda r, a: a.get("reviewScore") is not None),
)


def coverage_of(rows: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        lvl = (r.get("attributes") or {}).get("level")
        groups[f"{r['taxonomy']}/{lvl}" if lvl else r["taxonomy"]].append(r)
    return {g: {"rows": len(rs), "fields": {name: round(100 * sum(1 for r in rs if fn(r, r.get("attributes") or {})) / len(rs))
                                            for name, fn in COVER}} for g, rs in sorted(groups.items())}


def trim(obj, max_str: int = 140, max_list: int = 4, max_keys: int = 32):
    if isinstance(obj, str):
        return obj if len(obj) <= max_str else obj[:max_str - 1] + "…"
    if isinstance(obj, list):
        out = [trim(x, max_str, max_list, max_keys) for x in obj[:max_list]]
        return out + ([f"… +{len(obj) - max_list} mục"] if len(obj) > max_list else [])
    if isinstance(obj, dict):
        out = {k: trim(v, max_str, max_list, max_keys) for k, v in list(obj.items())[:max_keys]}
        if len(obj) > max_keys:
            out["…"] = f"+{len(obj) - max_keys} khoá"
        return out
    return obj


def pick_sample(run_dir: Path, rows: list[dict]) -> dict | None:
    """Một khách sạn có mặt ở cả Booking và Agoda: JSON thô hai nguồn → dòng Product sau khi gộp. Không có thì lấy một khách sạn bất kỳ."""
    import normalise as nm

    by_id = {r["productId"]: r for r in rows}
    rates = {"USD": 26300.0, "EUR": 30500.0}
    booking, agoda = {}, {}
    for r in read_jsonl(run_dir / "interim" / "booking_hotels.jsonl"):
        booking[f"booking:hotel:{r.get('hotelId') or fold(r.get('name') or '').replace(' ', '-')}"] = r
    for r in read_jsonl(run_dir / "interim" / "agoda_hotels.jsonl"):
        agoda[f"agoda:hotel:{r.get('slug')}:{r.get('citySlug')}"] = r
    pairs = []
    try:
        with open(run_dir / "dedup_report.csv", encoding="utf-8-sig", newline="") as f:
            pairs = [p for p in csv.DictReader(f) if p["kind"] == "hotel"]
    except OSError:
        pass
    candidates = []
    for n, p in enumerate(pairs):
        refs = (p["kept_sourceRef"], p["merged_sourceRef"])
        b = next((r for x in refs if (r := booking.get(x))), None)
        a = next((r for x in refs if (r := agoda.get(x))), None)
        final = next((by_id[i] for x in refs if (i := nm.product_id(x)) in by_id), None)
        if a and b and final:
            score = float(p["score"])
            # ưu tiên điểm đến quen thuộc và cặp mà tên không trùng hệt (thấy được việc ghép "mờ"); còn lại theo thứ tự file → xác định
            candidates.append(((p["destination"] not in SAMPLE_DESTINATIONS, score >= 100, n), p, a, b, final))
    if candidates:
        _, p, a, b, final = min(candidates, key=lambda c: c[0])
        mapped_b = nm.booking_hotel(b, rates)[0]
        mapped_a = nm.agoda_hotel(a, rates)
        return {"kind": "merged", "match": {"score": float(p["score"]), "distanceM": float(p["distance_m"]) if p["distance_m"] else None,
                                             "destination": p["destination"]},
                "raw": {"booking": trim(b), "agoda": trim(a)},
                "mapped": {"booking": trim(mapped_b) if mapped_b else None, "agoda": trim(mapped_a) if mapped_a else None},
                "final": trim(final)}
    for r in rows:
        if r["taxonomy"] == "hotel" and (r.get("attributes") or {}).get("level") == "property":
            return {"kind": "single", "raw": None, "mapped": None, "final": trim(r)}
    return None


def compare_frozen(run_products: Path, frozen: Path) -> dict | None:
    if not frozen.exists() or not run_products.exists():
        return None
    try:
        a = {r["productId"]: r for r in read_jsonl(run_products)}
        b = {r["productId"]: r for r in read_jsonl(frozen)}
    except (ValueError, KeyError, TypeError):
        return None  # phần so sánh chỉ để tham khảo: file đóng băng lỗi thì bỏ qua, không làm hỏng cả lượt chạy
    common = set(a) & set(b)
    return {"runRows": len(a), "frozenRows": len(b), "sameSha256": sha256_of(run_products) == sha256_of(frozen),
            "common": len(common), "identicalRows": sum(1 for k in common if a[k] == b[k]),
            "onlyInRun": len(set(a) - set(b)), "onlyInFrozen": len(set(b) - set(a))}


def previous_products(demo: Path, current: str) -> tuple[str, Path] | None:
    runs = demo / "runs"
    for p in sorted((x for x in runs.iterdir() if x.is_dir() and RUN_ID.match(x.name) and x.name != current), reverse=True) if runs.is_dir() else []:
        try:
            ok = json.loads((p / "state.json").read_text(encoding="utf-8")).get("status") == "succeeded"
        except (OSError, ValueError):
            continue
        if ok and (p / "products.jsonl").exists():
            return p.name, p / "products.jsonl"
    return None


def diff_products(prev: Path, cur: Path, prev_id: str, limit: int = 6) -> dict:
    """Dòng mới / biến mất / đổi giá giữa hai lượt (theo productId, ổn định giữa các lượt). Cho thấy luồng chạy lại thì dữ liệu được làm mới ra sao."""
    a = {r["productId"]: r for r in read_jsonl(prev)}
    b = {r["productId"]: r for r in read_jsonl(cur)}
    changed = [(k, a[k]["unitPrice"], b[k]["unitPrice"]) for k in a.keys() & b.keys()
               if a[k]["unitPrice"] != b[k]["unitPrice"] and a[k]["unitPrice"] is not None and b[k]["unitPrice"] is not None]
    changed.sort(key=lambda t: -abs(t[2] - t[1]))
    return {"previousRun": prev_id, "previousRows": len(a), "rows": len(b), "new": len(b.keys() - a.keys()), "removed": len(a.keys() - b.keys()),
            "priceChanged": len(changed),
            "examples": [{"name": b[k]["name"], "taxonomy": b[k]["taxonomy"], "before": x, "after": y} for k, x, y in changed[:limit]]}


def stage_report(state: RunState, args, run_dir: Path) -> str:
    rows = read_jsonl(run_dir / "products.jsonl")
    state.d["coverage"] = coverage_of(rows)
    state.d["sample"] = pick_sample(run_dir, rows)
    frozen = Path(args.source_data_dir) / FROZEN_NAME
    state.d["compare"] = compare_frozen(run_dir / "products.jsonl", frozen)
    prev = previous_products(demo_dir(), run_dir.name)
    state.d["changes"] = diff_products(prev[1], run_dir / "products.jsonl", prev[0]) if prev else None
    after = sha256_of(frozen)
    ok = after == state.d.get("frozenSha256")
    for g in state.d["guardrails"]:
        if g["name"] == "Catalog đóng băng chỉ đọc":
            g.update(ok=ok, detail=g["detail"] + (" → không đổi ✓" if ok else " → ĐÃ ĐỔI ✗"))
    if not ok:
        raise RuntimeError("Catalog đóng băng bị thay đổi trong lúc chạy!")
    cmp = state.d["compare"]
    state.done("report", rows=len(rows), sameAsFrozen=bool(cmp and cmp["sameSha256"]))
    if cmp:
        state.log("So với catalog đóng băng: " + ("GIỐNG HỆT từng byte" if cmp["sameSha256"] else
                                                  f"{cmp['identicalRows']}/{cmp['runRows']} dòng giống hệt (tập con hoặc khác nguồn)"))
    return "done"


# ---------------------------------------------------------------------------------------------- điều phối
def run_stage(state: RunState, sid: str, fn, *fn_args) -> bool:
    state.start(sid)
    try:
        status = fn(state, *fn_args) or "done"
    except Exception as e:  # noqa: BLE001 — mọi lỗi phải hiện lên giao diện, không được nuốt
        state.log(f"[{sid}] LỖI: {type(e).__name__}: {e}")
        state.done(sid, "failed", error=f"{type(e).__name__}: {e}")
        return False
    if state.stage(sid)["status"] == "running":
        state.done(sid, status)
    return status != "failed"


def run_pipeline(args) -> int:
    demo = demo_dir()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    if not args.run_id:  # chạy tự động có thể bắt đầu hai lượt trong cùng một giây
        n = 1
        while (demo / "runs" / run_id).exists():
            n += 1
            run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}"
    run_dir = demo / "runs" / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise GuardrailError(f"Lượt {run_id} đã tồn tại; dùng --run-id khác.")
    check_run_dir(run_dir, demo)
    if not args.no_db:
        check_db_target(args.db_host, args.db_port, args.db_name)  # tham số nguy hiểm bị từ chối ngay, không tạo lượt chạy
    lock = acquire_lock(demo)
    params = {k: getattr(args, k) for k in ("destinations", "max_hotels", "batch", "replay_delay_ms", "live_vinpearl", "live_tours", "tour_limit", "api", "only_api", "as_of",
                                            "no_db", "db_host", "db_port", "db_name")}
    state = RunState(run_dir, params)
    (demo / "latest.txt").write_text(run_id, encoding="utf-8")
    prune_runs(demo)
    mode = "chỉ dữ liệu API" if args.only_api else ("API + bản đã cào" if args.api else "phát lại bản đã cào")
    state.log(f"Bắt đầu lượt {run_id} ({'Vinpearl live + ' if (args.live_vinpearl or args.live_tours) else ''}{mode})")
    try:
        ok = run_stage(state, "trigger", stage_trigger, args, run_dir)
        ok = ok and run_stage(state, "ingest", stage_ingest, args, run_dir)
        ok = ok and run_stage(state, "normalise", stage_normalise, args, run_dir)
        loaded = ok and run_stage(state, "loader", stage_loader, args, run_dir)
        db_ok = loaded and run_stage(state, "database", stage_database, args, run_dir)
        rep_ok = ok and run_stage(state, "report", stage_report, args, run_dir)
        for s in state.d["stages"]:
            if s["status"] == "pending":
                s["status"] = "skipped"
        final = "succeeded" if (ok and loaded and db_ok and rep_ok) else "failed"
    except KeyboardInterrupt:
        state.log("Bị dừng bằng Ctrl+C")
        final = "stopped"
    finally:
        lock.unlink(missing_ok=True)
    state.finish(final)
    state.log(f"Kết thúc: {final}")
    return 0 if final == "succeeded" else 1


def latest_state(demo: Path) -> dict | None:
    try:
        rid = (demo / "latest.txt").read_text(encoding="utf-8").strip()
        return json.loads((demo / "runs" / rid / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cmd_status(args) -> int:
    st = latest_state(demo_dir())
    if not st:
        print("Chưa có lượt chạy nào. Chạy: python pipeline_demo.py run")
        return 1
    print(f"Lượt {st['runId']}: {st['status']} (bắt đầu {st['startedAt']})")
    for s in st["stages"]:
        print(f"  {s['title']:<22} {s['status']:<8} {json.dumps(s['metrics'], ensure_ascii=False)[:110]}")
    return 0


def cmd_probe(args) -> int:
    raw = args.input
    text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
    try:
        input_ = json.loads(text)
    except ValueError as e:
        print(f"--input không phải JSON hợp lệ: {e}", file=sys.stderr)
        return 2
    try:
        res = apify_source.probe(args.actor, input_, limit=args.limit, max_usd=args.max_usd, out_dir=demo_dir() / "probe",
                                 on_status=lambda r: print(f"  trạng thái: {r.get('status')} {r.get('statusMessage') or ''}", flush=True))
    except apify_source.ApifyError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 1
    print(f"\n{res['count']} dòng, chi phí {res['costUsd']} USD, JSON thô lưu ở {res['path']}\n")
    print(f"{'trường':<28}{'kiểu':<14}{'có giá trị':>10}  ví dụ")
    for f in res["fields"]:
        print(f"{f['key']:<28}{f['types']:<14}{str(f['filledPct']) + '%':>10}  {f['example']}")
    return 0


class FetchStatus:
    """data/demo/fetch.json: tiến độ tải hàng loạt (giao diện đọc file này). Ghi nguyên tử; nhiều luồng tải cùng báo về nên có khoá."""

    def __init__(self, demo: Path, kind: str, opts: "api_sources.FetchOptions", total: int):
        import threading

        self.path, self._lock = demo / "fetch.json", threading.Lock()
        demo.mkdir(parents=True, exist_ok=True)
        self.d = {"status": "fetching", "pid": os.getpid(), "source": kind, "startedAt": iso(), "finishedAt": None, "total": total, "done": 0,
                  "items": 0, "costUsd": 0.0, "maxUsd": opts.max_usd, "errors": [], "message": ""}
        self.save()

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def event(self, res: dict) -> None:
        with self._lock:
            self.d["done"] += 1
            self.d["items"] += res.get("items") or 0
            self.d["costUsd"] = round(self.d["costUsd"] + float(res.get("costUsd") or 0), 4)
            if res.get("error"):
                self.d["errors"] = (self.d["errors"] + [f"{res['destination']}: {res['error']}"])[-8:]
            self.save()

    def finish(self, status: str, message: str = "") -> None:
        with self._lock:
            self.d.update(status=status, finishedAt=iso(), message=message)
            self.save()


def fetch_options(args) -> "api_sources.FetchOptions":
    dests = [d.strip() for d in (args.destinations or "").split(",") if d.strip()] or [d.name for d in DESTINATIONS[:15]]
    checkin = args.checkin or (date.today() + timedelta(days=30)).isoformat()
    checkout = (date.fromisoformat(checkin) + timedelta(days=args.nights)).isoformat()
    routes = [r.strip().upper() for r in (args.routes or "").split(",") if r.strip()]
    return api_sources.FetchOptions(destinations=dests, max_items=args.max_items, max_usd=args.max_usd, checkin=checkin, checkout=checkout,
                                    adults=args.adults, concurrency=args.concurrency, pages=args.pages, routes=routes, month=args.month or checkin[:7])


def cmd_fetch(args) -> int:
    demo = demo_dir()
    old = None
    try:
        old = json.loads((demo / "fetch.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if old and old.get("status") == "fetching" and old.get("pid") != os.getpid() and pid_alive(int(old.get("pid") or 0)):
        raise GuardrailError(f"Đang có một lượt tải khác (pid {old['pid']}). Đợi nó xong.")
    opts = fetch_options(args)
    total = len(opts.routes or api_sources.DEFAULT_ROUTES) if args.source == "travelpayouts" else len(opts.destinations)
    est = api_sources.estimate_cost(args.source, len(opts.destinations), opts.max_items, opts.pages, len(opts.routes))
    print(f"Tải {args.source}: {total} lượt × tối đa {opts.max_items} mục, ước tính ~${est['usd']} ({est['unit']}), trần ${opts.max_usd}", flush=True)
    status = FetchStatus(demo, args.source, opts, total)
    try:
        results = api_sources.fetch(args.source, opts, demo / INBOX, on_event=status.event)
    except apify_source.ApifyError as e:
        status.finish("failed", str(e))
        print(f"Lỗi: {e}", file=sys.stderr)
        return 1
    good = [r for r in results if r["file"]]
    status.finish("done" if good else "failed", "" if good else "không lượt nào thành công")
    for r in results:
        print(f"  {r['destination']:<16} {'OK  ' if r['file'] else 'LỖI'} {r['items']:>5} mục  ${r['costUsd'] or 0}  {r['file'] or r['error']}", flush=True)
    print(f"Xong: {len(good)}/{len(results)} lượt, {sum(r['items'] for r in results)} mục, ${status.d['costUsd']} → {demo / INBOX}", flush=True)
    return 0 if good else 1


def cmd_pull(args) -> int:
    """Một lệnh: tải hàng loạt từ API vào hộp thư → tự nhận diện, đổi dạng, chuẩn hoá, nạp DB, báo cáo."""
    code = cmd_fetch(args)
    if code != 0:
        return code
    time.sleep(api_sources.SETTLE_SECONDS + 0.5)  # file fetch vừa ghi cần "nằm yên" một chút để intake() không bỏ lỡ (xem inbox_waiting)
    args.api = True
    args.destinations = "" if not getattr(args, "cached_destinations", False) else args.destinations  # tải theo điểm đến, phần đã cào giữ nguyên
    return run_pipeline(args)


def cmd_intake(args) -> int:
    demo = demo_dir()
    results = api_sources.intake(demo / INBOX, demo / STORE, min_age=0, log=print)
    if not results:
        print(f"Hộp thư đến trống: {demo / INBOX}")
    return 0


def cmd_auto(args) -> int:
    """Theo dõi hộp thư đến: có file mới thì tự chạy trọn luồng. Nguồn cấp file: `fetch` (cron / lịch của Apify) hoặc thả tay."""
    inbox = demo_dir() / INBOX
    print(f"Đang theo dõi {inbox} mỗi {args.every}s — file JSON mới sẽ được tự xử lý. Ctrl+C để dừng.", flush=True)
    cycles = 0
    try:
        while True:
            if api_sources.inbox_waiting(inbox):
                args.run_id, args.api = None, True
                try:
                    run_pipeline(args)
                except GuardrailError as e:
                    print(f"Bỏ qua vòng này: {e}", file=sys.stderr, flush=True)
            cycles += 1
            if args.max_cycles and cycles >= args.max_cycles:
                return 0
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("Đã dừng.")
        return 0


def add_run_args(r: argparse.ArgumentParser, with_destinations: bool = True) -> None:
    r.add_argument("--run-id", default=None, help="mặc định theo giờ: YYYYMMDD-HHMMSS")
    r.add_argument("--source-data-dir", type=Path, default=default_data_dir(), help="nơi có interim/ đã cào để phát lại (mặc định ./data)")
    if with_destinations:
        r.add_argument("--destinations", default="", help="chỉ các điểm đến này, vd. 'Nha Trang,Phú Quốc' (Vinpearl luôn giữ)")
    r.add_argument("--max-hotels", type=int, default=None, help="tối đa N bản ghi khách sạn Booking+Agoda, chia đều theo điểm đến")
    r.add_argument("--batch", type=int, default=100, help="số bản ghi mỗi nguồn mỗi nhịp phát lại")
    r.add_argument("--replay-delay-ms", type=int, default=300, help="nghỉ giữa các nhịp phát lại (để nhìn thấy dữ liệu đổ về); 0 = nhanh nhất")
    r.add_argument("--api", action="store_true", help="bật nhánh API: nhận file JSON trong hộp thư đến (data/demo/inbox) và dùng kho dữ liệu API")
    r.add_argument("--only-api", action="store_true", help="chỉ dữ liệu từ API + Vinpearl live, không phát lại bản đã cào (kéo theo --api)")
    r.add_argument("--live-vinpearl", action="store_true", help="gọi API Vinpearl thật cho khách sạn + hạng phòng (miễn phí, không cần key, HTTP thường)")
    r.add_argument("--calendar-days", type=int, default=1, help="với --live-vinpearl: hỏi giá N ngày liên tiếp từ hôm nay thay vì 1 ngày mẫu, "
                                                                 "dựng lịch trống thật (1..30; 30 = đủ cửa sổ đặt chỗ)")
    r.add_argument("--live-tours", action="store_true", help="gọi cả API vé/tour/combo/golf Vinpearl: nằm sau Cloudflare nên MỞ một cửa sổ Chromium; "
                                                              "lỗi thì tự dùng bản đã cào (kéo theo --live-vinpearl)")
    r.add_argument("--tour-limit", type=int, default=10, help="với --live-tours: chỉ lấy chi tiết N vé/tour đầu")
    r.add_argument("--live-trip", action="store_true", help="gọi Trip.com thật cho điểm tham quan + chuyến bay (miễn phí, HTTP thường, không trình duyệt)")
    r.add_argument("--no-fallback", action="store_true", help="với chế độ live: lỗi thì dừng, không tự dùng bản đã cào")
    r.add_argument("--as-of", default=date.today().isoformat(), help="ngày bắt đầu cửa sổ đặt chỗ 30 ngày (YYYY-MM-DD)")
    r.add_argument("--no-db", action="store_true", help="bỏ bước nạp Postgres")
    r.add_argument("--db-host", default="127.0.0.1")
    r.add_argument("--db-port", type=int, default=5432, help="Postgres local của repo (docker compose service postgres)")
    r.add_argument("--db-name", default="vota_demo")
    r.add_argument("--db-user", default="postgres")
    r.add_argument("--db-password", default=os.environ.get("DEMO_DB_PASSWORD", "postgres"))


def add_fetch_args(f: argparse.ArgumentParser, with_destinations: bool = True) -> None:
    f.add_argument("source", choices=api_sources.FETCH_KINDS, help="nguồn API cần token trong .env: Apify (APIFY_TOKEN), SerpApi (SERPAPI_KEY), Travelpayouts (TRAVELPAYOUTS_TOKEN)")
    if with_destinations:
        f.add_argument("--destinations", default="", help="điểm đến cần tải (mặc định 15 điểm đầu của kế hoạch)")
    f.add_argument("--max-items", type=int, default=50, help="tối đa mục mỗi điểm đến (Apify)")
    f.add_argument("--max-usd", type=float, default=1.0, help="trần chi tiêu cả lượt tải (Apify chia đều cho các điểm đến; gửi lên Apify làm maxTotalChargeUsd)")
    f.add_argument("--checkin", default="", help="ngày nhận phòng YYYY-MM-DD (mặc định hôm nay + 30 ngày)")
    f.add_argument("--nights", type=int, default=1)
    f.add_argument("--adults", type=int, default=2)
    f.add_argument("--concurrency", type=int, default=3, help="số lượt Apify chạy song song (gói Free tối đa 5)")
    f.add_argument("--pages", type=int, default=1, help="SerpApi: số trang mỗi điểm đến (~20 khách sạn/trang, mỗi trang tính 1 lượt tìm kiếm)")
    f.add_argument("--routes", default="", help="Travelpayouts: các tuyến, vd. HAN-SGN,SGN-DAD (mặc định 12 tuyến nội địa chính)")
    f.add_argument("--month", default="", help="Travelpayouts: tháng khởi hành YYYY-MM (mặc định tháng của ngày nhận phòng)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    add_run_args(sub.add_parser("run", help="chạy toàn bộ luồng"))
    f = sub.add_parser("fetch", help="tải hàng loạt từ API vào hộp thư đến (tốn tiền/lượt gọi theo gói của bạn; luôn có trần)")
    add_fetch_args(f)
    pl = sub.add_parser("pull", help="fetch + tự xử lý hết: hộp thư đến → chuẩn hoá → Postgres → báo cáo")
    add_fetch_args(pl)
    add_run_args(pl, with_destinations=False)
    sub.add_parser("intake", help="chỉ nhận hộp thư đến vào kho (không chạy cả luồng)")
    au = sub.add_parser("auto", help="theo dõi hộp thư đến, có file mới thì tự chạy trọn luồng")
    add_run_args(au)
    au.add_argument("--every", type=int, default=30, help="số giây giữa hai lần kiểm tra hộp thư")
    au.add_argument("--max-cycles", type=int, default=0, help="dừng sau N vòng (0 = chạy mãi)")
    sub.add_parser("status", help="trạng thái lượt chạy mới nhất")
    p = sub.add_parser("probe-apify", help="chạy thử actor Apify vài dòng để xem JSON thật (cần APIFY_TOKEN, tốn vài cent)")
    p.add_argument("--actor", required=True, help="dạng user/actor-name")
    p.add_argument("--input", required=True, help="JSON input của actor, hoặc @đường/dẫn/file.json")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--max-usd", type=float, default=0.10, help="trần chi tiêu cho lượt thử (gửi lên Apify)")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    cmds = {"run": run_pipeline, "fetch": cmd_fetch, "pull": cmd_pull, "intake": cmd_intake, "auto": cmd_auto, "status": cmd_status, "probe-apify": cmd_probe}
    try:
        date.fromisoformat(getattr(a, "as_of", date.today().isoformat()))
        return cmds[a.cmd](a)
    except (GuardrailError, ValueError) as e:
        print(f"Bị chặn: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
