"""Nạp sẵn cache giả thuyết LLM của query plan /search (SEARCH_LLM_FALLBACK; contract 1.17.0 `queryPlan.llm`) vào file JSONL.

Gọi model THẬT (cần API key của provider, ví dụ OPENAI_API_KEY trong .env) cho từng câu có plan rule `confidence <
--min-confidence` (mặc định 1.0 = mọi câu có ít nhất một lý do fallback), dùng đúng khoá cache + prompt mà backend dùng lúc request
(`SearchProducts.llm_hypothesis_request`). Câu đã có trong file thì bỏ qua (chạy lại = 0 lượt gọi), trừ `--force`. Backend / bench
đọc file này qua SEARCH_LLM_FALLBACK_CACHE_PATH; `SEARCH_LLM_FALLBACK_CACHE_ONLY=true` → phát lại tất định, không gọi API.

Catalog (để dựng gazetteer / từ vựng như lúc phục vụ) lấy từ một trong hai nguồn:
  --products-jsonl PATH  products.jsonl dạng CDP (snapshot catalog, nguồn của bench…) — không cần DB
  --database-url DSN     catalog search unit của Postgres (role vota_app; mặc định DATABASE_URL của .env)
Mỗi dòng cache có khoá chính theo câu đã chuẩn hoá VÀ khoá phụ theo câu gốc, nên bench / backend dùng catalog hơi khác vẫn hit.

    python -m src.backend.jobs.prewarm_llm_hypotheses --cache-path PATH.jsonl \
        --jsonl src/evaluation/search_bench/gold/gold.jsonl --products-jsonl PRODUCTS.jsonl [--model gpt-4o-mini] [--dry-run]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.backend.app.application.search.prewarm import read_query_file
from src.backend.app.application.search.query_plan_llm import (
    CachedQueryHypothesizer,
    HypothesisCache,
    prewarm_hypotheses,
)


def read_jsonl_queries(path: str | Path, field: str = "text") -> list[str]:
    out: list[str] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            v = row.get(field) if isinstance(row, dict) else None
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
    return out


def index_from_products_jsonl(path: str | Path):
    """UnitIndex (không vector) từ products.jsonl(.gz) dạng CDP: search unit = `Product.is_search_unit`, con gắn theo
    `parentProductId` — như `PostgresCatalogReader` (không cờ combo: gazetteer không cần)."""
    import numpy as np

    from src.backend.app.application.ports import UnitIndex
    from src.backend.app.domain.catalog import Product, UnitAttributes

    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    products = {}
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                p = Product.from_cdp(json.loads(line))
                products[p.product_id] = p
    children: dict[str, list] = defaultdict(list)
    parent_of: dict[str, str] = {}
    for p in products.values():
        if p.parent_id:
            parent_of[p.product_id] = p.parent_id
            children[p.parent_id].append(p)
    units = sorted((p for p in products.values() if p.is_search_unit), key=lambda p: p.product_id)
    return UnitIndex(units=units, taxonomy=np.array([p.taxonomy for p in units]),
                     destination=np.array([p.destination for p in units]),
                     available=np.array([bool(p.available) for p in units]),
                     recommendable=np.array([bool(p.available) for p in units]), parent_of=parent_of,
                     model_version="prewarm-llm", attrs=UnitAttributes.build(units, children, {}))


def load_index(*, database_url: str | None = None, products_jsonl: str | None = None):
    """UnitIndex của catalog (không vector) — chỉ cần để dựng gazetteer / từ vựng của query plan."""
    if products_jsonl:
        return index_from_products_jsonl(products_jsonl)
    from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader

    if not database_url:
        from src.backend.app.core.config import get_settings

        database_url = get_settings().database_url
    return PostgresCatalogReader(database_url).load().to_index(model_version="prewarm-llm")


def build_engine(index, *, tone_normalize: bool = False):
    from src.backend.app.application.search import SearchProducts

    # chỉ dùng bước chuẩn hoá + query plan: không embed, không truy vấn vector
    return SearchProducts(index, None, None, cutoff=0.0, normalize=True, tone_normalize=tone_normalize)


def build_hypothesizer(cache_path: str, *, model: str, cache_size: int, dry_run: bool) -> CachedQueryHypothesizer:
    from src.backend.app.infrastructure.llm.query_hypothesis import PROMPT_VERSION, build_query_hypothesizer

    inner: Any = None
    if not dry_run:
        from src.backend.app.core.config import get_settings

        s = get_settings()
        inner = build_query_hypothesizer(model=model, openai_api_key=s.openai_api_key or "",
                                         gemini_api_key=s.gemini_api_key or "",
                                         anthropic_api_key=s.anthropic_api_key or "", timeout_seconds=30.0,
                                         max_retries=2)
    tag = getattr(inner, "version", None) or f"{model}|{PROMPT_VERSION}"   # dry-run: tag như adapter thật
    return CachedQueryHypothesizer(inner, cache=HypothesisCache(cache_size, path=cache_path, tag=tag))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-path", required=True, help="file JSONL (= SEARCH_LLM_FALLBACK_CACHE_PATH)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="mỗi dòng một câu; '#' là chú thích")
    src.add_argument("--jsonl", help="file JSONL câu (ví dụ gold.jsonl)")
    parser.add_argument("--field", default="text", help="trường câu trong --jsonl (mặc định text)")
    parser.add_argument("--products-jsonl", default=None, help="products.jsonl(.gz) dạng CDP thay cho Postgres")
    parser.add_argument("--database-url", default=None, help="mặc định DATABASE_URL của .env")
    parser.add_argument("--model", default="gpt-4o-mini", help="= SEARCH_LLM_FALLBACK_MODEL")
    parser.add_argument("--min-confidence", type=float, default=1.0,
                        help="chỉ câu có confidence rule < ngưỡng (mặc định 1.0: mọi câu có ≥ 1 lý do)")
    parser.add_argument("--all", action="store_true", help="mọi câu, kể cả confidence 1.0")
    parser.add_argument("--force", action="store_true", help="gọi lại cả câu đã có trong cache (ghi nối, dòng sau thắng)")
    parser.add_argument("--tone-normalize", action="store_true", help="= SEARCH_TONE_NORMALIZE của backend / arm bench")
    parser.add_argument("--per-minute", type=float, default=0.0, help="giới hạn số lượt gọi / phút (0 = không giới hạn)")
    parser.add_argument("--cache-size", type=int, default=100_000)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm câu đủ điều kiện / đã cache, không gọi model")
    args = parser.parse_args(argv)

    queries = read_query_file(args.file) if args.file else read_jsonl_queries(args.jsonl, args.field)
    engine = build_engine(load_index(database_url=args.database_url, products_jsonl=args.products_jsonl),
                          tone_normalize=args.tone_normalize)
    hyp = build_hypothesizer(args.cache_path, model=args.model, cache_size=args.cache_size, dry_run=args.dry_run)
    if args.dry_run:
        eligible = cached = 0
        seen: set[str] = set()
        for q in queries:
            req = engine.llm_hypothesis_request(q)
            if req is None or req.keys[0] in seen or not (args.all or req.confidence < args.min_confidence):
                continue
            seen.add(req.keys[0])
            eligible += 1
            cached += hyp.cache.has(*req.keys)
        hyp.close()
        print(json.dumps({"queries": len(queries), "eligible": eligible, "cached": cached,
                          "toCall": eligible if args.force else eligible - cached, "dryRun": True},
                         ensure_ascii=False, indent=2))
        return 0
    try:
        report = prewarm_hypotheses(engine, hyp, queries, min_confidence=args.min_confidence, include_all=args.all,
                                    force=args.force, per_minute=args.per_minute,
                                    progress=lambda _k, status: print(status, end=" ", flush=True, file=sys.stderr))
    finally:
        hyp.close()
    print(file=sys.stderr)
    print(json.dumps({**report.as_dict(), "cachePath": args.cache_path, "model": args.model}, ensure_ascii=False, indent=2))
    to_call = report.eligible - report.skipped
    return 1 if to_call and report.failed == to_call else 0


if __name__ == "__main__":
    sys.exit(main())
