#!/usr/bin/env python3
"""Job hằng ngày chạy trên console (VPS không có trình duyệt): cào các nguồn HTTP → chuẩn hoá → gate → promote catalog.

  python daily.py run                  # cào mọi worker song song rồi publish (cron 1 lần/ngày, xem cron_daily.sh)
  python daily.py run --no-publish     # chỉ cào
  python daily.py publish              # chỉ chuẩn hoá + gate + promote từ data/interim hiện có
  python daily.py accept <lượt>        # promote catalog của một lượt bị gate chặn, sau khi đã soát
  python daily.py status               # lượt gần nhất, catalog hiện hành, khoá
  python daily.py versions             # các data version (mỗi lần promote là một version theo ngày)
  python daily.py diff <cũ> [<mới>]    # so sánh hai version (bỏ <mới> = so với catalog đang dùng)
  python daily.py switch <version>     # catalog đang dùng = version đó, nạp lại DB đích (--load), dòng thừa → available=false
  python daily.py freeze <version> v1  # gắn nhãn và chép thành snapshots/<version>/ để commit
  UI: python monitor.py → http://127.0.0.1:8765/daily (trên VPS: ssh -L 8765:127.0.0.1:8765 <vps>)

Worker: mỗi origin một tiến trình con chạy `crawl.py` tuần tự trong worker (giãn cách theo host vẫn do crawl.py lo), các worker
chạy song song với nhau. Mọi collector ghi vào data/interim/<nguồn>.jsonl như khi chạy tay; các nguồn cần trình duyệt
(booking.com, trip.com khách sạn/combo) không có worker — bản ghi cũ của chúng trong interim vẫn được chuẩn hoá lại.

Publish (theo docs, chốt với người dùng 23/09/2026):
  1. chép data/interim → data/daily/<lượt>/stage/interim, chạy normalise.py --no-plan --rooms-per-hotel 0 --flights-per-route 0
  2. giữ dòng: sản phẩm có trong catalog đang dùng mà lượt này không thấy vẫn được giữ; không thấy >= RETIRE_DAYS ngày thì
     available=false (không bao giờ xoá dòng: app.booking_items / app.cart_items có khoá ngoại tới cdp.products)
  3. gate so với catalog đang dùng, theo từng nguồn: số sản phẩm đang bán giảm > 20% hoặc độ phủ một trường giảm > 25 điểm %
     → không promote, thoát mã 1, catalog cũ giữ nguyên
  4. promote: sao lưu data/products.jsonl vào data/backups/ rồi thay bằng catalog mới (ghi file tạm rồi đổi tên)
  5. nạp (--load local,cloud hoặc DAILY_LOAD trong .env): `seed --catalog-only` vào Postgres của từng đích, rồi job embed
     vào Weaviate của đích đó (tắt bằng --no-index). Kết nối đọc từ src/data_collection/.env, xem bảng TARGETS.
Mã thoát: 0 ổn · 1 gate chặn / lỗi · 2 có worker bị chặn hoặc lỗi (catalog vẫn publish từ phần đã có) · 3 promote xong nhưng
nạp DB / embed lỗi · 0 kèm SKIP khi đang có lượt khác.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import log as structlog
from collectors.common import default_data_dir

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
RETIRE_DAYS = 7
MAX_COUNT_DROP = 0.20
MAX_COVERAGE_DROP = 0.25
KEEP_BACKUPS = 14
KEEP_RUNS = 30
EXIT_BLOCKED = 75  # crawl.py: bị chặn liên tiếp nên tự dừng
CALENDAR_DAYS = 30
COVERAGE_FIELDS = ("unitPrice", "description", "imageUrl", "coordinates")

# Đích nạp sau khi promote. Giá trị lấy từ biến môi trường / src/data_collection/.env — không bao giờ ghi vào code, log hay báo cáo.
#   seed    : kết nối cho `python -m data_collection.seed --catalog-only` (cần INSERT/UPDATE cdp.products, DELETE/INSERT
#             catalog.combo_items)
#   db      : kết nối job embed đọc catalog (mặc định = seed)
#   weaviate: Weaviate của đích đó; job embed ghi vào collection e5-small của backend (VECTOR_COLLECTION). Model chạy trong
#             tiến trình nên không cần khoá embedding nào (FR-SRC-02; đã bỏ đường lui Cohere) — xem index_missing()
TARGETS = {
    "local": {"seed": "SEED_DATABASE_URL", "db": "DATABASE_URL", "weaviate": "WEAVIATE_URL", "weaviate_key": "WEAVIATE_API_KEY"},
    "cloud": {"seed": "CLOUD_SEED_DATABASE_URL", "db": "CLOUD_DATABASE_URL", "weaviate": "CLOUD_WEAVIATE_URL",
              "weaviate_key": "CLOUD_WEAVIATE_API_KEY"},
}


def workers(calendar_days: int = CALENDAR_DAYS) -> dict[str, list[list[str]]]:
    """origin → các lệnh crawl.py chạy tuần tự. Hai lệnh Vinpearl chung host booking-hotel-api nên nằm cùng worker.
    Phạm vi điểm đến: DAILY_DESTINATIONS (mặc định @v1 = 38 điểm của catalog v1, collectors/plan.py)."""
    offsets = ",".join(str(i) for i in range(calendar_days))
    scope = os.environ.get("DAILY_DESTINATIONS") or "@v1"
    return {
        "vinpearl": [
            ["vinpearl", "--no-browser", "--refresh", "--price-dates", offsets],
            ["vinpearl-bundles", "--days", str(calendar_days)],
        ],
        "trip": [
            ["trip-flights", "--refresh", "--destinations", scope],
            ["trip-attractions", "--destinations", scope],
        ],
        # agoda: sitemap tự đọc lại sau 7 ngày; mỗi ngày lấp các ngày giá còn thiếu (ngày +30 mới) rồi làm mới ngày gần,
        # tự dừng êm sau DAILY_AGODA_HOURS giờ (mặc định 14) để kịp publish trong ngày
        "agoda": [
            ["agoda-api", "--destinations", scope, "--days", str(calendar_days),
             "--per-city", os.environ.get("DAILY_AGODA_PER_CITY") or "50",
             "--max-hours", os.environ.get("DAILY_AGODA_HOURS") or "14"],
        ],
    }


# ---------------------------------------------------------------------- tiện ích


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_rows(path: Path, rows: list[dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_of(row: dict) -> str:
    return (row.get("sourceRef") or "?").split(":", 1)[0]


class DailyLock:
    """Khoá không chờ: đã có lượt khác đang chạy thì lượt này bỏ qua (cron không chồng lượt)."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # Windows: không khoá được, chấp nhận
            pass
        except OSError:
            self._fh.close()
            self._fh = None
            return False
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(f"{os.getpid()} {now_local()}")
        self._fh.flush()
        return True

    def release(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


# ---------------------------------------------------------------------- giữ dòng + gate (thuần, có test)


def carry_forward(fresh: list[dict], previous: list[dict], ledger: dict[str, str], today: date,
                  retire_days: int = RETIRE_DAYS) -> tuple[list[dict], dict[str, str], Counter]:
    """Catalog mới = mọi dòng lượt này thấy + dòng của catalog đang dùng mà lượt này không thấy.
    `ledger`: productId → ngày thấy gần nhất. Dòng không thấy >= retire_days ngày thì available=false; dòng chưa có trong ledger
    (lượt đầu dùng ledger) bắt đầu tính từ hôm nay. Trả về (catalog, ledger mới, thống kê). Không sửa đầu vào."""
    stats: Counter = Counter()
    ledger = dict(ledger)
    day = today.isoformat()
    fresh_ids = {p["productId"] for p in fresh}
    for pid in fresh_ids:
        ledger[pid] = day
    out = list(fresh)
    stats["fresh"] = len(fresh)
    for p in previous:
        pid = p["productId"]
        if pid in fresh_ids:
            continue
        seen = ledger.setdefault(pid, day)
        row = copy.deepcopy(p)
        row["attributes"] = dict(row.get("attributes") or {}, lastSeenAt=seen)
        if (today - date.fromisoformat(seen)).days >= retire_days:
            if row.get("available"):
                stats["retired"] += 1
            row["available"] = False
        else:
            stats["carried"] += 1
        out.append(row)
    stats["new"] = len(fresh_ids - {p["productId"] for p in previous})
    stats["total"] = len(out)
    return out, ledger, stats


def _has(row: dict, name: str) -> bool:
    if name == "coordinates":
        a = row.get("attributes") or {}
        return a.get("latitude") is not None and a.get("longitude") is not None
    return row.get(name) not in (None, "", [])


def profile(rows: list[dict]) -> dict[str, dict]:
    """Theo nguồn: số dòng, số dòng đang bán, độ phủ các trường trên dòng đang bán."""
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[source_of(r)].append(r)
    out = {}
    for src, rs in sorted(by.items()):
        live = [r for r in rs if r.get("available")]
        cov = {f: round(sum(_has(r, f) for r in live) / len(live), 4) if live else 0.0 for f in COVERAGE_FIELDS}
        out[src] = {"rows": len(rs), "available": len(live), "coverage": cov}
    return out


def gate(new: dict[str, dict], old: dict[str, dict], max_count_drop: float = MAX_COUNT_DROP,
         max_coverage_drop: float = MAX_COVERAGE_DROP) -> list[str]:
    problems = []
    for src, o in old.items():
        n = new.get(src) or {"rows": 0, "available": 0, "coverage": {}}
        if n["rows"] < o["rows"]:
            problems.append(f"{src}: số dòng giảm {o['rows']} → {n['rows']} (catalog chỉ được tăng)")
        if o["available"] and (o["available"] - n["available"]) / o["available"] > max_count_drop:
            problems.append(f"{src}: sản phẩm đang bán giảm {o['available']} → {n['available']} (> {max_count_drop:.0%})")
        for f, before in o["coverage"].items():
            after = n["coverage"].get(f, 0.0)
            if before - after > max_coverage_drop:
                problems.append(f"{src}: độ phủ {f} giảm {before:.0%} → {after:.0%} (> {max_coverage_drop * 100:.0f} điểm %)")
    return problems


# ---------------------------------------------------------------------- lượt chạy


@dataclass
class Run:
    data: Path
    run_id: str
    dir: Path = field(init=False)
    state: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self.dir = self.data / "daily" / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state.setdefault("runId", self.run_id)
        self.state.setdefault("startedAt", now_local())
        structlog.configure(run_id=self.run_id, flow="daily")

    def stage(self, name: str, status: str = "running", **info) -> None:
        """Ghi bước đang chạy để UI biết luồng đang ở đâu: crawl → normalise → carry → gate → promote → load:<đích>."""
        stages = self.state.setdefault("stages", [])
        cur = next((x for x in stages if x["name"] == name), None)
        if cur is None:
            cur = {"name": name, "startedAt": now_local()}
            stages.append(cur)
        cur.update(status=status, **info)
        if status == "running":
            structlog.emit("step.start", f"daily.stage.start name={name}", step=name, human="")
        else:
            structlog.emit("step.end", f"daily.stage.end name={name} status={status}",
                           "ERROR" if status in ("failed", "error", "blocked") else
                           "WARNING" if status in ("warn", "skipped", "timeout") else "INFO",
                           step=name, status=status, human="")
        if status != "running":
            cur["finishedAt"] = now_local()
        self.state["currentStage"] = name if status == "running" else None
        self.save()

    def save(self) -> None:
        with self._lock:
            tmp = self.dir / "state.json.tmp"
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.dir / "state.json")


