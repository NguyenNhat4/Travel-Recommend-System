"""Composition root nối các biến SEARCH_* 1.16.0 (và ba cờ 1.18.0 SEARCH_DURATION_FILTER / SEARCH_POI_RESOLVE /
SEARCH_ENTITY_FILTER) vào `SearchProducts` (main.build_recsys); mặc định tắt / trung tính."""
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


def test_v118_flags_default_off_and_reach_the_engine(data_dir):
    """07/10 (contract 1.18.0): ba cờ mặc định tắt (tắt không parse → response y hệt 1.17.0) và được truyền tới engine."""
    s, engine = _build(data_dir)
    assert (s.search_duration_filter, s.search_poi_resolve, s.search_entity_filter) == (False, False, False)
    assert (engine.duration_filter, engine.poi_resolve, engine.entity_filter) == (False, False, False)
    r = engine("VinWonders 3 ngày 2 đêm", limit=50)
    assert not {"duration", "entity", "location"} & set(r["diagnostics"].get("queryPlan", {}))
    _, on = _build(data_dir, search_duration_filter=True, search_poi_resolve=True, search_entity_filter=True)
    assert (on.duration_filter, on.poi_resolve, on.entity_filter) == (True, True, True)
    qp = on("VinWonders 3 ngày 2 đêm", limit=50)["diagnostics"]["queryPlan"]
    assert qp["duration"] == {"days": 3, "nights": 2, "source": "query"} and qp["entity"]["role"] == "gate"
    # mỗi cờ độc lập: bật một cờ không kéo hai cờ kia
    _, one = _build(data_dir, search_poi_resolve=True)
    assert (one.duration_filter, one.poi_resolve, one.entity_filter) == (False, True, False)


def test_production_defaults_restored(data_dir):
    """Mặc định production 06/10 (history/2026-10-06-search-e5-production-f12356-llm-fallback.md): F1, F2 relax (cutoff 0,80),
    F3, F5, F6 bật, F4 tắt; LLM fallback off và không dựng hypothesizer. Merge 21d72ae từng lật các giá trị này về tắt."""
    s, engine = _build(data_dir)
    assert (s.search_dest_filter, s.search_negation_filter, s.search_route_filter, s.search_numeric_filter) == (
        True, True, True, True)
    assert s.search_taxonomy_filter is False
    # 14/10 (bench gold_v7, plan 2026-10-13): câu không dấu phục hồi dấu thay vì nới cutoff; cổng bằng chứng + câu không giải
    # thích được bật; thời lượng / embed residual / backgroundScore vẫn tắt.
    assert (s.search_no_diacritics_mode, s.search_no_diacritics_cutoff) == ("restore", 0.80)
    assert (s.search_evidence_gate, s.search_unexplained_empty) == (True, True)
    assert (s.search_duration_mask, s.search_embed_residual, s.search_emit_background) == (False, False, False)
    assert (s.search_llm_fallback, s.search_llm_fallback_min_confidence, s.search_llm_fallback_timeout_ms) == (
        "off", 0.75, 1500)
    assert (engine.dest_filter, engine.negation_filter, engine.route_filter, engine.numeric_filter) == (
        True, True, True, True)
    assert engine.taxonomy_filter is False and engine.no_diacritics is None and engine.no_diacritics_cutoff is None
    assert engine.no_diacritics_restore and engine.unexplained_empty and engine.hybrid.evidence_gate
    assert engine.llm_fallback == "off" and engine.hypothesizer is None and engine._llm is None
    # Chuỗi rỗng từ .env = "không đặt" cho cutoff câu không dấu (Settings._OPTIONAL_BLANK_IS_NONE).
    assert Settings(_env_file=None, search_no_diacritics_cutoff="").search_no_diacritics_cutoff is None


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
