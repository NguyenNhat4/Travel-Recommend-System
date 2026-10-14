"""SearchProducts — cờ 13/10 (contract 1.28.0; plan docs/plan/2026-10-13-search-evidence-gate-no-answer.md; FR-SRC-03/04 chốt
13/10): cổng bằng chứng theo cụm (`HybridConfig.evidence_gate`), thời lượng có vai trò (`duration_mask`), embed residual
(`embed_residual`), câu không giải thích được (`unexplained_empty`), `backgroundScore` (`emit_background`), phục hồi dấu
(`no_diacritics_restore`). Mọi cờ tắt → response y hệt engine cũ.

Catalog = ROWS của conftest + các unit tái hiện lỗi production 13/10."""
import json

import pytest

from src.backend.app.application.search import SearchProducts
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import ROWS, FakeEmbedder, P
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore

V128_ROWS = [
    *ROWS,
    P("TT1", "Thị trấn Hoàng Hôn - Sunset Town", "attraction", "Phú Quốc", {}, price=None,
      desc="Khu phố đi bộ ven biển phong cách Địa Trung Hải."),
    P("CD1", "Chợ Đêm Đà Lạt", "attraction", "Đà Lạt", {"ticketed": False}, price=None, desc="Chợ đêm sầm uất trung tâm."),
    P("HD2", "December Hotel Dalat - Ngay Trung Tâm & Chợ Đêm", "hotel", "Đà Lạt", {"level": "property", "starRating": 3},
      price=None, desc="Khách sạn gần chợ đêm, view đồi thông."),
    P("HD3", "Khách sạn Đồi Thông Đà Lạt", "hotel", "Đà Lạt", {"level": "property", "starRating": 4}, price=None,
      desc="Khách sạn yên tĩnh giữa đồi thông."),
    P("HR3", "Khách sạn Đồi Thông Đà Lạt - Deluxe", "hotel", "Đà Lạt", {"level": "room", "parentProductId": "HD3"},
      price=1200000),
    P("T2", "[Tour 2 Đảo] - [2 ngày] - VinWonders Nha Trang x Đảo Hòn Tằm", "attraction", "Nha Trang", {}, price=1500000),
    P("CB1", "[Combo 01 ngày] - VinWonders + Vinpearl Safari", "combo", "Phú Quốc", {}, price=1800000),
]
NEW_FLAGS = dict(duration_mask=True, embed_residual=True, unexplained_empty=True, emit_background=True)
GATE = HybridConfig(lexical_cutoff=-1.0, evidence_gate=True)


class SpyEmbedder(FakeEmbedder):
    def __init__(self):
        self.seen: list[str] = []

    def embed_query(self, q):
        self.seen.append(q)
        return super().embed_query(q)


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    d = tmp_path_factory.mktemp("v128")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in V128_ROWS), encoding="utf-8")
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".emb")).load()
    return {"index": index, "vectors": vectors}


def _engine(cat, embedder=None, hybrid=GATE, cutoff=-1.0, **kw):
    return SearchProducts(cat["index"], cat["vectors"], embedder or FakeEmbedder(), cutoff=cutoff,
                          lexical=cat["vectors"] if hybrid is not None else None, hybrid=hybrid, **kw)


def _ids(r):
    return [x["productId"] for x in r["results"]]


def _strip(r):
    r = json.loads(json.dumps(r))
    r["diagnostics"].pop("stageMs", None)
    return r


QUERIES = ("Nguyễn Khắc Tiệp", "khách sạn Đà Lạt 2 ngày 1 đêm", "2 ngày 1 đêm", "Trần Thị Mai", "chợ đêm Đà Lạt",
           "nguyen khac tiep", "resort Nha Trang có hồ bơi")


@pytest.mark.parametrize("q", QUERIES)
def test_flags_off_is_identical_to_engine_without_new_fields(cat, q):
    old = SearchProducts(cat["index"], cat["vectors"], FakeEmbedder(), cutoff=0.0, lexical=cat["vectors"],
                         hybrid=HybridConfig(lexical_cutoff=0.0))
    new = SearchProducts(cat["index"], cat["vectors"], FakeEmbedder(), cutoff=0.0, lexical=cat["vectors"],
                         hybrid=HybridConfig(lexical_cutoff=0.0, evidence_gate=False),
                         duration_mask=False, embed_residual=False, unexplained_empty=False, emit_background=False)
    assert _strip(old(q)) == _strip(new(q))


def test_evidence_gate_blocks_reversed_tone_less_rescue(cat):
    rescue = dict(cutoff=2.0)   # không hit dense nào qua cutoff → chỉ còn đường vớt BM25
    without = _engine(cat, hybrid=HybridConfig(lexical_cutoff=-1.0), **rescue)("Trần Thị Mai")
    assert "TT1" in _ids(without)          # lỗi production: bỏ dấu + túi chữ → "Thị trấn" khớp 2/3
    gated = _engine(cat, **rescue)("Trần Thị Mai")
    assert "TT1" not in _ids(gated) and gated["diagnostics"]["evidenceGate"] is True
    assert "CD1" in _ids(_engine(cat, **rescue)("Chợ Đêm Đà Lạt"))   # khớp đúng cụm vẫn được vớt


