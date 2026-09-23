"""`vb fast-report` — bảng + quy tắc chốt spec-fasttrack §6 (viết trước khi chạy) → runs/<run>/fast_report.md + fast_decision.json.

Ngưỡng đọc từ config (không đặt số mới):
  A1 ≥ quality.a1_pass (1M, min 4 bucket, cấu hình b) · A3 = 1 · B1 P99 @ perf.b1_rate_qps ≤ scoring.metrics.B1.pass.1m ·
  B3 ≤ scoring.metrics.B3.pass.1m (ghi nhận) · C1 ≤ scoring.metrics.C1.pass.1m (ghi nhận).
Quy tắc:
1. Trượt G3 hoặc A3 < 1 → loại.
2. pgvector đạt A1 và B1 ở 1M → chốt pgvector.  3. Không thì pgvectorscale đạt → chốt.  4. Không thì Qdrant đạt → chốt.
5. Không engine nào đạt ở 1M → chốt pgvector cho quy mô hiện tại; chạy spec.md đầy đủ (thêm Milvus, Weaviate) trước ~200k vector.
Đọc số: CI 95% của P99 hai engine chồng nhau → hoà; hoà → pgvector. Số 1M là dữ liệu KHUẾCH ĐẠI — chỉ dùng khi qua kiểm LID.
"""
from __future__ import annotations

import json
from typing import Any

from . import paths
from .config import VBenchConfig
from .results import dump_json, git_commit, host_info, now_iso, read_result
from .runners.perf import ci_overlap

BIG = "1m"


def _metric(cfg: VBenchConfig, name: str, scale: str) -> float | None:
    m = (cfg.scoring.model_extra or {}).get("metrics", {}).get(name, {})
    p = m.get("pass")
    return p.get(scale) if isinstance(p, dict) else p


def collect(cfg: VBenchConfig, run_id: str, engine: str, big: str) -> dict[str, Any]:
    r: dict[str, Any] = {"engine": engine}
    fast = paths.run_dir(run_id, create=False) / engine / "fast.json"
    r["fast"] = json.loads(fast.read_text(encoding="utf-8")) if fast.exists() else None
    g = read_result(run_id, engine, "catalog", "gates")
    r["G3"] = (g or {}).get("metrics", {}).get("G3")
    for scale in ("catalog", big):
        q = read_result(run_id, engine, scale, "quality")
        qm = (q or {}).get("metrics", {})
        r[f"quality_{scale}"] = {"status": (q or {}).get("status"), "A1": qm.get("A1"), "A3": qm.get("A3"), "config_b": qm.get("config_b"),
                                 "a1_fail": qm.get("a1_fail"), "A4": qm.get("A4"),
                                 "a1_by_bucket_b": next((c["a1_by_bucket"] for c in qm.get("configs", []) if c["name"] == qm.get("config_b")), None),
                                 "configs": [{"name": c["name"], "a1_min": c["a1_min"], "A3": c["A3"], "p99": c["latency_ms"]["p99"],
                                              "status": c["status"]} for c in qm.get("configs", [])]} if q else None
        ld = read_result(run_id, engine, scale, "load")
        r[f"load_{scale}"] = (ld or {}).get("metrics") if ld and ld.get("status") == "ok" else None
        res = paths.step_dir(run_id, engine, scale, create=False) / "resources.json"
        r[f"C1_{scale}"] = json.loads(res.read_text(encoding="utf-8"))["C1"] if res.exists() else None
        r[f"engine_version_{scale}"] = (ld or q or {}).get("engine_version")
    for scale in ("catalog", big):
        q = read_result(run_id, engine, scale, "quality")
        qm = (q or {}).get("metrics", {})
        cb = qm.get("config_b")
        rate = next((c.get("plan_uses_index_rate") for c in qm.get("configs", []) if c["name"] == cb), None)
        ld = r.get(f"load_{scale}") or {}
        idx_built = ld.get("indexed_vectors_count")          # Qdrant: 0 = chưa build HNSW (segment dưới indexing_threshold)
        if idx_built is not None and ld.get("points_count"):
            r[f"ann_used_{scale}"] = f"{idx_built}/{ld['points_count']} vector đã index"
        elif rate is not None:
            r[f"ann_used_{scale}"] = f"plan dùng index {rate:.0%} (query có filter)"
        else:
            r[f"ann_used_{scale}"] = "—"
    p = read_result(run_id, engine, big, "perf")
    pm = (p or {}).get("metrics", {})
    lv = {x["rate_qps"]: x for x in pm.get("levels", [])}
    r["perf"] = {"status": (p or {}).get("status"), "levels": lv, "B1": pm.get("B1"), "transport_floor": pm.get("transport_floor"),
                 "query_config": pm.get("query_config")} if p else None
    return r


