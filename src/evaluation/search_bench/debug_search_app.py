"""Streamlit Debug App: Phân tích & Gỡ lỗi toàn diện Pipeline Tìm kiếm V-OTA.

Bao gồm đầy đủ 5 giai đoạn chính theo đúng kiến trúc kỹ thuật của hệ thống:
1. Thu nhận và chuẩn hóa (Query Ingestion & Normalization)
2. Query understanding & Router (Hiểu ý định & Kế hoạch truy vấn)
3. Filter first & Candidate Universe (Lọc cứng không gian ứng viên)
4. Candidate Retrieval Đa Kênh (Dense E5-Small, Lexical BM25, Fuzzy Trigram)
5. Ranking, Fusion & Kết quả (RRF, Cutoff Gate, Coverage Gate, Revalidation, Soft Star)

App dùng chung PostgreSQL (qua SSH tunnel) và Weaviate Cloud (ProductE5Small),
chạy đúng logic production `SearchProducts` và hiển thị chi tiết Input, Output,
Mục đích, Nguyên lý, cùng Candidate Top 1 & Top Cuối của từng bước.
"""

from __future__ import annotations

import os
import sys
import time
import pickle
import hashlib
from typing import Any
from collections import Counter
import streamlit as st
import numpy as np
import types
import importlib.machinery

# Windows WDAC compatibility stub for sklearn.metrics (avoids _heap.pyd block)
if "sklearn" not in sys.modules:
    _m_sk = types.ModuleType("sklearn")
    _m_sk.__spec__ = importlib.machinery.ModuleSpec("sklearn", None)
    sys.modules["sklearn"] = _m_sk
if "sklearn.metrics" not in sys.modules:
    _m_met = types.ModuleType("sklearn.metrics")
    _m_met.__spec__ = importlib.machinery.ModuleSpec("sklearn.metrics", None)
    _m_met.roc_curve = lambda *args, **kwargs: (None, None, None)
    sys.modules["sklearn.metrics"] = _m_met

# Windows WDAC compatibility stub for scipy.optimize (avoids scipy.fft -> _uarray.pyd block)
if "scipy.optimize" not in sys.modules:
    _m_opt = types.ModuleType("scipy.optimize")
    _m_opt.__spec__ = importlib.machinery.ModuleSpec("scipy.optimize", None)
    _m_opt.linear_sum_assignment = lambda *args, **kwargs: ([], [])
    sys.modules["scipy.optimize"] = _m_opt


# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.backend.app.core.config import get_settings
from src.backend.app.application.ports import (
    UnitIndex,
    VectorSearchPort,
    VectorHit,
    LexicalHit,
)
from src.backend.app.domain.catalog import Product, TEXT_BUILDER_VERSION
from src.backend.app.domain.search import (
    QueryNormalizer,
    QueryPlan,
    PlanParams,
    PlanFlags,
    PlanGazetteers,
    HybridConfig,
    build_query_plan,
    is_unaccented,
    tokens,
    query_tokens,
    coverage,
    revalidate,
    soft_star_order,
    hybrid_filter_score,
    candidate_filter_score,
    SOURCE_PARAM,
    SOURCE_QUERY,
)
from src.backend.app.domain.search.fuzzy import FuzzyIndex
from src.backend.app.domain.search.tone import detect_style, normalize_tone
from src.backend.app.application.search.use_cases import (
    SearchProducts,
    StageTimer,
    canonical_query,
    PROFILE_NO_DIACRITICS,
    FALLBACK_DROPPED_EMPTY,
    _child_filter,
    _normalization_diagnostics,
    _plan_diagnostics,
    _plan_gazetteers,
    scored,
)
from src.backend.app.infrastructure.vectors.postgres_store import (
    CatalogUnits,
    PostgresCatalogReader,
)
from src.backend.app.infrastructure.vectors.weaviate_store import (
    WeaviateVectorSearch,
    WeaviateVectorStore,
    connect_weaviate,
)
from src.backend.app.infrastructure.embeddings.factory import build_embedder

