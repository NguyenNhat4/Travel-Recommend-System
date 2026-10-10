"""Streamlit workbench for offline comparison of ten recommender prototypes."""
from __future__ import annotations

import csv
import io
import json
from collections import Counter

import streamlit as st

from src.evaluation.benchmark import benchmark_rows_have_p99, run_benchmark
from src.evaluation.architecture_diagram import mermaid_source, render_mermaid_html
from src.evaluation.data_source import EvaluationData, load_evaluation_data
from src.evaluation.recommender_prototypes import build_recommenders

st.set_page_config(page_title="Recommender Architecture Lab", page_icon="🧭", layout="wide")


@st.cache_resource(show_spinner="Đang tải catalog và embedding cache…")
def cached_evaluation_data() -> EvaluationData:
    return load_evaluation_data()


def _persona_models(data: EvaluationData):
    cache_key = (data.index.model_version, len(data.events), data.events[-1].get("timestamp") if data.events else None)
    if st.session_state.get("persona_model_cache_key") != cache_key:
        with st.spinner("Đang fit 10 prototype trên lịch sử seed…"):
            st.session_state.persona_models = build_recommenders(data.index, data.events)
            st.session_state.persona_model_cache_key = cache_key
    return st.session_state.persona_models


def _format_percent(value: float) -> str:
    return f"{value:.1%}"


def _render_benchmark(data: EvaluationData) -> None:
    st.subheader("Benchmark temporal holdout")
    st.caption("Giữ purchase mới nhất của mỗi user; mọi model dùng chung tập train và target.")
    col_k, col_seed = st.columns(2)
    with col_k:
        k = st.slider("Độ dài danh sách K", min_value=20, max_value=50, value=20, step=10)
    with col_seed:
        seed = st.number_input("Seed tái lập", min_value=0, max_value=2**31 - 1, value=42, step=1)

    if st.button("Chạy benchmark 10 phương pháp", type="primary", width="stretch"):
        try:
            with st.spinner("Đang fit model và chấm cùng một holdout…"):
                rows, split = run_benchmark(data.index, data.events, k=k, seed=int(seed))
            st.session_state.benchmark_rows = rows
            st.session_state.benchmark_target_count = len(split.targets)
            st.session_state.benchmark_seed = int(seed)
            st.session_state.benchmark_k = k
        except Exception as exc:
            st.exception(exc)

    rows = st.session_state.get("benchmark_rows")
    if not rows:
        st.info("Chạy benchmark để xem bảng xếp hạng, metric và file xuất.")
        return
    if not benchmark_rows_have_p99(rows):
        for key in ("benchmark_rows", "benchmark_target_count", "benchmark_seed", "benchmark_k"):
            st.session_state.pop(key, None)
        st.warning("Kết quả đang lưu được tạo trước khi có p99. Hãy chạy lại benchmark để tính metric này.")
        return

    st.caption(
        f"Holdout users: {st.session_state.benchmark_target_count:,} · "
        f"K={st.session_state.benchmark_k} · seed={st.session_state.benchmark_seed} · "
        "metric được tính trên top‑20 để nhất quán với handbook."
    )
    display_rows = []
    for row in rows:
        display_rows.append({
            "Phương pháp": row["label"],
            "Recall@10": _format_percent(row["recall@10"]),
            "Recall@20": _format_percent(row["recall@20"]),
            "NDCG@10": f"{row['ndcg@10']:.3f}",
            "Cross-category": _format_percent(row["cross_category_rate"]),
            "Availability precision": _format_percent(row["availability_precision"]),
            "Catalog coverage": _format_percent(row["catalog_coverage"]),
            "p95 rank (ms)": f"{row['p95_runtime_ms']:.2f}",
            "p99 rank (ms)": f"{row['p99_runtime_ms']:.2f}",
        })
    st.dataframe(display_rows, hide_index=True, width="stretch")

    metric_key = st.selectbox(
        "Biểu đồ metric",
        ["recall@10", "recall@20", "ndcg@10", "cross_category_rate", "availability_precision", "catalog_coverage", "p95_runtime_ms", "p99_runtime_ms"],
        format_func=lambda key: {
            "recall@10": "Recall@10",
            "recall@20": "Recall@20",
            "ndcg@10": "NDCG@10",
            "cross_category_rate": "Cross-category rate",
            "availability_precision": "Availability precision",
            "catalog_coverage": "Catalog coverage",
            "p95_runtime_ms": "p95 rank runtime (ms)",
            "p99_runtime_ms": "p99 rank runtime (ms)",
        }[key],
    )
    chart = {
        "Phương pháp": [row["label"] for row in rows],
        "Giá trị": [row[metric_key] for row in rows],
    }
    st.bar_chart(chart, x="Phương pháp", y="Giá trị", horizontal=True)

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    json_payload = {
        "dataset": "seeded synthetic CDP history",
        "holdoutUsers": st.session_state.benchmark_target_count,
        "k": st.session_state.benchmark_k,
        "seed": st.session_state.benchmark_seed,
        "methods": rows,
    }
    download_csv, download_json = st.columns(2)
    with download_csv:
        st.download_button("Tải kết quả CSV", csv_buffer.getvalue(), "recsys-benchmark.csv", "text/csv", width="stretch")
    with download_json:
        st.download_button("Tải kết quả JSON", json.dumps(json_payload, ensure_ascii=False, indent=2), "recsys-benchmark.json", "application/json", width="stretch")

    with st.expander("Ý nghĩa và giới hạn của phương pháp", expanded=False):
        for row in rows:
            st.markdown(f"**{row['label']}** — {row['limitation']}")


