"""Part 8 (phần ngày 1) — nạp arm YAML dạng đã giải đầy đủ.

Tham chiếu `@<cổng>`, `inherit`, kiểm "đổi đúng một nhóm trường" và `sb arms check` thuộc Part 8/12 (ngày 4): gặp `@`
hoặc `inherit` ở đây thì báo rõ thay vì đoán.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from . import paths
from .textbuild import VariantError, normalize_variant


class ArmError(ValueError):
    pass


class Arm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    stage: str
    parent: Optional[str]
    description: str
    text_variant: str
    model: str
    embedding_types: Literal["float", "int8"]
    query_input_type: Literal["query", "document"]
    retrieval: Literal["dense", "bm25", "hybrid", "dense+query_vec"]
    query_vec: Optional[dict[str, Any]]
    fusion: Optional[dict[str, Any]]
    bm25: dict[str, Any]
    filters: dict[str, Any]
    boost: dict[str, Any]
    dedupe_parent: bool
    query_preproc: dict[str, Any]
    cutoff: dict[str, Any]
    csls: Optional[dict[str, Any]]
    rerank: Optional[dict[str, Any]]
    fallback_bm25_only: bool
    phase: int
    composite: bool = False
    engine: Literal["bench", "app"] = "bench"     # app = cổng APP: chạy đúng SearchProducts của backend (app_adapter.py)
    app: Optional[dict[str, Any]] = None          # tham số production: cutoff, candidate_k, hybrid, normalize, rrf_k, lexical_*…


def _refs(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj] if obj.startswith("@") or "+@" in obj else []
    if isinstance(obj, dict):
        return [r for v in obj.values() for r in _refs(v)]
    if isinstance(obj, list):
        return [r for v in obj for r in _refs(v)]
    return []


def load_arm(arm_id: str, arms_dir: Path | None = None) -> Arm:
    p = (arms_dir or paths.ARMS_DIR) / f"{arm_id}.yaml"
    if not p.exists():
        raise ArmError(f"không có arm {arm_id} ({p}) — danh sách arm: docs/spec/bench/arms.md")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ArmError(f"{p.name}: YAML lỗi — {e}") from None
    if not isinstance(raw, dict):
        raise ArmError(f"{p.name}: phải là một mapping YAML")
    if "inherit" in raw or _refs(raw):
        raise ArmError(f"arm {arm_id} dùng tham chiếu @/inherit ({_refs(raw) or 'inherit'}) — giải tham chiếu là Part 12 (ngày 4)")
    try:
        arm = Arm.model_validate(raw)
        arm.text_variant = normalize_variant(arm.text_variant)
    except (ValidationError, VariantError) as e:
        raise ArmError(f"{p.name}: {e}") from None
    if arm.id != arm_id:
        raise ArmError(f"{p.name}: id {arm.id!r} ≠ tên file")
    if arm.phase > 1:
        raise ArmError(f"arm {arm_id} thuộc phase {arm.phase} — không chạy tuần này")
    return arm
