"""Đọc `algos_v1.yaml` → cấu hình đã giải `inherit`, kiểm `requires`, dựng `AlgoArm` và tính `algosHash` (spec `recsys-algos-v1.md` §8).

Không import chéo `search_bench` (mẫu pydantic + `deep_merge` chép lại, 6 dòng). `implicit`/`scipy` chỉ được kiểm bằng
`importlib.util.find_spec` ở đây; import thật nằm trong `fit` của scorer.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..engine import config_hash
from . import SCORER_MODULES, get_scorer_class
from .funnel import MODES, POOLS, RERANKS, AlgoArm, CtxCache, FunnelCfg

#: khoá cấu trúc của một entry `algos:`; mọi khoá khác là tham số của scorer
META_KEYS = {"scorer", "inherit", "tier", "requires", "expect_equal_to", "status", "seeds", "estimate", "funnel"}
LIB_REQUIRES = {"implicit": ("implicit", "scipy")}


class CommonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matrix: dict[str, Any] = Field(default_factory=dict)
    funnel: dict[str, Any] = Field(default_factory=dict)


class AlgosFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    common: CommonConfig = Field(default_factory=CommonConfig)
    algos: dict[str, dict[str, Any]]


class AlgoSpec(BaseModel):
    """Một entry đã giải `inherit`."""
    model_config = ConfigDict(extra="forbid")
    name: str
    scorer: str
    tier: int = 1
    requires: str | None = None
    expect_equal_to: str | None = None
    status: str = "run"                                    # run | not_run
    seeds: list[int] | None = None
    estimate: dict[str, Any] | None = None
    funnel: dict[str, Any] = Field(default_factory=dict)   # ghi đè common.funnel cho riêng entry này
    params: dict[str, Any] = Field(default_factory=dict)


class AlgosConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    common: CommonConfig
    algos: dict[str, AlgoSpec]
    source: str

    def resolved(self) -> dict:
        """Dạng JSON ổn định để băm / ghi summary."""
        return {"version": self.version, "common": self.common.model_dump(),
                "algos": {n: a.model_dump(exclude={"name"}) for n, a in self.algos.items()}}


class AlgosError(ValueError):
    """Cấu hình thuật toán sai — thoát mã 1 trước khi chạm DB."""


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _resolve(name: str, raw: dict[str, dict[str, Any]], seen: tuple[str, ...] = ()) -> dict[str, Any]:
    if name not in raw:
        raise AlgosError(f"algos.{seen[-1] if seen else name}: inherit tới {name!r} không tồn tại")
    if name in seen:
        raise AlgosError(f"algos: inherit vòng {' → '.join(seen + (name,))}")
    entry = dict(raw[name])
    parent = entry.pop("inherit", None)
    if parent is None:
        return entry
    return deep_merge(_resolve(parent, raw, seen + (name,)), entry)


def load_algos(path: str | Path) -> AlgosConfig:
    p = Path(path)
    if not p.exists():
        raise AlgosError(f"--algos {p}: không tìm thấy file")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        parsed = AlgosFile.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — gom lỗi yaml/pydantic thành một thông báo
        raise AlgosError(f"--algos {p}: {exc}") from exc
    funnel = parsed.common.funnel
    for key in ("pool",):
        if key in funnel and funnel[key] not in POOLS:
            raise AlgosError(f"common.funnel.pool={funnel[key]!r}: chỉ {POOLS}")
    for r in rerank_list(funnel):
        if r not in RERANKS:
            raise AlgosError(f"common.funnel.rerank={r!r}: chỉ {RERANKS}")
    algos: dict[str, AlgoSpec] = {}
    for name in parsed.algos:
        merged = _resolve(name, parsed.algos)
        scorer = merged.get("scorer")
        if scorer not in SCORER_MODULES:
            raise AlgosError(f"algos.{name}: scorer {scorer!r} không có trong registry (có: {sorted(SCORER_MODULES)})")
        meta = {k: merged[k] for k in META_KEYS if k in merged}
        params = {k: v for k, v in merged.items() if k not in META_KEYS}
        try:
            algos[name] = AlgoSpec(name=name, params=params, **meta)
        except Exception as exc:  # noqa: BLE001
            raise AlgosError(f"algos.{name}: {exc}") from exc
        if algos[name].expect_equal_to and algos[name].expect_equal_to not in set(parsed.algos) | {"engine", "engine_nommr"}:
            raise AlgosError(f"algos.{name}.expect_equal_to={algos[name].expect_equal_to!r} không phải arm trong file hay engine/engine_nommr")
    return AlgosConfig(version=parsed.version, common=parsed.common, algos=algos, source=str(p))


def rerank_list(funnel: dict[str, Any]) -> list[str]:
    r = funnel.get("rerank", "none")
    return [str(x) for x in (r if isinstance(r, (list, tuple)) else [r])]


def select(cfg: AlgosConfig, only: list[str] | None = None, max_tier: int | None = None) -> list[AlgoSpec]:
    """Thứ tự yaml; `--only` lấy đúng tên (lỗi nếu không có); bỏ `status: not_run` và tier > max_tier khi không --only."""
    if only:
        missing = [n for n in only if n not in cfg.algos]
        if missing:
            raise AlgosError(f"--only {missing}: không có trong {cfg.source} (có: {sorted(cfg.algos)})")
        not_run = [n for n in only if cfg.algos[n].status != "run"]
        if not_run:
            raise AlgosError(f"--only {not_run}: status {[cfg.algos[n].status for n in not_run]} — chưa có cài đặt (spec §6.2 bpr_dest)")
        return [cfg.algos[n] for n in cfg.algos if n in set(only)]
    return [a for a in cfg.algos.values() if a.status == "run" and (max_tier is None or a.tier <= max_tier)]


def missing_libs(specs: list[AlgoSpec]) -> dict[str, list[str]]:
    """{tên algo: [lib thiếu]} cho các entry có `requires`."""
    out: dict[str, list[str]] = {}
    for a in specs:
        if not a.requires:
            continue
        libs = [m for m in LIB_REQUIRES.get(a.requires, (a.requires,)) if importlib.util.find_spec(m) is None]
        if libs:
            out[a.name] = libs
    return out


def lib_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for mod in ("numpy", "scipy", "implicit", "threadpoolctl"):
        try:
            out[mod] = importlib.import_module(mod).__version__
        except Exception:  # noqa: BLE001
            out[mod] = None
    return out


def funnel_cfg(cfg: AlgosConfig, spec: AlgoSpec, *, mode: str, rerank: str, pool: str | None = None, k: int | None = None) -> FunnelCfg:
    f = deep_merge(cfg.common.funnel, spec.funnel)
    return FunnelCfg(mode=mode, pool=pool or f.get("pool", "mask"), rerank=rerank, pool_k=int(f.get("pool_k", 200)),
                     popular_k=int(f.get("popular_k", 50)), k=int(k or f.get("k", 20)))


def build_arms(cfg: AlgosConfig, specs: list[AlgoSpec], *, mode: str, reranks: list[str], pool: str | None, k: int,
               ctx: CtxCache, vector_search) -> list[tuple[AlgoSpec, object, list[AlgoArm]]]:
    """Mỗi spec → (spec, scorer đã khởi tạo [một per seed], các AlgoArm theo rerank). Scorer của cùng seed dùng chung cho mọi rerank
    (fit một lần)."""
    if mode not in MODES:
        raise AlgosError(f"--mode {mode!r}: chỉ {MODES}")
    out = []
    for spec in specs:
        cls = get_scorer_class(spec.scorer)
        seeds = spec.seeds or [None]
        for seed in seeds:
            params = dict(spec.params)
            if seed is not None:
                params["seed"] = seed
            try:
                scorer = cls(**params)
            except TypeError as exc:
                raise AlgosError(f"algos.{spec.name}: tham số không hợp với {cls.__name__}: {exc}") from exc
            arms = [AlgoArm(spec.name, scorer, funnel_cfg(cfg, spec, mode=mode, rerank=r, pool=pool, k=k), ctx, vector_search, seed=seed)
                    for r in reranks]
            out.append((spec, scorer, arms))
    return out


def algos_hash(cfg: AlgosConfig, specs: list[AlgoSpec], engine_cfg: dict, *, mode: str, reranks: list[str], pool: str | None,
               k: int, libs: dict) -> str:
    return config_hash({"engine": engine_cfg, "common": cfg.common.model_dump(), "mode": mode, "reranks": reranks, "pool": pool, "k": k,
                        "algos": {a.name: a.model_dump(exclude={"name", "estimate"}) for a in specs}, "libs": libs})
