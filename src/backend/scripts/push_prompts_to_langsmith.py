"""Đẩy system prompt của Itinerary Agent (`app/agents/steps/prompts.py`) lên LangSmith Prompt Hub.

Chạy từ repo root: `LANGSMITH_API_KEY=... .venv/bin/python src/backend/scripts/push_prompts_to_langsmith.py [--dry-run]`.
Mỗi lần chạy tạo commit mới cho prompt nào có text khác bản trên hub (SDK bỏ qua prompt không đổi) và gắn tag
`--tag` (mặc định `prod`) vào commit đó. Chỉ text tĩnh lên hub, không có dữ liệu người dùng.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from app.agents.steps import prompts  # noqa: E402

PREFIX = "vota-itinerary-"
HUB_PROMPTS = {
    "classify": (prompts.CLASSIFY_PROMPT, "Node classify: phân luồng travel / explore / vague / fare / stop / "
                                         "conversation / out_of_scope."),
    "extract": (prompts.EXTRACT_PROMPT, "Node extract: trích intent chuyến đi (hậu tố ngôn ngữ nối trong code)."),
    "converse": (prompts.CONVERSATION_PROMPT, "Node converse/clarify: viết câu trả lời (hậu tố ngôn ngữ nối trong code)."),
    "tool-plan": (prompts.TOOL_PLAN_PROMPT, "Node tool: lập tool plan Search/Recommendation."),
    "similar-hint": (prompts.SIMILAR_HINT, "Node tool: gợi ý get_similar_products, nối sau tool-plan khi đổi món."),
    "destination": (prompts.DESTINATION_PROMPT, "Node tool: chọn điểm đến theo catalog."),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="prod", help="commit tag gắn vào commit vừa đẩy (mặc định prod)")
    parser.add_argument("--dry-run", action="store_true", help="chỉ liệt kê, không gọi LangSmith")
    args = parser.parse_args()

    client = None
    if not args.dry_run:
        from langsmith import Client
        client = Client()
    for key, (text, description) in HUB_PROMPTS.items():
        name = PREFIX + key
        if client is None:
            print(f"[dry-run] {name}: {len(text)} ký tự")
            continue
        # mustache: prompt có `{adults: N, ...}` nên f-string sẽ coi là biến; mustache chỉ nhận `{{ }}` (không có).
        template = ChatPromptTemplate.from_messages([("system", text)], template_format="mustache")
        url = client.push_prompt(name, object=template, description=description, commit_tags=[args.tag], is_public=False)
        print(f"{name}: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
