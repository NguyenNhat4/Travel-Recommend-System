"""Nạp config/sbench.yaml + .env gốc repo, validate bằng pydantic (spec §1.2).

Mọi con số chỉ nằm trong YAML; module này không đặt giá trị mặc định cho chúng. Các mục của Part chưa cài (gold, synth,
metrics…) giữ nguyên dạng mở để YAML đầy đủ của spec validate được ngay từ bây giờ.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict

from evaluation.vector_bench.config import read_env_file

from . import paths

# Khoá được nạp từ .env gốc repo (file đó còn chứa DATABASE_URL, WEAVIATE_URL của app — không được lẫn vào bench).
ENV_ALLOW = ("COHERE_API_KEY", "AWS_PROFILE", "LLM_PROVIDER")
ENV_ALLOW_PREFIX = "SBENCH_"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Open(BaseModel):
    """Mục của Part chưa cài: giữ nguyên, không ép kiểu từng khoá."""
    model_config = ConfigDict(extra="allow")


class RunConfig(_M):
    seed: int
    default_run_id: str


class CatalogConfig(_M):
    products_path: str
    snapshot_path: str
    sample_path: str
    search_unit_variants: list[str]
    amenity_seed_path: str
    amenity_scope: Literal["property_only", "property_plus_rooms"]
    amenity_min_freq: int
    amenity_fuzzy_min: float
    fake_n: int


class TextConfig(_M):
    max_words: int
    max_amenities: int
    max_room_names: int
    max_description_words: int
    sentence_df_drop: int
    desc_words_by_modifier: dict[str, Optional[int]]
    token_p99_max: int
    token_hard_max: int


class ModelConfig(_M):
    dim: int
    api_model: Optional[str] = None           # Cohere
    max_batch: Optional[int] = None
    truncate: Optional[Literal["NONE"]] = None  # spec §1.7: không bao giờ END/START
    output_dimension: Optional[int] = None
    hf_model: Optional[str] = None            # sentence-transformers
    max_seq_length: Optional[int] = None
    device: Optional[str] = None
    batch_size: Optional[int] = None
    trust_remote_code: Optional[bool] = None


class RetryConfig(_M):
    max_attempts: int
    backoff_s: list[float]


class BedrockConfig(_M):
    model_id: str
    region: str


class EmbeddingConfig(_M):
    provider: Literal["cohere", "bedrock", "local", "fake"]
    models: dict[str, ModelConfig]
    input_type: dict[Literal["document", "query"], str]
    bedrock: BedrockConfig
    retry: RetryConfig
    cost_per_1m_tokens_usd: dict[str, float]
    max_inputs_per_min: int


class Bm25Config(_M):
    k1: float
    b: float
    tokenization: Literal["word", "whitespace", "lowercase", "field", "trigram"]
    stopwords_preset: Literal["none", "en"]


class HybridDefault(_M):
    fusion: Literal["ranked", "relative_score"]
    alpha: float


class WeaviateConfig(_M):
    url: str
    grpc_port: int
    image: str
    vector_index: Literal["flat", "hnsw"]
    bm25: Bm25Config
    ascii_fold: Literal["analyzer", "shadow"]
    hybrid_default: HybridDefault
    query_timeout_s: float
    load_batch_size: int


class DoctorConfig(_M):
    min_free_gb: float
    min_weaviate_version: str


class SBenchConfig(_M):
    run: RunConfig
    catalog: CatalogConfig
    text: TextConfig
    embedding: EmbeddingConfig
    weaviate: WeaviateConfig
    doctor: DoctorConfig
    gold: _Open
    synth: _Open
    metrics: _Open
    latency: _Open
    holes: _Open
    stages: _Open
    regression: _Open

    def model_cfg(self, model: str) -> ModelConfig:
        try:
            return self.embedding.models[model]
        except KeyError:
            raise ValueError(f"model không có trong config: {model!r} (có: {', '.join(self.embedding.models)})") from None


def load_env(env_file: Path | None = None) -> list[str]:
    """Nạp các khoá được phép từ `.env` gốc repo vào os.environ, không ghi đè biến đã có. Trả tên khoá đã nạp."""
    loaded = []
    for k, v in read_env_file(env_file or paths.repo_root() / ".env").items():
        if (k in ENV_ALLOW or k.startswith(ENV_ALLOW_PREFIX)) and v and k not in os.environ:
            os.environ[k] = v
            loaded.append(k)
    return loaded


def load_config(path: str | Path | None = None) -> SBenchConfig:
    p = Path(path) if path else paths.DEFAULT_CONFIG
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return SBenchConfig.model_validate(raw)