def evaluate_rules(cfg: VBenchConfig, rows: dict[str, dict], lid_ok: bool | None, big: str,
                   block_reason: str | None = None, catalog_fake: bool = False) -> dict[str, Any]:
    """Mỗi engine một trạng thái: pass | fail | unmeasured. Đi theo decision_order: pass → chốt; fail → xét engine sau;
    unmeasured → CHƯA CHỐT (không được nhảy qua engine ưu tiên cao hơn chưa đo đủ)."""
    a1_pass = cfg.quality.a1_pass
    b1_thr = _metric(cfg, "B1", big)
    b1_rate = cfg.perf.b1_rate_qps
    baseline = (cfg.decision.model_extra or {}).get("baseline", "pgvector")
    reasons: list[str] = []
    excluded: dict[str, str] = {}
    state: dict[str, str] = {}
    for e in cfg.fast.decision_order:
        r = rows.get(e)
        if r is None:
            state[e] = "unmeasured"
            reasons.append(f"{e}: chưa chạy trong run này")
            continue
        g3 = (r.get("G3") or {}).get("status")
        a3s = [x["A3"] for x in (r.get("quality_catalog"), r.get(f"quality_{big}")) if x and x.get("A3") is not None]
        if g3 == "fail":
            excluded[e] = "G3 = fail"
        elif any(a < 1.0 for a in a3s):
            excluded[e] = f"A3 = {min(a3s):.4f} < 1"
        qb = r.get(f"quality_{big}") or {}
        a1 = qb.get("A1")
        p99 = ((r.get("perf") or {}).get("B1") or {}).get("p99_ms")
        ok_a1 = a1 is not None and a1 >= a1_pass and not qb.get("a1_fail")
        ok_b1 = p99 is not None and b1_thr is not None and p99 <= b1_thr
        if e in excluded or (a1 is not None and not ok_a1) or (p99 is not None and not ok_b1):
            state[e] = "fail"
        elif ok_a1 and ok_b1 and g3 in ("pass", "pass_emulated"):
            state[e] = "pass"
        else:
            state[e] = "unmeasured"
        a1_s = "—" if a1 is None else f"{a1:.4f}"
        p99_s = "—" if p99 is None else f"{p99:.1f} ms"
        reasons.append(f"{e}: G3 {g3 or 'chưa chạy'}; A1({big}, b) = {a1_s} ({'đạt' if ok_a1 else 'không đạt'} ≥ {a1_pass}); "
                       f"B1 P99 @{b1_rate:g} QPS = {p99_s} ({'đạt' if ok_b1 else 'không đạt'} ≤ {b1_thr} ms)"
                       + (f"; LOẠI: {excluded[e]}" if e in excluded else "") + f" → {state[e]}")
    winner, rule, undecided = None, None, False
    if catalog_fake:
        undecided = True
        reasons.append("Catalog embed bằng backend fake → chỉ thử khung, KHÔNG chốt.")
    elif block_reason or lid_ok is False:
        rule = 5
        reasons.append(f"Số 1M không dùng để chốt ({block_reason or 'dữ liệu khuếch đại trượt kiểm LID/gần trùng'}) → quy tắc 5.")
    else:
        for i, e in enumerate(cfg.fast.decision_order):
            st = state.get(e, "unmeasured")
            if st == "pass":
                winner, rule = e, 2 + i
                break
            if st == "unmeasured":
                undecided = True
                reasons.append(f"{e} chưa đo đủ (thiếu G3 / A1 / B1 ở {big}) → chưa áp được quy tắc {2 + i}; "
                               f"chạy lại `vb fast --engines {e}`.")
                break
        if winner is None and not undecided:
            rule = 5
    if rule == 5 and winner is None:
        winner = baseline
        reasons.append("Không engine nào đạt ở 1M (hoặc số 1M không dùng được) → chốt pgvector cho quy mô hiện tại "
                       "(5k → 100k vector, dựa trên số ở catalog); chạy spec.md đầy đủ, thêm Milvus và Weaviate, TRƯỚC khi "
                       "catalog vượt ~200k vector.")
    # "Đọc số cho đúng": CI 95% của P99 hai engine chồng nhau → hoà; hoà → pgvector
    ties = []
    b0 = ((rows.get(baseline) or {}).get("perf") or {}).get("B1") or {}
    for e in rows:
        if e == baseline:
            continue
        be = ((rows[e].get("perf") or {}).get("B1") or {})
        if ci_overlap(b0.get("p99_ci95"), be.get("p99_ci95")):
            ties.append(f"{baseline} ~ {e} (CI P99 {b0.get('p99_ci95')} và {be.get('p99_ci95')} chồng nhau → hoà)")
    tie_override = False
    if rule in (3, 4) and winner and baseline in rows and baseline not in excluded:
        qb0 = rows[baseline].get(f"quality_{big}") or {}
        a1_0 = qb0.get("A1")
        base_ok_a1 = a1_0 is not None and a1_0 >= a1_pass and not qb0.get("a1_fail")
        ciw = (((rows[winner].get("perf") or {}).get("B1")) or {}).get("p99_ci95")
        if base_ok_a1 and ci_overlap(b0.get("p99_ci95"), ciw):
            reasons.append(f"{baseline} đạt A1; CI P99 của {baseline} {b0.get('p99_ci95')} và {winner} {ciw} chồng nhau → hoà "
                           f"→ {baseline} (fasttrack §6 'Đọc số cho đúng').")
            winner, tie_override = baseline, True
    return {"winner": winner, "rule_applied": rule, "undecided": undecided, "tie_override": tie_override, "reasons": reasons,
            "excluded": excluded, "state": state, "p99_ties": ties, "block_reason": block_reason,
            "thresholds": {"A1": a1_pass, "A3": 1.0, "B1_p99_ms": b1_thr, "B1_rate_qps": b1_rate,
                           "B3_minutes": _metric(cfg, "B3", big), "C1_gb": _metric(cfg, "C1", big)}}