def _render_persona_explorer(data: EvaluationData) -> None:
    st.subheader("Khám phá gợi ý theo persona/user")
    events_by_user: dict[str, list[dict]] = {}
    for event in data.events:
        user_id = event.get("cdpUserId")
        if user_id:
            events_by_user.setdefault(str(user_id), []).append(event)
    users = sorted(events_by_user)
    if not users:
        st.warning("Không có user ID trong event snapshot.")
        return

    user_id = st.selectbox("Chọn CDP user", users)
    top_k = st.slider("Số gợi ý hiển thị", min_value=3, max_value=20, value=10, key="persona_top_k")
    models = _persona_models(data)
    labels = {model.key: model.label for model in models}
    selected = st.multiselect("Chọn phương pháp", list(labels), default=list(labels), format_func=lambda key: labels[key])
    user_events = events_by_user[user_id]
    counts = Counter(event.get("eventName", "unknown") for event in user_events)
    st.caption(f"{user_id} · {len(user_events)} event · " + " / ".join(f"{name}: {count}" for name, count in sorted(counts.items())))

    model_map = {model.key: model for model in models}
    tabs = st.tabs([labels[key] for key in selected]) if selected else []
    for tab, key in zip(tabs, selected):
        with tab:
            model = model_map[key]
            recommendations = model.recommend(user_id, user_events, k=top_k, seed=42)
            st.caption(model.description)
            st.caption(f"Giới hạn: {model.limitation}")
            rows = []
            for rank, recommendation in enumerate(recommendations, 1):
                product_index = data.index.idx[recommendation.product_id]
                product = data.index.units[product_index]
                rows.append({
                    "#": rank,
                    "Sản phẩm": product.name,
                    "Danh mục": product.taxonomy,
                    "Điểm đến": product.destination,
                    "Còn khả dụng": bool(data.index.available[product_index]),
                    "Điểm": round(recommendation.score, 5),
                })
            st.dataframe(rows, hide_index=True, width="stretch")


st.title("🧭 Recommender Architecture Lab")
st.warning(
    "Kết quả là prototype trên lịch sử seed tổng hợp. Chúng hữu ích để so sánh cách hoạt động của các kiến trúc, "
    "không dự đoán chất lượng với khách hàng thật. ALS, graph và sequence đặc biệt nhạy với dữ liệu thưa."
)

with st.sidebar:
    st.markdown("### Nguồn dữ liệu")
    st.caption("PostgreSQL đã seed · catalog qua DATABASE_URL · event qua CDP_DATABASE_URL")
    if st.button("Tải lại snapshot", width="stretch"):
        cached_evaluation_data.clear()
        st.session_state.pop("persona_model_cache_key", None)
        for key in ("benchmark_rows", "benchmark_target_count", "benchmark_seed", "benchmark_k"):
            st.session_state.pop(key, None)
        st.rerun()

try:
    data = cached_evaluation_data()
except Exception as exc:
    st.error("Không tải được dữ liệu evaluation.")
    st.exception(exc)
    st.stop()

st.caption(f"{data.source_label} · {len(data.index.units):,} search units · {len(data.events):,} events")
with st.expander("Kiến trúc 10 recommender", expanded=False):
    st.caption("Luồng chung dùng cùng catalog, temporal holdout và quy tắc eligibility cho cả 10 phương pháp.")
    st.iframe(render_mermaid_html(mermaid_source()), height=720, scrolling=True)
mode = st.radio("Chế độ", ["Benchmark batch", "Persona explorer"], horizontal=True)
if mode == "Benchmark batch":
    _render_benchmark(data)
else:
    _render_persona_explorer(data)
