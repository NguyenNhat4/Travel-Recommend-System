"""Nạp config/vbench.yaml + docker/.env, validate bằng pydantic (spec §1.2).

Mọi con số (ngưỡng, bucket, tham số sweep…) chỉ nằm trong YAML; module này không đặt giá trị mặc định cho chúng.
"""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import paths


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class _Open(BaseModel):
    """Mục spec liệt kê nhưng fast-track chưa dùng: giữ nguyên, không ép kiểu từng khoá."""
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------- run
class EngineLimits(_M):
    cpus: float
    mem: str


class RunConfig(_M):
    seed: int
    profile: Literal["local", "full"]
    scales: dict[str, list[str]]
    engines: list[str]
    engine_limits: dict[str, EngineLimits]
    default_run_id: str


# ---------------------------------------------------------------- dataset
class CatalogConfig(_M):
    source: Literal["jsonl", "db", "fake"]
    products_path: str
    database_url_env: str
    fake_n: int
    amenity_scope: Literal["property_only", "property_plus_rooms"]
    amenity_min_freq: int
    max_amenities_in_text: int
    max_room_names_in_text: int
    max_description_words: int


class ScaleConfig(_M):
    vectors: Literal["cohere-vi", "fake", "amplify"]
    hf_dataset: str
    hf_config: str
    sizes: dict[str, int]
    n_queries: int
    n_reserve: int
    correlation: Literal["none", "cluster"]
    geo_jitter_m: float


class DatasetConfig(_M):
    catalog: CatalogConfig
    scale: ScaleConfig


class EmbeddingConfig(_M):
    backend: Literal["st", "fake"]
    model: str
    dim: int
    normalize: bool
    max_seq_length: int
    batch_size: int
    device: str
    query_prefix: str
    passage_prefix: str


# ---------------------------------------------------------------- queries / GT
class Bucket(_M):
    range: tuple[float, float] | None
    quota: int
    min_matches: int = 1   # spec chỉ đặt min_matches cho b01; bucket khác chỉ cần tập khác rỗng


class QueriesConfig(_M):
    n_total: int
    gold_max: int
    buckets: dict[str, Bucket]
    filter_type_weights: dict[str, float]
    available_true_rate: float
    geo_radius_m: list[float]
    price_quantiles: list[float]
    star_min_values: list[float]
    max_attempts: int
    text_slices: dict[str, float]

    @field_validator("buckets")
    @classmethod
    def _quota_sum(cls, v):
        if not v:
            raise ValueError("queries.buckets rỗng")
        return v


class GroundTruthConfig(_M):
    k: int
    tie_eps: float
    chunk_rows: int
    geo_boundary_tol: float
    self_check_items: int
    self_check_min_score: float
    self_check_naive: int


# ---------------------------------------------------------------- engines
class IndexConfig(_M):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class EngineConfig(BaseModel):
    """Khoá kết nối (dsn/url/port…) khác nhau theo engine → cho phép extra."""
    model_config = ConfigDict(extra="allow")
    index_configs: list[IndexConfig]
    default_query: dict[str, Any]
    query_sweep: list[dict[str, Any]]

    def index(self, name: str | None) -> IndexConfig:
        if name is None:
            return self.index_configs[0]
        for ic in self.index_configs:
            if ic.name == name:
                return ic
        raise KeyError(f"index config '{name}' không có trong {[i.name for i in self.index_configs]}")

    def get(self, key: str, default: Any = None) -> Any:
        return (self.model_extra or {}).get(key, default)


class LoadConfig(_M):
    batch_size: int
    shuffle: bool


class QualityConfig(_M):
    k: int
    a1_pass: float
    a1_floor: float
    exact_max_rows: int
    a4_n_filters: int
    a5: dict[str, Any]
    a2: dict[str, Any]
    explain_sample: int


class G3Config(_M):
    per_type: int
    types: list[str]
    k: int


class GatesConfig(_M):
    model_config = ConfigDict(extra="allow")
    g3: G3Config


class PerfConfig(_M):
    k: int
    load_model: Literal["open_loop"]
    rates_qps: list[float]
    duration_s: float
    warmup_s: float
    timeout_ms: float
    b1_rate_qps: float
    reps: int
    harness_max_p99_ms: float
    workers: int
    bootstrap: int
    b4: dict[str, Any]
    b5: dict[str, Any]
    b6: dict[str, Any]
    sampler_interval_s: float