def _f(x, fmt="{:.4f}", none="—"):
    return none if x is None else fmt.format(x)


def render(cfg: VBenchConfig, run_id: str, rows: dict[str, dict], dec: dict, stats_big: dict | None, big: str) -> str:
    th = dec["thresholds"]
    engines = list(rows)
    L: list[str] = []
    L.append(f"# Fast-track chọn vector DB — run `{run_id}`\n")
    hi = host_info()
    L.append(f"- Ngày: {now_iso()} · git `{git_commit()}` · máy: {hi.get('cpu')}, {hi.get('vcpus')} vCPU, RAM {hi.get('ram_gb')} GB, "
             f"{hi.get('os')}, Docker {hi.get('docker')}")
    L.append(f"- Giới hạn engine: {cfg.fast.engine_limits.cpus} CPU / {cfg.fast.engine_limits.mem} · Postgres env: {dict(cfg.fast.pg_env)}")
    cat = json.loads((paths.data_dir('catalog', create=False) / paths.EMBED_META).read_text(encoding='utf-8')) \
        if (paths.data_dir('catalog', create=False) / paths.EMBED_META).exists() else {}
    L.append(f"- Catalog: {cat.get('n')} search unit, model {cat.get('model')} ({cat.get('backend')}), sha {str(cat.get('vectors_sha256'))[:12]}")
    if stats_big:
        ck = stats_big.get("checks", {})
        L.append(f"- {big}: {stats_big.get('n')} vector **{stats_big.get('vectors')}** — sigma {stats_big.get('sigma')} · LID ratio "
                 f"{_f(ck.get('lid_ratio'), '{:.3f}')} (cần {cfg.fast.amplify.lid_ratio}) → {'PASS' if ck.get('lid_pass') else 'FAIL'} · "
                 f"gần trùng {_f(ck.get('near_dup_rate'), '{:.4%}')} → {'PASS' if ck.get('near_dup_pass') else 'FAIL'}")
        L.append(f"  - {stats_big.get('note', '')}")
    L.append("")
    L.append("## Bảng metric (fasttrack §6)\n")
    L.append("| Metric | Ngưỡng | " + " | ".join(engines) + " |")
    L.append("|---|---|" + "---|" * len(engines))

    def row(name, thr, fn):
        L.append(f"| {name} | {thr} | " + " | ".join(fn(rows[e]) for e in engines) + " |")
    row("G3 ngữ nghĩa filter (catalog)", "0 vi phạm", lambda r: (r.get("G3") or {}).get("status", "—"))
    row("A3 precision (catalog)", "= 1,0", lambda r: _f((r.get("quality_catalog") or {}).get("A3")))
    row(f"A3 precision ({big})", "= 1,0", lambda r: _f((r.get(f"quality_{big}") or {}).get("A3")))
    row("A1 min bucket (catalog, b)", "tham khảo", lambda r: _f((r.get("quality_catalog") or {}).get("A1")))
    row(f"A1 min bucket ({big}, b)", f"≥ {th['A1']}", lambda r: _f((r.get(f"quality_{big}") or {}).get("A1")))
    row(f"cấu hình (b) ({big})", "", lambda r: f"`{(r.get(f'quality_{big}') or {}).get('config_b') or '—'}`")

    def p99(r, rate):
        lv = ((r.get("perf") or {}).get("levels") or {}).get(rate)
        return "—" if not lv else f"{lv['p99']:.1f} [{lv['p99_ci95'][0]:.1f}, {lv['p99_ci95'][1]:.1f}]" + \
            (f" · timeout {lv['timeouts']}" if lv["timeouts"] else "")
    rates = list(cfg.fast.perf.rates_qps)
    row(f"B1 P99 ms @{rates[0]:g} QPS ({big}) [CI95]", f"≤ {th['B1_p99_ms']}", lambda r: p99(r, rates[0]))
    for rt in rates[1:]:
        row(f"B2 P99 ms @{rt:g} QPS ({big}) [CI95]", "ghi nhận", lambda r, rt=rt: p99(r, rt))
    row(f"B3 load + build ({big}, phút)", f"≤ {th['B3_minutes']} (ghi nhận)", lambda r: _f((r.get(f"load_{big}") or {}).get("b3_minutes"), "{:.1f}"))
    row(f"C1 RAM đỉnh ({big}, GB)", f"≤ {th['C1_gb']} (ghi nhận)", lambda r: _f((r.get(f"C1_{big}") or {}).get("mem_peak_gb"), "{:.2f}"))
    row("index ANN thật sự dùng (catalog)", "đọc A1 theo cột này", lambda r: r.get("ann_used_catalog", "—"))
    row(f"index ANN thật sự dùng ({big})", "đọc A1 theo cột này", lambda r: r.get(f"ann_used_{big}", "—"))
    row("count exact (catalog)", "tham khảo", lambda r: _f(((r.get("quality_catalog") or {}).get("A4") or {}).get("count_exact_rate"), "{:.2f}"))
    row("sàn transport P50/P99 ms", "tham khảo", lambda r: "—" if not (r.get("perf") or {}).get("transport_floor") else
        "{:.2f} / {:.2f}".format(r["perf"]["transport_floor"]["p50_ms"], r["perf"]["transport_floor"]["p99_ms"]))
    row("trạng thái fast", "", lambda r: f"{(r.get('fast') or {}).get('status', '—')} ({(r.get('fast') or {}).get('minutes', '—')} phút)")
    L.append("")
    L.append("## Kết luận\n")
    if dec.get("undecided"):
        L.append("**CHƯA CHỐT** — xem lý do bên dưới.\n")
    else:
        L.append(f"**Chốt: {dec['winner']}** (quy tắc {dec['rule_applied']} của fasttrack §6"
                 + ("; hoà CI P99 → pgvector" if dec.get("tie_override") else "") + ").\n")
    for s in dec["reasons"]:
        L.append(f"- {s}")
    if dec["p99_ties"]:
        L.append("- Đọc số P99: " + "; ".join(dec["p99_ties"]))
    L.append("\n## Ghi chú đọc số\n")
    L.append("- P99 đo bằng tải open-loop, latency tính từ thời điểm LẼ RA gửi; timeout tính vào phân vị; không tính embed query.")
    L.append("- A1 chỉ là số của ANN khi cột 'index ANN thật sự dùng' cho thấy index được dùng: Qdrant không build HNSW khi mỗi "
             "segment dưới indexing_threshold (A1 khi đó là brute force), còn planner Postgres có thể chọn plan exact cho query "
             "có filter (plan_uses_index_rate).")
    L.append("- `perf.json` tách `status_split` (ok_in_budget · ok_but_late · engine_timeout · skipped_late) và `uncapped_ms`: "
             "P99 trong bảng bị kẹt trần ở timeout, không phải latency thật khi engine quá tải.")
    if (stats_big or {}).get("vectors") == "amplify":
        L.append(f"- Mọi số {big} là trên dữ liệu khuếch đại từ catalog thật (fasttrack §3): chỉ dùng cho hiệu năng và hành vi filter.")
    else:
        L.append(f"- Dữ liệu {big}: {(stats_big or {}).get('vectors', 'không rõ')} — không dùng để chốt.")
    L.append("- Client chạy trên Windows qua port-forward của Docker Desktop: 'sàn transport' là chi phí một request rỗng — phần "
             "còn lại của latency là của engine.")
    L.append("\n## A1 theo bucket (cấu hình b)\n")
    for e in engines:
        for scale in ("catalog", big):
            qb = rows[e].get(f"quality_{scale}") or {}
            if qb.get("a1_by_bucket_b"):
                L.append(f"- {e} / {scale}: " + ", ".join(f"{b} {v:.4f}" for b, v in qb["a1_by_bucket_b"].items()))
    L.append("\n## Các cấu hình đã sweep\n")
    for e in engines:
        for scale in ("catalog", big):
            qb = rows[e].get(f"quality_{scale}") or {}
            for c in qb.get("configs") or []:
                L.append(f"- {e} / {scale} · `{c['name']}` · A1min {_f(c['a1_min'])} · A3 {_f(c['A3'])} · P99 1 client "
                         f"{_f(c['p99'], '{:.1f}')} ms · {c['status']}")
    return "\n".join(L) + "\n"


