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


def test_gold_slice_quota_matches_target_and_min(cfg):
    """spec §1.2 + Part 5 `sb gold check`: tổng quota = target, mỗi slice ≥ min_per_slice."""
    from evaluation.search_bench.gold_schema import SLICES
    q = cfg.gold.slices
    assert sum(q.values()) == cfg.gold.target == 306                     # 13/10: 232 (gold_v6) + 40 + 12 + 8 + 6 + 8 (gold_v7)
    assert min(q.values()) >= cfg.gold.min_per_slice                     # mục tiêu mỗi slice ≥ tối thiểu (3)
    assert len(q) * cfg.gold.min_per_slice <= cfg.gold.minimum <= cfg.gold.target
    assert cfg.gold.minimum == 66 and len(q) == 22
    # quota và SLICES cùng tập, năm slice gold_v7 nối CUỐI (`sb gold split` seed RNG theo SLICES.index)
    assert set(q) == set(SLICES) and SLICES[-5:] == ("no_answer", "name_collision", "duration_only", "duration_stay", "slang_residual")


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


def test_test_config_overrides_only_what_it_lists(cfg, test_cfg):
    """Config riêng cho test chỉ thu nhỏ khoá được liệt kê; mọi khoá khác giống config thật; file thật giữ số của spec."""
    assert cfg.gold.min_per_slice == 3 and test_cfg.gold.min_per_slice == 1        # 28/09: 10 → 3
    assert test_cfg.gold.slices == cfg.gold.slices and test_cfg.gold.target == cfg.gold.target
    assert test_cfg.model_dump(exclude={"gold"}) == cfg.model_dump(exclude={"gold"})


def test_deep_merge():
    base = {"a": {"x": 1, "y": {"z": 2}}, "b": [1, 2]}
    assert sconfig.deep_merge(base, {"a": {"y": {"z": 3}}, "b": [9]}) == {"a": {"x": 1, "y": {"z": 3}}, "b": [9]}
    assert base == {"a": {"x": 1, "y": {"z": 2}}, "b": [1, 2]}              # không sửa bản gốc


def test_overrides_are_validated(tmp_path):
    bad = tmp_path / "o.yaml"
    bad.write_text("catalog:" + chr(10) + "  typo_key: 1" + chr(10), encoding="utf-8")
    with pytest.raises(ValidationError):
        sconfig.load_config(overrides_path=bad)
    bad.write_text("- 1" + chr(10), encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        sconfig.load_config(overrides_path=bad)


def test_gold_small_needs_the_test_config(cfg, test_cfg):
    """gold_small.jsonl (10 query / 9 slice) đạt min_per_slice của config test nhưng không đạt config thật (3) — lý do
    `gold check` trên fixture phải dùng config riêng cho test."""
    import json
    from collections import Counter
    from pathlib import Path
    rows = [json.loads(x) for x in (Path(__file__).parent / "fixtures" / "gold_small.jsonl").read_text(encoding="utf-8").splitlines()]
    per_slice = Counter(r["slice"] for r in rows)
    assert set(per_slice) <= set(cfg.gold.slices)
    assert min(per_slice.values()) >= test_cfg.gold.min_per_slice
    assert min(per_slice.values()) < cfg.gold.min_per_slice
