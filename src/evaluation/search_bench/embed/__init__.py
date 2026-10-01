"""Part 3 — chọn embedder theo model và bọc cache. `make_embedder` là cửa vào duy nhất cho mọi lệnh cần vector.

`embedder_name` tính tên embedder (chuỗi model trong khoá cache, gồm mọi tuỳ chọn làm đổi vector) mà KHÔNG gọi API —
`sb load` / `sb query` dùng nó để từ chối vector hay collection do embedder khác sinh ra.
"""
from __future__ import annotations

import os

import structlog

from .. import paths
from ..config import SBenchConfig
from .base import EmbedBatchError, Embedder, EmbedStats, InputType, TokenLimitError, l2_normalize
from .cache import CachedEmbedder, EmbeddingCache, cache_key

__all__ = ["CachedEmbedder", "EmbedBatchError", "Embedder", "EmbedStats", "EmbedderUnavailable", "EmbeddingCache",
           "InputType", "TokenLimitError", "cache_key", "embedder_name", "l2_normalize", "make_embedder"]

log = structlog.get_logger("sbench.embed")


class EmbedderUnavailable(RuntimeError):
    pass


def _model_cfg(cfg: SBenchConfig, model: str):
    try:
        return cfg.model_cfg(model)
    except ValueError as e:
        raise EmbedderUnavailable(str(e)) from None


def _kind(cfg: SBenchConfig, model: str) -> str:
    mcfg = _model_cfg(cfg, model)
    if model == "fake" or cfg.embedding.provider == "fake":
        return "fake"
    if model.startswith("cohere-"):
        if cfg.embedding.provider == "bedrock":
            raise EmbedderUnavailable("provider bedrock chưa cài — ngày 1 chốt Cohere API trực tiếp (embedding.provider: cohere)")
        if cfg.embedding.provider != "cohere":
            raise EmbedderUnavailable(f"model {model} cần provider cohere, config đang là {cfg.embedding.provider}")
        return "cohere"
    if mcfg.hf_model:
        return "local"
    raise EmbedderUnavailable(f"không biết cách embed model {model}")


def embedder_name(cfg: SBenchConfig, model: str, *, embedding_type: str = "float", fake_ignore_input_type: bool = False) -> str:
    kind = _kind(cfg, model)
    if kind == "fake":
        return "fake@noit" if fake_ignore_input_type else "fake"
    mcfg = _model_cfg(cfg, model)
    if kind == "local":
        if embedding_type != "float":
            raise EmbedderUnavailable(f"model local {model} chỉ có embedding_types float")
        return mcfg.hf_model
    return mcfg.api_model + (f"@d{mcfg.output_dimension}" if mcfg.output_dimension else "") + \
        ("@int8" if embedding_type == "int8" else "")


def _local(cfg: SBenchConfig, model: str, embedding_type: str, preflight: bool):
    import importlib.util
    from .local_hf import REQUIRED_LIBS, LocalHFEmbedder
    if embedding_type != "float":
        raise EmbedderUnavailable(f"model local {model} chỉ có embedding_types float")
    missing = [lib for lib in REQUIRED_LIBS if importlib.util.find_spec(lib) is None]
    if missing:
        raise EmbedderUnavailable(f"thiếu {', '.join(missing)} — pip install -r src/evaluation/search_bench/requirements-extra.txt "
                                  f"(cần cho model local {model})")
    return LocalHFEmbedder(model, cfg.model_cfg(model), preflight=preflight)


def _cohere(cfg: SBenchConfig, model: str, embedding_type: str, preflight: bool):
    from .cohere_api import CohereEmbedder
    key = os.environ.get("COHERE_API_KEY")
    if not key:
        raise EmbedderUnavailable("thiếu COHERE_API_KEY (môi trường hoặc .env gốc repo)")
    mcfg = cfg.model_cfg(model)
    counter = None
    if preflight:
        from .. import tokens
        try:
            counter = tokens.TokenCounter(tokens.ensure_tokenizer(mcfg.api_model, key))
        except tokens.TokenizerUnavailable as e:   # không có tokenizer thì vẫn embed, API tự từ chối text quá dài
            log.warning("không có tokenizer offline — bỏ kiểm token trước khi gọi API, pacer chỉ đếm input", model=mcfg.api_model,
                        error=str(e).replace(key, "***")[:160])
    return CohereEmbedder(model, mcfg, cfg.embedding, api_key=key, embedding_type=embedding_type,
                          token_counter=counter, token_hard_max=cfg.text.token_hard_max)


def make_embedder(cfg: SBenchConfig, model: str, *, no_cache: bool = False, fake_ignore_input_type: bool = False,
                  embedding_type: str = "float", preflight: bool = True) -> CachedEmbedder:
    kind = _kind(cfg, model)
    if kind == "fake":
        from .fake import FakeEmbedder
        inner = FakeEmbedder(_model_cfg(cfg, model).dim, ignore_input_type=fake_ignore_input_type)
    elif kind == "local":
        inner = _local(cfg, model, embedding_type, preflight)
    else:
        inner = _cohere(cfg, model, embedding_type, preflight)
    expected = embedder_name(cfg, model, embedding_type=embedding_type, fake_ignore_input_type=fake_ignore_input_type)
    if inner.name != expected:
        raise EmbedderUnavailable(f"embedder {inner.name} ≠ tên mong đợi {expected}")
    return CachedEmbedder(inner, EmbeddingCache(paths.cache_dir() / paths.EMBED_CACHE), no_cache=no_cache)
