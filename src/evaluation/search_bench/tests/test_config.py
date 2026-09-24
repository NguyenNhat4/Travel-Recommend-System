from __future__ import annotations

import os

import pytest
import yaml
from pydantic import ValidationError

from evaluation.search_bench import config as sconfig
from evaluation.search_bench import paths


def test_config_loads_with_spec_numbers(cfg):
    assert cfg.embedding.input_type == {"document": "search_document", "query": "search_query"}
    assert cfg.model_cfg("cohere-v3").truncate == "NONE"
    assert cfg.model_cfg("cohere-v3").max_batch <= 96
    assert cfg.metrics.guards.p95_cache_miss_ms_max == 250                # NFR-PERF-01
    assert cfg.catalog.search_unit_variants == ["hotel_property", "flight_route", "attraction", "combo", "golf"]
    assert cfg.weaviate.url.startswith("http://127.0.0.1:")


def test_strict_section_rejects_unknown_key(tmp_path):
    raw = yaml.safe_load(paths.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["catalog"]["typo_key"] = 1
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValidationError):
        sconfig.load_config(p)


def test_truncate_end_is_rejected(tmp_path):
    raw = yaml.safe_load(paths.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["embedding"]["models"]["cohere-v3"]["truncate"] = "END"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValidationError):
        sconfig.load_config(p)


def test_unknown_model_message(cfg):
    with pytest.raises(ValueError, match="không có trong config"):
        cfg.model_cfg("nope")


def test_load_env_allow_list_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("COHERE_API_KEY=abc\nDATABASE_URL=postgres://x\nSBENCH_HOME=/tmp/x\nWEAVIATE_URL=http://y\n", encoding="utf-8")
    for k in ("COHERE_API_KEY", "DATABASE_URL", "SBENCH_HOME", "WEAVIATE_URL"):
        monkeypatch.delenv(k, raising=False)
    loaded = sconfig.load_env(env)
    assert sorted(loaded) == ["COHERE_API_KEY", "SBENCH_HOME"]
    assert "DATABASE_URL" not in os.environ and "WEAVIATE_URL" not in os.environ


def test_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("COHERE_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("COHERE_API_KEY", "from-env")
    assert sconfig.load_env(env) == []
    assert os.environ["COHERE_API_KEY"] == "from-env"


def test_data_dir_per_dataset(home):
    assert paths.data_dir("jsonl") == home.resolve() / "data"
    assert paths.data_dir("sample") == home.resolve() / "data" / "_sample"
    with pytest.raises(ValueError):
        paths.data_dir("prod")


def test_relative_sbench_home_resolves_against_repo(monkeypatch):
    monkeypatch.setenv("SBENCH_HOME", "bench_out/search/_x")
    assert paths.sbench_home() == (paths.repo_root() / "bench_out" / "search" / "_x").resolve()
