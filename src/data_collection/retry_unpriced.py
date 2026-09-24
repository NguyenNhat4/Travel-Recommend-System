#!/usr/bin/env python3
"""Thử lại ngày khác cho khách sạn Booking/Agoda chưa có giá trong các job batch.

Khách sạn không có giá ở ngày đã hỏi (hết phòng hoặc nguồn không trả giá) không bị loại: cào lại đúng những URL đó
với ngày nhận phòng lệch +14 rồi +45 ngày so với ngày gốc của job. Ngày thật của mỗi giá nằm trong `priceQuery`
của bản ghi (và `attributes.priceQuery` sau chuẩn hoá); không so sánh giá xuyên ngày. Vẫn không có giá thì giữ
`available=false`.

  python retry_unpriced.py                    # xem kế hoạch (không truy cập mạng)
  python retry_unpriced.py --run              # chạy +14 ngày, rồi +45 ngày cho phần vẫn chưa có giá
  python retry_unpriced.py --run --offsets 7  # chỉ một lượt +7 ngày

Chạy khi các terminal cào khách sạn đã xong (mỗi job chỉ một tiến trình). Kết quả ghi vào job mới trong
data/batches/ như mọi job khác, dùng chung nhịp truy cập theo host; tiếp tục bằng `batch.py merge` và `normalise.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import batch
from collectors.common import Paths, RunLock

ROOT = Path(__file__).resolve().parent
PRICED = {"booking-hotels": "booking_hotels", "agoda-hotels": "agoda_hotels"}


def job_dirs(root: Path) -> list[tuple[Path, dict]]:
    out = []
    for manifest in sorted(root.glob("*/job.json")):
        try:
            out.append((manifest.parent, json.loads(manifest.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def arg_after(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


def has_price(record: dict) -> bool:
    price = record.get("minPrice")
    return isinstance(price, (int, float)) and price > 0


def latest_records(root: Path) -> dict[tuple[str, str], tuple[dict, dict]]:
    """(nguồn, key) → (bản ghi mới nhất, spec của job đã cào nó), trên mọi job batch."""
    latest: dict[tuple[str, str], tuple[dict, dict]] = {}
    for folder, spec in job_dirs(root):
        source = spec.get("source")
        if source not in PRICED:
            continue
        path = folder / "interim" / f"{PRICED[source]}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").split("\n"):  # không dùng splitlines(): cắt cả ở U+0085/U+2028
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # dòng cuối đang được ghi dở
            key = rec.get("key")
            if not key or rec.get("recordType") is None:
                continue
            k = (source, key)
            if k not in latest or (rec.get("crawledAt") or "") >= (latest[k][0].get("crawledAt") or ""):
                latest[k] = (rec, spec)
    return latest


def find_unpriced(root: Path) -> dict[tuple, dict]:
    """(nguồn, thành phố, tham số job) → {"urls": [...], "baseDate": ngày gốc, "spec": spec gốc}. Chỉ URL chưa có giá."""
    groups: dict[tuple, dict] = {}
    for (source, _key), (rec, spec) in latest_records(root).items():
        if has_price(rec) or not rec.get("url"):
            continue
        args = spec.get("args") or []
        base = arg_after(args, "--checkin") or ((rec.get("priceQuery") or {}).get("checkin"))
        if not base:
            continue
        g = groups.setdefault((source, spec.get("city"), tuple(args)), {"urls": [], "baseDate": base, "spec": spec})
        g["urls"].append(rec["url"])
    return groups


def retry_spec(group: dict, source: str, offset: int) -> dict:
    """Job thử lại: cùng tham số tìm URL như job gốc, đổi ngày nhận phòng, chỉ cào các URL chưa có giá (--match)."""
    spec = group["spec"]
    day = date.fromisoformat(group["baseDate"]) + timedelta(days=offset)
    args = list(spec.get("args") or [])
    for flag in ("--checkin", "--nights", "--adults"):
        if flag in args:
            i = args.index(flag)
            del args[i:i + 2]
    rx = "|".join(re.escape(u) for u in sorted(set(group["urls"])))
    args += ["--checkin", str(day), "--nights", "1", "--adults", "2", "--match", rx]
    return {"source": source, "city": spec.get("city"), "period": f"retry {day}", "retryOffsetDays": offset,
            "retryOf": group["baseDate"], "args": args}


def plan_pass(root: Path, offset: int) -> list[dict]:
    return [retry_spec(g, source, offset) for (source, _city, _args), g in sorted(find_unpriced(root).items(), key=lambda x: x[0][:2])]


def run_specs(root: Path, specs: list[dict], delay: float, fast: bool) -> int:
    env = dict(os.environ, CRAWL_RATE_DB=str(root / "rate.sqlite3"), CRAWL_SHARED_CACHE=str(root / "shared"))
    failures = 0
    for spec in specs:
        folder = root / batch.job_id(spec)
        cmd = [sys.executable, str(ROOT / "crawl.py"), "--data-dir", str(folder), spec["source"], *spec["args"], "--delay", str(delay)]
        if fast and spec["source"] == "booking-hotels":
            cmd.append("--fast")
        paths = Paths(folder).ensure()
        try:
            with RunLock(paths, "batch_job"):
                (folder / "job.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"→ {spec['source']} {spec['city']} {spec['period']} ({spec['args'].count('|') + 1} URL)", flush=True)
                code = subprocess.call(cmd, env=env)
                (folder / "last-run.json").write_text(json.dumps({"exitCode": code}), encoding="utf-8")
        except SystemExit as exc:
            print(f"BỎ QUA job đang bận {folder.name}: {exc}", flush=True)
            failures += 1
            continue
        failures += bool(code)
        if code == 75:
            print("Bị chặn: dừng, nghỉ vài giờ rồi chạy lại.", flush=True)
            return 75
    return 2 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT / "data/batches")
    ap.add_argument("--offsets", default="14,45", help="số ngày lệch so với ngày gốc, mỗi lượt chỉ thử URL còn chưa có giá")
    ap.add_argument("--run", action="store_true", help="chạy thật (mặc định chỉ in kế hoạch)")
    ap.add_argument("--delay", type=float, default=4)
    ap.add_argument("--fast", action="store_true", help="booking-hotels: chặn CSS/tracker")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    offsets = [int(x) for x in a.offsets.split(",") if x.strip()]
    code = 0
    for n, offset in enumerate(offsets, 1):
        specs = plan_pass(root, offset)
        total = sum(s["args"][s["args"].index("--match") + 1].count("|") + 1 for s in specs)
        print(f"Lượt {n}/{len(offsets)} (+{offset} ngày): {total} khách sạn chưa có giá trong {len(specs)} job", flush=True)
        for s in specs:
            print(f"  {s['source']:15s} {str(s['city']):16s} {s['period']}", flush=True)
        if not a.run or not specs:
            if not a.run:
                print("(xem trước: thêm --run để chạy; lượt sau được tính lại từ kết quả lượt trước)")
                break
            continue
        code = run_specs(root, specs, a.delay, a.fast) or code
        if code == 75:
            break
    return code


if __name__ == "__main__":
    raise SystemExit(main())