# ---------------------------------------------------------------- fast-track
class FastPerf(_M):
    rates_qps: list[float]
    duration_s: float
    reps: int


class AmplifyConfig(_M):
    k_nn: int
    alpha: tuple[float, float]
    sigmas: list[float]
    calib_samples: int
    block_rows: int
    geo_jitter_m: float
    amenity_drop: float
    amenity_add: float
    price_log_sd: float
    lid_k: int
    lid_ratio: tuple[float, float]
    near_dup_cos: float
    near_dup_max_rate: float
    info_queries: int
    info_k: int


class FastConfig(_M):
    engines: list[str]
    decision_order: list[str]
    scales: list[str]
    max_minutes_per_engine: float
    engine_limits: EngineLimits
    pg_env: dict[str, str]
    index: dict[str, IndexConfig]
    query_sweep: dict[str, list[dict[str, Any]]]
    perf: FastPerf
    amplify: AmplifyConfig


class VBenchConfig(_M):
    run: RunConfig
    dataset: DatasetConfig
    embedding: EmbeddingConfig
    queries: QueriesConfig
    groundtruth: GroundTruthConfig
    engines: dict[str, EngineConfig]
    load: LoadConfig
    quality: QualityConfig
    gates: GatesConfig
    perf: PerfConfig
    scoring: _Open
    decision: _Open
    fast: FastConfig

    # đường dẫn file đã nạp (để worker spawn tự nạp lại — spec §1.5 Windows)
    source_path: str | None = None

    def engine(self, name: str) -> EngineConfig:
        if name not in self.engines:
            raise KeyError(f"engine '{name}' không có trong config.engines")
        return self.engines[name]

    def engine_index(self, engine: str, name: str | None) -> IndexConfig:
        """Tìm index config theo tên trong engines.<e>.index_configs rồi fast.index.<e>."""
        ec = self.engine(engine)
        if name is None:
            return ec.index_configs[0]
        for ic in ec.index_configs:
            if ic.name == name:
                return ic
        fi = self.fast.index.get(engine)
        if fi is not None and fi.name == name:
            return fi
        raise KeyError(f"index '{name}' không có cho engine {engine}")

    def limits(self, profile: str | None = None) -> EngineLimits:
        return self.run.engine_limits[profile or self.run.profile]


def load_config(path: str | Path | None = None, profile: str | None = None) -> VBenchConfig:
    p = Path(path) if path else paths.DEFAULT_CONFIG
    with open(p, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    cfg = VBenchConfig.model_validate(raw)
    cfg.source_path = str(p.resolve())
    if profile:
        cfg.run.profile = profile  # type: ignore[assignment]
    return cfg


def read_env_file(path: Path = paths.DOCKER_ENV_FILE) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------------------------------------------------------------- query configs
def expand_query_configs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Khai triển một phần tử query_sweep: giá trị là list → tích Descartes. {mode: ann, ef: [40, 64]} → 2 cấu hình."""
    keys = list(spec.keys())
    values = [v if isinstance(v, list) else [v] for v in spec.values()]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def query_config_name(qp: dict[str, Any]) -> str:
    parts = [str(qp.get("mode", "ann"))]
    for k in sorted(qp):
        if k != "mode":
            parts.append(f"{k}={qp[k]}")
    return ",".join(parts)


def sweep_for(cfg: VBenchConfig, engine: str, which: Literal["full", "fast"]) -> list[dict[str, Any]]:
    """Cấu hình (a) = default_query đứng đầu, rồi các cấu hình khai triển từ sweep (bỏ trùng)."""
    ec = cfg.engine(engine)
    sweep = ec.query_sweep if which == "full" else cfg.fast.query_sweep.get(engine, [])
    out: list[dict[str, Any]] = [dict(ec.default_query)]
    seen = {query_config_name(ec.default_query)}
    for item in sweep:
        for qp in expand_query_configs(item):
            n = query_config_name(qp)
            if n not in seen:
                seen.add(n)
                out.append(qp)
    return out
