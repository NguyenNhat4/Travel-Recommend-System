"""`--vectors npy:<prefix>` (plan 2026-10-05 6.5): đọc vector đã embed của search bench, kiểm trước khi dùng."""
from __future__ import annotations

import json

import numpy as np
import pytest

from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.evaluation.recsys_bench.data_source import read_npy_vectors


def _write(tmp_path, E, ids, **meta):
    prefix = str(tmp_path / "vec_T3+R_e5-small")
    np.save(f"{prefix}.npy", np.asarray(E, dtype=np.float32))
    (tmp_path / "vec_T3+R_e5-small.ids.json").write_text(json.dumps(ids), encoding="utf-8")
    base = {"dim": np.asarray(E).shape[1], "cache_model": "intfloat/multilingual-e5-small",
            "text_builder_version": TEXT_BUILDER_VERSION}
    (tmp_path / "vec_T3+R_e5-small.meta.json").write_text(json.dumps({**base, **meta}), encoding="utf-8")
    return prefix


def _unit(n, d, seed=0):
    E = np.random.default_rng(seed).normal(size=(n, d))
    return E / np.linalg.norm(E, axis=1, keepdims=True)


def test_reads_ids_matrix_and_meta(tmp_path):
    E = _unit(3, 4)
    ids, got, meta = read_npy_vectors(_write(tmp_path, E, ["a", "b", "c"]))
    assert ids == ["a", "b", "c"] and got.dtype == np.float32 and got.shape == (3, 4)
    assert np.allclose(got, E, atol=1e-6) and meta["cache_model"] == "intfloat/multilingual-e5-small"


@pytest.mark.parametrize("case, match", [
    ("ids_count", "không khớp"),
    ("dup_ids", "trùng"),
    ("dim", "chiều"),
    ("text_builder", "text"),
    ("not_normalized", "L2"),
    ("no_model", "cache_model"),
])
def test_rejects_inconsistent_files(tmp_path, case, match):
    E, ids, meta = _unit(3, 4), ["a", "b", "c"], {}
    if case == "ids_count":
        ids = ["a", "b"]
    elif case == "dup_ids":
        ids = ["a", "a", "c"]
    elif case == "dim":
        meta["dim"] = 8
    elif case == "text_builder":
        meta["text_builder_version"] = "catalog-text-v1"
    elif case == "not_normalized":
        E = E * 2
    elif case == "no_model":
        meta["cache_model"] = ""
    with pytest.raises(ValueError, match=match):
        read_npy_vectors(_write(tmp_path, E, ids, **meta))


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_npy_vectors(str(tmp_path / "khong-co"))
