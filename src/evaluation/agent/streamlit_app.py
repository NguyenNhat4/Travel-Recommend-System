"""FastAPI-only chat demo with a safe LangGraph SSE trace."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
import streamlit as st

API_BASE = os.getenv("ASSISTANT_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
logger = logging.getLogger(__name__)
st.set_page_config(page_title="Itinerary Agent Demo", page_icon="🧭", layout="wide")
st.html("""
<style>
div[data-testid="stColumn"]:has(.st-key-execution_panel) {
    position: sticky;
    top: 3.75rem;
    align-self: flex-start;
    max-height: calc(100vh - 5rem);
    overflow-y: auto;
}
.st-key-execution_panel {
    padding: 0.25rem 0.5rem 1rem;
}
@media (max-width: 768px) {
    div[data-testid="stColumn"]:has(.st-key-execution_panel) {
        position: static;
        max-height: none;
        overflow-y: visible;
    }
}
</style>
""")


def parse_sse(response: httpx.Response):
    event_name, data_lines = None, []
    for line in response.iter_lines():
        if not line:
            if event_name and data_lines:
                yield event_name, json.loads("\n".join(data_lines))
            event_name, data_lines = None, []
        elif line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())


def graph_dot(topology: dict[str, Any], trace: list[dict[str, Any]]) -> str:
    completed = {item["nodeId"] for item in trace}
    failed = {item["nodeId"] for item in trace if item.get("outcome") not in {"completed", "success"}}
    lines = ["digraph G {", 'rankdir="LR";', 'node [shape="box", style="rounded,filled"];']
    for node in topology.get("nodes", []):
        color = "#fecaca" if node in failed else "#bbf7d0" if node in completed else "#e5e7eb"
        lines.append(f'"{node}" [fillcolor="{color}"];')
    for edge in topology.get("edges", []):
        style = "dashed" if edge.get("conditional") else "solid"
        lines.append(f'"{edge["source"]}" -> "{edge["target"]}" [style="{style}"];')
    return "\n".join([*lines, "}"])


def render_product(product: dict[str, Any], *, note: str | None = None) -> None:
    image_url = product.get("imageUrl")
    image_col, detail_col = st.columns([1, 3]) if image_url else (None, st.container())
    if image_col is not None:
        with image_col:
            st.image(image_url, width=180)
    with detail_col:
        st.markdown(f"**{product['name']}**")
        st.caption(f"{product.get('taxonomy', 'product')} · {product.get('destination', '')}")
        if product.get("unitPrice") is not None:
            st.write(f"Giá tham khảo: **{product['unitPrice']:,} {product.get('currency', 'VND')}**")
        if note:
            st.write(note)
        product_url = product.get("attributes", {}).get("url")
        if product_url:
            st.link_button("Xem sản phẩm", product_url, width="content")


def render_response(body: dict[str, Any]) -> None:
    status = body.get("status")
    error = body.get("error") if isinstance(body.get("error"), dict) else None
    if error:
        st.error(error.get("message", "Agent API trả về lỗi."))
        request_id = error.get("requestId")
        if request_id:
            st.caption(f"Mã truy vết: `{request_id}`")
    elif status == "NEEDS_CLARIFICATION":
        st.info(body.get("question", "Vui lòng bổ sung thông tin."))
        if body.get("knownIntent"):
            st.caption(f"Đã ghi nhớ: {body['knownIntent']}")
    elif status == "COMPLETED":
        plan = body.get("itinerary", {})
        product_slots = [
            (day, slot)
            for day in plan.get("days", [])
            for slot in day.get("slots", [])
            if isinstance(slot.get("product"), dict)
        ]
        stay = plan.get("stay") or {}
        product_count = len(product_slots) + (1 if stay.get("product") else 0)
        st.success(f"Đã tìm thấy {product_count} sản phẩm thực từ catalog")
        if stay:
            with st.expander(f"Lưu trú · {stay['nights']} đêm", expanded=True):
                render_product(stay["product"], note=stay.get("note"))
        for day in plan.get("days", []):
            real_slots = [slot for slot in day.get("slots", []) if isinstance(slot.get("product"), dict)]
            if not real_slots:
                continue
            label = f"Ngày {day['day']}" + (f" · {day['date']}" if day.get("date") else "")
            with st.expander(label, expanded=True):
                for slot in real_slots:
                    st.markdown(f"**{slot['time']}**")
                    render_product(slot["product"], note=slot.get("note"))
        total = plan.get("estimatedTotal")
        if total is not None:
            st.metric("Tổng sản phẩm ước tính", f"{total:,} {plan.get('currency', 'VND')}")
        if body.get("warnings"):
            with st.expander("Lưu ý về giá và khả dụng", expanded=False):
                for warning in body["warnings"]:
                    st.caption(f"• {warning['message']}")
    elif status == "FALLBACK":
        st.warning(body.get("message", "Agent chưa thể tạo lịch trình."))
        groups = body.get("searchResults") if isinstance(body.get("searchResults"), dict) else {}
        seen: set[str] = set()
        grounded_products: list[dict[str, Any]] = []
        for products in groups.values():
            for product in products if isinstance(products, list) else []:
                product_id = product.get("productId") if isinstance(product, dict) else None
                if product_id and product_id not in seen:
                    seen.add(product_id)
                    grounded_products.append(product)
        if grounded_products:
            st.markdown(f"**{len(grounded_products)} sản phẩm thực để bạn tham khảo**")
            for product in grounded_products:
                with st.expander(product["name"], expanded=True):
                    render_product(product)
    elif status == "NO_RESULTS":
        st.warning(body.get("message", "Không tìm thấy sản phẩm phù hợp."))
    else:
        st.write(body.get("message") or body.get("question") or "Agent đã trả về response không xác định.")
    with st.expander("Xem JSON response", expanded=False):
        st.json(body)


if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
    st.session_state.messages = [{"role": "assistant", "content": {
        "status": "NEEDS_CLARIFICATION", "question": "Bạn muốn đi đâu và trong bao nhiêu ngày?"
    }}]
    st.session_state.topology = {"nodes": [], "edges": []}
    st.session_state.trace = []

st.title("🧭 Travel Itinerary Agent")
st.caption("Streamlit → FastAPI → LangGraph thật · tool dùng mock catalog 50 sản phẩm ở development")

with st.sidebar:
    st.subheader("Backend")
    st.code(API_BASE)
    try:
        health = httpx.get(f"{API_BASE}/assistant/status", timeout=2).json()
        st.success(f"{health['status']} · {health['dataMode']} · {health.get('productCount') or 0} sản phẩm")
    except Exception:
        st.error("Không kết nối được FastAPI")
    language = st.selectbox("Ngôn ngữ", ["vi", "en"], format_func=lambda value: "Tiếng Việt" if value == "vi" else "English")
    if st.button("Cuộc hội thoại mới", width="stretch"):
        st.session_state.conversation_id = None
        st.session_state.messages = []
        st.session_state.trace = []
        st.rerun()

chat_col, graph_col = st.columns([3, 2], gap="large")
with chat_col:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], dict):
                render_response(message["content"])
            else:
                st.markdown(message["content"])
with graph_col:
    with st.container(key="execution_panel"):
        st.subheader("LangGraph execution")
        graph_placeholder, trace_placeholder = st.empty(), st.empty()
        if st.session_state.topology["nodes"]:
            graph_placeholder.graphviz_chart(graph_dot(st.session_state.topology, st.session_state.trace), width="stretch")
        if st.session_state.trace:
            trace_placeholder.dataframe(st.session_state.trace, hide_index=True, width="stretch")

if prompt := st.chat_input("Ví dụ: Lập lịch trình Đà Nẵng 3 ngày"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.trace = []
    payload = {"message": prompt, "context": {"language": language}}
    if st.session_state.conversation_id:
        payload["conversationId"] = st.session_state.conversation_id
    try:
        with httpx.stream("POST", f"{API_BASE}/assistant/itineraries/stream", json=payload, timeout=30) as response:
            response.raise_for_status()
            final_body = None
            for event, data in parse_sse(response):
                if event == "graph.topology":
                    st.session_state.topology = data
                elif event == "node.completed":
                    st.session_state.trace.append(data)
                elif event == "run.completed":
                    final_body = data["response"]
                elif event == "run.failed":
                    raise RuntimeError(data["error"]["error"]["message"])
                graph_placeholder.graphviz_chart(graph_dot(st.session_state.topology, st.session_state.trace), width="stretch")
                trace_placeholder.dataframe(st.session_state.trace, hide_index=True, width="stretch")
        if final_body is None:
            raise RuntimeError("Stream kết thúc nhưng không có kết quả")
        st.session_state.conversation_id = final_body.get("conversationId", st.session_state.conversation_id)
        st.session_state.messages.append({"role": "assistant", "content": final_body})
    except Exception as exc:
        logger.exception(
            "streamlit.agent_request_failed conversationId=%s apiBase=%s",
            st.session_state.conversation_id or "new", API_BASE,
        )
        st.session_state.messages.append({"role": "assistant", "content": {
            "status": "FALLBACK", "message": f"Không gọi được agent API: {exc}"
        }})
    st.rerun()
