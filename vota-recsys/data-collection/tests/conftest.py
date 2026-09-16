"""Shared fixtures. Everything here runs offline unless marked ``pg``."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# The project uses a flat layout so `python -m cli` works from the package
# directory (spec section 2 writes the commands that way). Tests therefore add
# that directory to sys.path rather than relying on an installed package.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _utf8_environment():
    """Make the test run encoding-identical to a real run.

    Without this, a test that prints a Vietnamese product name passes on a UTF-8
    machine and fails on a default Windows console — which is the bug it should
    be catching, not one it should be introducing.
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("POSTGRES_PASSWORD", "test-not-used")
    import runtime

    runtime.setup_encoding()


@pytest.fixture(scope="session")
def cfg():
    import config

    return config.load_config()


@pytest.fixture
def fixture_bytes():
    """Read a committed fixture, transparently gunzipping ``.gz``."""

    def _read(*parts: str) -> bytes:
        path = FIXTURES.joinpath(*parts)
        if not path.exists():
            pytest.skip(f"fixture not present: {path.relative_to(FIXTURES)}")
        if path.suffix == ".gz":
            import gzip

            return gzip.decompress(path.read_bytes())
        return path.read_bytes()

    return _read


@pytest.fixture
def db_available(cfg):
    """Skip a ``pg`` test when Postgres is not running, rather than failing it."""
    import db

    try:
        db.check_connection(cfg)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")
    return True
