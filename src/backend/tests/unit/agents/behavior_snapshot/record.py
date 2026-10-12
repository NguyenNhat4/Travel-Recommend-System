"""Ghi cassette tool + LLM và snapshot hành vi từ chế độ `inprocess` và LLM thật (`.env`).

Chỉ chạy khi chủ ý đổi prompt, hành vi hoặc dữ liệu. Cần Postgres và Weaviate local đã nạp catalog:

    docker compose up -d --wait postgres weaviate
    HF_HUB_OFFLINE=1 .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record [--only X01,X02] [--fresh]

Mặc định giữ bản ghi đã có, chỉ gọi tool/LLM cho tham số hoặc payload mới. `--fresh` ghi lại toàn bộ hai cassette.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from contextlib import asynccontextmanager

from .harness import (CASSETTE, SNAPSHOT, CassetteLlm, ToolCassette, dump_json, dump_tools, load_json, load_tools,
                      run_all)


@asynccontextmanager
async def inprocess_app():
    """App backend thật với lifespan đầy đủ: tool `inprocess` (Search, Recommendation, Catalog) và LLM như runtime."""
    os.environ["ITINERARY_DATA_MODE"] = "inprocess"
    from src.backend.app.main import app

    async with app.router.lifespan_context(app):
        tools = getattr(app.state, "itinerary_http_clients", None)
        if type(tools).__name__ != "InProcessItineraryTools":
            raise SystemExit(f"cần ITINERARY_DATA_MODE=inprocess, đang là {type(tools).__name__}")
        if getattr(app.state, "search", None) is None:
            raise SystemExit("RecSys chưa nạp được: kiểm Postgres, Weaviate và catalog local")
        if getattr(app.state, "itinerary_llm", None) is None:
            raise SystemExit("LLM chưa cấu hình: kiểm API key và ITINERARY_USE_LLM trong .env")
        yield app


async def record(only: set[str] | None, fresh: bool) -> None:
    llm_records = {} if fresh else load_json(CASSETTE, {})
    tool_records = {} if fresh else load_tools()
    try:
        async with inprocess_app() as app:
            llm = CassetteLlm(llm_records, inner=app.state.itinerary_llm)
            tools = ToolCassette(tool_records, inner=app.state.itinerary_http_clients)
            result = await run_all(llm, tools, only)
    finally:
        # Ghi cả khi một kịch bản lỗi giữa chừng: lần chạy sau không phải gọi lại phần đã ghi.
        dump_json(CASSETTE, llm_records)
        dump_tools(tool_records)
    snapshot = load_json(SNAPSHOT, {}) if only else {}
    snapshot.update(result)
    dump_json(SNAPSHOT, snapshot)
    turns = sum(len(turns) for turns in result.values())
    print(f"recorded {len(result)} scenarios, {turns} turns, "
          f"llm cassette {len(llm_records)} entries, tool cassette {len(tool_records)} entries")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", default="", help="Danh sách id kịch bản, phân tách bằng dấu phẩy.")
    parser.add_argument("--fresh", action="store_true", help="Bỏ cassette cũ, gọi tool và LLM cho mọi lượt.")
    args = parser.parse_args()
    only = {item.strip() for item in args.only.split(",") if item.strip()} or None
    asyncio.run(record(only, args.fresh))


if __name__ == "__main__":
    main()
