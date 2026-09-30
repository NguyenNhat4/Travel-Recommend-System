"""Part 9 (30/09): `sb latency http` và `sb parity` — bộ câu cố định, đo qua httpx.MockTransport (không mạng), tóm tắt
hit/miss theo embedCache, cổng parity. Mode weaviate của parity chỉ kiểm phần so sánh (engine giả); phần nạp ProductVM
từ Cloud cần Weaviate + tunnel → chạy tay."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from evaluation.search_bench import latency as L, parity as P, paths
from evaluation.search_bench.gold_schema import read_gold_jsonl

LAT_Q = paths.CONFIG_DIR / "latency_queries.yaml"
PAR_Q = paths.CONFIG_DIR / "parity_queries.yaml"
SLICES = {"dest_type", "audience_style", "amenity_single", "amenity_multi", "amenity_negation", "amenity_offtaxonomy",
          "parent_child", "named_entity", "no_diacritics", "abbrev_typo", "multi_constraint", "cross_vertical", "out_of_catalog"}


def _gold_texts() -> set[str]:
    return {L.canonical(r.text) for r in read_gold_jsonl(paths.GOLD_JSONL) if r.status == "active"}


def test_latency_queries_prewarmed_in_gold_and_cold_outside():
    g = L.load_queries(LAT_Q)
    gold = _gold_texts()
    assert len(g["prewarmed"]) == 25 and len(g["cold"]) == 25
    assert set(g["prewarmed"]) <= gold, sorted(set(g["prewarmed"]) - gold)
    assert not set(g["cold"]) & gold
    assert len(set(g["prewarmed"])) == 25 and len(set(g["cold"])) == 25


def test_parity_queries_cover_every_slice_and_required_texts():
    qs = P.load_parity_queries(PAR_Q)
    assert len(qs) == 20 and {q.slice for q in qs} == SLICES
    texts = {q.text for q in qs}
    assert set(P.REQUIRED_TEXTS) <= texts
    gold = _gold_texts()
    assert all(q.text in gold for q in qs if q.qid) and all(q.text not in gold for q in qs if not q.qid)


def test_load_queries_rejects_overlap(tmp_path):
    p = tmp_path / "q.yaml"
    p.write_text("prewarmed: ['a  b']\ncold: ['a b']\n", encoding="utf-8")
    with pytest.raises(L.LatencyError, match="cả hai nhóm"):
        L.load_queries(p)


class _Server:
    """Giả /search: lần gặp đầu của một câu là miss (embed 400 ms), sau đó hit (embed 3 ms); top-10 cố định theo câu;
    một câu ném 503 để kiểm ghi lỗi."""

    def __init__(self, *, with_cache: bool = True, ids_of=None):
        self.seen: set[str] = set()
        self.with_cache = with_cache
        self.calls: list[str] = []
        self.ids_of = ids_of or (lambda q: [f"{abs(hash(q)) % 97}-{i}" for i in range(10)])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        self.calls.append(q)
        if q == "boom":
            return httpx.Response(503, json={"error": {"code": "SEARCH_UNAVAILABLE"}})
        miss = q not in self.seen
        self.seen.add(q)
        embed = 400 if miss else 3
        diag = {"latencyMs": embed + 40, "searchMode": "HYBRID_CANDIDATE_SCORE",
                "stageMs": {"normalize": 1, "embed": embed, "dense": 20, "lexical": 10, "fuse": 5, "hydrate": 2}}
        if self.with_cache:
            diag["embedCache"] = "miss" if miss else "hit"
        return httpx.Response(200, json={"results": [{"productId": pid} for pid in self.ids_of(q)][: int(request.url.params["limit"])],
                                         "total": 10, "diagnostics": diag})


def test_measure_and_summarize_split_hit_miss_and_drop_first():
    srv = _Server()
    client = httpx.Client(transport=httpx.MockTransport(srv))
    groups = {"prewarmed": ["a", "b"], "cold": ["c", "boom"]}
    samples = L.measure("http://x", groups, runs=3, limit=10, timeout_s=5, client=client)
    assert len(samples) == 12 and srv.calls[:4] == ["a", "b", "c", "boom"]
    s = L.summarize(samples, drop_first=True)
    assert s["n_ok"] == 9 and s["n_error"] == 3 and s["errors"][0]["text"] == "boom" and "503" in s["errors"][0]["error"]
    # lượt 1 bị bỏ khỏi bảng → embed p95 là số hit
    assert s["by_group"]["all"]["latency_ms"]["n"] == 6 and s["by_group"]["all"]["stage_ms"]["embed"]["p95"] == 3
    assert s["by_group"]["cold"]["latency_ms"]["n"] == 2
    # miss = lần gặp đầu (lượt 1) của 3 câu OK; hit = 6 mẫu lượt 2–3
    assert s["by_cache"]["miss"]["embed_ms"]["n"] == 3 and s["by_cache"]["miss"]["embed_ms"]["p50"] == 400
    assert s["by_cache"]["hit"]["embed_ms"]["n"] == 6 and s["by_cache"]["hit"]["latency_ms"]["p50"] == 43
    assert s["top10_stable"] == 3 and s["top10_total"] == 3 and s["embed_cache_seen"] == ["hit", "miss"]
    assert s["search_modes"] == ["HYBRID_CANDIDATE_SCORE"]
    # không drop_first → 9 mẫu, không có embedCache thì by_cache rỗng
    assert L.summarize(samples, drop_first=False)["by_group"]["all"]["latency_ms"]["n"] == 9
    s2 = L.summarize(L.measure("http://x", groups, runs=1, limit=10, timeout_s=5,
                               client=httpx.Client(transport=httpx.MockTransport(_Server(with_cache=False)))), drop_first=True)
    assert s2["by_cache"] == {} and s2["embed_cache_seen"] == [] and s2["by_group"]["all"]["latency_ms"]["n"] == 3   # 1 lượt: giữ


def test_write_latency_and_cli(home, monkeypatch):
    from evaluation.search_bench.__main__ import app
    srv = _Server()
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real(transport=httpx.MockTransport(srv)))
    r = CliRunner().invoke(app, ["--run-id", "t1", "latency", "http", "--base-url", "http://fake", "--runs", "2", "--label", "cache-off"])
    assert r.exit_code == 0, r.output
    p = paths.run_dir("t1", create=False) / "latency-cache-off.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["label"] == "cache-off" and d["summary"]["n_samples"] == 100 and len(d["samples"]) == 100
    assert d["summary"]["by_cache"]["miss"]["embed_ms"]["n"] == 50 and d["summary"]["top10_stable"] == 50
    assert "prewarmed" in r.output and "cold" in r.output
    # thiếu base-url → exit 2
    monkeypatch.delenv("SBENCH_CLOUD_BASE_URL", raising=False)
    assert CliRunner().invoke(app, ["latency", "http"]).exit_code == 2


def test_parity_http_verdict_and_mismatch_report():
    a = _Server(ids_of=lambda q: [f"{q}-{i}" for i in range(10)])
    b = _Server(ids_of=lambda q: ([f"{q}-{i}" for i in range(10)] if q != "KS biển tại NT" else [f"z-{i}" for i in range(10)]))

    def route(request: httpx.Request) -> httpx.Response:
        return (a if request.url.host == "a" else b)(request)
    client = httpx.Client(transport=httpx.MockTransport(route))
    qs = P.load_parity_queries(PAR_Q)
    rows = P.parity_http("http://a", "http://b", qs, k=10, timeout_s=5, client=client)
    assert len(rows) == 20 and sum(r.top1_same for r in rows) == 19
    res = P.verdict(rows, k=10, top1_min=18, overlap_min=8)
    assert res["pass"] is False and res["overlap_min_seen"] == 0 and res["mismatch"][0]["text"] == "KS biển tại NT"
    assert P.verdict(rows, k=10, top1_min=18, overlap_min=0)["pass"] is True
    assert rows[0].a_diag["searchMode"] == "HYBRID_CANDIDATE_SCORE"


def test_parity_engines_records_errors_and_write(home):
    qs = P.load_parity_queries(PAR_Q)[:3]

    def sa(q):
        return ["p1", "p2", "p3"], [0.9, 0.8, 0.7], {"total": 3}

    def sb(q):
        if q == qs[1].text:
            raise RuntimeError("weaviate down")
        return ["p1", "p3", "p2"], [0.9, 0.8, 0.7], {"total": 3}
    rows = P.parity_engines(sa, sb, qs)
    assert rows[1].error and "weaviate down" in rows[1].error and rows[0].top1_same and rows[0].overlap(10) == 3
    res = P.verdict(rows, k=10, top1_min=2, overlap_min=3)
    assert res["pass"] is False and res["n_error"] == 1 and any("error" in m for m in res["mismatch"])
    p = P.write_parity("t2", mode="weaviate", rows=rows, result=res, meta={"arm": "APP.hybrid_norm"})
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["mode"] == "weaviate" and d["rows"][0]["overlap"] == 3 and d["verdict"]["pass"] is False


def test_parity_row_top1_semantics():
    assert P.ParityRow("q", "s", [], []).top1_same is True                 # cả hai rỗng (out_of_catalog) = trùng
    assert P.ParityRow("q", "s", ["a"], []).top1_same is False
    assert P.ParityRow("q", "s", ["a", "b"], ["a", "c"]).overlap(10) == 1


def test_app_adapter_context_defaults_to_bench_weaviate(cfg):
    from evaluation.search_bench import app_adapter as A
    ctx = A.AppContext(cfg=cfg, dataset="sample", cat=None)
    assert ctx.weaviate_url is None and ctx.api_key == "" and ctx.collection == A.PRODUCT_BENCH
    assert hasattr(A, "build_vm_catalog") and hasattr(A, "parity_contexts") and hasattr(A, "load_collection")