# Page layout & styling
st.set_page_config(
    page_title="V-OTA Search Debugger",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_DIR = os.path.join(REPO_ROOT, ".embcache")
CATALOG_CACHE_FILE = os.path.join(CACHE_DIR, "debug_catalog_units.pkl")


# ==============================================================================
# Resource Caching Helpers
# ==============================================================================

@st.cache_resource(show_spinner="Đang khởi tạo Weaviate Vector Store...")
def get_weaviate_search():
    """Khởi tạo kết nối Weaviate Cloud Vector DB (Collection ProductE5Small)."""
    settings = get_settings()
    client = connect_weaviate(
        settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        grpc_port=settings.weaviate_grpc_port,
        timeout_seconds=settings.weaviate_timeout_seconds,
    )
    vs = WeaviateVectorSearch(
        client,
        collection=settings.vector_collection,
        dimension=settings.embed_dimension,
    )
    return vs, client


@st.cache_resource(show_spinner="Đang nạp mô hình Embedder intfloat/multilingual-e5-small...")
def get_embedder():
    """Khởi tạo mô hình E5-Small local qua transformers + torch CPU."""
    settings = get_settings()
    return build_embedder(settings)


@st.cache_resource(show_spinner="Đang nạp Catalog từ PostgreSQL / Cache...")
def get_catalog_units(force_reload: bool = False) -> CatalogUnits:
    """Nạp CatalogUnits từ disk cache nếu có, hoặc query từ PostgreSQL."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not force_reload and os.path.exists(CATALOG_CACHE_FILE):
        try:
            with open(CATALOG_CACHE_FILE, "rb") as f:
                cat = pickle.load(f)
            return cat
        except Exception as exc:
            st.warning(f"Lỗi đọc cache: {exc}, tiến hành nạp từ database...")

    settings = get_settings()
    reader = PostgresCatalogReader(settings.database_url)
    cat = reader.load()
    try:
        with open(CATALOG_CACHE_FILE, "wb") as f:
            pickle.dump(cat, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as exc:
        st.warning(f"Không thể lưu cache: {exc}")
    return cat


# ==============================================================================
# Helper functions for UI rendering
# ==============================================================================

def render_step_card(step_num: str, title: str, purpose: str, principle: str):
    """Hiển thị card giải thích mục đích và nguyên lý hoạt động của từng bước."""
    st.markdown(
        f"""
        <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 6px; margin-bottom: 12px;">
            <div style="font-weight: 700; color: #1e3a8a; font-size: 15px; margin-bottom: 4px;">
                {step_num}. {title}
            </div>
            <div style="font-size: 13px; color: #334155; margin-bottom: 4px;">
                🎯 <b>Mục đích (Dùng để làm gì):</b> {purpose}
            </div>
            <div style="font-size: 13px; color: #334155;">
                ⚙️ <b>Nguyên lý (Làm với nguyên lý gì):</b> {principle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_candidate_summary(p: Product, score: float | None = None, score_label: str = "Score"):
    """Format tóm tắt một ứng viên để hiển thị Top 1 / Top Cuối."""
    score_str = f" | **{score_label}**: `{score:.4f}`" if score is not None else ""
    price_str = f"{p.unit_price:,.0f} {p.currency}" if p.unit_price else "Liên hệ"
    return (
        f"- **ID**: `{p.product_id}` | **Tên**: **{p.name}**\n"
        f"  - **Taxonomy**: `{p.taxonomy}` | **Điểm đến**: `{p.destination}` | **Giá**: `{price_str}`{score_str}"
    )


# ==============================================================================
# Main Application Flow
# ==============================================================================

def main():
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 16px;">
            <h2 style="margin: 0; color: #0f172a;">🔍 V-OTA Search Debugger & Pipeline Inspector</h2>
            <span style="background-color: #dbeafe; color: #1e40af; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 9999px;">
                Clean Architecture • Contract 1.18.0
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    settings = get_settings()

    # Sidebar: Configurations & Toggles
    with st.sidebar:
        st.header("⚙️ Cấu Hình Debug Search")
        st.caption("Các núm điều khiển pipeline tìm kiếm (bật/tắt để quan sát phản ứng)")

        # Section 1: Database & Cache
        with st.expander("📦 Hạ tầng & Dữ liệu", expanded=False):
            st.markdown(f"**Database**: `{settings.database_url.split('@')[-1]}`")
            st.markdown(f"**Weaviate**: `{settings.vector_collection}`")
            st.markdown(f"**Embedder**: `{settings.embed_model}`")
            if st.button("🔄 Tải lại Catalog từ Database", use_container_width=True):
                get_catalog_units.clear()
                st.success("Đã làm mới cache Catalog!")
                st.rerun()

        # Section 2: General & Thresholds
        with st.expander("🎚️ Ngưỡng Điểm & Phân Trang", expanded=True):
            cutoff = st.slider("Cutoff Cosine", min_value=0.0, max_value=1.0, value=0.84, step=0.01,
                               help="Ngưỡng tối thiểu cosine tương đồng ngữ nghĩa")
            limit = st.slider("Limit (Số kết quả hiển thị)", min_value=1, max_value=50, value=20)
            offset = st.number_input("Offset", min_value=0, value=0, step=1)
            normalize = st.checkbox("Bật Query Normalizer", value=True, help="Unicode NFC, lowercase, alias")
            tone_normalize = st.checkbox("Bật Tone Normalize (hoà ↔ hòa)", value=False,
                                         help="Đưa vị trí dấu thanh về kiểu đa số của catalog")

        # Section 3: Hybrid & Fusion
        with st.expander("🔀 Hybrid Retrieval & RRF Fusion", expanded=True):
            hybrid_on = st.checkbox("Bật Hybrid (Dense + BM25)", value=True)
            candidate_k = st.slider("Dense Candidate K", 10, 500, 200)
            lexical_candidate_k = st.slider("BM25 Candidate K", 10, 200, 50)
            lexical_cutoff = st.slider("Lexical Cutoff", 0.0, 1.0, 0.50, step=0.05,
                                       help="Ngưỡng cosine tối thiểu cho hit từ nhánh BM25")
            min_coverage = st.slider("Lexical Min Coverage", 0.0, 1.0, 0.10, step=0.05,
                                     help="Độ phủ từ khóa tối thiểu của hit BM25 trong tên sản phẩm")
            rrf_k = st.number_input("RRF K (Hằng số làm mượt)", min_value=1, max_value=100, value=30)
            st.markdown("---")
            st.markdown("**Trọng số RRF**")
            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                dense_weight = st.number_input("Dense W", value=1.0, step=0.1)
            with col_w2:
                lexical_weight = st.number_input("Lex W", value=1.0, step=0.1)
            with col_w3:
                fuzzy_weight = st.number_input("Fuzzy W", value=1.0, step=0.1)
            st.markdown("---")
            st.markdown("**Kênh Fuzzy (Trigram)**")
            fuzzy_k = st.slider("Fuzzy K (0 = Tắt)", min_value=0, max_value=50, value=0)
            fuzzy_candidate_k = st.number_input("Fuzzy Candidate K", min_value=10, max_value=500, value=200)
            fuzzy_min_sim = st.slider("Fuzzy Min Similarity", min_value=0.1, max_value=1.0, value=0.6, step=0.05)

        # Section 4: Query Plan Hard Filters (F1 - F7, POI, Entity)
        with st.expander("🛡️ Hard Filters (F1-F7, POI, Entity)", expanded=True):
            dest_filter = st.checkbox("F1: Lọc cứng Điểm đến suy ra", value=settings.search_dest_filter)
            dest_filter_fallback = st.checkbox("FR-SRC-04: Fallback khi điểm đến làm F rỗng", value=settings.search_dest_filter_fallback)
            negation_filter = st.checkbox("F3: Phủ định tiện ích / sản phẩm ('không có X')", value=settings.search_negation_filter)
            taxonomy_filter = st.checkbox("F4: Lọc loại sản phẩm ('khách sạn', 'golf') [ĐÃ CHỐT BẬT]", value=settings.search_taxonomy_filter)
            taxonomy_strong_only = st.checkbox("F4: Chỉ lọc cue mạnh (bỏ cue yếu như 'phòng')", value=settings.search_taxonomy_strong_only)
            route_filter = st.checkbox("F5: Lọc tuyến bay ('từ A đến B')", value=settings.search_route_filter)
            numeric_filter = st.checkbox("F6: Lọc giá / sao suy từ câu", value=settings.search_numeric_filter)
            party_filter = st.checkbox("F6: Lọc sức chứa đoàn khách ('4 người')", value=settings.search_party_filter)
            # 07/10 (contract 1.18.0): F7 duration & POI resolve an toàn
            duration_filter = st.checkbox("F7: Thời lượng ('3 ngày 2 đêm', 3N2Đ) [BẬT - Tiêu cụm khỏi BM25]", value=settings.search_duration_filter)
            poi_resolve = st.checkbox("POI: Địa danh gazetteer ('Hồ Hoàn Kiếm', 'Cầu Rồng') [BẬT - Ánh xạ vào F1]", value=settings.search_poi_resolve)
            entity_filter = st.checkbox("Entity gate: 'VinWonders' / 'Safari' → chỉ attraction/combo có tên chứa entity", value=settings.search_entity_filter)

        # Section 5: Câu không dấu
        with st.expander("🔤 Câu Không Dấu (No Diacritics)", expanded=False):
            no_diacritics_mode = st.selectbox("Chế độ câu không dấu", ["relax", "off"], index=0)
            no_diacritics_cutoff = st.slider("Cutoff câu không dấu", 0.0, 1.0, 0.80, step=0.05)
            no_diacritics_lexical_k = st.slider("BM25 K câu không dấu", 10, 200, 50)
            no_diacritics_min_coverage = st.slider("Min Coverage câu không dấu", 0.0, 1.0, 0.10, step=0.05)

        # Section 6: Tham số Request tường minh
        with st.expander("📋 Ghi Đè Tham Số Request (Explicit Overrides)", expanded=False):
            st.caption("Mặc định taxonomy=None (chỉ gọi 1 lần toàn bộ catalog theo yêu cầu)")
            override_taxonomy = st.selectbox(
                "Taxonomy",
                [None, "hotel", "hotel_room", "attraction", "golf", "flight", "combo", "tour"],
                index=0,
                format_func=lambda x: "None (Toàn bộ catalog)" if x is None else str(x),
            )
            override_destination = st.text_input("Destination (ví dụ 'Nha Trang')", value="")
            override_price_min = st.number_input("Giá tối thiểu (VNĐ)", min_value=0, value=0, step=100000)
            override_price_max = st.number_input("Giá tối đa (VNĐ)", min_value=0, value=0, step=100000)
            override_star_min = st.slider("Sao tối thiểu", 0.0, 5.0, 0.0, step=0.5)
            override_available_only = st.checkbox("Chỉ sản phẩm còn bán (availableOnly)", value=True)
            override_adults = st.number_input("Người lớn (Adults)", min_value=0, value=0)
            override_children = st.number_input("Trẻ em (Children)", min_value=0, value=0)

    # Main Input Area: Quick Presets & Query bar
    if "search_query_input" not in st.session_state:
        st.session_state["search_query_input"] = "khách sạn gần Hồ Hoàn Kiếm 3 ngày 2 đêm"

    def apply_query_preset(preset_text: str):
        st.session_state["search_query_input"] = preset_text

    st.markdown("##### 💡 Câu truy vấn mẫu (Presets thử nghiệm nhanh F4, F7 & POI):")
    col_pre1, col_pre2, col_pre3, col_pre4, col_pre5 = st.columns(5)
    with col_pre1:
        st.button(
            "🏨 F4+F7+POI (Hà Nội)\n'khách sạn gần Hồ Hoàn Kiếm 3 ngày 2 đêm'",
            on_click=apply_query_preset,
            args=("khách sạn gần Hồ Hoàn Kiếm 3 ngày 2 đêm",),
            use_container_width=True,
            help="Test: F4=hotel, F7=3 ngày 2 đêm (cắt khỏi BM25), POI='Hồ Hoàn Kiếm' ➔ Hà Nội",
        )
    with col_pre2:
        st.button(
            "🏖️ F4+F7+POI (Nha Trang)\n'resort gần Bãi Dài Nha Trang 3N2Đ'",
            on_click=apply_query_preset,
            args=("resort gần Bãi Dài Nha Trang 3N2Đ",),
            use_container_width=True,
            help="Test: F4=hotel, F7=3N2Đ, POI='Bãi Dài' ➔ Nha Trang",
        )
    with col_pre3:
        st.button(
            "🎢 F7+Entity (Phú Quốc)\n'vé VinWonders Phú Quốc 4 ngày 3 đêm'",
            on_click=apply_query_preset,
            args=("vé VinWonders Phú Quốc 4 ngày 3 đêm",),
            use_container_width=True,
            help="Test: F7=4N3Đ, Entity gate 'vinwonders', Destination='Phú Quốc'",
        )
    with col_pre4:
        st.button(
            "🌉 F4+POI (Đà Nẵng)\n'khách sạn Đà Nẵng gần Cầu Rồng'",
            on_click=apply_query_preset,
            args=("khách sạn Đà Nẵng gần Cầu Rồng",),
            use_container_width=True,
            help="Test: F4=hotel, POI='Cầu Rồng' ➔ Đà Nẵng",
        )
    with col_pre5:
        st.button(
            "✈️ F4+F5 (Tuyến bay)\n'vé máy bay Sài Gòn đi Hà Nội'",
            on_click=apply_query_preset,
            args=("vé máy bay Sài Gòn đi Hà Nội",),
            use_container_width=True,
            help="Test: F4=flight, F5 Route SGN ➔ HAN",
        )

    col_q, col_btn = st.columns([5, 1])
    with col_q:
        q = st.text_input(
            "Nhập câu truy vấn tìm kiếm (Đơn lẻ, 1 lần gọi duy nhất với taxonomy=None):",
            key="search_query_input",
            placeholder="Gõ từ khóa, ví dụ: 'khách sạn gần Hồ Hoàn Kiếm 3 ngày 2 đêm', 'resort gần Bãi Dài 3N2Đ'...",
        )
    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        run_search = st.button("🚀 Chạy Search", use_container_width=True, type="primary")

    if not q.strip():
        st.info("Vui lòng nhập câu truy vấn và bấm 'Chạy Search'.")
        return

    # Load resources
    try:
        catalog = get_catalog_units()
        index = catalog.to_index(f"{settings.embed_model}:{TEXT_BUILDER_VERSION}")
        vector_search, weaviate_client = get_weaviate_search()
        embedder = get_embedder()
    except Exception as exc:
        st.error(f"❌ Lỗi khi khởi tạo hạ tầng tìm kiếm: {exc}")
        return

    # ==============================================================================
    # PIPELINE EXECUTION & STAGE-BY-STAGE INSPECTION
    # ==============================================================================

    st.markdown("### 🔄 Quá Trình Thực Thi Các Giai Đoạn Tìm Kiếm")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 1: Thu nhận và chuẩn hóa (Query Ingestion & Normalization)
    # --------------------------------------------------------------------------
    st.markdown("---")
    render_step_card(
        step_num="Giai đoạn 1",
        title="Thu nhận và chuẩn hóa (Query Ingestion & Normalization)",
        purpose="Chuẩn hoá ký tự nhập liệu về Unicode NFC, chuyển chữ thường, gộp khoảng trắng, đồng nhất vị trí dấu thanh tiếng Việt (hòa ↔ hoà), nhận diện câu không dấu và phát hiện các địa danh, từ vựng catalog trong câu.",
        principle="Áp dụng quy tắc regex, chuẩn hóa bảng mã Unicode NFC, bộ phân tích âm vị học tiếng Việt (Vowel Diacritic Placement) và tra cứu từ vựng từ điển (Catalog Gazetteer Lookup) tạo tiền đề cho việc tạo vector embedding và truy vấn BM25 nhất quán."
    )

    t0_norm = time.perf_counter()
    normalizer = QueryNormalizer(
        destinations=set(index.destination.tolist()),
        names=(p.name for p in index.units),
        tone=tone_normalize,
    ) if normalize else None

    nq = normalizer(q) if normalizer else None
    canonical_text = canonical_query(nq.text if nq else q)
    t_norm_ms = (time.perf_counter() - t0_norm) * 1000

    col1_in, col1_out = st.columns(2)
    with col1_in:
        st.markdown("**📥 Input**")
        st.code(f"raw_query: {q}", language="yaml")
        st.markdown(f"- **Normalize**: `{normalize}` | **Tone Normalize**: `{tone_normalize}`")
    with col1_out:
        st.markdown("**📤 Output**")
        unacc = is_unaccented(nq.text if nq else q)
        t_style = detect_style([q]) or "N/A"
        st.code(
            f"normalized_text: {nq.text if nq else q}\n"
            f"canonical_query (cache key): {canonical_text}\n"
            f"detected_destinations: {list(nq.destinations) if nq and nq.destinations else []}\n"
            f"applied_aliases: {list(nq.applied_aliases) if nq and nq.applied_aliases else []}\n"
            f"party_detected: {nq.party if nq else 'None'}\n"
            f"is_unaccented: {unacc}\n"
            f"tone_style: {t_style}\n"
            f"latency: {t_norm_ms:.2f} ms",
            language="yaml",
        )

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 2: Query understanding & Router (Hiểu ý định & Kế hoạch truy vấn)
    # --------------------------------------------------------------------------
    st.markdown("---")
    render_step_card(
        step_num="Giai đoạn 2",
        title="Query understanding & Router (Hiểu ý định & Kế hoạch truy vấn)",
        purpose="Phân tích ngữ nghĩa để bóc tách ý định (intent), thực thể (entities), và các ràng buộc cứng: F4 loại sản phẩm ('khách sạn', 'golf'), F7 thời lượng chuyến đi ('3 ngày 2 đêm', '3N2Đ'), Search POI Resolve (địa danh gazetteer con về Điểm đến chính thức), F1 điểm đến, F3 phủ định, F5 tuyến bay, F6 giá/sao/khách; đồng thời làm sạch chuỗi lexical text cho BM25.",
        principle="Phân tích cú pháp rule-based kết hợp Gazetteer (PLACES 52 địa danh & ENTITIES từ catalog): nhận diện cue từ vựng mạnh/yếu cho F4 taxonomy; bóc tách thời lượng F7 (1-30 ngày/đêm) và cắt bỏ hoàn toàn cụm này khỏi lexical_text của BM25 để chống nhiễu (an toàn 100% không làm rỗng F); tra cứu địa danh gazetteer (longest-match-first) để ánh xạ về Điểm đến chính thức (destination_via_poi=True) đưa vào bộ lọc cứng F1; nhận diện cấu trúc phủ định, tuyến bay và biểu thức số lượng."
    )

    # 07/10 (1.18.0): như SearchProducts.__post_init__ — bảng entity chỉ giữ khoá có unit trong catalog, bảng địa danh bỏ entry
    # trỏ tới điểm đến catalog không có
    gazetteers = _plan_gazetteers(index.units, entities=index.attrs.entities, destinations=set(index.destination.tolist()))
    plan_flags = PlanFlags(
        destination=dest_filter,
        negation=negation_filter,
        taxonomy=taxonomy_filter,
        route=route_filter,
        numeric=numeric_filter,
        taxonomy_strong_only=taxonomy_strong_only,
        party=party_filter,
        duration=duration_filter,
        poi=poi_resolve,
        entity=entity_filter,
    )
    plan_params = PlanParams(
        taxonomy=override_taxonomy,
        destination=override_destination if override_destination.strip() else None,
        origin=None,
        price_min=override_price_min if override_price_min > 0 else None,
        price_max=override_price_max if override_price_max > 0 else None,
        star_min=override_star_min if override_star_min > 0 else None,
        available_only=override_available_only,
        adults=override_adults if override_adults > 0 else None,
        children=override_children if override_children > 0 else None,
    )

    t0_plan = time.perf_counter()
    plan = build_query_plan(nq, q, plan_params, plan_flags, gazetteers)
    decision = plan.destination
    t_plan_ms = (time.perf_counter() - t0_plan) * 1000

    # Trực quan hóa nổi bật F4, F7, POI Resolve bằng 3 Callout Cards
    st.markdown("##### 📌 Phân Tích Ý Định Cốt Lõi (F4 Taxonomy, F7 Duration & POI Resolve):")
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        if plan.taxonomy:
            st.markdown(
                f"""
                <div style="background-color: #f3e8ff; border: 1px solid #d8b4fe; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #6b21a8; font-size: 14px; margin-bottom: 6px;">🏷️ F4: Taxonomy Filter [ĐÃ BẬT]</div>
                    <div style="font-size: 13px; color: #3b0764; margin-bottom: 4px;"><b>Taxonomy nhận diện:</b> <code style="color: #6b21a8; background: #fff; padding: 2px 6px; border-radius: 4px;">{plan.taxonomy}</code></div>
                    <div style="font-size: 12px; color: #581c87;"><b>Độ mạnh cue:</b> <code>{plan.taxonomy_strength}</code></div>
                    <div style="font-size: 12px; color: #4c1d95; margin-top: 6px;">➔ <i>Lọc cứng <code>mask(taxonomy='{plan.taxonomy}')</code> ở Giai đoạn 3</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #475569; font-size: 14px; margin-bottom: 6px;">🏷️ F4: Taxonomy Filter</div>
                    <div style="font-size: 13px; color: #64748b;"><b>Taxonomy:</b> <code>None</code> (Toàn bộ catalog)</div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 6px;"><i>Không phát hiện cue loại hình sản phẩm đặc thù</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with col_k2:
        if plan.duration_source:
            st.markdown(
                f"""
                <div style="background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #065f46; font-size: 14px; margin-bottom: 6px;">⏱️ F7: Duration Filter [BẬT]</div>
                    <div style="font-size: 13px; color: #064e3b; margin-bottom: 4px;"><b>Thời lượng:</b> <code style="color: #065f46; background: #fff; padding: 2px 6px; border-radius: 4px;">{plan.duration_days} ngày, {plan.duration_nights} đêm</code> ({plan.duration_days}N{plan.duration_nights}Đ)</div>
                    <div style="font-size: 12px; color: #047857;"><b>Nguồn bóc tách:</b> <code>{plan.duration_source}</code></div>
                    <div style="font-size: 12px; color: #064e3b; margin-top: 6px;">➔ <i>Đã <b>tiêu span khỏi BM25</b> để chống nhiễu từ khoá. Không lọc cứng vào F (an toàn 100%)</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #475569; font-size: 14px; margin-bottom: 6px;">⏱️ F7: Duration Filter</div>
                    <div style="font-size: 13px; color: #64748b;"><b>Thời lượng:</b> <code>None</code></div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 6px;"><i>Không phát hiện cụm thời lượng (3N2Đ, N ngày M đêm...)</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with col_k3:
        if plan.location:
            st.markdown(
                f"""
                <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #1e40af; font-size: 14px; margin-bottom: 6px;">📍 Search POI Resolve [BẬT]</div>
                    <div style="font-size: 13px; color: #1e3a8a; margin-bottom: 4px;"><b>Địa danh POI:</b> <code style="color: #1e40af; background: #fff; padding: 2px 6px; border-radius: 4px;">{plan.location.name}</code> (<code>{plan.location.kind}</code>)</div>
                    <div style="font-size: 13px; color: #1e3a8a; margin-bottom: 4px;"><b>Ánh xạ Điểm đến:</b> <b><code style="color: #1e3a8a; background: #dbeafe; padding: 2px 6px; border-radius: 4px;">{plan.location.destination}</code></b></div>
                    <div style="font-size: 12px; color: #1d4ed8;"><b>destination_via_poi:</b> <code>{plan.destination_via_poi}</code></div>
                    <div style="font-size: 12px; color: #1e3a8a; margin-top: 6px;">➔ <i>Đưa '{plan.location.destination}' vào F1 lọc cứng không gian F</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif decision.value:
            st.markdown(
                f"""
                <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #1e40af; font-size: 14px; margin-bottom: 6px;">📍 Điểm đến Trực tiếp (F1)</div>
                    <div style="font-size: 13px; color: #1e3a8a; margin-bottom: 4px;"><b>Điểm đến:</b> <code style="color: #1e40af; background: #fff; padding: 2px 6px; border-radius: 4px;">{decision.value}</code></div>
                    <div style="font-size: 12px; color: #1d4ed8;"><b>Nguồn:</b> <code>{decision.source}</code></div>
                    <div style="font-size: 12px; color: #1e3a8a; margin-top: 6px;"><i>Nhận diện trực tiếp từ câu truy vấn (không qua POI)</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; height: 100%;">
                    <div style="font-weight: 700; color: #475569; font-size: 14px; margin-bottom: 6px;">📍 Địa danh & Điểm đến</div>
                    <div style="font-size: 13px; color: #64748b;"><b>Điểm đến:</b> <code>None</code></div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 6px;"><i>Không phát hiện POI hay điểm đến cụ thể</i></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Bảng biến đổi chuỗi truy vấn (Text Transformation Pipeline)
    st.markdown("##### 🔀 Biến Đổi Chuỗi Truy Vấn Qua Từng Bước:")
    trans_col1, trans_col2, trans_col3 = st.columns(3)
    with trans_col1:
        st.caption("1. Chuỗi người dùng nhập (Raw):")
        st.code(q, language="text")
    with trans_col2:
        st.caption("2. Sau Chuẩn hóa Unicode/Dấu (Normalized):")
        st.code(nq.text if nq else q, language="text")
    with trans_col3:
        st.caption("3. Sau khi F7 Tiêu cụm thời lượng (BM25 Lexical Text):")
        st.code(plan.lexical_text, language="text")

    if plan.duration_source:
        st.caption("💡 *Ghi chú F7*: Cụm thời lượng đã được cắt bỏ khỏi chuỗi BM25 Lexical Text, giúp BM25 chỉ tập trung khớp tên sản phẩm, tiện ích và thương hiệu mà không bị nhiễu bởi các con số ngày/đêm.")

    col2_in, col2_out = st.columns(2)
    with col2_in:
        st.markdown("**📥 Input (Stage 2)**")
        st.code(
            f"canonical_text: {canonical_text}\n"
            f"params: taxonomy={override_taxonomy}, dest={override_destination or None}\n"
            f"flags: F1(dest)={dest_filter}, F3(neg)={negation_filter}, F4(tax)={taxonomy_filter}, F5(route)={route_filter}, F6(num)={numeric_filter}, party={party_filter}\n"
            f"flags 1.18.0: F7(duration)={duration_filter}, poi={poi_resolve}, entity={entity_filter}",
            language="yaml",
        )
    with col2_out:
        st.markdown("**📤 Output Chi Tiết (Query Plan Object)**")
        plan_diag = plan.as_diagnostics(extended=True)
        plan_dict = {
            "confidence": plan.confidence,
            "fallback_reasons": list(plan.fallback_reasons),
            "destination_decision": {
                "value": decision.value,
                "source": decision.source,
                "skipped": decision.skipped,
                "candidates": list(decision.candidates),
            },
            "taxonomy": plan.taxonomy,
            "taxonomy_strength": plan.taxonomy_strength,
            "must_not_taxonomies": list(plan.must_not_taxonomies),
            "must_not_flags": list(plan.must_not_flags),
            "price_range": f"{plan.price_min} -> {plan.price_max}" if plan.price_source else None,
            "star_min": plan.star_min,
            "party_total": plan.party_total if plan.party_source else None,
            "duration (F7)": {
                "days": plan.duration_days,
                "nights": plan.duration_nights,
                "source": plan.duration_source,
            } if plan.duration_source else None,
            "poi_location": {
                "key": plan.location.key,
                "name": plan.location.name,
                "kind": plan.location.kind,
                "destination": plan.location.destination,
            } if plan.location else None,
            "destination_via_poi": plan.destination_via_poi,
            "lexical_text_for_bm25": plan.lexical_text,
            "diagnostics": plan_diag,
            "latency": f"{t_plan_ms:.2f} ms",
        }
        st.json(plan_dict)

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 3: Filter first & Candidate Universe (Lọc cứng không gian ứng viên)
    # --------------------------------------------------------------------------
    st.markdown("---")
    render_step_card(
        step_num="Giai đoạn 3",
        title="Filter first & Candidate Universe F (Lọc cứng không gian ứng viên)",
        purpose="Loại bỏ triệt để các sản phẩm vi phạm ràng buộc cứng (địa danh - bao gồm điểm đến suy ra từ Search POI Resolve, loại hình từ F4 Taxonomy, tuyến bay F5, giá/sao/khách F6, thực thể) ngay từ đầu để tạo ra không gian ứng viên hợp lệ F, ngăn chặn việc sản phẩm sai địa điểm/sai loại bị kéo lên do tương đồng ngữ nghĩa. (Lưu ý: F7 hiện tại an toàn 100% không lọc cứng vào F).",
        principle="Thực hiện phép toán bitwise AND trên các vector boolean thuộc tính tiền tính toán (Pre-computed NumPy attribute masks: mask_taxonomy, mask_destination, mask_price, mask_star, require_entities...), đồng thời kiểm tra tính khả thi của các sản phẩm con (hạng phòng/chuyến bay) thuộc sản phẩm cha."
    )

    # Measure mask breakdown
    t0_mask = time.perf_counter()
    mask_kwargs = plan.mask_kwargs(destination=decision.value)
    mask = index.mask(**mask_kwargs)
    allowed = index.allowed_ids(mask)
    t_mask_ms = (time.perf_counter() - t0_mask) * 1000

    total_catalog = len(index.units)
    f_count = int(mask.sum())
    f_ratio = (f_count / total_catalog * 100) if total_catalog else 0

    col3_in, col3_out = st.columns(2)
    with col3_in:
        st.markdown("**📥 Input (Điều kiện tạo Mask)**")
        st.markdown(f"- **Tổng số Search Units ban đầu**: `{total_catalog}`")
        mask_desc_lines = []
        for k, v in mask_kwargs.items():
            extra = ""
            if k == "destination" and plan.destination_via_poi and plan.location:
                extra = f"  # 📍 Suy ra từ POI: '{plan.location.name}'"
            elif k == "taxonomy" and plan.taxonomy:
                extra = f"  # 🏷️ Suy ra từ F4 ({plan.taxonomy_strength})"
            mask_desc_lines.append(f"  {k}: {v}{extra}")
        st.code("mask_kwargs:\n" + "\n".join(mask_desc_lines), language="yaml")
        st.caption("🛡️ *Nguyên lý an toàn F7*: Do catalog chưa có thuộc tính duration, F7 không áp vào mask để bảo vệ không gian F không bị rỗng.")
    with col3_out:
        st.markdown("**📤 Output (Candidate Universe F)**")
        st.markdown(f"- **Số lượng ứng viên hợp lệ |F|**: `{f_count}` / `{total_catalog}` (**{f_ratio:.1f}%**)")
        st.markdown(f"- **Thời gian tính toán mask**: `{t_mask_ms:.2f} ms`")
        if plan.destination_via_poi and plan.location:
            st.success(f"📍 Điểm đến `{decision.value}` được suy ra từ POI `{plan.location.name}` đã thu hẹp F về đúng địa bàn!")
        if plan.taxonomy:
            st.info(f"🏷️ F4 đã lọc cứng chỉ giữ lại các sản phẩm có taxonomy `{plan.taxonomy}`.")
        if f_count == 0:
            st.error("⚠️ Candidate Universe F = ∅ (Rỗng)! Không có sản phẩm nào thỏa mãn toàn bộ bộ lọc cứng.")

    # Candidate Top 1 & Top Cuối của Universe F
    st.markdown("##### 👥 Các ứng viên trong Universe F (Multi-candidate):")
    if f_count > 0:
        f_indices = np.where(mask)[0]
        top1_f = index.units[f_indices[0]]
        bottom_f = index.units[f_indices[-1]]
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown(f"**🥇 Candidate Top 1 của Universe F (Index #{f_indices[0]}):**")
            st.markdown(format_candidate_summary(top1_f))
        with col_f2:
            st.markdown(f"**🔚 Candidate Top Cuối của Universe F (Index #{f_indices[-1]}):**")
            st.markdown(format_candidate_summary(bottom_f))
    else:
        st.caption("Universe F rỗng.")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 4: Candidate Retrieval Đa Kênh (Dense, BM25, Fuzzy)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### ⚡ Giai đoạn 4: Candidate Retrieval Đa Kênh (Truy hồi ứng viên)")

    # 4A. Dense Retrieval
    render_step_card(
        step_num="Giai đoạn 4A",
        title="Dense Retrieval (Semantic Vector Search)",
        purpose="Truy hồi các sản phẩm có độ tương đồng ngữ nghĩa cao nhất dựa trên câu diễn đạt tự nhiên, sở thích, phong cách chuyến đi của khách hàng.",
        principle="Vector hóa câu truy vấn bằng E5-Small (tiền tố 'query: ', 384 chiều, L2 normalized) và tính khoảng cách Cosine Similarity cos(q, d) = (q · d) / (||q|| · ||d||) với vector sản phẩm (tiền tố 'passage: ') trên kho vector Weaviate HNSW, giới hạn trong tập allowed IDs."
    )

    t0_embed = time.perf_counter()
    qvec = embedder.embed_query(canonical_text)
    t_embed_ms = (time.perf_counter() - t0_embed) * 1000

    t0_dense = time.perf_counter()
    dense_hits = [
        h for h in vector_search.near_vector(qvec, allowed, candidate_k)
        if h.product_id in index.idx
    ]
    t_dense_ms = (time.perf_counter() - t0_dense) * 1000

    col4a_in, col4a_out = st.columns(2)
    with col4a_in:
        st.markdown("**📥 Input (Dense)**")
        st.markdown(f"- **Query**: `{canonical_text}`")
        st.markdown(f"- **Embedding Model**: `intfloat/multilingual-e5-small` (384 chiều)")
        st.markdown(f"- **Candidate K**: `{candidate_k}` | **Allowed IDs**: `{len(allowed)}`")
        st.markdown(f"- **Thời gian embed**: `{t_embed_ms:.2f} ms`")
    with col4a_out:
        st.markdown("**📤 Output (Dense Hits)**")
        st.markdown(f"- **Số lượng Dense Candidates thu hồi**: `{len(dense_hits)}`")
        st.markdown(f"- **Thời gian truy vấn Weaviate**: `{t_dense_ms:.2f} ms`")

    st.markdown("##### 🎯 Kết quả Dense Retrieval (Top 1 & Top Cuối):")
    if dense_hits:
        d_top1 = index.units[index.idx[dense_hits[0].product_id]]
        d_bot = index.units[index.idx[dense_hits[-1].product_id]]
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown(f"**🥇 Candidate Top 1 Dense (Rank #1):**")
            st.markdown(format_candidate_summary(d_top1, score=dense_hits[0].score, score_label="Cosine"))
        with col_d2:
            st.markdown(f"**🔚 Candidate Top Cuối Dense (Rank #{len(dense_hits)}):**")
            st.markdown(format_candidate_summary(d_bot, score=dense_hits[-1].score, score_label="Cosine"))
    else:
        st.caption("Không có ứng viên Dense nào được thu hồi.")

    # 4B. Lexical Retrieval (BM25)
    render_step_card(
        step_num="Giai đoạn 4B",
        title="Lexical Retrieval (BM25 Keyword Search)",
        purpose="Bắt chính xác các từ khóa đặc thù, tên thương hiệu (Vinpearl, VinWonders), địa danh hoặc từ hiếm mà dense vector dễ bỏ sót. Đặc biệt, nhờ F7 cắt cụm thời lượng ('3 ngày 2 đêm', '3N2Đ'), chuỗi BM25 không còn bị ô nhiễm bởi các từ 'ngày', 'đêm', loại bỏ triệt để false-positive như khách sạn 'Chợ Đêm'.",
        principle="Sử dụng thuật toán xếp hạng Okapi BM25 trên inverted index của Weaviate: tính điểm dựa trên tần suất từ (Term Frequency - TF) và nghịch đảo tần suất tài liệu (Inverse Document Frequency - IDF) kết hợp chuẩn hóa độ dài tài liệu. Đầu vào là chuỗi plan.lexical_text đã được F7 làm sạch span thời lượng."
    )

    lex_text = canonical_query(plan.lexical_text)
    t0_lex = time.perf_counter()
    lex_hits = []
    if hybrid_on:
        try:
            lex_hits = [
                h for h in vector_search.bm25(lex_text, allowed, lexical_candidate_k, with_vectors=True)
                if h.product_id in index.idx
            ]
        except Exception as exc:
            st.warning(f"Lỗi BM25: {exc}")
    t_lex_ms = (time.perf_counter() - t0_lex) * 1000

    col4b_in, col4b_out = st.columns(2)
    with col4b_in:
        st.markdown("**📥 Input (Lexical BM25)**")
        st.markdown(f"- **Lexical Text (Đã qua xử lý F7)**: `{lex_text}`")
        if plan.duration_source:
            st.markdown(f"- **Span thời lượng đã loại bỏ (F7)**: `{plan.duration_days} ngày {plan.duration_nights} đêm` ({plan.duration_days}N{plan.duration_nights}Đ)")
        st.markdown(f"- **Candidate K**: `{lexical_candidate_k}`")
        st.markdown(f"- **Trạng thái Hybrid**: `{hybrid_on}`")
    with col4b_out:
        st.markdown("**📤 Output (BM25 Hits)**")
        st.markdown(f"- **Số lượng BM25 Candidates thu hồi**: `{len(lex_hits)}`")
        st.markdown(f"- **Thời gian truy vấn BM25**: `{t_lex_ms:.2f} ms`")

    st.markdown("##### 🎯 Kết quả BM25 Retrieval (Top 1 & Top Cuối):")
    if lex_hits:
        l_top1 = index.units[index.idx[lex_hits[0].product_id]]
        l_bot = index.units[index.idx[lex_hits[-1].product_id]]
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.markdown(f"**🥇 Candidate Top 1 BM25 (Rank #1):**")
            st.markdown(format_candidate_summary(l_top1, score=lex_hits[0].score, score_label="BM25 Score"))
        with col_l2:
            st.markdown(f"**🔚 Candidate Top Cuối BM25 (Rank #{len(lex_hits)}):**")
            st.markdown(format_candidate_summary(l_bot, score=lex_hits[-1].score, score_label="BM25 Score"))
    else:
        st.caption("Không có ứng viên BM25 nào được thu hồi (hoặc nhánh Hybrid đang tắt).")

    # 4C. Fuzzy Retrieval (Trigram)
    render_step_card(
        step_num="Giai đoạn 4C",
        title="Fuzzy Retrieval (Trigram Name Matching)",
        purpose="Cứu các trường hợp lỗi chính tả (typo), viết tắt hoặc không gõ dấu tiếng Việt khớp với tên sản phẩm trong catalog.",
        principle="Xây dựng chỉ mục 3-gram (Trigram) kiểu pg_trgm trên tên search units trong bộ nhớ. Tính độ tương đồng Dice/Jaccard trên tập các lát cắt trigram trong cửa sổ token ±1 độ dài tên, lọc lấy các ứng viên có độ tương đồng ≥ fuzzy_min_sim."
    )

    t0_fuz = time.perf_counter()
    fuzzy_found = []
    if hybrid_on and fuzzy_k > 0:
        fuzzy_idx = FuzzyIndex.build([p.name for p in index.units])
        fuzzy_found = fuzzy_idx.search(q, allowed=mask, k=fuzzy_candidate_k, min_sim=fuzzy_min_sim)
    t_fuz_ms = (time.perf_counter() - t0_fuz) * 1000

    col4c_in, col4c_out = st.columns(2)
    with col4c_in:
        st.markdown("**📥 Input (Fuzzy)**")
        st.markdown(f"- **Query**: `{q}`")
        st.markdown(f"- **Fuzzy K**: `{fuzzy_k}` | **Min Sim**: `{fuzzy_min_sim}`")
    with col4c_out:
        st.markdown("**📤 Output (Fuzzy Hits)**")
        st.markdown(f"- **Số lượng Fuzzy Candidates**: `{len(fuzzy_found)}`")
        st.markdown(f"- **Thời gian tính toán**: `{t_fuz_ms:.2f} ms`")

    st.markdown("##### 🎯 Kết quả Fuzzy Retrieval (Top 1 & Top Cuối):")
    if fuzzy_found:
        fuz_top1 = index.units[fuzzy_found[0][0]]
        fuz_bot = index.units[fuzzy_found[-1][0]]
        col_fz1, col_fz2 = st.columns(2)
        with col_fz1:
            st.markdown(f"**🥇 Candidate Top 1 Fuzzy (Rank #1):**")
            st.markdown(format_candidate_summary(fuz_top1, score=fuzzy_found[0][1], score_label="Trigram Sim"))
        with col_fz2:
            st.markdown(f"**🔚 Candidate Top Cuối Fuzzy (Rank #{len(fuzzy_found)}):**")
            st.markdown(format_candidate_summary(fuz_bot, score=fuzzy_found[-1][1], score_label="Trigram Sim"))
    else:
        st.caption("Không có ứng viên Fuzzy nào (hoặc Fuzzy K = 0 đang tắt theo mặc định).")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 5: Ranking, Fusion & Kết quả (Hợp nhất & Trả kết quả)
    # --------------------------------------------------------------------------
    st.markdown("---")
    render_step_card(
        step_num="Giai đoạn 5",
        title="Ranking, Fusion & Kết quả cuối (Hợp nhất & Xếp hạng)",
        purpose="Hợp nhất các danh sách ứng viên qua Reciprocal Rank Fusion (RRF), áp dụng các cổng lọc chất lượng (Cutoff Gate, Min Coverage Gate), kiểm tra lại tính toàn vẹn (Revalidation), ghép nối phòng con (Matched Children) và sắp xếp sao.",
        principle="Điểm RRF tính theo công thức RRF(d) = Σ w_r / (k + rank_r(d)) giúp kết hợp nhiều kênh mà không cần chuẩn hóa thang điểm. Lưới an toàn lọc lại bảo đảm không vi phạm ràng buộc cha-con, và soft star order ưu tiên hiển thị."
    )

    # Execute Hybrid / Dense Fusion using production logic
    t0_fuse = time.perf_counter()
    qv = np.asarray(qvec, dtype=np.float32)
    qn = float(np.linalg.norm(qv)) or 1.0
    cosines = {index.idx[h.product_id]: float(h.score) for h in dense_hits}

    for h in lex_hits:
        u = index.idx[h.product_id]
        if u not in cosines and h.vector is not None and len(h.vector):
            v = np.asarray(h.vector, dtype=np.float32)
            cosines[u] = float(v @ qv) / ((float(np.linalg.norm(v)) or 1.0) * qn)

    dense_rank = {index.idx[h.product_id]: r for r, h in enumerate(dense_hits, 1)}
    lexical_rank = {index.idx[h.product_id]: r for r, h in enumerate(lex_hits, 1)}

    fuzzy_rank = {u: r for r, (u, _) in enumerate(fuzzy_found, 1)} if fuzzy_found else None
    fuzzy_sim = dict(fuzzy_found) if fuzzy_found else {}
    fuzzy_admissible = (lambda u: fuzzy_sim.get(u, 0.0) >= fuzzy_min_sim) if fuzzy_found else None

    # Determine profile & config
    profile = PROFILE_NO_DIACRITICS if (no_diacritics_mode == "relax" and is_unaccented(q, 3)) else None
    effective_cutoff = no_diacritics_cutoff if profile else cutoff

    fusion_cfg = dict(
        fuzzy_k=fuzzy_k,
        fuzzy_candidate_k=fuzzy_candidate_k,
        fuzzy_min_sim=fuzzy_min_sim,
        dense_weight=dense_weight,
        lexical_weight=lexical_weight,
        fuzzy_weight=fuzzy_weight,
    )
    hybrid_config = HybridConfig(
        rrf_k=rrf_k,
        lexical_k=lexical_candidate_k,
        lexical_cutoff=min(lexical_cutoff, effective_cutoff),
        min_coverage=min_coverage,
        **fusion_cfg,
    ) if hybrid_on else None

    facet_fields = {"taxonomy": index.taxonomy, "destination": index.destination}
    name_tokens = [set(tokens(p.name)) for p in index.units]
    q_tokens = query_tokens(lex_text)

    if hybrid_on and hybrid_config:
        outcome = hybrid_filter_score(
            cosines,
            dense_rank,
            lexical_rank,
            lambda u: coverage(q_tokens, name_tokens[u]) >= hybrid_config.min_coverage,
            effective_cutoff,
            hybrid_config,
            f_count,
            facet_fields,
            fuzzy_rank=fuzzy_rank,
            fuzzy_admissible=fuzzy_admissible,
        )
    else:
        outcome = candidate_filter_score(
            [index.idx[h.product_id] for h in dense_hits],
            [h.score for h in dense_hits],
            effective_cutoff,
            f_count,
            facet_fields,
        )

    # Revalidation & joint children
    order, drops = revalidate(outcome.order, mask)
    child_filter = _child_filter(plan)
    if plan.price_active and plan.party_active:
        children_attrs = index.attrs.children
        kept = [u for u in order if not children_attrs[u] or index.matched_children(u, limit=1, **child_filter)]
        drops += (len(order) - len(kept))
        order = kept

    if plan.star_active:
        order = soft_star_order(order, index.star_known_ok(plan.star_min))

    outcome.order = order
    t_fuse_ms = (time.perf_counter() - t0_fuse) * 1000

    col5_in, col5_out = st.columns(2)
    with col5_in:
        st.markdown("**📥 Input (Fusion & Gates)**")
        st.markdown(f"- **RRF K**: `{rrf_k}` | **Effective Cutoff**: `{effective_cutoff}`")
        st.markdown(f"- **Dense Candidates**: `{len(dense_hits)}` | **BM25 Candidates**: `{len(lex_hits)}`")
        st.markdown(f"- **Trọng số**: Dense `{dense_weight}` | Lexical `{lexical_weight}` | Fuzzy `{fuzzy_weight}`")
    with col5_out:
        st.markdown("**📤 Output (Ranking Summary)**")
        st.markdown(f"- **Tổng số sản phẩm vượt qua toàn bộ các cổng (Relevant Count)**: `{outcome.total}`")
        st.markdown(f"- **Số sản phẩm bị loại ở cổng Cutoff/Coverage**: `{len(dense_hits) + len(lex_hits) - outcome.total}`")
        st.markdown(f"- **Revalidated Drops (Kiểm lại vi phạm)**: `{drops}`")
        st.markdown(f"- **Thời gian Fusion & Ranking**: `{t_fuse_ms:.2f} ms`")

    # Final Candidates: Top 1 & Top Cuối
    st.markdown("##### 🏆 Kết Quả Cuối Cùng (Candidate Top 1 & Top Cuối):")
    if outcome.order:
        final_top1_idx = outcome.order[0]
        final_bot_idx = outcome.order[-1]
        final_top1 = index.units[final_top1_idx]
        final_bot = index.units[final_bot_idx]

        col_fn1, col_fn2 = st.columns(2)
        with col_fn1:
            st.markdown(f"**🥇 Candidate Top 1 Cuối Cùng (Rank #1):**")
            st.markdown(format_candidate_summary(final_top1, score=outcome.scores[final_top1_idx], score_label="Final Score"))
            if child_filter and index.attrs.children[final_top1_idx]:
                mc = index.matched_children(final_top1_idx, **child_filter)
                st.caption(f"Matched Children: {mc}")
        with col_fn2:
            st.markdown(f"**🔚 Candidate Top Cuối Cùng (Rank #{len(outcome.order)}):**")
            st.markdown(format_candidate_summary(final_bot, score=outcome.scores[final_bot_idx], score_label="Final Score"))
            if child_filter and index.attrs.children[final_bot_idx]:
                mc = index.matched_children(final_bot_idx, **child_filter)
                st.caption(f"Matched Children: {mc}")
    else:
        st.warning("Không có sản phẩm nào đạt yêu cầu sau bước Cutoff và Ranking.")

    # --------------------------------------------------------------------------
    # HIỂN THỊ DANH SÁCH SẢN PHẨM PHÂN TRANG (PAGINATED PRODUCT LIST)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown(f"### 📋 Danh Sách Sản Phẩm Kết Quả (Hiển thị {min(limit, len(outcome.order))} / {outcome.total})")

    page_indices = outcome.order[offset : offset + limit]
    if page_indices:
        for r, u in enumerate(page_indices, offset + 1):
            prod = index.units[u]
            score_val = outcome.scores[u]
            price_val = f"{prod.unit_price:,.0f} {prod.currency}" if prod.unit_price else "Liên hệ"

            with st.container():
                col_img, col_info, col_meta = st.columns([1.5, 4.5, 2])
                with col_img:
                    if prod.image_url:
                        st.image(prod.image_url, use_container_width=True)
                    else:
                        st.markdown("<div style='height: 90px; background: #e2e8f0; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #64748b;'>No Image</div>", unsafe_allow_html=True)
                with col_info:
                    st.markdown(f"**#{r}. {prod.name}**")
                    st.caption(f"ID: `{prod.product_id}` | Taxonomy: `{prod.taxonomy}` | Điểm đến: `{prod.destination}`")
                    if prod.description:
                        desc_snip = prod.description[:140] + "..." if len(prod.description) > 140 else prod.description
                        st.markdown(f"<span style='font-size: 13px; color: #475569;'>{desc_snip}</span>", unsafe_allow_html=True)
                with col_meta:
                    st.markdown(f"**Điểm**: `{score_val:.4f}`")
                    st.markdown(f"**Giá**: `{price_val}`")
                    if child_filter and index.attrs.children[u]:
                        m_children = index.matched_children(u, **child_filter)
                        st.caption(f"Phòng khớp: {len(m_children)} phòng")
                st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid #f1f5f9;' />", unsafe_allow_html=True)
    else:
        st.info("Trang kết quả trống.")

    # --------------------------------------------------------------------------
    # DIAGNOSTICS & TIMING BREAKDOWN
    # --------------------------------------------------------------------------
    with st.expander("📊 Báo Cáo Diagnostics & Latency Breakdown", expanded=False):
        col_diag1, col_diag2 = st.columns(2)
        with col_diag1:
            st.markdown("**Độ trễ từng Stage (Latency):**")
            st.json({
                "normalizeMs": round(t_norm_ms, 2),
                "planMs": round(t_plan_ms, 2),
                "maskMs": round(t_mask_ms, 2),
                "embedMs": round(t_embed_ms, 2),
                "denseMs": round(t_dense_ms, 2),
                "lexicalMs": round(t_lex_ms, 2),
                "fuzzyMs": round(t_fuz_ms, 2),
                "fuseMs": round(t_fuse_ms, 2),
                "totalPipelineMs": round(t_norm_ms + t_plan_ms + t_mask_ms + t_embed_ms + t_dense_ms + t_lex_ms + t_fuz_ms + t_fuse_ms, 2),
            })
        with col_diag2:
            st.markdown("**Phân bố Facets kết quả:**")
            st.json(outcome.facets)


if __name__ == "__main__":
    main()