def test_evidence_gate_keeps_rrf_boost_only_with_phrase_in_name_or_text(cat):
    eng = _engine(cat)
    r = eng("khách sạn gần chợ đêm")
    assert {"HD2", "CD1"} <= set(_ids(r))


@pytest.mark.parametrize("q,span", [("Nguyễn Khắc Tiệp", "Nguyễn Khắc Tiệp"),
                                    ("khách sạn Nguyễn Khắc Tiệp", "Nguyễn Khắc Tiệp"),
                                    ("xkcd qwzt plorb", "xkcd qwzt plorb")])
def test_unexplained_residual_returns_empty_without_embedding(cat, q, span):
    spy = SpyEmbedder()
    r = _engine(cat, embedder=spy, **NEW_FLAGS)(q)
    qp = r["diagnostics"]["queryPlan"]
    assert r["total"] == 0 and r["results"] == [] and r["topScore"] is None and r["backgroundScore"] is None
    assert qp["emptyReason"] == "unexplained" and span in qp["unexplained"]
    assert r["diagnostics"]["filteredCount"] > 0 and spy.seen == []
    assert sum(r["facets"]["taxonomy"].values()) == r["total"]


def test_slang_residual_keeps_searching(cat):
    r = _engine(cat, **NEW_FLAGS)("khách sạn Đà Lạt rẻ bèo")
    assert r["total"] > 0 and r["diagnostics"]["queryPlan"].get("emptyReason") != "unexplained"


def test_name_with_explained_part_drops_only_the_name(cat):
    spy = SpyEmbedder()
    r = _engine(cat, embedder=spy, **NEW_FLAGS)("Nguyễn Khắc Tiệp gần biển")
    qp = r["diagnostics"]["queryPlan"]
    assert qp["unparsed"] == ["Nguyễn Khắc Tiệp"] and qp["denseText"] == "gần biển" and spy.seen == ["gần biển"]
    assert r["total"] > 0


def test_duration_gate_filters_tickets_and_combos_filter_only(cat):
    r = _engine(cat, **NEW_FLAGS)("2 ngày 1 đêm")
    qp = r["diagnostics"]["queryPlan"]
    assert qp["duration"] == {"days": 2, "nights": 1, "source": "query", "role": "gate"}
    assert _ids(r) == ["T2"] and r["diagnostics"]["filterOnly"] is True and r["cutoff"] == 0.0


def test_duration_gate_on_hotel_tab_is_empty_with_reason(cat):
    r = _engine(cat, **NEW_FLAGS)("2 ngày 1 đêm", taxonomy="hotel")
    assert r["total"] == 0 and r["diagnostics"]["queryPlan"]["emptyReason"] == "duration"


def test_duration_stay_never_drops_hotels(cat):
    r = _engine(cat, **NEW_FLAGS)("khách sạn Đà Lạt 2 ngày 1 đêm")
    assert r["diagnostics"]["queryPlan"]["duration"]["role"] == "stay"
    assert {"HD2", "HD3"} <= set(_ids(r))


def test_embed_residual_sends_query_without_consumed_spans(cat):
    spy = SpyEmbedder()
    r = _engine(cat, embedder=spy, **NEW_FLAGS)("đảo gần biển 2 ngày")
    assert spy.seen == ["đảo gần biển"] and r["diagnostics"]["queryPlan"]["denseText"] == "đảo gần biển"


def test_background_score_only_when_flag_on(cat):
    on = _engine(cat, emit_background=True)("resort Nha Trang có hồ bơi")
    assert 0.0 <= on["backgroundScore"] <= 1.0 and "saturated" in on["diagnostics"]
    assert "backgroundScore" not in _engine(cat)("resort Nha Trang có hồ bơi")


def test_accent_restore_declares_profile_without_relaxed_cutoff(cat):
    r = _engine(cat, no_diacritics_restore=True)("cho dem da lat")
    assert r["diagnostics"]["accentRestored"] and r["diagnostics"]["queryProfile"] == "no_diacritics"
    assert r["cutoff"] == -1.0   # không có bộ ngưỡng nới: giữ cutoff chung


def test_derive_plan_false_disables_new_families(cat):
    r = _engine(cat, **NEW_FLAGS)("Nguyễn Khắc Tiệp", derive_plan=False)
    assert r["diagnostics"].get("queryPlan", {}).get("emptyReason") != "unexplained"


def test_duration_with_other_content_is_soft_not_filtered(cat):
    # chốt 14/10: câu còn nội dung ngoài thời lượng → không lọc (vé VinWonders không ghi số ngày vẫn còn)
    r = _engine(cat, **NEW_FLAGS)("VinWonders 3 ngày 2 đêm")
    assert r["diagnostics"]["queryPlan"]["duration"]["role"] == "soft"
    assert "A1" in _ids(r) and r["diagnostics"]["queryPlan"].get("emptyReason") is None
