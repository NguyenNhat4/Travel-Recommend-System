"""Làm nóng cache vector truy vấn của một backend **đang chạy** qua HTTP.

Cache nằm trong tiến trình backend (LRU, `application/search/query_cache.py`) nên tiến trình khác không ghi thẳng được;
job này gọi `GET /api/v1/search?q=…&limit=1` từng câu (không cần đăng nhập, đi qua BFF được) và đếm `diagnostics.embedCache`
hit / miss. Chạy lần hai cùng danh sách phải ra `miss 0`. Dùng khi backend khởi động với `SEARCH_PREWARM=false`, hoặc
để kiểm prewarm lúc khởi động đã xong.

    python -m src.backend.jobs.prewarm_query_cache --base-url https://v-ota.duckdns.org [--file data/search_prewarm_queries.txt] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from src.backend.app.application.search.prewarm import read_query_file

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FILE = BACKEND_DIR / "data" / "search_prewarm_queries.txt"
SEARCH_PATH = "/api/v1/search"


def warm(base_url: str, queries: list[str], *, limit: int = 1, timeout_seconds: float = 30.0, client: httpx.Client | None = None,
         progress: Callable[[str, str | None], None] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    own = client is None
    client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
    counts = {"hit": 0, "miss": 0, "noCache": 0}
    errors: list[dict[str, str]] = []
    try:
        for q in queries:
            try:
                r = client.get(base_url.rstrip("/") + SEARCH_PATH, params={"q": q, "limit": limit})
                if r.status_code != 200:
                    errors.append({"query": q, "error": f"HTTP {r.status_code}"})
                    continue
                status = ((r.json().get("diagnostics") or {}).get("embedCache")) or "noCache"
            except Exception as exc:  # noqa: BLE001 — timeout, DNS: ghi lỗi, đi tiếp
                errors.append({"query": q, "error": f"{type(exc).__name__}: {exc}"})
                continue
            counts[status if status in counts else "noCache"] += 1
            if progress is not None:
                progress(q, status)
    finally:
        if own:
            client.close()
    return {"queries": len(queries), **counts, "errors": len(errors), "errorSamples": errors[:5],
            "seconds": round(time.monotonic() - started, 1)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="gốc URL backend hoặc BFF, vd https://v-ota.duckdns.org")
    parser.add_argument("--file", default=str(DEFAULT_FILE), help="mỗi dòng một câu; '#' là chú thích")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm câu, không gọi HTTP")
    args = parser.parse_args(argv)
    queries = list(dict.fromkeys(read_query_file(args.file)))
    if args.dry_run:
        print(json.dumps({"queries": len(queries), "file": args.file, "dryRun": True}, ensure_ascii=False, indent=2))
        return 0
    report = warm(args.base_url, queries, limit=args.limit, timeout_seconds=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if queries and report["errors"] == len(queries) else 0


if __name__ == "__main__":
    sys.exit(main())
