"""Versioned, transactional append of synthetic histories; never replaces existing users."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from . import config as C
from .database import EVENT, PROFILE, copy_rows
from .seed_histories import generate


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def build(catalog, *, batch, as_of, seed=42):
    if not re.fullmatch(r"[a-z0-9-]{1,48}", batch):
        raise ValueError("batch: 1–48 lowercase letters, digits or hyphens")
    prefix = f"VPX:{batch}:"
    result = generate(catalog, as_of, seed=seed, profile="append-v1")
    personas = {p[0] for p in C.PERSONAS}
    profiles = [dict(p, cdp_user_id=prefix + p["cdp_user_id"]) for p in result["profiles"] if p["cdp_user_id"] not in personas]
    events = []
    for e in result["events"]:
        if e["cdp_user_id"] in personas:
            continue
        e = dict(e)
        e.pop("event_id")
        e["cdp_user_id"] = prefix + e["cdp_user_id"]
        if e["event_group_id"]:
            e["event_group_id"] = prefix + e["event_group_id"]
        events.append(e)
    payload = dict(format=1, synthetic=True, batch=batch, prefix=prefix, as_of=as_of.isoformat(), seed=seed,
                   catalog_sha256=digest(catalog), profiles=profiles, events=events)
    return dict(payload=payload, sha256=digest(payload))


def validate(artifact):
    p = artifact["payload"]
    if digest(p) != artifact["sha256"]:
        raise ValueError("artifact checksum mismatch")
    if p["format"] != 1 or p["synthetic"] is not True or not re.fullmatch(r"[a-z0-9-]{1,48}", p["batch"]):
        raise ValueError("invalid batch metadata")
    prefix = f"VPX:{p['batch']}:"
    ids = [r["cdp_user_id"] for r in p["profiles"]]
    if p["prefix"] != prefix or not ids or len(set(ids)) != len(ids) or any(not i.startswith(prefix) for i in ids):
        raise ValueError("invalid profile namespace")
    users = set(ids)
    if any(e["cdp_user_id"] not in users or (e["event_group_id"] and not e["event_group_id"].startswith(prefix)) for e in p["events"]):
        raise ValueError("event outside batch")
    return p


def apply(conn, artifact):
    """Caller owns transaction. Raises on any collision; all-or-nothing, including validation."""
    p = validate(artifact)
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (p["prefix"],))
    conn.execute("CREATE TEMP TABLE append_profiles (LIKE cdp.profiles) ON COMMIT DROP")
    conn.execute("CREATE TEMP TABLE append_events (LIKE cdp.events) ON COMMIT DROP")
    conn.execute("ALTER TABLE append_events DROP COLUMN event_id")
    ec = [c for c in EVENT if c != "event_id"]
    copy_rows(conn, "append_profiles", PROFILE, p["profiles"])
    copy_rows(conn, "append_events", ec, p["events"])
    # Lock references before checking absence, preventing deletion before commit.
    conn.execute("SELECT p.product_id FROM cdp.products p WHERE p.product_id IN (SELECT product_id FROM append_events) FOR KEY SHARE").fetchall()
    missing = conn.execute("SELECT count(*) FROM append_events e LEFT JOIN cdp.products p USING(product_id) WHERE e.product_id IS NOT NULL AND p.product_id IS NULL").fetchone()[0]
    if missing:
        raise ValueError(f"{missing} events reference missing products; nothing appended")
    existing = conn.execute("SELECT count(*) FROM cdp.profiles WHERE starts_with(cdp_user_id, %s)", (p["prefix"],)).fetchone()[0]
    if existing:
        for table, cols in (("profiles", PROFILE), ("events", ec)):
            columns = ','.join('"' + c + '"' for c in cols)
            different = conn.execute(f"""SELECT EXISTS (
                (SELECT {columns} FROM cdp.{table} WHERE starts_with(cdp_user_id, %s) EXCEPT ALL SELECT {columns} FROM append_{table})
                UNION ALL
                (SELECT {columns} FROM append_{table} EXCEPT ALL SELECT {columns} FROM cdp.{table} WHERE starts_with(cdp_user_id, %s)))""", (p["prefix"], p["prefix"])).fetchone()[0]
            if different:
                raise ValueError(f"batch collision or changed persisted {table}; nothing appended")
        status = "already_applied"
    else:
        collision = conn.execute("SELECT EXISTS(SELECT 1 FROM cdp.events WHERE event_group_id IN (SELECT event_group_id FROM append_events))").fetchone()[0]
        if collision:
            raise ValueError("event group collision")
        for table, cols in (("profiles", PROFILE), ("events", ec)):
            columns = ','.join('"' + c + '"' for c in cols)
            conn.execute(f"INSERT INTO cdp.{table} ({columns}) SELECT {columns} FROM append_{table}")
        status = "inserted"
    event_ids = [r[0] for r in conn.execute("SELECT event_id FROM cdp.events WHERE starts_with(cdp_user_id, %s) ORDER BY event_id", (p["prefix"],))]
    return dict(status=status, batch=p["batch"], artifact_sha256=artifact["sha256"], profiles=len(p["profiles"]),
                events=len(event_ids), profile_ids=[r["cdp_user_id"] for r in p["profiles"]], event_ids=event_ids)


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--batch", required=True)
    prepare.add_argument("--as-of", type=date.fromisoformat, required=True)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--out", type=Path, required=True)
    load = sub.add_parser("apply")
    load.add_argument("--artifact", type=Path, required=True)
    load.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ["SEED_DATABASE_URL"]
    if args.command == "prepare":
        args.out.mkdir(parents=True, exist_ok=False)
        with psycopg.connect(url, connect_timeout=8, row_factory=dict_row, options="-c default_transaction_read_only=on -c statement_timeout=30000") as conn:
            with conn.cursor(name="append_catalog") as cursor:
                cursor.execute("SELECT * FROM cdp.products ORDER BY product_id")
                cursor.itersize = 250
                rows = list(cursor)
        names = dict(product_id="productId", unit_price="unitPrice", available_from="availableFrom", available_to="availableTo", image_url="imageUrl", source_ref="sourceRef")
        catalog = [{names.get(k, k): v for k, v in r.items()} for r in rows]
        catalog = json.loads(encoded(catalog))
        # Decimal numeric prices are encoded as strings by default=str.
        for r in catalog:
            if r["unitPrice"] is not None:
                r["unitPrice"] = float(r["unitPrice"])
        artifact = build(catalog, batch=args.batch, as_of=args.as_of, seed=args.seed)
        (args.out / "catalog.json").write_bytes(encoded(catalog))
        (args.out / "batch.json").write_bytes(encoded(artifact))
        print(json.dumps(dict(batch=args.batch, sha256=artifact["sha256"], profiles=len(artifact["payload"]["profiles"]), events=len(artifact["payload"]["events"]))))
    else:
        raw = args.artifact.read_bytes()
        artifact = json.loads(gzip.decompress(raw) if args.artifact.suffix == ".gz" else raw)
        # Reserve receipt before DB commit; an interrupted write can be recovered by idempotent rerun to a new receipt.
        with args.receipt.open("x") as output:
            with psycopg.connect(url, connect_timeout=10, options="-c lock_timeout=10000 -c statement_timeout=120000") as conn:
                receipt = apply(conn, artifact)
            output.write(json.dumps(receipt, indent=2))
        print(json.dumps({k: v for k, v in receipt.items() if not k.endswith("_ids")}))


if __name__ == "__main__":
    main()
