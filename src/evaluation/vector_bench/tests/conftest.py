"""pytest: thêm <repo>/src vào sys.path; test `integration` chỉ chạy khi gọi `pytest -m integration` (cần engine đang chạy)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: cần engine chạy qua `vb engine up <engine>`")


def pytest_collection_modifyitems(config, items):
    if "integration" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="integration: chạy bằng `pytest -m integration`")
    for it in items:
        if "integration" in it.keywords:
            it.add_marker(skip)


@pytest.fixture(scope="session")
def cfg():
    from evaluation.vector_bench.config import load_config
    return load_config()
