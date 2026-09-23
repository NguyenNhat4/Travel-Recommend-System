"""pytest: thêm <repo>/src vào sys.path; test `integration` chỉ chạy khi gọi `pytest -m integration` (cần Weaviate
của sbench đang chạy). Mỗi test dùng SBENCH_HOME riêng trong tmp_path để không đụng bench_out/ thật."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: cần Weaviate của sbench (docker/compose.yml) đang chạy")
    config.addinivalue_line("filterwarnings", "ignore:The httpx module is deprecated")


def pytest_collection_modifyitems(config, items):
    if "integration" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="integration: chạy bằng `pytest -m integration`")
    for it in items:
        if "integration" in it.keywords:
            it.add_marker(skip)


@pytest.fixture(scope="session")
def cfg():
    from evaluation.search_bench.config import load_config
    return load_config()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SBENCH_HOME", str(tmp_path / "sbench"))
    return tmp_path / "sbench"


@pytest.fixture(scope="session")
def sample_records(cfg):
    from evaluation.search_bench.catalog import load_records
    records, _ = load_records(cfg, "sample")
    return records
