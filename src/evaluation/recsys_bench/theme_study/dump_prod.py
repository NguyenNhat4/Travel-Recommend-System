"""Tải (chỉ đọc) cdp.products, cdp.events, catalog.combo_items của DB staging/production qua API GET của monitor crawler.
Không ghi gì lên production. Kết quả: <out>/<table>.jsonl"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", required=True, help="<monitor>/api/dbx/rows")
ap.add_argument("out")
ap.add_argument("tables", nargs="+")
a = ap.parse_args()
BASE = a.base_url
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
for table in a.tables:
    path = out / f"{table}.jsonl"
    off, total, t0 = 0, None, time.time()
    with path.open("w", encoding="utf-8") as f:
        while total is None or off < total:
            q = urllib.parse.urlencode({"table": table, "limit": 500, "offset": off})
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(f"{BASE}?{q}", timeout=120) as r:
                        data = json.load(r)
                    break
                except Exception as e:  # mạng chập chờn: thử lại
                    print(f"{table} offset {off}: {e}; thử lại", flush=True); time.sleep(3 * (attempt + 1))
            else:
                raise SystemExit(f"{table}: lỗi liên tiếp ở offset {off}")
            if data.get("error"):
                raise SystemExit(f"{table}: {data['error']}")
            total = data["total"]
            for row in data["rows"]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            off += len(data["rows"])
            if not data["rows"]:
                break
    print(f"{table}: {off}/{total} dòng, {time.time() - t0:.0f}s", flush=True)
