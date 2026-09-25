"""Validate and materialize a versioned catalog snapshot into ignored runtime data."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from .config import DEFAULT_DATA_DIR

BUFFER_SIZE = 1024 * 1024
SNAPSHOT_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(BUFFER_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(entry: object, key: str) -> dict:
    if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
        raise ValueError(f"snapshot manifest requires {key}.file")
    if not isinstance(entry.get("sha256"), str) or not isinstance(entry.get("rows"), int):
        raise ValueError(f"snapshot manifest requires {key}.sha256 and {key}.rows")
    return entry


def _count_rows(path: Path) -> int:
    with path.open("rb") as stream:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""))


def _validate_file(path: Path, entry: dict, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"snapshot {label} is missing: {path.name}")
    actual_hash = _sha256(path)
    if actual_hash != entry["sha256"]:
        raise ValueError(f"snapshot {label} checksum mismatch: {actual_hash}")
    actual_rows = _count_rows(path)
    if actual_rows != entry["rows"]:
        raise ValueError(f"snapshot {label} row count mismatch: {actual_rows}")


def materialize_snapshot(snapshot_path: Path, runtime_root: Path = DEFAULT_DATA_DIR) -> Path:
    """Verify a ``products.jsonl.gz`` bundle and return its runtime JSONL path.

    The tracked archive is never modified. Its content is expanded under the
    ignored ``data/snapshots/<snapshotId>`` directory alongside the reviewed
    combo mapping required to reproduce ``catalog.combo_items``.
    """
    snapshot_path = snapshot_path.resolve()
    manifest_path = snapshot_path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"snapshot manifest is missing: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1:
        raise ValueError("unsupported snapshot manifest schemaVersion")
    snapshot_id = manifest.get("snapshotId")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID.fullmatch(snapshot_id):
        raise ValueError("snapshotId must contain only letters, numbers, dot, underscore or dash")

    products = _require_file(manifest.get("products"), "products")
    manual = _require_file(manifest.get("comboManual"), "comboManual")
    if products["file"] != snapshot_path.name:
        raise ValueError("snapshot path does not match manifest products.file")
    if _sha256(snapshot_path) != products.get("gzipSha256"):
        raise ValueError("snapshot compressed checksum mismatch")

    manual_source = snapshot_path.parent / manual["file"]
    _validate_file(manual_source, manual, "combo manual mapping")

    target_dir = runtime_root.resolve() / "snapshots" / snapshot_id
    target_dir.mkdir(parents=True, exist_ok=True)
    products_target = target_dir / "products.jsonl"
    products_temp = target_dir / ".products.jsonl.tmp"
    manual_target = target_dir / "combo_items_manual.jsonl"
    manual_temp = target_dir / ".combo_items_manual.jsonl.tmp"

    try:
        digest = hashlib.sha256()
        rows = 0
        with gzip.open(snapshot_path, "rb") as source, products_temp.open("wb") as target:
            while chunk := source.read(BUFFER_SIZE):
                digest.update(chunk)
                rows += chunk.count(b"\n")
                target.write(chunk)
        if digest.hexdigest() != products["sha256"]:
            raise ValueError("snapshot products checksum mismatch after decompression")
        if rows != products["rows"]:
            raise ValueError(f"snapshot products row count mismatch: {rows}")

        shutil.copyfile(manual_source, manual_temp)
        os.replace(products_temp, products_target)
        os.replace(manual_temp, manual_target)
    finally:
        products_temp.unlink(missing_ok=True)
        manual_temp.unlink(missing_ok=True)

    return products_target