def run_worker(run: Run, name: str, steps: list[list[str]], deadline: float | None) -> None:
    info = run.state["workers"][name] = {"status": "running", "steps": [], "startedAt": now_local()}
    run.save()
    log_path = run.dir / f"{name}.log"
    for step in steps:
        argv = [sys.executable, str(HERE / "crawl.py"), "--data-dir", str(run.data)] + step
        started = time.monotonic()
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"\n=== {now_local()} {' '.join(step)}\n")
            log.flush()
            proc = subprocess.Popen(argv, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            timed_out = False
            while proc.poll() is None:
                if deadline and time.time() > deadline and not timed_out:
                    timed_out = True  # SIGINT: collector lưu tiến độ rồi thoát (mã 130), lượt sau làm tiếp
                    os.killpg(proc.pid, signal.SIGINT)
                time.sleep(2)
        code = proc.returncode
        info["steps"].append({"cmd": step[0], "exit": code, "seconds": round(time.monotonic() - started),
                              **({"timedOut": True} if timed_out else {})})
        run.save()
        if code == EXIT_BLOCKED:
            info["status"] = "blocked"
            break
        if timed_out:
            info["status"] = "timeout"
            break
    else:
        info["status"] = "ok" if all(s["exit"] == 0 for s in info["steps"]) else "error"
    info["finishedAt"] = now_local()
    run.save()


def crawl(run: Run, only: set[str] | None, max_hours: float | None) -> bool:
    deadline = time.time() + max_hours * 3600 if max_hours else None
    plan = {k: v for k, v in workers().items() if not only or k in only}
    run.state["workers"] = {}
    run.stage("crawl")
    threads = [threading.Thread(target=run_worker, args=(run, name, steps, deadline), name=name) for name, steps in plan.items()]
    structlog.emit("daily.crawl.start", f"[daily] {run.run_id}: {len(threads)} worker song song ({', '.join(plan)}) – log ở {run.dir}",
                   workers=list(plan), step="crawl")
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ok = all(w["status"] == "ok" for w in run.state["workers"].values())
    run.stage("crawl", "done" if ok else "warn")
    for name, w in run.state["workers"].items():
        structlog.emit("daily.worker.end", f"[daily]   {name}: {w['status']} "
                       + ", ".join(f"{s['cmd']}={s['exit']}" for s in w["steps"]),
                       "INFO" if w["status"] == "ok" else "ERROR", source=name, step="crawl", status=w["status"],
                       steps={s["cmd"]: s["exit"] for s in w["steps"]})
    return ok


def publish(run: Run, today: date) -> int:
    data = run.data
    stage = run.dir / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "interim").mkdir(parents=True)
    for f in sorted((data / "interim").glob("*.jsonl")):
        shutil.copy2(f, stage / "interim" / f.name)
    if not any((stage / "interim").iterdir()):
        run.state["publish"] = {"status": "error", "error": "data/interim trống – chép interim nền vào trước (xem README)"}
        run.save()
        structlog.emit("daily.normalise.empty", "[daily] data/interim trống, không có gì để chuẩn hoá.", "ERROR")
        return 1
    argv = [sys.executable, str(HERE / "normalise.py"), "--data-dir", str(stage), "--no-plan", "--rooms-per-hotel", "0",
            "--flights-per-route", "0", "--report-json", str(stage / "normalise_report.json")]
    run.stage("normalise")
    with open(run.dir / "normalise.log", "w", encoding="utf-8") as log:
        code = subprocess.call(argv, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
    if code != 0 or not (stage / "products.jsonl").exists():
        run.state["publish"] = {"status": "error", "error": f"normalise.py thoát mã {code}"}
        run.stage("normalise", "failed", error=f"thoát mã {code}")
        return 1
    run.stage("normalise", "done")
    run.stage("carry")

    current_path = data / "products.jsonl"
    ledger_path = data / "state" / "catalog_seen.json"
    previous = read_rows(current_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    catalog, new_ledger, stats = carry_forward(read_rows(stage / "products.jsonl"), previous, ledger, today)
    write_rows(stage / "catalog.jsonl", catalog)
    (stage / "catalog_seen.json").write_text(json.dumps(new_ledger, ensure_ascii=False), encoding="utf-8")
    run.stage("carry", "done", **{k: stats.get(k, 0) for k in ("fresh", "new", "carried", "retired", "total")})
    new_profile, old_profile = profile(catalog), profile(previous)
    problems = gate(new_profile, old_profile)
    run.stage("gate", "blocked" if problems else "done", problems=problems)
    run.state["publish"] = {"status": "blocked" if problems else "pending", "baseSha256": sha256_of(current_path),
                            "stats": dict(stats), "problems": problems, "profile": new_profile, "previousProfile": old_profile}
    run.save()
    if problems:
        structlog.emit("daily.gate.blocked", "[daily] GATE CHẶN – giữ catalog cũ:\n  - " + "\n  - ".join(problems),
                       "ERROR", step="gate", problem_count=len(problems))
        structlog.emit("daily.gate.review", f"[daily] Soát {stage}/catalog.jsonl; đúng thì: python daily.py accept {run.run_id}",
                       step="gate")
        return 1
    return promote(run)


def promote(run: Run) -> int:
    data = run.data
    stage = run.dir / "stage"
    current_path = data / "products.jsonl"
    pub = run.state.get("publish") or {}
    if sha256_of(current_path) != pub.get("baseSha256"):
        structlog.emit("daily.promote.stale", "[daily] data/products.jsonl đã đổi sau khi lượt này chuẩn hoá – chạy publish lại thay vì promote bản cũ.",
                       "ERROR", step="promote")
        return 1
    backups = data / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    if current_path.exists():
        with open(current_path, "rb") as src, gzip.open(backups / f"products-{run.run_id}.jsonl.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
        for old in sorted(backups.glob("products-*.jsonl.gz"))[:-KEEP_BACKUPS]:
            old.unlink()
    tmp = data / "products.jsonl.tmp"
    shutil.copyfile(stage / "catalog.jsonl", tmp)
    os.replace(tmp, current_path)
    (data / "state").mkdir(parents=True, exist_ok=True)
    os.replace(stage / "catalog_seen.json", data / "state" / "catalog_seen.json")
    version = create_version(data, run.run_id, pub.get("stats") or {})
    pub.update(status="promoted", promotedAt=now_local(), sha256=sha256_of(current_path), version=version)
    run.state["publish"] = pub
    run.stage("promote", "done", version=version)
    s = pub.get("stats") or {}
    structlog.emit("daily.promote.done", f"[daily] Promote xong: {s.get('total')} dòng ({s.get('fresh')} thấy lượt này, {s.get('new', 0)} mới, "
                   f"{s.get('carried', 0)} giữ lại, {s.get('retired', 0)} ngừng bán) → {current_path}",
                   step="promote", records=s.get("total"), new=s.get("new", 0), retired=s.get("retired", 0))
    return 0


def write_report(run: Run) -> None:
    st = run.state
    lines = [f"[daily] lượt {st['runId']} · bắt đầu {st.get('startedAt')} · kết thúc {st.get('finishedAt')}"]
    for name, w in (st.get("workers") or {}).items():
        lines.append(f"- worker {name}: {w['status']} · " + ", ".join(f"{s['cmd']} mã {s['exit']} ({s['seconds']}s)" for s in w["steps"]))
    pub = st.get("publish")
    if pub:
        s = pub.get("stats") or {}
        lines.append(f"- publish: {pub['status']} · {s.get('total', '?')} dòng · mới {s.get('new', 0)} · giữ lại {s.get('carried', 0)} "
                     f"· ngừng bán {s.get('retired', 0)}")
        lines += [f"  ! {p}" for p in pub.get("problems") or []]
        for src, p in (pub.get("profile") or {}).items():
            cov = " ".join(f"{k}={v:.0%}" for k, v in p["coverage"].items())
            lines.append(f"  {src:9s} {p['available']:>6}/{p['rows']:<6} đang bán · {cov}")
    lines.append(f"- mã thoát {st.get('exitCode')}")
    (run.dir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


def load_env(paths: tuple[Path, ...] = (HERE / ".env", REPO_ROOT / ".env")) -> None:
    """Nạp KEY=VALUE từ src/data_collection/.env rồi .env ở gốc repository vào os.environ (không ghi đè biến đã có; file đứng
    trước thắng). Giá trị có thể đặt trong nháy. Cả hai file đều nằm trong .gitignore."""
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        _load_env_text(text)


def _load_env_text(text: str) -> None:
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and value and key not in os.environ:  # dòng trống không che giá trị có thật ở file sau
            os.environ[key] = value


def target_env(target: str) -> tuple[dict[str, str], list[str]]:
    """Biến môi trường cho tiến trình con của một đích, và danh sách biến còn thiếu (chỉ tên, không bao giờ giá trị)."""
    spec = TARGETS[target]
    seed = os.environ.get(spec["seed"], "")
    missing = [spec["seed"]] if not seed else []
    weaviate = _with_scheme(os.environ.get(spec["weaviate"], ""))
    key = os.environ.get(spec["weaviate_key"], "")
    if not key and weaviate and _host(weaviate) == _host(_with_scheme(os.environ.get("WEAVIATE_URL", ""))):
        key = os.environ.get("WEAVIATE_API_KEY", "")  # cùng cluster với WEAVIATE_URL của backend → dùng chung key
    env = dict(os.environ, SEED_DATABASE_URL=seed, DATABASE_URL=os.environ.get(spec["db"]) or seed,
               WEAVIATE_URL=weaviate, WEAVIATE_API_KEY=key)
    return env, missing


def index_missing(env) -> list[str]:
    """Biến còn thiếu để chạy bước embed (chỉ tên, không bao giờ giá trị). e5-small chạy trong tiến trình (FR-SRC-02) nên
    chỉ cần WEAVIATE_URL; COHERE_API_KEY không còn dùng (đã bỏ đường lui Cohere, update-archive/2026-10-06-bo-duong-lui-cohere)."""
    return [] if env.get("WEAVIATE_URL") else ["WEAVIATE_URL"]


def _with_scheme(url: str) -> str:
    return url if not url or url.startswith(("http://", "https://")) else "https://" + url  # Weaviate Cloud cho URL không scheme


def _host(url: str) -> str | None:
    from urllib.parse import urlsplit
    return urlsplit(url).hostname if url else None


def load_targets(run: Run, targets: list[str], index: bool, today: date, retire_missing: bool = False) -> bool:
    """Sau promote/switch: nạp catalog vào từng đích bằng seed --catalog-only, rồi (tuỳ chọn) chạy job embed vào Weaviate của
    đích đó. `retire_missing` (switch version): dòng trong DB không có ở catalog này → available=false, không xoá."""
    ok = True
    results = run.state.setdefault("load", {})
    version = active_version(run.data)
    for target in targets:
        env, missing = target_env(target)
        res = results[target] = {"startedAt": now_local(), "version": version}
        run.stage(f"load:{target}")
        if missing:
            res.update(status="skipped", error=f"thiếu biến {', '.join(missing)} trong .env")
            structlog.emit("daily.load.skipped", f"[daily] nạp {target}: bỏ qua – thiếu {', '.join(missing)} (xem README, mục Job hằng ngày)",
                           "WARNING", step=f"load:{target}", source=target)
            ok = False
            run.stage(f"load:{target}", "skipped", error=res["error"])
            continue
        # --real-flight-dates: dữ liệu thật giữ ngày bay thật (PRD data-model §3); chỉ seed demo mới dời vé vào cửa sổ.
        argv = [sys.executable, "-m", "data_collection.seed", "--catalog-only", "--real-flight-dates",
                "--products", str(run.data / "products.jsonl"),
                "--as-of", today.isoformat()] + (["--retire-missing"] if retire_missing else [])
        with open(run.dir / f"load-{target}.log", "w", encoding="utf-8") as log:
            code = subprocess.call(argv, cwd=HERE.parent, env=env, stdout=log, stderr=subprocess.STDOUT)
            res["seedExit"] = code
            if code == 0 and index:
                index_gap = index_missing(env)
                if index_gap:
                    res["index"] = f"skipped: thiếu {'/'.join(index_gap)}"
                else:
                    log.write(f"\n=== {now_local()} embed_products\n")
                    log.flush()
                    res["indexExit"] = subprocess.call([sys.executable, "-m", "src.data_collection.index_backlog",
                                                       "--state-file", str(run.data / "state" / f"index_pending-{target}.json")],
                                                       cwd=REPO_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        backlog_file = run.data / "state" / f"index_pending-{target}.json"
        if index and backlog_file.exists():
            res["indexPending"] = json.loads(backlog_file.read_text())
        succeeded = code == 0 and res.get("indexExit", 0) == 0
        res["status"] = ("partial" if res.get("indexPending") else "ok") if succeeded else "error"
        res["finishedAt"] = now_local()
        ok = ok and succeeded
        if code == 0:
            record_loaded(run.data, target, version, run.run_id)
        structlog.emit("daily.load.done", f"[daily] nạp {target}: {res['status']} (log: {run.dir / f'load-{target}.log'})",
                       "INFO" if succeeded else "ERROR", step=f"load:{target}", source=target, status=res["status"])
        run.stage(f"load:{target}", "done" if succeeded else "failed", indexPending=bool(res.get("indexPending")))
    return ok


# ---------------------------------------------------------------------- data version
# Mỗi lần promote = một version theo ngày (2026-09-24, trùng ngày thì 2026-09-24.2) trong data/versions/<id>/:
#   products.jsonl.gz (nén tất định) · catalog_seen.json (ledger giữ dòng) · manifest.json (số liệu, checksum, nhãn)
# data/versions/ACTIVE = version đang là data/products.jsonl; data/versions/loaded.json = version đang nằm trong từng DB đích.
# Đóng băng (freeze) = gắn nhãn v1/v2 và chép sang snapshots/<id>/ theo đúng format seed/snapshot.py để commit.

VERSION_ID = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\.\d+)?$")
LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


def versions_dir(data: Path) -> Path:
    return data / "versions"


def gzip_file(src: Path, dst: Path) -> None:
    """gzip tất định (mtime=0, không tên file) để cùng nội dung ra cùng checksum."""
    tmp = dst.with_name(dst.name + ".tmp")
    with open(src, "rb") as f, open(tmp, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
        shutil.copyfileobj(f, gz)
    os.replace(tmp, dst)


def summarize(rows: list[dict]) -> dict:
    tax: dict[str, Counter] = defaultdict(Counter)
    dest: Counter = Counter()
    for r in rows:
        tax[r.get("taxonomy") or "?"]["rows"] += 1
        if r.get("available"):
            tax[r.get("taxonomy") or "?"]["available"] += 1
            dest[r.get("destination") or "?"] += 1
    return {"rows": len(rows), "available": sum(1 for r in rows if r.get("available")),
            "byTaxonomy": {k: dict(v) for k, v in sorted(tax.items())}, "byDestination": dict(dest.most_common()),
            "bySource": profile(rows)}


def active_version(data: Path) -> str | None:
    try:
        return (versions_dir(data) / "ACTIVE").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def set_active(data: Path, version: str) -> None:
    tmp = versions_dir(data) / "ACTIVE.tmp"
    tmp.write_text(version, encoding="utf-8")
    os.replace(tmp, versions_dir(data) / "ACTIVE")


def read_manifest(data: Path, version: str) -> dict:
    if not VERSION_ID.match(version):
        raise ValueError(f"version không hợp lệ: {version}")
    path = versions_dir(data) / version / "manifest.json"
    if not path.is_file():
        raise ValueError(f"không có version {version}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(data: Path, manifest: dict) -> None:
    path = versions_dir(data) / manifest["version"] / "manifest.json"
    tmp = path.with_name("manifest.json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def create_version(data: Path, run_id: str, stats: dict, today: date | None = None) -> str:
    base = (today or date.today()).isoformat()
    root = versions_dir(data)
    root.mkdir(parents=True, exist_ok=True)
    version, n = base, 2
    while (root / version).exists():
        version, n = f"{base}.{n}", n + 1
    vdir = root / version
    vdir.mkdir()
    current = data / "products.jsonl"
    gzip_file(current, vdir / "products.jsonl.gz")
    ledger = data / "state" / "catalog_seen.json"
    if ledger.exists():
        shutil.copyfile(ledger, vdir / "catalog_seen.json")
    rows = read_rows(current)
    write_manifest(data, {
        "schemaVersion": 1, "version": version, "label": None, "createdAt": now_local(), "runId": run_id,
        "previousVersion": active_version(data), "stats": {k: v for k, v in stats.items()},
        "products": {"file": "products.jsonl.gz", "rows": len(rows), "sha256": sha256_of(current),
                     "gzipSha256": sha256_of(vdir / "products.jsonl.gz")},
        **summarize(rows),
    })
    set_active(data, version)
    prune_versions(data)
    return version


def loaded_versions(data: Path) -> dict:
    path = versions_dir(data) / "loaded.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def record_loaded(data: Path, target: str, version: str | None, run_id: str) -> None:
    loaded = loaded_versions(data)
    loaded[target] = {"version": version, "runId": run_id, "at": now_local()}
    path = versions_dir(data) / "loaded.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("loaded.json.tmp")
    tmp.write_text(json.dumps(loaded, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def list_versions(data: Path) -> list[dict]:
    root = versions_dir(data)
    out = []
    for vdir in sorted((p for p in root.glob("*") if p.is_dir() and VERSION_ID.match(p.name)), reverse=True) if root.exists() else []:
        try:
            out.append(json.loads((vdir / "manifest.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def prune_versions(data: Path, keep: int = KEEP_RUNS) -> None:
    """Giữ `keep` version mới nhất, cộng mọi version đã đóng băng / đang dùng / đang nằm trong một DB đích."""
    protected = {active_version(data)} | {v.get("version") for v in loaded_versions(data).values()}
    for i, m in enumerate(list_versions(data)):
        if i >= keep and not m.get("label") and m["version"] not in protected:
            shutil.rmtree(versions_dir(data) / m["version"], ignore_errors=True)


def version_rows(data: Path, version: str) -> list[dict]:
    read_manifest(data, version)
    return read_rows(versions_dir(data) / version / "products.jsonl.gz")


def diff_versions(old: list[dict], new: list[dict], sample: int = 15) -> dict:
    """Khác biệt giữa hai catalog: thêm, bỏ, ngừng bán, bán lại, đổi giá — tổng và theo nguồn / điểm đến."""
    a = {r["productId"]: r for r in old}
    b = {r["productId"]: r for r in new}
    kinds = {"added": [], "removed": [], "retired": [], "revived": [], "priceChanged": [], "otherChanged": []}
    for pid, r in b.items():
        o = a.get(pid)
        if o is None:
            kinds["added"].append(r)
        elif o.get("available") and not r.get("available"):
            kinds["retired"].append(r)
        elif r.get("available") and not o.get("available"):
            kinds["revived"].append(r)
        elif o.get("unitPrice") is not None and r.get("unitPrice") is not None and o["unitPrice"] != r["unitPrice"]:
            kinds["priceChanged"].append(r)
        elif o != r:  # mô tả, ảnh, lịch giá, lastSeenAt…
            kinds["otherChanged"].append(r)
    kinds["removed"] = [r for pid, r in a.items() if pid not in b]

    def brief(r: dict) -> dict:
        o = a.get(r["productId"]) or {}
        return {"productId": r["productId"], "name": r.get("name"), "taxonomy": r.get("taxonomy"), "destination": r.get("destination"),
                "source": source_of(r), "unitPrice": r.get("unitPrice"), "oldUnitPrice": o.get("unitPrice"), "available": r.get("available")}

    return {k: {"count": len(v), "bySource": dict(Counter(source_of(r) for r in v).most_common()),
                "byDestination": dict(Counter(r.get("destination") or "?" for r in v).most_common(15)),
                "sample": [brief(r) for r in v[:sample]]} for k, v in kinds.items()}


def switch_version(data: Path, version: str) -> dict:
    """Catalog đang dùng = version đã chọn (sao lưu bản hiện tại trước). Không nạp DB — gọi load_targets sau đó."""
    manifest = read_manifest(data, version)
    vdir = versions_dir(data) / version
    current = data / "products.jsonl"
    tmp = data / "products.jsonl.tmp"
    with gzip.open(vdir / "products.jsonl.gz", "rb") as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst)
    if sha256_of(tmp) != manifest["products"]["sha256"]:
        tmp.unlink()
        raise ValueError(f"checksum của version {version} không khớp manifest – không switch")
    backups = data / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    if current.exists():
        with open(current, "rb") as src, gzip.open(backups / f"products-switch-{datetime.now():%Y%m%d-%H%M%S}.jsonl.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
    os.replace(tmp, current)
    (data / "state").mkdir(parents=True, exist_ok=True)
    if (vdir / "catalog_seen.json").exists():
        shutil.copyfile(vdir / "catalog_seen.json", data / "state" / "catalog_seen.json")
    previous = active_version(data)
    set_active(data, version)
    return {"version": version, "previous": previous, "rows": manifest["products"]["rows"]}


def freeze_version(data: Path, version: str, label: str, snapshots: Path = HERE / "snapshots") -> Path:
    """Gắn nhãn (v1, v2…) và chép version thành snapshots/<version>/ đúng format seed/snapshot.py (commit được)."""
    if not LABEL.match(label):
        raise ValueError("nhãn chỉ gồm chữ, số, '.', '_' hoặc '-', tối đa 32 ký tự (vd. v1)")
    manifest = read_manifest(data, version)
    if any(m.get("label") == label and m["version"] != version for m in list_versions(data)):
        raise ValueError(f"nhãn {label} đã dùng cho version khác")
    target = snapshots / version
    if target.exists():
        raise ValueError(f"{target} đã tồn tại – snapshot không được sửa, chọn version khác")
    manual = data / "combo_items_manual.jsonl"
    if not manual.is_file():
        raise ValueError(f"thiếu {manual} (mapping combo duyệt tay đi kèm mọi snapshot)")
    target.mkdir(parents=True)
    shutil.copyfile(versions_dir(data) / version / "products.jsonl.gz", target / "products.jsonl.gz")
    shutil.copyfile(manual, target / "combo_items_manual.jsonl")
    snap = {
        "schemaVersion": 1, "snapshotId": version, "release": label,
        "description": f"Catalog {label}: version {version} của job hằng ngày ({manifest['products']['rows']} sản phẩm)",
        "products": {k: manifest["products"][k] for k in ("file", "rows", "sha256", "gzipSha256")},
        "comboManual": {"file": manual.name, "rows": sum(1 for line in open(manual, encoding="utf-8") if line.strip()),
                        "sha256": sha256_of(manual)},
    }
    (target / "manifest.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest.update(label=label, frozenAt=now_local(),
                    snapshot=str(target.relative_to(HERE)) if target.is_relative_to(HERE) else str(target))
    write_manifest(data, manifest)
    return target


def prune_runs(data: Path, keep: int = KEEP_RUNS) -> None:
    runs = sorted(p for p in (data / "daily").glob("*") if p.is_dir())
    for old in runs[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


# ---------------------------------------------------------------------- lệnh


def cmd_run(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    lock = DailyLock(data / "state" / "daily.lock")
    if not lock.acquire():
        structlog.emit("catalog.lock.busy", f"[daily] SKIP: đang có lượt khác chạy (khoá {lock.path})", "WARNING", flow="daily")
        return 0
    try:
        run = Run(data, a.run_id or datetime.now().strftime("%Y%m%d-%H%M%S"))
        (data / "daily" / "latest.txt").write_text(run.run_id, encoding="utf-8")
        workers_ok = True
        if a.cmd == "run" and not a.no_crawl:
            only = {x.strip() for x in a.workers.split(",") if x.strip()} if a.workers else None
            workers_ok = crawl(run, only, a.max_hours)
        else:
            run.stage("crawl", "skipped")
        code = 0
        today = date.fromisoformat(a.today) if a.today else date.today()
        if a.cmd == "publish" or not a.no_publish:
            code = publish(run, today)
            targets = [t.strip() for t in (a.load or "").split(",") if t.strip()]
            if code == 0 and targets and not load_targets(run, targets, not a.no_index, today):
                code = 3
        if code == 0 and not workers_ok:
            code = 2
        run.state.update(finishedAt=now_local(), exitCode=code)
        run.save()
        structlog.emit("run.end", f"run.end exit={code}", "INFO" if code == 0 else "ERROR" if code == 1 else "WARNING",
                       exit_code=code, status="ok" if code == 0 else "failed" if code == 1 else "partial")
        write_report(run)
        prune_runs(data)
        return code
    finally:
        lock.release()


def cmd_accept(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    run_dir = data / "daily" / a.run
    try:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    except OSError:
        print(f"Không thấy lượt {a.run} trong {data / 'daily'}", file=sys.stderr)
        return 1
    if (state.get("publish") or {}).get("status") != "blocked":
        print(f"Lượt {a.run} không ở trạng thái bị gate chặn ({(state.get('publish') or {}).get('status')}).", file=sys.stderr)
        return 1
    lock = DailyLock(data / "state" / "daily.lock")
    if not lock.acquire():
        print("Đang có lượt khác chạy, thử lại sau.", file=sys.stderr)
        return 1
    try:
        run = Run(data, a.run, state=state)
        run.state["publish"]["acceptedAt"] = now_local()
        code = promote(run)
        targets = [t.strip() for t in (a.load or "").split(",") if t.strip()]
        if code == 0 and targets and not load_targets(run, targets, not a.no_index, date.today()):
            code = 3
        return code
    finally:
        lock.release()


def cmd_versions(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    active, loaded = active_version(data), loaded_versions(data)
    rows = list_versions(data)
    if not rows:
        print("Chưa có version nào (version được tạo ở mỗi lần promote).")
        return 0
    for m in rows:
        where = [t for t, v in loaded.items() if v.get("version") == m["version"]]
        flags = " ".join(x for x in (("ĐANG DÙNG" if m["version"] == active else ""), (f"[{m['label']}]" if m.get("label") else ""),
                                     (f"DB: {', '.join(where)}" if where else "")) if x)
        s = m.get("stats") or {}
        print(f"{m['version']:13s} {m['products']['rows']:>6} dòng · đang bán {m.get('available', '?'):>6} · mới {s.get('new', 0):>5} "
              f"· ngừng bán {s.get('retired', 0):>4} · {m['createdAt'][:16]}  {flags}")
    return 0


def cmd_diff(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    old = version_rows(data, a.old)
    new = version_rows(data, a.new) if a.new else read_rows(data / "products.jsonl")
    for kind, d in diff_versions(old, new).items():
        print(f"{kind:13s} {d['count']:>6}  " + ", ".join(f"{k} {v}" for k, v in d["bySource"].items()))
    return 0


def cmd_switch(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    lock = DailyLock(data / "state" / "daily.lock")
    if not lock.acquire():
        print("Đang có lượt khác chạy, thử lại sau.", file=sys.stderr)
        return 1
    try:
        run = Run(data, f"switch-{datetime.now():%Y%m%d-%H%M%S}")
        run.state.update(kind="switch", version=a.version)
        (data / "daily" / "latest.txt").write_text(run.run_id, encoding="utf-8")
        run.stage("switch")
        try:
            info = switch_version(data, a.version)
        except ValueError as e:
            run.stage("switch", "failed", error=str(e))
            print(f"[daily] {e}", file=sys.stderr)
            code = 1
        else:
            run.stage("switch", "done", **info)
            print(f"[daily] Catalog đang dùng = version {a.version} ({info['rows']} dòng; trước đó {info['previous']})", flush=True)
            targets = [t.strip() for t in (a.load or "").split(",") if t.strip()]
            code = 0 if not targets or load_targets(run, targets, not a.no_index, date.today(), retire_missing=True) else 3
        run.state.update(finishedAt=now_local(), exitCode=code)
        run.save()
        return code
    finally:
        lock.release()


def cmd_freeze(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    try:
        target = freeze_version(data, a.version, a.label)
    except ValueError as e:
        print(f"[daily] {e}", file=sys.stderr)
        return 1
    print(f"[daily] Đóng băng {a.version} thành {a.label}: {target} (commit thư mục này để team dùng chung)")
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    data = a.data_dir.resolve()
    current = data / "products.jsonl"
    print(f"Catalog: {current} · {sum(1 for _ in open(current, encoding='utf-8')) if current.exists() else 0} dòng")
    lock = DailyLock(data / "state" / "daily.lock")
    if lock.acquire():
        lock.release()
        print("Khoá: không có lượt nào đang chạy")
    else:
        print(f"Khoá: đang chạy ({(data / 'state' / 'daily.lock').read_text(encoding='utf-8').strip()})")
    runs = sorted(p for p in (data / "daily").glob("*") if p.is_dir()) if (data / "daily").exists() else []
    for r in runs[-a.last:]:
        report = r / "report.txt"
        print("\n" + (report.read_text(encoding="utf-8").strip() if report.exists() else f"[daily] lượt {r.name}: chưa xong / không có báo cáo"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=default_data_dir(), help="thư mục dữ liệu (mặc định ./data)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="cào song song rồi publish")
    r.add_argument("--workers", default=None, help=f"chỉ các worker này, vd. vinpearl (có: {', '.join(workers())})")
    r.add_argument("--max-hours", type=float, default=None, help="hạn cho phần cào; quá hạn thì dừng êm worker còn chạy rồi publish")
    r.add_argument("--no-publish", action="store_true", help="chỉ cào")
    r.add_argument("--no-crawl", action="store_true", help="bỏ phần cào (giống publish)")
    pb = sub.add_parser("publish", help="chuẩn hoá + gate + promote từ data/interim hiện có")
    ac = sub.add_parser("accept", help="promote catalog của lượt bị gate chặn")
    ac.add_argument("run")
    for sp in (r, pb):
        sp.add_argument("--run-id", default=None, help="mặc định theo giờ: YYYYMMDD-HHMMSS")
        sp.add_argument("--today", default=None, help="ngày tính giữ dòng/ngừng bán (mặc định hôm nay, YYYY-MM-DD)")
    for sp in (r, pb, ac):
        sp.add_argument("--load", default=None, help=f"nạp sau promote vào các đích: {', '.join(TARGETS)} (mặc định DAILY_LOAD trong .env)")
        sp.add_argument("--no-index", action="store_true", help="không chạy job embed vào Weaviate sau khi nạp")
    s = sub.add_parser("status", help="lượt gần nhất và catalog hiện hành")
    s.add_argument("--last", type=int, default=3)
    sub.add_parser("versions", help="liệt kê các version (mới nhất trước), version đang dùng và đang nằm trong DB")
    df = sub.add_parser("diff", help="so sánh hai version (bỏ NEW = so với catalog đang dùng)")
    df.add_argument("old")
    df.add_argument("new", nargs="?")
    sw = sub.add_parser("switch", help="đổi catalog đang dùng sang một version rồi nạp lại DB đích")
    sw.add_argument("version")
    sw.add_argument("--load", default=None, help=f"nạp lại các đích: {', '.join(TARGETS)} (mặc định DAILY_LOAD trong .env)")
    sw.add_argument("--no-index", action="store_true", help="không chạy job embed sau khi nạp")
    fz = sub.add_parser("freeze", help="gắn nhãn (v1, v2…) và chép version thành snapshots/<version>/ để commit")
    fz.add_argument("version")
    fz.add_argument("label")
    return p


def main(argv: list[str] | None = None) -> int:
    load_env()
    a = build_parser().parse_args(argv)
    if getattr(a, "load", "missing") is None:
        a.load = os.environ.get("DAILY_LOAD", "")
    if any(t.strip() and t.strip() not in TARGETS for t in (getattr(a, "load", "") or "").split(",")):
        print(f"--load chỉ nhận: {', '.join(TARGETS)}", file=sys.stderr)
        return 2
    if a.cmd in ("run", "publish"):
        for k in ("no_crawl", "no_publish", "workers", "max_hours"):
            if not hasattr(a, k):
                setattr(a, k, None)
        return cmd_run(a)
    handlers = {"accept": cmd_accept, "versions": cmd_versions, "diff": cmd_diff, "switch": cmd_switch, "freeze": cmd_freeze}
    return handlers.get(a.cmd, cmd_status)(a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        structlog.emit("run.stopped", "[daily] Đã dừng theo yêu cầu.", "WARNING", flow="daily")
        sys.exit(130)