def _big_scale(cfg: VBenchConfig, run_id: str) -> str:
    """Scale lớn nhất thật sự đã chạy trong run (fast.json của engine), không thì theo fast.scales."""
    for e in cfg.fast.decision_order:
        fj = paths.run_dir(run_id, create=False) / e / "fast.json"
        if fj.exists():
            sc = json.loads(fj.read_text(encoding="utf-8")).get("scales") or []
            if sc:
                return sc[-1]
    return BIG if BIG in cfg.fast.scales else cfg.fast.scales[-1]


def run_fast_report(cfg: VBenchConfig, *, run_id: str) -> int:
    big = _big_scale(cfg, run_id)
    rows = {e: collect(cfg, run_id, e, big) for e in cfg.fast.decision_order
            if (paths.run_dir(run_id, create=False) / e).exists()}
    if not rows:
        print(f"run {run_id} chưa có kết quả engine nào")
        return 1
    sp = paths.data_dir(big, create=False) / paths.STATS
    stats_big = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
    em = paths.data_dir("catalog", create=False) / paths.EMBED_META
    catalog_fake = bool(em.exists() and json.loads(em.read_text(encoding="utf-8")).get("backend") == "fake")
    src = (stats_big or {}).get("vectors")
    block = None
    lid_ok: bool | None = None
    if src is None:
        block = f"không có data/{big}/stats.json"
    elif src == "fake":
        block = f"dữ liệu {big} là vector fake"
    elif src == "amplify":
        lid_ok = bool(stats_big.get("checks_pass"))
    shas = [(read_result(run_id, e, big, st) or {}).get("dataset", {}).get("vectors_sha256")
            for e in rows for st in ("quality", "perf")]
    if stats_big and any(v not in (None, stats_big.get("vectors_sha256")) for v in shas):
        block = f"kết quả run đo trên dữ liệu {big} khác data/{big} hiện tại (sha256 lệch)"
    dec = evaluate_rules(cfg, rows, lid_ok, big, block_reason=block, catalog_fake=catalog_fake)
    md_text = render(cfg, run_id, rows, dec, stats_big, big)
    out = paths.run_dir(run_id) / "fast_report.md"
    out.write_text(md_text, encoding="utf-8")
    dump_json(paths.run_dir(run_id) / "fast_decision.json",
              {**dec, "run_id": run_id, "git_commit": git_commit(), "generated_at": now_iso(),
               "catalog_embed_backend": "fake" if catalog_fake else "real",
               "data_big": {"scale": big, "vectors": (stats_big or {}).get("vectors"), "checks_pass": lid_ok,
                            "vectors_sha256": (stats_big or {}).get("vectors_sha256")},
               "engine_versions": {e: r.get(f"engine_version_{big}") or r.get("engine_version_catalog") for e, r in rows.items()}})
    print(md_text)
    print(f"→ {out}")
    return 0
