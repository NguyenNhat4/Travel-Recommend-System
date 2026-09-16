"""Import every third-party module the tree actually uses.

`uv sync` succeeding proves the lock resolves, not that the code can run:
a module used in one code path but missing from pyproject.toml fails on the
first real invocation instead of in CI. This test closes that gap — it is the
reason `lxml` and `bcrypt` are pinned rather than assumed.
"""

from __future__ import annotations

import importlib

import pytest

# (import name, why it is needed)
REQUIRED = [
    ("sqlalchemy", "db layer"),
    ("psycopg", "postgres driver (v3, binary wheels)"),
    ("httpx", "http client"),
    ("selectolax", "HTML parsing, last-resort DOM strategy"),
    ("lxml", "XXE-safe sitemap XML parsing in collectors/extract.py"),
    ("typer", "CLI"),
    ("yaml", "config.yaml and the curated data files"),
    ("dotenv", ".env loading"),
    ("bcrypt", "demo account password hashes, verifiable by Spring Security"),
]


@pytest.mark.parametrize("module,reason", REQUIRED)
def test_dependency_importable(module, reason):
    importlib.import_module(module)


def test_psycopg_is_the_binary_distribution():
    """Plain `psycopg` needs libpq + pg_config at build time, which a stock
    Windows machine does not have."""
    import psycopg

    assert psycopg.__version__.startswith("3."), "psycopg v3 is required"


def test_dsn_uses_the_psycopg_driver(cfg):
    """A bare postgresql:// URL makes SQLAlchemy look for psycopg2, which is
    not a dependency of this project."""
    assert cfg.database_url.startswith("postgresql+psycopg://")


def test_no_unpinned_import_of_dropped_dependencies():
    """These were considered and deliberately dropped; using one silently
    reintroduces a dependency the lock does not carry."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for dropped in ("import orjson", "import numpy", "import rapidfuzz", "import tenacity"):
            if dropped in text:
                offenders.append(f"{path.relative_to(root)}: {dropped}")
    assert not offenders, (
        "dropped dependencies are being imported: " + "; ".join(offenders)
    )
