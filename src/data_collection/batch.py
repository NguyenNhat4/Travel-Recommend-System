#!/usr/bin/env python3
"""City/month jobs with stable sharding, isolated resumable state and shared pacing."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from collectors.booking_flights import flight_dates
from collectors.common import Paths, RunLock
from collectors.plan import DESTINATIONS, select_destinations
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SOURCES = ("booking-flights", "trip-flights", "booking-hotels", "agoda-hotels", "trip-attractions", "vinpearl",
           "booking-attractions")
# booking-flights chỉ chạy khi chọn thẳng (`batch.py run booking-flights`), không nằm trong mặc định: kiểm 19/09/2026,
# trình duyệt thường thấy 281 chuyến SGN-HAN ngày 15/10 nhưng phiên Playwright của crawler nhận kết quả rỗng
# ("Không có chuyến bay nào khớp"). Đây là phản hồi với phiên tự động; dự án không stealth/đổi fingerprint nên
# không có cách hợp lệ để lấy. Chuyến bay dùng dữ liệu có cấu trúc của trip.com.
OPT_IN_SOURCES = ("booking-flights",)
TAXONOMY_SOURCES = {"hotel": ("booking-hotels", "agoda-hotels"),
                    "flight": ("trip-flights",),
                    "attraction": ("trip-attractions", "vinpearl", "booking-attractions"),
                    "combo": ("vinpearl",), "golf": ("vinpearl",)}
CITY_SOURCES = ("vinpearl", "booking-hotels", "agoda-hotels", "trip-attractions", "trip-flights")
BOOKING_FLIGHTS_WARNING = ("CẢNH BÁO booking-flights: Booking trả kết quả rỗng cho phiên tự động (trình duyệt thường thấy "
                           "chuyến bay, Playwright thấy 0). Nguồn này chưa dùng được; xem ghi chú trong batch.py.")


def select_sources(source=None, taxonomy=None):
    if source and taxonomy:
        raise ValueError("Chỉ chọn một source hoặc --taxonomy; bỏ cả hai để cào mọi nguồn theo thành phố")
    return (source,) if source else TAXONOMY_SOURCES[taxonomy] if taxonomy else CITY_SOURCES


def month_values(months, year=None):
    if not months:
        return None
    values = []
    for value in months.split(","):
        value = value.strip()
        if value.isdigit():
            if year is None:
                raise ValueError("Tháng dạng 1,2 cần --year để tránh cào nhầm năm")
            value = f"{year:04d}-{int(value):02d}"
        date.fromisoformat(value + "-01")
        values.append(value)
    return ",".join(sorted(set(values)))


def job_id(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def plan_jobs(source, cities, months=None, dates=None, origins=None, per_destination=100, full_vinpearl=False):
    chosen = select_destinations(cities)
    if source == "booking-attractions":
        # Vé/tour/hoạt động: danh sách toàn quốc (~13.500 trang) lấy từ sitemap, không chia theo thành phố. Không nằm trong
        # mặc định của chế độ thành phố vì rất lớn: chạy `batch.py run booking-attractions --limit 800`, chạy lại để tiếp tục.
        return [{"source": source, "city": "all", "period": None, "args": []}], [
            "Booking attractions: một job toàn quốc từ sitemap; dùng --limit N để cào từng đợt, chạy lại để tiếp tục."]
    if source == "vinpearl":
        return [{"source": source, "city": "all", "period": None, "once": True,
                 "args": [] if full_vinpearl else ["--skip-hotels"]}], [
            "Vinpearl: discovery toàn nguồn một job dùng chung; phân về thành phố sau chuẩn hóa, giữ lịch nguồn cung cấp."]
    airports = sorted({a for d in DESTINATIONS for a in d.airports})
    origins = sorted(set(x.strip().upper() for x in origins.split(","))) if origins else airports
    if not set(origins) <= set(airports):
        raise ValueError("Sân bay đi chưa có trong collectors/plan.py")
    if source == "trip-flights" and (months or dates):
        raise ValueError("Trip là trang tham khảo tuyến; không hỗ trợ coverage từng ngày. Dùng booking-flights cho --months.")
    calendar_days = flight_dates(months, dates) if source in ("booking-flights", "booking-hotels", "agoda-hotels") else []
    if source == "trip-attractions" and (months or dates):
        raise ValueError("Trip attractions thu thập nội dung, không phải kiểm tra vé từng ngày")
    specs, skipped = [], []
    if source == "booking-hotels":
        # Khách sạn thương hiệu Vinpearl trên Booking là dữ liệu toàn quốc: một job dùng chung thay vì lặp ở mỗi thành phố.
        for day in calendar_days or [None]:
            args = ["--brand-only"] + (["--checkin", str(day), "--nights", "1", "--adults", "2"] if day else [])
            specs.append({"source": source, "city": "all", "period": str(day) if day else None, "once": True, "args": args})
    for city in chosen:
        if source.endswith("flights"):
            if not city.airports:
                skipped.append(city.name + ": chưa cấu hình sân bay đến; không tự gán sân bay lân cận")
                continue
            for target in city.airports:
                routes = [f"{origin}-{target}" for origin in origins if origin != target]
                if not routes:
                    continue
                # Một job = mọi tuyến tới một sân bay đến (mỗi tháng một job): một trình duyệt / một lượt tải trang sân bay
                # cho cả nhóm thay vì mỗi tuyến một tiến trình.
                groups = sorted({d.strftime("%Y-%m") for d in calendar_days}) or [None]
                for month in groups:
                    selected = [str(d) for d in calendar_days if d.strftime("%Y-%m") == month]
                    args = ["--routes", ",".join(routes)]
                    if selected:
                        args += ["--depart-dates", ",".join(selected)]
                    specs.append({"source": source, "city": city.name, "route": ",".join(routes),
                                  "period": month, "args": args})
        else:
            missing = {"agoda-hotels": ("agoda_city", "slug Agoda"), "trip-attractions": ("trip_city", "ID Trip")}.get(source)
            if missing and not getattr(city, missing[0]):
                # Không tạo job rỗng (Agoda còn mở cả cửa sổ trình duyệt rồi đóng ngay); không tự đoán ID.
                skipped.append(f"{city.name}: chưa có {missing[1]} đã kiểm chứng cho {source}")
                continue
            for day in calendar_days or [None]:
                args = ["--destinations", city.name, "--per-destination", str(per_destination)]
                if source == "booking-hotels":
                    args.append("--no-brand-sitemap")
                if day:
                    args += ["--checkin", str(day), "--nights", "1", "--adults", "2"]
                specs.append({"source": source, "city": city.name, "period": str(day) if day else None, "args": args})
    return specs, skipped


def job_finished(folder):
    """Lần chạy gần nhất của job kết thúc bình thường (mã thoát 0)."""
    try:
        return json.loads((folder / "last-run.json").read_text(encoding="utf-8")).get("exitCode") == 0
    except (OSError, ValueError):
        return False


def shard_jobs(specs, worker):
    index, total = map(int, worker.split("/"))
    if not 1 <= index <= total:
        raise ValueError("worker phải có dạng 1/3, 2/3, 3/3")
    return [s for s in specs if int(job_id(s), 16) % total == index - 1]


def merge_interim(job_dirs, destination):
    """Idempotent atomic import. Keep raw evidence in original job directories."""
    paths = Paths(destination).ensure()
    imported = 0
    with RunLock(paths, "batch_merge"):
        by_source = {}
        for job in job_dirs:
            # Never read a JSONL while its collector is appending to it.
            manifest = json.loads((job / "job.json").read_text()) if (job / "job.json").exists() else None
            sources = [manifest["source"].replace("-", "_")] if manifest else [p.stem for p in (job / "interim").glob("*.jsonl")]
            for source in sources:
                with RunLock(Paths(job).ensure(), source):
                    file = job / "interim" / f"{source}.jsonl"
                    if not file.exists():
                        continue
                    # split("\n"), không phải splitlines(): splitlines() cắt cả ở U+0085/U+2028 nằm trong chuỗi JSON hợp lệ
                    for line in file.read_text(encoding="utf-8").split("\n"):
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        record["rawArchive"] = str((job / "raw").resolve())
                        by_source.setdefault(source, []).append(record)
        for source, records in by_source.items():
            with RunLock(paths, source):
                target = paths.interim / f"{source}.jsonl"
                lines = [x for x in target.read_text(encoding="utf-8").split("\n") if x.strip()] if target.exists() else []
                seen = {json.dumps(json.loads(line), sort_keys=True, ensure_ascii=False) for line in lines if line.strip()}
                new = []
                for record in records:
                    canonical = json.dumps(record, sort_keys=True, ensure_ascii=False)
                    if canonical not in seen:
                        seen.add(canonical)
                        new.append(canonical)
                if new:
                    tmp = target.with_suffix(".merge.tmp")
                    tmp.write_text("\n".join(lines + new) + "\n", encoding="utf-8")
                    tmp.replace(target)
                    imported += len(new)
    return imported


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("source", choices=SOURCES, nargs="?")
    run.add_argument("--taxonomy", choices=tuple(TAXONOMY_SOURCES))
    run.add_argument("--cities", help="một hoặc nhiều thành phố, phân cách dấu phẩy; mặc định 15")
    run.add_argument("--months", help="YYYY-MM,YYYY-MM; mỗi ngày còn ở tương lai")
    run.add_argument("--year", type=int, help="dùng với --months 1,2,3")
    run.add_argument("--dates", help="YYYY-MM-DD,YYYY-MM-DD")
    run.add_argument("--origins", help="sân bay đi, vd. SGN,HAN; mặc định mọi sân bay đã cấu hình")
    run.add_argument("--worker", default="1/1")
    run.add_argument("--per-destination", type=int, default=100)
    run.add_argument("--dry-run", action="store_true", help="in kế hoạch, không truy cập mạng")
    run.add_argument("--limit", type=int, help="giới hạn URL mỗi job, để chạy thử")
    run.add_argument("--headless", action="store_true")
    run.add_argument("--fast", action="store_true", help="booking-hotels: không chờ trang tải xong, chặn CSS/tracker (nhanh gấp đôi)")
    run.add_argument("--concurrency", type=int, help="số tab song song cho booking/agoda (vẫn chung nhịp --delay theo host)")
    run.add_argument("--delay", type=float, default=4)
    run.add_argument("--refresh", action="store_true", help="chỉ flight: lấy snapshot mới")
    run.add_argument("--again", action="store_true", help="chạy lại cả job dùng chung một lần (Vinpearl, khách sạn thương hiệu Vinpearl) đã xong")
    merge = sub.add_parser("merge")
    merge.add_argument("--into", type=Path, default=ROOT / "data")
    merge.add_argument("--input", type=Path, action="append", help="thư mục crawl bổ sung, có thể lặp")
    for p in (run, merge):
        p.add_argument("--root", type=Path, default=ROOT / "data/batches")
    args = parser.parse_args(argv)
    if args.command == "merge":
        jobs = sorted(p.parent for p in args.root.glob("*/job.json")) + (args.input or [])
        print(f"Imported {merge_interim(jobs, args.into.resolve())} new observations; raw stays in job directories.")
        return 0
    try:
        if args.delay < 1 or args.per_destination < 1 or (args.limit is not None and args.limit < 1):
            raise ValueError("delay >= 1, per-destination và limit > 0")
        sources = select_sources(args.source, args.taxonomy)
        if any(s in OPT_IN_SOURCES for s in sources):
            print(BOOKING_FLIGHTS_WARNING, flush=True)
        city_mode = not args.source and not args.taxonomy
        multi_source = not args.source
        if args.refresh and any(not s.endswith("flights") for s in sources):
            raise ValueError("--refresh chỉ hỗ trợ flight; đổi ngày hotel tạo job mới")
        months = month_values(args.months, args.year)
        # Keep the same default query date when resuming after midnight.
        if not months and not args.dates and any(s in ("booking-flights", "booking-hotels", "agoda-hotels") for s in sources):
            anchor = args.root.resolve() / "query-day.txt"
            default_day = str(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date() + timedelta(days=30))
            if args.dry_run:
                args.dates = anchor.read_text().strip() if anchor.exists() else default_day
            else:
                with RunLock(Paths(args.root.resolve()).ensure(), "batch_query_date"):
                    if not anchor.exists():
                        anchor.write_text(default_day + "\n", encoding="utf-8")
                    args.dates = anchor.read_text().strip()
        specs, skipped = [], []
        for source in sources:
            reference_only = source in ("trip-flights", "trip-attractions", "vinpearl")
            if reference_only and (months or args.dates) and multi_source:
                skipped.append(source + ": thu thập tham khảo một lần, không giả lập coverage từng ngày")
            items, notes = plan_jobs(source, args.cities,
                                     None if multi_source and reference_only else months,
                                     None if multi_source and reference_only else args.dates,
                                     args.origins, args.per_destination, full_vinpearl=city_mode)
            specs.extend(items)
            skipped.extend(notes)
        if city_mode:
            order = {d.name: i for i, d in enumerate(select_destinations(args.cities))}
            specs.sort(key=lambda s: (order.get(s["city"], -1), CITY_SOURCES.index(s["source"]), s.get("route", ""), s.get("period") or ""))
        jobs = shard_jobs(specs, args.worker)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    root = args.root.resolve()
    env = dict(os.environ, CRAWL_RATE_DB=str(root / "rate.sqlite3"), CRAWL_SHARED_CACHE=str(root / "shared"))
    print(f"Worker {args.worker}: {len(jobs)}/{len(specs)} jobs; cities are destinations. Shared rate: {root / 'rate.sqlite3'}", flush=True)
    for message in skipped:
        print("SKIP " + message, flush=True)
    failures = 0
    blocked_sources = set()
    for spec in jobs:
        if spec["source"] in blocked_sources:
            print(f"SKIP blocked source {spec['source']}: {spec['city']}", flush=True)
            continue
        folder = root / job_id(spec)
        if spec.get("once") and not args.again and job_finished(folder):
            print(f"SKIP job dùng chung đã xong: {spec['source']} {spec['city']} (--again để chạy lại)", flush=True)
            continue
        cmd = [sys.executable, str(ROOT / "crawl.py"), "--data-dir", str(folder), spec["source"], *spec["args"], "--delay", str(args.delay)]
        if args.limit:
            cmd += ["--tour-limit" if spec["source"] == "vinpearl" else "--limit", str(args.limit)]
        if args.headless:
            cmd += ["--headless"]
        if args.fast and spec["source"] in ("booking-hotels", "booking-attractions"):
            cmd += ["--fast"]  # agoda tự tắt --fast; các nguồn khác không có tuỳ chọn này
        if args.concurrency and spec["source"] in ("booking-hotels", "agoda-hotels", "booking-attractions"):
            cmd += ["--concurrency", str(args.concurrency)]
        if args.refresh:
            cmd += ["--refresh"]
        print(shlex.join(cmd), flush=True)
        if args.dry_run:
            continue
        paths = Paths(folder).ensure()
        try:
            with RunLock(paths, "batch_job"):
                (folder / "job.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                code = subprocess.call(cmd, env=env)
                (folder / "last-run.json").write_text(json.dumps({"exitCode": code}), encoding="utf-8")
        except SystemExit as exc:
            print(f"SKIP busy job {folder.name}: {exc}", flush=True)
            failures += 1
            continue
        if code:
            failures += 1
        if code == 75:
            blocked_sources.add(spec["source"])
            print(f"Source blocked: stop further {spec['source']} jobs in this worker; other sources may continue.", flush=True)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
