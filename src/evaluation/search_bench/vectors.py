"""Part 3 — file vector đã embed: data_dir/vec_<variant>_<model>[__query].npy + .ids.json + .meta.json.

Meta ghi items_sha256 và digest của text đã embed để `sb load` từ chối nạp vector cũ vào collection mới.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from evaluation.vector_bench.results import dump_json

from . import paths
from .textbuild import normalize_variant


class VectorsMissing(RuntimeError):
    pass


def tag_of(embedder_name: str) -> str:
    """Phần tuỳ chọn làm đổi vector (@int8, @noit…) của tên embedder → hậu tố file, để không đè file của chế độ mặc định.
    `@d<dim>` của v4 là mặc định của model nên không thành hậu tố."""
    opts = [o for o in embedder_name.split("@")[1:] if not o.startswith("d")]
    return "".join(f"__{o}" for o in opts)


def stem(dataset: str, variant: str, model: str, input_type: str, tag: str = "") -> Path:
    suffix = ("__query" if input_type == "query" else "") + tag
    return paths.data_dir(dataset) / f"vec_{normalize_variant(variant)}_{model}{suffix}"


def texts_digest(text_hashes: list[str]) -> str:
    return hashlib.sha256("\n".join(text_hashes).encode("utf-8")).hexdigest()


def write(dataset: str, variant: str, model: str, input_type: str, ids: list[str], vecs: np.ndarray, *, extra: dict,
          tag: str = "") -> dict:
    s = stem(dataset, variant, model, input_type, tag)
    np.save(s.with_suffix(".npy"), np.asarray(vecs, dtype=np.float32))
    dump_json(s.with_suffix(".ids.json"), ids)
    meta = {"file": s.with_suffix(".npy").name, "variant": normalize_variant(variant), "model": model, "input_type": input_type,
            "dataset": dataset, "n": len(ids), "dim": int(vecs.shape[1]) if len(vecs) else None,
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), **extra}
    dump_json(s.with_suffix(".meta.json"), meta)
    return meta


def read(dataset: str, variant: str, model: str, input_type: str) -> tuple[list[str], np.ndarray, dict]:
    s = stem(dataset, variant, model, input_type)
    files = [s.with_suffix(x) for x in (".npy", ".ids.json", ".meta.json")]
    if not all(f.exists() for f in files):
        raise VectorsMissing(f"chưa có {files[0].name} — chạy `sb --dataset {dataset} embed --variant {variant} --model {model}` trước")
    vecs = np.load(files[0])
    ids = json.loads(files[1].read_text(encoding="utf-8"))
    meta = json.loads(files[2].read_text(encoding="utf-8"))
    if len(ids) != len(vecs):
        raise VectorsMissing(f"{files[0].name}: {len(vecs)} vector nhưng {len(ids)} id — embed lại")
    return ids, vecs, meta
