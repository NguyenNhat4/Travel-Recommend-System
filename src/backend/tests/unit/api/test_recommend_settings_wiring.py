"""Composition root nối pool `recsys-io` (RECOMMEND_IO_WORKERS, 2026-10-12) vào `RecommendForUser` (main.build_recsys)."""
from concurrent.futures import ThreadPoolExecutor

from src.backend.app.core.config import Settings
from src.backend.app.main import build_recsys
from src.backend.tests.conftest import FakeEmbedder
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader


def _recommend(data_dir, **kwargs):
    emb = FakeEmbedder()
    store = InMemoryVectorStore(str(data_dir / "products.jsonl"), emb, str(data_dir / ".embcache"))
    return build_recsys(Settings(_env_file=None), embedder=emb, vector_store=store,
                        cdp_reader=JsonlCdpReader(str(data_dir / "events.jsonl")), **kwargs)["recommend"]


def test_io_workers_default_and_bounds():
    assert Settings(_env_file=None).recommend_io_workers == 16
    assert Settings(_env_file=None, recommend_io_workers=0).recommend_io_workers == 0   # 0 = tuần tự (rollback)


def test_executor_reaches_the_engine(data_dir):
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert _recommend(data_dir, recommend_executor=pool).executor is pool
    assert _recommend(data_dir).executor is None
