"""Part 9 (lite, fasttrack §4): G3 — ngữ nghĩa filter ở catalog (ALL-of, NOT, range, geo). G1, G2, G4–G7: hoãn.

G3: gates.g3.per_type query cho mỗi loại trong gates.g3.types, lấy từ queries.jsonl; thiếu thì sinh thêm bằng cùng generator
vào gate_queries.jsonl. Chạy với cấu hình (a) (default_query), k = gates.g3.k, đếm vi phạm (bỏ vùng biên).
Pass khi 0 vi phạm và không có UnsupportedFilter. Geo giả lập → pass_emulated. Thoát mã 2 nếu gate fail.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np

from .. import paths
from ..config import IndexConfig, VBenchConfig, query_config_name
from ..dataset.items import Dataset
from ..engines.base import QueryTimeout, StoreOptions, UnsupportedFilter
from ..engines.registry import make_store
from ..filters import boundary, mask
from ..querygen import generate_of_type
from ..results import now_iso, write_result

log = logging.getLogger("vbench.gates")


def gate_queries(ds: Dataset, cfg: VBenchConfig) -> list[dict]:
    """per_type query mỗi loại: ưu tiên queries.jsonl (dùng query vector của nó), thiếu → sinh thêm (vector mượn của query có sẵn)."""
    g3 = cfg.gates.g3
    out: list[dict] = []
    extra: list[dict] = []
    seen = {json.dumps(q["filter"], sort_keys=True, ensure_ascii=False) for q in ds.queries if q["filter"] is not None}
    for ftype in g3.types:
        have = [i for i, q in enumerate(ds.queries) if q["filter_type"] == ftype][: g3.per_type]
        for i in have:
            out.append({"qid": ds.queries[i]["qid"], "filter": ds.queries[i]["filter"], "filter_type": ftype, "qv_index": i})
        need = g3.per_type - len(have)
        if need > 0:
            gen = generate_of_type(ds.table, cfg, ftype, need, seen)
            for j, g in enumerate(gen):
                qv_index = int((len(extra) + j) % len(ds.queries))
                rec = {"qid": f"g-{ftype}-{j + 1:03d}", "filter": g["filter"], "filter_type": ftype, "qv_index": qv_index,
                       "n_match": g["n_match"]}
                out.append(rec)
                extra.append(rec)
    if extra:
        with open(ds.dir / paths.GATE_QUERIES, "w", encoding="utf-8", newline="\n") as fh:
            for r in extra:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


def violations(ds: Dataset, f: Any, hits: list[tuple[str, float]], geo_tol: float) -> tuple[int, int, int]:
    """(vi phạm, số kết quả không tính vùng biên, số id lạ)."""
    rows, unknown = [], 0
    for pid, _ in hits:
        r = ds.row_of.get(pid)
        if r is None:
            unknown += 1
        else:
            rows.append(r)
    if not rows:
        return unknown, unknown, unknown
    sub = ds.table.take(np.array(rows))
    ok = mask(f, sub)
    bnd = boundary(f, sub, geo_tol)
    keep = ~bnd
    return int((~ok & keep).sum()) + unknown, int(keep.sum()) + unknown, unknown


def g3_check(ds: Dataset, store, cfg: VBenchConfig, qp: dict) -> dict:
    g3 = cfg.gates.g3
    per_type: dict[str, dict] = {}
    unsupported: list[str] = []
    timeouts = 0
    for q in gate_queries(ds, cfg):
        t = per_type.setdefault(q["filter_type"], {"n": 0, "violations": 0, "results": 0, "unknown_ids": 0})
        t["n"] += 1
        try:
            hits = store.search(ds.query_vectors[q["qv_index"]], q["filter"], g3.k, qp)
        except UnsupportedFilter as e:
            unsupported.append(e.op)
            continue
        except QueryTimeout:
            timeouts += 1
            continue
        v, n, u = violations(ds, q["filter"], hits, cfg.groundtruth.geo_boundary_tol)
        t["violations"] += v
        t["results"] += n
        t["unknown_ids"] += u
    geo_mode = store.capabilities().geo
    total_v = sum(t["violations"] for t in per_type.values())
    if unsupported or total_v > 0:
        status = "fail"
    elif geo_mode == "emulated":
        status = "pass_emulated"
    else:
        status = "pass"
    return {"status": status, "query_config": query_config_name(qp), "k": g3.k, "per_type": per_type,
            "violations": total_v, "unsupported_ops": sorted(set(unsupported)), "timeouts": timeouts, "geo": geo_mode}


def run_gates(cfg: VBenchConfig, *, engine: str, run_id: str, only: str = "g3", scale: str = "catalog",
              index_name: str | None = None, index: IndexConfig | None = None, engine_limits: dict | None = None) -> int:
    started = now_iso()
    want = {x.strip().lower() for x in only.split(",") if x.strip()}
    ds = Dataset(scale)
    idx = index or cfg.engine_index(engine, index_name)
    store = make_store(cfg, engine, ds.dim, StoreOptions(timeout_ms=cfg.perf.timeout_ms))
    store.connect()
    gates: dict[str, Any] = {}
    try:
        qp_a = dict(cfg.engine(engine).default_query)          # cấu hình (a)
        for g in ("g1", "g2", "g4", "g5", "g6", "g7"):
            gates[g.upper()] = {"status": "skipped", "reason": "ngoài phạm vi fast-track (spec-fasttrack §4 Part 9)"}
        if "g3" in want:
            gates["G3"] = g3_check(ds, store, cfg, qp_a)
        ev, cv = store.server_version(), store.client_version()
    except Exception as e:  # noqa: BLE001
        log.exception("gate %s lỗi", engine)
        store.close()
        write_result(run_id, engine, scale, "gates", status="error", metrics=gates, started_at=started, error=repr(e),
                     index_config=idx.model_dump(), engine_limits=engine_limits)
        return 1
    store.close()
    failed = [k for k, v in gates.items() if v.get("status") == "fail"]
    write_result(run_id, engine, scale, "gates", status="fail" if failed else "ok", metrics=gates, started_at=started,
                 engine_version=ev, client_version=cv, index_config=idx.model_dump(), engine_limits=engine_limits)
    g = gates.get("G3")
    if g:
        print(f"G3 {engine}: {g['status']} · vi phạm {g['violations']} · unsupported {g['unsupported_ops'] or 'không'} · "
              + " · ".join(f"{t}: {v['n']} query / {v['results']} kết quả / {v['violations']} vi phạm" for t, v in g["per_type"].items()))
    return 2 if failed else 0
