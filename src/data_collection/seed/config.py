"""Configuration shared by the deterministic week-1 seed pipeline."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_COLLECTION_DIR = REPO_ROOT / "src" / "data_collection"
DEFAULT_DATA_DIR = DATA_COLLECTION_DIR / "data"
DEFAULT_SNAPSHOT_DIR = DATA_COLLECTION_DIR / "snapshots" / "2026-09-21"
DEFAULT_PRODUCTS_SNAPSHOT = DEFAULT_SNAPSHOT_DIR / "products.jsonl.gz"
DEFAULT_PRODUCTS_CANDIDATES = (
    DEFAULT_DATA_DIR / "products.jsonl",
    DEFAULT_PRODUCTS_SNAPSHOT,
    DATA_COLLECTION_DIR / "products.jsonl",
    DATA_COLLECTION_DIR / "products.synthetic.jsonl",
)

DEFAULT_SEED = 42
DEFAULT_USERS = 2_000
# Calibrated on the 10,320-row catalog: popular-in-destination Recall@20
# stays below the 0.60 ceiling while the purchase distribution remains skewed.
DEFAULT_ZIPF = 0.8
DEFAULT_VINPEARL_BOOST = 2.0
DEFAULT_MAX_EVENTS = 15
DEFAULT_INSIDER_EVENTS_PER_PROFILE = 10.0

VOTA_URL_ENV = "SEED_DATABASE_URL"
INSIDER_URL_ENV = "INSIDER_DATABASE_URL"
DEFAULT_VOTA_URL = "postgresql://postgres:postgres@localhost:5432/vota"
DEFAULT_INSIDER_URL = "postgresql://postgres:postgres@localhost:5432/insider"


def find_products(explicit: Path | None = None) -> Path | None:
    """Return the first usable real/synthetic catalog path."""
    candidates = (explicit,) if explicit else DEFAULT_PRODUCTS_CANDIDATES
    return next((path.resolve() for path in candidates if path and path.is_file()), None)
