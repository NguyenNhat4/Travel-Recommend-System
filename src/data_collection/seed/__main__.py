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
    ZIPF_S,
    find_products,
)
from .database import load_insider, load_vota
from .snapshot import materialize_snapshot


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--users", type=int, default=DEFAULT_USERS)
    parser.add_argument("--products", type=Path, help="products.jsonl; default searches src/data_collection/data first")
    parser.add_argument("--reset", action="store_true", help="truncate local demo/seed state before loading")
    parser.add_argument("--generate-only", action="store_true", help="generate artifacts but do not connect to PostgreSQL")
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
    print(f"[1/5] Parse {products_path}")
    parse_combos.main(["--data-dir", str(data_dir)])
    print("[2/5] Build cdp.products rows")
    load_products.main(["--data-dir", str(data_dir), "--out-dir", str(loader_dir), "--as-of", args.as_of.isoformat()])
    print("[3/5] Generate CDP history and app personas")
    if seed_histories.main([
        "--data-dir", str(data_dir), "--out-dir", str(seed_dir), "--as-of", args.as_of.isoformat(),
        "--seed", str(args.seed), "--profiles", str(args.users), "--zipf", str(ZIPF_S),
        "--vinpearl-boost", str(VINPEARL_BOOST), "--max-events", str(MAX_EVENTS_PER_USER),
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
