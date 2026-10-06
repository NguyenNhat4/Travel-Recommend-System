"""Nạp config/sbench.yaml + .env gốc repo, validate bằng pydantic (spec §1.2).

Mọi con số chỉ nằm trong YAML; module này không đặt giá trị mặc định cho chúng. Các mục của Part chưa cài (gold, synth,
metrics…) giữ nguyên dạng mở để YAML đầy đủ của spec validate được ngay từ bây giờ.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from evaluation.vector_bench.config import read_env_file

from . import paths

# Khoá được nạp từ .env gốc repo (file đó còn chứa DATABASE_URL, WEAVIATE_URL của app — không được lẫn vào bench).
ENV_ALLOW = ("COHERE_API_KEY", "AWS_PROFILE", "LLM_PROVIDER")
ENV_ALLOW_PREFIX = "SBENCH_"

#: Phase A (05/10): tên trường gold v4 mà `metrics.load_gold` đọc → tên nội bộ của `GoldQuery`. Tên cuối của máy gán nhãn chưa
#: chốt nên ánh xạ nằm trong config (`metrics.gold_fields`); thiếu khoá nào thì dùng tên mặc định ở đây.
DEFAULT_GOLD_FIELDS: dict[str, str] = {
    "forbidden_filter": "forbidden_filter",   # AST filter: kết quả KHÔNG được xuất hiện
    "forbidden": "forbidden",                 # danh sách product_id cấm
    "origin": "origin",                       # chặng bay kỳ vọng (attributes.originCity)
    "destination_city": "destination_city",   # (attributes.destinationCity)
    "expected_parse": "expected_parse",       # {taxonomy, destination, origin, destination_city, must_not, must_not_brands,
                                              #  must_not_taxonomies, price_max, price_min, star_min, party_total} (metrics.PARSE_FIELDS)
    "family": "family",                       # họ câu: biến thể không dấu / gõ sai của cùng một ý định (gộp theo họ)
}


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
    query_prefix: Optional[str] = None        # e5: "query: " / "passage: " — ghép trước text theo input_type (embed/local_hf.py)
    passage_prefix: Optional[str] = None
    input_type_mode: Literal["asymmetric", "symmetric"] = "asymmetric"  # symmetric local model dùng cùng encoder cho query/document
    pooling: Optional[Literal["mean", "cls"]] = None   # model local: mean (e5) | cls (bge-m3, gte); mặc định mean


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
    max_tokens_per_min: int


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


class WinRule(_M):
    min_delta_recall: float
    p_max: float
    max_slice_loss: float
    tie_delta_ndcg: float


class Guards(_M):
    constraint_precision_min: float
    parent_dup_max: float
    zero_result_in_catalog_max: float
    hub_score_max: float
    p95_cache_miss_ms_max: float
    # Phase A (05/10) — đề xuất, chờ chốt Sprint 2 (xem chú thích trong sbench.yaml); None = chưa có ngưỡng. Chưa có `select()`
    # nên chưa nơi nào ép các ngưỡng này — chỉ đọc và báo.
    forbidden_at_10_max: Optional[float] = None
    direction_accuracy_min: Optional[float] = None
    filter_pass_min: Optional[float] = None
    parse_accuracy_min: Optional[float] = None


class GuardsProposed(_M):
    """`sb guards` (06/10): ngưỡng guard Phase A ĐỀ XUẤT, chưa chốt — lệnh chỉ in PASS/FAIL để đọc, không chặn gì (kiến trúc
    search OTA §15 "Hard fail khi forbidden …"). Mọi giá trị nằm ở sbench.yaml `metrics.guards_proposed`."""
    forbidden_at_10_max: float
    direction_accuracy_min: float
    filter_pass_min: float
    parse_accuracy_min: float          # áp cho từng trường của parse_accuracy
    constraint_precision_min: float
    zero_result_in_catalog_max: float


class WeakResultsConfig(_M):
    """`sb weak-results` (06/10): lưới ngưỡng phân tích quy tắc "kết quả yếu" (hợp đồng search §3.4, S2 của §10)."""
    top_score_grid: list[float]        # WEAK_RESULT_TOP_SCORE thử
    margin_grid: list[float]           # WEAK_RESULT_MARGIN thử


class MetricsConfig(_M):
    k: int
    ndcg_gain: Literal["pow2"]
    mrr_relevant_min: int
    recall_relevant_min: int
    extra_recall_k: list[int]
    bootstrap: int
    win_rule: WinRule
    guards: Guards
    rerank_keep_if_delta_ndcg: float
    hub_random_queries: int
    # Phase A (05/10): tên trường gold v4 (xem DEFAULT_GOLD_FIELDS) và file forbidden chẩn đoán cho gold_v3 (đường dẫn tương đối
    # theo thư mục gói search_bench; None = không gắn). Gold có `forbidden_filter` thì gold thắng.
    gold_fields: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_GOLD_FIELDS))
    # 06/10: `forbidden_overrides` (chỉ forbidden_filter) được thay bằng `annotations` (forbidden_filter, origin,
    # destination_city, expected_parse, family theo qid — `metrics.load_annotations`). Cả hai cùng cấu hình thì annotations
    # thắng phần forbidden_filter; gold có trường nào thì gold thắng trường đó.
    forbidden_overrides: Optional[str] = None
    annotations: Optional[str] = "config/query_annotations.yaml"
    # 06/10 (người dùng chốt phương án b, gold-guide "Rubric v4"): lúc chấm, nhãn ≥ 1 của sản phẩm có variant ngoài
    # `allowed_variants` của câu (annotations) tính là 0 — áp cả nhãn cũ v1–v3 mà không sửa gold.jsonl.
    rubric_v4_projection: bool = True
    guards_proposed: Optional[GuardsProposed] = None
    weak_results: Optional[WeakResultsConfig] = None

    @field_validator("gold_fields")
    @classmethod
    def _gold_fields_known(cls, v: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(v) - set(DEFAULT_GOLD_FIELDS))
        if unknown:
            raise ValueError(f"metrics.gold_fields: khoá lạ {unknown} (có: {', '.join(DEFAULT_GOLD_FIELDS)})")
        return {**DEFAULT_GOLD_FIELDS, **v}


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
    metrics: MetricsConfig
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


def deep_merge(base: dict, overrides: dict) -> dict:
    """Bản sao của `base` với `overrides` ghi đè theo từng khoá lồng nhau (dict gộp, giá trị khác thay thế)."""
    out = dict(base)
    for k, v in overrides.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(path: str | Path | None = None, *, overrides_path: str | Path | None = None) -> SBenchConfig:
    """Nạp sbench.yaml; `overrides_path` (chỉ dùng cho test) ghi đè một phần — file config thật không đổi."""
    p = Path(path) if path else paths.DEFAULT_CONFIG
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if overrides_path:
        over = yaml.safe_load(Path(overrides_path).read_text(encoding="utf-8")) or {}
        if not isinstance(over, dict):
            raise ValueError(f"{overrides_path}: phải là mapping YAML")
        raw = deep_merge(raw, over)
    return SBenchConfig.model_validate(raw)
