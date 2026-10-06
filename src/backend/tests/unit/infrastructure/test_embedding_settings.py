"""Cấu hình embedding (FR-SRC-02, chốt 06/10): mặc định local e5-small 384 chiều + collection ProductE5 + cutoff 0,84;
provider Cohere là đường lui tự lấy bộ giá trị của mình; model ↔ số chiều ↔ revision được kiểm; composition root chọn
adapter theo provider; revision trong Dockerfile trùng config."""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.backend.app.core.config import LOCAL_EMBED_REVISION, REPO_ROOT, Settings
from src.backend.app.infrastructure.embeddings import factory
from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder
from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_defaults_are_local_e5_small(monkeypatch):
    for name in ("EMBED_PROVIDER", "EMBED_MODEL", "EMBED_DIMENSION", "EMBED_MODEL_REVISION", "WEAVIATE_COLLECTION",
                 "SEARCH_CUTOFF", "SEARCH_NO_DIACRITICS_CUTOFF", "SEARCH_LEXICAL_CUTOFF"):
        monkeypatch.delenv(name, raising=False)
    s = _settings()
    assert (s.embed_provider, s.embed_model, s.embed_dimension) == ("local", "intfloat/multilingual-e5-small", 384)
    assert s.embed_model_revision == "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    assert s.weaviate_collection == "ProductE5"
    assert (s.search_cutoff, s.search_no_diacritics_cutoff, s.search_lexical_cutoff) == (0.84, 0.80, 0.50)
    assert factory.embedding_model_version(s) == "intfloat/multilingual-e5-small:catalog-text-v2"


def test_cohere_provider_falls_back_to_its_own_values_when_not_set_explicitly(monkeypatch):
    for name in ("EMBED_MODEL", "EMBED_DIMENSION", "WEAVIATE_COLLECTION", "SEARCH_CUTOFF", "SEARCH_NO_DIACRITICS_CUTOFF"):
        monkeypatch.delenv(name, raising=False)
    s = _settings(embed_provider="cohere")
    assert (s.embed_model, s.embed_dimension, s.weaviate_collection) == ("embed-multilingual-v3.0", 1024, "Product")
    assert (s.search_cutoff, s.search_no_diacritics_cutoff) == (0.62, None)
    assert factory.embedding_model_version(s) == "embed-multilingual-v3.0:catalog-text-v2"
    # Giá trị đặt tường minh luôn thắng.
    s = _settings(embed_provider="cohere", weaviate_collection="ProductCohere", search_cutoff=0.6)
    assert (s.weaviate_collection, s.search_cutoff) == ("ProductCohere", 0.6)


def test_env_vars_drive_the_provider(monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "cohere")
    for name in ("EMBED_MODEL", "EMBED_DIMENSION", "WEAVIATE_COLLECTION", "SEARCH_CUTOFF"):
        monkeypatch.delenv(name, raising=False)
    s = _settings()
    assert (s.embed_provider, s.embed_dimension, s.weaviate_collection) == ("cohere", 1024, "Product")


@pytest.mark.parametrize("kw, message", [
    ({"embed_dimension": 1024}, "EMBED_DIMENSION=1024"),                                  # local e5-small là 384
    ({"embed_provider": "cohere", "embed_dimension": 384}, "EMBED_DIMENSION=384"),       # Cohere v3 là 1024
    ({"embed_model": "embed-multilingual-v3.0"}, "không dùng được với EMBED_PROVIDER=local"),
    ({"embed_provider": "cohere", "embed_model": "intfloat/multilingual-e5-small"}, "EMBED_PROVIDER=cohere"),
    ({"embed_model_revision": " "}, "EMBED_MODEL_REVISION"),
    ({"embed_provider": "openai"}, "embed_provider"),
])
def test_invalid_combinations_are_rejected(kw, message, monkeypatch):
    for name in ("EMBED_PROVIDER", "EMBED_MODEL", "EMBED_DIMENSION", "EMBED_MODEL_REVISION"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError, match=message):
        _settings(**kw)


def test_blank_no_diacritics_cutoff_means_use_search_cutoff(monkeypatch):
    monkeypatch.setenv("SEARCH_NO_DIACRITICS_CUTOFF", "")
    assert _settings().search_no_diacritics_cutoff is None


def test_factory_picks_adapter_by_provider_without_loading_anything(monkeypatch):
    for name in ("EMBED_MODEL", "EMBED_DIMENSION", "EMBED_MODEL_REVISION", "EMBED_THREADS"):
        monkeypatch.delenv(name, raising=False)
    local = factory.build_embedder(_settings(embed_threads=2))
    assert isinstance(local, LocalE5Embedder)
    assert (local.name, local.revision, local.dimension, local.threads) == (
        "intfloat/multilingual-e5-small", LOCAL_EMBED_REVISION, 384, 2)
    assert local._model is None and local._tokenizer is None   # nạp lười: dựng adapter không tải model
    cohere = factory.build_embedder(_settings(embed_provider="cohere", cohere_api_key="k"))
    try:
        assert isinstance(cohere, CohereEmbedder) and (cohere.name, cohere.dimension) == ("embed-multilingual-v3.0", 1024)
    finally:
        cohere.close()


def test_composition_root_builds_local_embedder_warms_it_and_wraps_the_query_cache(monkeypatch):
    from src.backend.app import main
    from src.backend.app.application.search.query_cache import CachingQueryEmbedder

    built = []

    class Probe:
        name = "intfloat/multilingual-e5-small"

        def warmup(self):
            built.append("warmup")

    def fake_build(settings):
        built.append(settings.embed_provider)
        return Probe()

    monkeypatch.setattr(factory, "build_embedder", fake_build)
    for name in ("EMBED_PROVIDER", "EMBED_MODEL", "EMBED_DIMENSION"):
        monkeypatch.delenv(name, raising=False)
    embedder = main.build_query_embedder(_settings())
    assert built == ["local", "warmup"]
    assert isinstance(embedder, CachingQueryEmbedder) and isinstance(embedder.inner, Probe)
    assert isinstance(main.build_query_embedder(_settings(search_embed_cache=False)), Probe)


def test_composition_root_does_not_load_the_model_when_the_index_is_unavailable(monkeypatch):
    """Weaviate chưa sẵn sàng → build_recsys lỗi ở bước nạp index, chưa dựng embedder (không nạp model mỗi lần thử lại)."""
    from src.backend.app import main

    monkeypatch.setattr(main, "build_query_embedder", lambda settings: pytest.fail("không được dựng embedder"))

    import src.backend.app.infrastructure.vectors.weaviate_store as ws

    monkeypatch.setattr(ws, "connect_weaviate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("weaviate down")))
    with pytest.raises(RuntimeError, match="weaviate down"):
        main.build_recsys(_settings())


def test_dockerfile_downloads_the_same_revision_as_the_config():
    dockerfile = (REPO_ROOT / "Dockerfile.backend").read_text(encoding="utf-8")
    assert re.search(r"ARG EMBED_MODEL_REVISION=(\w+)", dockerfile).group(1) == LOCAL_EMBED_REVISION
    assert "ARG EMBED_MODEL=intfloat/multilingual-e5-small" in dockerfile
    pins = Path(REPO_ROOT / "src/backend/requirements-embed.txt").read_text(encoding="utf-8")
    assert re.search(r"^torch==", pins, re.M) and re.search(r"^transformers==", pins, re.M)
    assert "sentence-transformers" not in re.sub(r"#.*", "", pins)
