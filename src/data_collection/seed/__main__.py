"""Run the complete V-OTA catalog/history/Insider seed pipeline."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import gen_products, load_products, parse_combos, report, seed_histories, seed_insider
from .config import (
    CHANNEL_EVENTS_PER_PROFILE,
    DEFAULT_DATA_DIR,
    DEFAULT_INSIDER_URL,
    DEFAULT_SEED,
    DEFAULT_USERS,
    DEFAULT_VOTA_URL,
    INSIDER_TOKEN_DEFAULT,
    INSIDER_URL_ENV,
    MAX_EVENTS_PER_USER,
    VINPEARL_BOOST,
    VOTA_URL_ENV,
    PROFILES,
    ZIPF_S,
    find_products,
)
from .database import history_backup, history_restore, load_history, load_insider, load_vota, read_jsonl, upsert_catalog
from .snapshot import materialize_snapshot


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--users", type=int, default=DEFAULT_USERS)
    parser.add_argument("--products", type=Path, help="products.jsonl; default searches src/data_collection/data first")
    parser.add_argument("--reset", action="store_true", help="truncate local demo/seed state before loading")
    parser.add_argument("--generate-only", action="store_true", help="generate artifacts but do not connect to PostgreSQL")
    parser.add_argument("--catalog-only", action="store_true",
                        help="only upsert cdp.products and replace catalog.combo_items of the catalog's combos; never deletes, "
                             "never touches cdp.profiles/events, app.* or insider (for a database already in use, e.g. staging)")
    parser.add_argument("--real-flight-dates", action="store_true",
                        help="with --catalog-only: real crawl data (daily.py) — keep fixed-date flight quotes on their real date and "
                             "block expired quotes instead of shifting them into the demo window")
    parser.add_argument("--profile", choices=sorted(PROFILES), default=None,
                        help="bộ dữ liệu sinh khác demo (vd eval-v2: 5.000 khách, khách quay lại, bỏ giỏ — config.PROFILES)")
    parser.add_argument("--history-only", action="store_true",
                        help="chỉ thay lịch sử seed (cdp.profiles upsert, event sinh cũ của khách VP + 7 số, đơn seed P1) trên database đang "
                             "dùng; giữ event phát sinh qua web của tài khoản test / khách seed (persona P1–P4 reset về kịch bản), đơn thật, catalog, Insider, tài khoản / giỏ web; "
                             "tính lại hồ sơ khách có event được giữ; kiểm catalog đích")
    parser.add_argument("--keep-events-since", type=date.fromisoformat, default=None,
                        help="--history-only: giữ event của khách seed / persona từ ngày này (giờ VN) — event phát sinh qua web; mặc định "
                             "as_of của lần seed cũ, suy từ đơn seed P1")
    parser.add_argument("--drop-missing-products", action="store_true",
                        help="--history-only: bỏ event trỏ sản phẩm không có trong catalog đích (mặc định: dừng) và tính lại hồ sơ khách đó")
    parser.add_argument("--history-backup", type=Path, default=None,
                        help="--history-only: trước khi nạp, lưu phần sẽ bị thay ra file JSON (bắt buộc nên dùng trên staging)")
    parser.add_argument("--history-restore", type=Path, default=None,
                        help="khôi phục lịch sử seed từ file của --history-backup (ngay sau một lần nạp hỏng) rồi dừng")
    parser.add_argument("--retire-missing", action="store_true",
                        help="with --catalog-only: set available=false on database rows absent from this catalog (switching data version)")
    return parser.parse_args(argv)


def _set_partner_token(seed_dir: Path) -> None:
    path = seed_dir / "insider_partners.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if rows:
        rows[0]["request_token"] = os.environ.get("INSIDER_TOKEN", INSIDER_TOKEN_DEFAULT)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    products_path = find_products(args.products)
    if products_path is None:
        products_path = DEFAULT_DATA_DIR / "products.synthetic.jsonl"
        print(f"WARNING: no crawled products.jsonl found; generating {products_path}", file=sys.stderr)
        gen_products.write(products_path, gen_products.generate(args.as_of, args.seed))

    if products_path.name.endswith(".jsonl.gz"):
        products_path = materialize_snapshot(products_path)

    data_dir = products_path.parent
    if products_path.name != "products.jsonl":
        # The step scripts intentionally share a stable basename.  A generated
        # fallback is copied only inside the ignored data directory.
        canonical = DEFAULT_DATA_DIR / "products.jsonl"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_bytes(products_path.read_bytes())
        products_path, data_dir = canonical, canonical.parent

    loader_dir, seed_dir = data_dir / "loader", data_dir / "seed"
    if args.catalog_only:
        if args.reset:
            print("--catalog-only never truncates; drop --reset", file=sys.stderr)
            return 2
        print(f"[1/3] Parse {products_path}")
        parse_combos.main(["--data-dir", str(data_dir)])
        print("[2/3] Build cdp.products rows")
        load_products.main(["--data-dir", str(data_dir), "--out-dir", str(loader_dir), "--as-of", args.as_of.isoformat()]
                           + (["--real-flight-dates"] if args.real_flight_dates else []))
        if args.generate_only:
            print(f"Generated catalog artifacts under {loader_dir}; PostgreSQL was not changed.")
            return 0
        print(f"[3/3] Upsert catalog into ${VOTA_URL_ENV}")
        counts = upsert_catalog(os.environ.get(VOTA_URL_ENV, DEFAULT_VOTA_URL), data_dir, retire_missing=args.retire_missing)
        print("Catalog: " + " · ".join(f"{name}={count}" for name, count in counts.items()))
        return 0
    if args.history_restore:
        counts = history_restore(os.environ.get(VOTA_URL_ENV, DEFAULT_VOTA_URL), args.history_restore)
        print("Restore: " + " · ".join(f"{name}={count}" for name, count in counts.items()))
        return 0
    if args.history_only:
        if args.reset:
            print("--history-only never truncates; drop --reset", file=sys.stderr)
            return 2
        print(f"[1/2] Generate CDP history ({args.profile or 'demo'}) from {products_path}")
        hist_args = ["--data-dir", str(data_dir), "--out-dir", str(seed_dir), "--as-of", args.as_of.isoformat(), "--seed", str(args.seed)]
        if seed_histories.main(hist_args + (["--profile", args.profile] if args.profile else [])) != 0:
            return 1
        if args.generate_only:
            print(f"Generated history under {seed_dir}; PostgreSQL was not changed.")
            return 0
        print(f"[2/2] Replace seed-customer history in ${VOTA_URL_ENV} (catalog, Insider and web users untouched)")
        source_ids = {r["productId"] for r in read_jsonl(products_path)}
        if args.history_backup:
            saved = history_backup(os.environ.get(VOTA_URL_ENV, DEFAULT_VOTA_URL), args.history_backup)
            print(f"Backup → {args.history_backup}: " + " · ".join(f"{t}={n}" for t, n in saved.items()))
        counts = load_history(os.environ.get(VOTA_URL_ENV, DEFAULT_VOTA_URL), data_dir, source_ids, as_of=args.as_of,
                              keep_events_since=args.keep_events_since, drop_missing_products=args.drop_missing_products)
        print("History: " + " · ".join(f"{name}={count}" for name, count in counts.items()))
        print("Insider clone was not regenerated; run the full seed on a fresh database to rebuild it.")
        return 0
    print(f"[1/5] Parse {products_path}")
    parse_combos.main(["--data-dir", str(data_dir)])
    print("[2/5] Build cdp.products rows")
    load_products.main(["--data-dir", str(data_dir), "--out-dir", str(loader_dir), "--as-of", args.as_of.isoformat()])
    print("[3/5] Generate CDP history and app personas")
    size = ["--profile", args.profile] if args.profile else ["--profiles", str(args.users), "--max-events", str(MAX_EVENTS_PER_USER)]
    if seed_histories.main([
        "--data-dir", str(data_dir), "--out-dir", str(seed_dir), "--as-of", args.as_of.isoformat(),
        "--seed", str(args.seed), "--zipf", str(ZIPF_S), "--vinpearl-boost", str(VINPEARL_BOOST), *size,
    ]) != 0:
        return 1
    print("[4/5] Generate Insider clone rows")
    if seed_insider.main([
        "--seed-dir", str(seed_dir), "--out-dir", str(seed_dir), "--as-of", args.as_of.isoformat(),
        "--seed", str(args.seed), "--events-per-profile", str(CHANNEL_EVENTS_PER_PROFILE),
    ]) != 0:
        return 1
    _set_partner_token(seed_dir)

    if args.generate_only:
        print(f"Generated artifacts under {data_dir}; PostgreSQL was not changed.")
        return 0

    vota_url = os.environ.get(VOTA_URL_ENV, DEFAULT_VOTA_URL)
    insider_url = os.environ.get(INSIDER_URL_ENV, DEFAULT_INSIDER_URL)
    print("[5/5] Load V-OTA and Insider PostgreSQL transactions")
    counts = {**load_vota(vota_url, data_dir, args.reset), **load_insider(insider_url, data_dir, args.reset)}
    db_counts = report.collect(vota_url, insider_url)
    block = report.render(products_path, args.as_of, args.seed, db_counts)
    report.update_readme(Path(__file__).resolve().parents[1] / "README.md", block)
    print("Loaded: " + " · ".join(f"{table}={count}" for table, count in counts.items()))
    print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
