"""FastAPI-only chat demo with a safe LangGraph SSE trace."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
import streamlit as st

API_BASE = os.getenv("ASSISTANT_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
st.set_page_config(page_title="Itinerary Agent Demo", page_icon="🧭", layout="wide")


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


def render_response(body: dict[str, Any]) -> None:
    status = body.get("status")
    if status == "NEEDS_CLARIFICATION":
        st.info(body.get("question", "Vui lòng bổ sung thông tin."))
        if body.get("knownIntent"):
            st.caption(f"Đã ghi nhớ: {body['knownIntent']}")
    elif status == "COMPLETED":
        plan = body.get("itinerary", {})
        st.success(f"Đã tạo lịch trình {len(plan.get('days', []))} ngày")
        if plan.get("stay"):
            st.markdown(f"**Lưu trú:** {plan['stay']['product']['name']} ({plan['stay']['nights']} đêm)")
        for day in plan.get("days", []):
            label = f"Ngày {day['day']}" + (f" · {day['date']}" if day.get("date") else "")
            with st.expander(label, expanded=True):
                for slot in day.get("slots", []):
                    product = slot.get("product")
                    st.write(f"{slot['time']} — {product['name'] if product else slot.get('activityType')}")
                    if product and product.get("unitPrice") is not None:
                        st.caption(f"{product['unitPrice']:,} {product.get('currency', 'VND')} · {slot.get('source')}")
        total = plan.get("estimatedTotal")
        st.metric("Tổng ước tính", f"{total:,} {plan.get('currency', 'VND')}" if total is not None else "Chưa đủ dữ liệu")
    else:
        st.warning(body.get("message", "Agent chưa thể tạo lịch trình."))
    with st.expander("JSON response"):
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
    if st.button("Cuộc hội thoại mới", use_container_width=True):
        st.session_state.conversation_id = None
        st.session_state.messages = []
        st.session_state.trace = []
        st.rerun()

chat_col, graph_col = st.columns([3, 2], gap="large")
with chat_col:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            render_response(message["content"]) if isinstance(message["content"], dict) else st.markdown(message["content"])
with graph_col:
    st.subheader("LangGraph execution")
    graph_placeholder, trace_placeholder = st.empty(), st.empty()
    if st.session_state.topology["nodes"]:
        graph_placeholder.graphviz_chart(graph_dot(st.session_state.topology, st.session_state.trace), use_container_width=True)
    if st.session_state.trace:
        trace_placeholder.dataframe(st.session_state.trace, hide_index=True, use_container_width=True)

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
                graph_placeholder.graphviz_chart(graph_dot(st.session_state.topology, st.session_state.trace), use_container_width=True)
                trace_placeholder.dataframe(st.session_state.trace, hide_index=True, use_container_width=True)
        if final_body is None:
            raise RuntimeError("Stream kết thúc nhưng không có kết quả")
        st.session_state.conversation_id = final_body.get("conversationId", st.session_state.conversation_id)
        st.session_state.messages.append({"role": "assistant", "content": final_body})
    except Exception as exc:
        st.session_state.messages.append({"role": "assistant", "content": {
            "status": "FALLBACK", "message": f"Không gọi được agent API: {exc}"
        }})
    st.rerun()
