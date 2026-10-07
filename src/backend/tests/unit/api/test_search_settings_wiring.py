"""Composition root nối các biến SEARCH_* 1.16.0 vào `SearchProducts` (main.build_recsys); mặc định tắt / trung tính."""
from src.backend.app.core.config import Settings
from src.backend.app.main import build_recsys
from src.backend.tests.conftest import FakeEmbedder
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader


def _build(data_dir, **overrides):
    settings = Settings(_env_file=None, **overrides)
    emb = FakeEmbedder()
    store = InMemoryVectorStore(str(data_dir / "products.jsonl"), emb, str(data_dir / ".embcache"))
    return settings, build_recsys(settings, embedder=emb, vector_store=store,
                                  cdp_reader=JsonlCdpReader(str(data_dir / "events.jsonl")))["search"]


def test_defaults_are_off_and_identity(data_dir):
    s, engine = _build(data_dir)
    assert (s.search_tone_normalize, s.search_taxonomy_strong_only, s.search_party_filter, s.search_log_queries) == (
        False, False, False, False)
    assert (s.search_fuzzy_k, s.search_fuzzy_candidate_k, s.search_fuzzy_min_sim) == (0, 50, 0.75)
    assert (s.search_rrf_dense_weight, s.search_rrf_lexical_weight, s.search_rrf_fuzzy_weight) == (1.0, 1.0, 1.0)
    assert not (engine.tone_normalize or engine.taxonomy_strong_only or engine.party_filter)
    assert engine.hybrid.fuzzy_k == 0 and engine.fuzzy_on is False and engine._fuzzy is None
    assert (engine.hybrid.dense_weight, engine.hybrid.lexical_weight, engine.hybrid.fuzzy_weight) == (1.0, 1.0, 1.0)


def test_settings_reach_the_engine_and_both_hybrid_configs(data_dir):
    _, engine = _build(data_dir, search_tone_normalize=True, search_taxonomy_strong_only=True, search_party_filter=True,
                       search_fuzzy_k=4, search_fuzzy_candidate_k=30, search_fuzzy_min_sim=0.8,
                       search_rrf_dense_weight=1.0, search_rrf_lexical_weight=0.5, search_rrf_fuzzy_weight=0.7,
                       search_no_diacritics_mode="relax")
    assert engine.tone_normalize and engine.taxonomy_strong_only and engine.party_filter
    for cfg in (engine.hybrid, engine.no_diacritics):
        assert (cfg.fuzzy_k, cfg.fuzzy_candidate_k, cfg.fuzzy_min_sim) == (4, 30, 0.8)
        assert (cfg.dense_weight, cfg.lexical_weight, cfg.fuzzy_weight) == (1.0, 0.5, 0.7)
    assert engine.fuzzy_on and len(engine._fuzzy) == len(engine.index.units)   # dựng lúc nạp, không ở request đầu
    _, dense_only = _build(data_dir, search_hybrid=False, search_fuzzy_k=4)
    assert dense_only.hybrid is None and dense_only.fuzzy_on is False      # fuzzy chỉ chạy trong nhánh hybrid
