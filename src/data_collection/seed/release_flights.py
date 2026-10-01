"""Insert bundled, observed flight fares into an existing VM catalog (never reset)."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

from .database import PRODUCT, copy_rows, read_jsonl
from .load_products import convert
from .snapshot import materialize_snapshot

BUNDLE = Path(__file__).resolve().parents[1] / "snapshots/2026-09-30-business/products.jsonl.gz"


def load_bundle(path: Path = BUNDLE) -> list[dict]:
    """Check both catalog and evidence before connecting to any database."""
    manifest = json.loads(path.with_name("manifest.json").read_text())
    entry = manifest["evidence"]
    evidence_bytes = path.with_name(entry["file"]).read_bytes()
    if hashlib.sha256(evidence_bytes).hexdigest() != entry["gzipSha256"]:
        raise ValueError("flight evidence checksum mismatch")
    evidence = json.loads(gzip.decompress(evidence_bytes))
    with tempfile.TemporaryDirectory(prefix="vota-release-flights-") as scratch:
        rows = read_jsonl(materialize_snapshot(path, Path(scratch)))
    if len(evidence) != entry["rows"] or len(rows) != len(evidence):
        raise ValueError("flight evidence count mismatch")
    if len({r["productId"] for r in rows}) != len(rows):
        raise ValueError("duplicate flight productId")
    by_url = {q["url"]: q for q in evidence}
    for row in rows:
        attrs = row["attributes"]
        proof = by_url.get(attrs.get("url"), {})
        if (row["taxonomy"] != "flight" or attrs.get("level") != "flight"
                or attrs.get("cabinClass") != "BUSINESS" or not attrs.get("fixedDepartureDate")
                or not attrs.get("parentProductId") or row["currency"] != "VND"
                or not isinstance(row["unitPrice"], int) or row["unitPrice"] <= 0
                or proof.get("price") != row["unitPrice"]
                or not proof.get("cabin", "").startswith("Thương Gia")
                or proof.get("observedAt") != attrs.get("priceObservedAt")
                or attrs.get("flightNumber", "MISSING") not in proof.get("flight", "")):
            raise ValueError("flight has missing or inconsistent source evidence")
        if row["availableFrom"] != attrs["departureAt"][:10] or row["availableTo"] != row["availableFrom"]:
            raise ValueError("flight availability must equal its observed departure date")
        if datetime.fromisoformat(attrs["arrivalAt"]) <= datetime.fromisoformat(attrs["departureAt"]):
            raise ValueError("invalid flight times")
    return rows


def import_flights(url: str, rows: list[dict], as_of: date) -> dict[str, int]:
    """Atomic, insert-only import; a replay cannot overwrite any newer live quote."""
    converted, _ = convert(rows, {}, as_of, real_flight_dates=True)
    parents = sorted({r["attributes"]["parentProductId"] for r in converted})
    with psycopg.connect(url, connect_timeout=15) as conn:
        conn.execute("SET LOCAL lock_timeout = '15s'")
        conn.execute("SET LOCAL statement_timeout = '60s'")
        # Serialize with the live catalog writer, without touching app/history tables.
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")
        found = conn.execute("""
            SELECT product_id::text FROM cdp.products
            WHERE product_id = ANY(%s::uuid[]) AND taxonomy = 'flight'
              AND attributes->>'level' = 'route' FOR KEY SHARE
        """, (parents,)).fetchall()
        if {r[0] for r in found} != set(parents):
            raise ValueError("release flights require their existing parent routes; import aborted")
        conn.execute("CREATE TEMP TABLE release_flights (LIKE cdp.products INCLUDING DEFAULTS) ON COMMIT DROP")
        copy_rows(conn, "release_flights", PRODUCT, converted)
        columns = ", ".join(PRODUCT)
        inserted = conn.execute(f"""
            INSERT INTO cdp.products ({columns}) SELECT {columns} FROM release_flights
            ON CONFLICT (product_id) DO NOTHING RETURNING product_id
        """).fetchall()
    return {"bundleRows": len(rows), "inserted": len(inserted),
            "existingKept": len(rows) - len(inserted),
            "bundleAvailableInWindow": sum(r["available"] for r in converted)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date())
    parser.add_argument("--env-file", type=Path, help="Read only CLOUD_SEED_DATABASE_URL from an ignored local file")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    rows = load_bundle()
    if args.validate_only:
        print(json.dumps({"validated": len(rows), "routes": len({r['attributes']['parentProductId'] for r in rows})}))
        return 0
    url = os.environ.get("CLOUD_SEED_DATABASE_URL", "")
    if args.env_file:
        for line in args.env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "CLOUD_SEED_DATABASE_URL":
                url = value.strip().strip("\"'")
    if not url:
        parser.error("CLOUD_SEED_DATABASE_URL is required; no local database fallback")
    try:
        result = import_flights(url, rows, args.as_of)
    except psycopg.Error as exc:
        # Connection exceptions can contain connection details; never print a DSN.
        raise SystemExit(f"Flight import failed: {type(exc).__name__}; SQLSTATE={exc.sqlstate or 'connection'}") from None
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
