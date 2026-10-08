"""Job `prewarm_llm_hypotheses`: nạp cache JSONL giả thuyết LLM cho câu confidence thấp, chạy lại = 0 lượt gọi (model giả)."""
import json

from src.backend.app.application.search.query_plan_llm import CachedQueryHypothesizer, HypothesisCache
from src.backend.app.domain.search.hypothesis import QueryHypothesis
from src.backend.app.infrastructure.llm import query_hypothesis as qh
from src.backend.jobs import prewarm_llm_hypotheses as job
from src.backend.tests.conftest import ROWS

Q = "đi chơi Nha Trang cuối tuần cho cả nhà 4 người giá rẻ dưới 5 triệu"


class Fake:
    version = f"gpt-4o-mini|{qh.PROMPT_VERSION}"
    calls = 0

    def hypothesize(self, query, context):
        Fake.calls += 1
        return QueryHypothesis(taxonomy="attraction", confidence=0.9)


def test_job_fills_cache_once_and_bench_replays_it(tmp_path, monkeypatch, capsys):
    products = tmp_path / "products.jsonl"
    products.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    gold.write_text("\n".join(json.dumps({"qid": i, "text": t}, ensure_ascii=False)
                              for i, t in enumerate([Q, "Vinpearl Resort Nha Trang", Q])), encoding="utf-8")
    cache = tmp_path / "hyp.jsonl"
    monkeypatch.setattr(qh, "build_query_hypothesizer", lambda **kw: Fake())
    args = ["--cache-path", str(cache), "--jsonl", str(gold), "--products-jsonl", str(products)]

    assert job.main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out) == {"queries": 3, "eligible": 1, "cached": 0, "toCall": 1, "dryRun": True}
    assert job.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["eligible"], out["called"], out["failed"]) == (1, 1, 0) and Fake.calls == 1
    assert job.main(args) == 0
    assert json.loads(capsys.readouterr().out)["skipped"] == 1 and Fake.calls == 1

    replay = CachedQueryHypothesizer(None, cache=HypothesisCache(path=cache), cache_only=True)
    engine = job.build_engine(job.index_from_products_jsonl(products))
    req = engine.llm_hypothesis_request(Q)
    hit, hyp = replay.peek(req.keys)
    assert hit and hyp.taxonomy == "attraction"
