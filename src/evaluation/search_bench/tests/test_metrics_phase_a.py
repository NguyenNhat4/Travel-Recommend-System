"""Phase A (05/10) — metric forbidden / direction / filter_pass / parse_ok trên items tự dựng (không Weaviate, không fixture
gold_small). Công thức tính tay ghi ở comment; None-safety của aggregate và thứ tự ưu tiên gold > forbidden_overrides."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from evaluation.search_bench import metrics as M
from evaluation.search_bench.config import DEFAULT_GOLD_FIELDS

# ------------------------------------------------------------------ items: 3 tuyến bay, 3 khách sạn, 1 điểm tham quan
ITEMS = pd.DataFrame({
    "product_id": ["f_bmt_hn", "f_hn_dn", "f_sgn_hn", "h_pool", "h_kitchen", "h_plain", "a_golf"],
    "variant": ["flight_route", "flight_route", "flight_route", "hotel_property", "hotel_property", "hotel_property", "attraction"],
    "taxonomy": ["flight", "flight", "flight", "hotel", "hotel", "hotel", "attraction"],
    "origin_city": ["Buôn Ma Thuột", "Hà Nội", "TP. Hồ Chí Minh", "", "", "", ""],
    "destination_city": ["Hà Nội", "Đà Nẵng", "Hà Nội", "", "", "", ""],
    "features": [[], [], [], ["pool", "spa"], ["kitchen"], [], []],
    "unit_price_min": [1.5e6, 1.2e6, 0.9e6, 2.0e6, 0.8e6, None, 3.0e5],
    "star_rating": [None, None, None, 5.0, 3.0, None, None],
    "destination": ["Hà Nội", "Đà Nẵng", "Hà Nội", "Côn Đảo", "TP. Hồ Chí Minh", "Hạ Long", "Hội An"],
    "parent_product_id": [None] * 7,
}).set_index("product_id", drop=False)


@pytest.fixture()
def ctx(cfg):
    return M.EvalContext(cfg.metrics, ITEMS, {})


def gq(qid="q", **kw) -> M.GoldQuery:
    base = dict(qid=qid, text="t", slice="s", judgments={"h_pool": 2})
    base.update(kw)
    return M.GoldQuery(**base)


# ------------------------------------------------------------------ forbidden
def test_forbidden_hits_filter_or_list(ctx):
    g = gq(forbidden_filter={"contains_any": ["features", ["pool"]]}, forbidden=["a_golf"])
    # top-4: h_pool (khớp filter), h_kitchen (không), a_golf (trong danh sách), h_plain → 2/4
    row = M.evaluate_query(g, ["h_pool", "h_kitchen", "a_golf", "h_plain"], ctx)
    assert (row["forbidden_hits"], row["forbidden_n"]) == (2, 4)
    # không có spec → None/None; có spec nhưng không kết quả → 0/0
    assert M.evaluate_query(gq(), ["h_pool"], ctx)["forbidden_hits"] is None
    assert M.evaluate_query(gq(), ["h_pool"], ctx)["forbidden_n"] is None
    assert (M.evaluate_query(g, [], ctx)["forbidden_hits"], M.evaluate_query(g, [], ctx)["forbidden_n"]) == (0, 0)


def test_forbidden_route_filter(ctx):
    g = gq(forbidden_filter={"and": [{"eq": ["variant", "flight_route"]},
                                     {"not": {"and": [{"eq": ["origin_city", "Buôn Ma Thuột"]}, {"eq": ["destination_city", "Hà Nội"]}]}}]})
    # f_bmt_hn đúng chặng; f_hn_dn, f_sgn_hn sai chặng; h_pool không phải tuyến bay → 2/4
    row = M.evaluate_query(g, ["f_bmt_hn", "f_hn_dn", "f_sgn_hn", "h_pool"], ctx)
    assert (row["forbidden_hits"], row["forbidden_n"]) == (2, 4)


# ------------------------------------------------------------------ direction
@pytest.mark.parametrize("origin, dest, top, want", [
    (None, None, ["f_bmt_hn"], None),                                   # câu không nêu chiều
    ("Buôn Ma Thuột", "Hà Nội", ["f_bmt_hn", "h_pool"], 1),             # khách sạn không tính
    ("Buôn Ma Thuột", "Hà Nội", ["f_bmt_hn", "f_hn_dn"], 0),            # một tuyến sai chiều
    (None, "Hà Nội", ["f_bmt_hn", "f_sgn_hn"], 1),                      # chỉ so điểm đến
    ("Ha Noi", None, ["f_hn_dn"], 1),                                   # so sau fold (không dấu vẫn khớp)
    ("Hà Nội", None, ["h_pool", "a_golf"], None),                       # không tuyến bay nào trong top-k → không xác định, không phải 1 rỗng
    ("Hà Nội", None, [], None),
])
def test_direction_ok(ctx, origin, dest, top, want):
    row = M.evaluate_query(gq(origin=origin, destination_city=dest), top, ctx)
    assert row["direction_ok"] == want


def test_direction_without_route_not_counted_in_accuracy(ctx, cfg):
    # a: câu nêu chiều nhưng top-k toàn khách sạn → None, bị loại khỏi direction_accuracy; chỉ b (sai chiều) được tính
    rows = [M.evaluate_query(gq("a", origin="Hà Nội"), ["h_pool", "a_golf"], ctx),
            M.evaluate_query(gq("b", origin="Hà Nội"), ["f_bmt_hn"], ctx)]
    assert M.aggregate(rows, cfg.metrics)["overall"]["direction_accuracy"] == 0.0


def test_direction_needs_ram_columns(cfg):
    bare = M.EvalContext(cfg.metrics, ITEMS.drop(columns=["origin_city", "destination_city"]), {})
    with pytest.raises(M.MetricsError, match="origin_city"):
        M.evaluate_query(gq(origin="Hà Nội"), ["f_bmt_hn"], bare)
    # câu không nêu chiều thì không cần cột
    assert M.evaluate_query(gq(), ["f_bmt_hn"], bare)["direction_ok"] is None


# ------------------------------------------------------------------ filter_pass
def test_filter_pass(ctx):
    row = M.evaluate_query(gq(), ["h_pool", "h_kitchen", "f_bmt_hn"], ctx, applied_filter={"eq": ["taxonomy", "hotel"]})
    assert (row["filter_pass_ok"], row["filter_pass_n"]) == (2, 3)
    none = M.evaluate_query(gq(), ["h_pool"], ctx)
    assert none["filter_pass_ok"] is None and none["filter_pass_n"] is None
    empty = M.evaluate_query(gq(), [], ctx, applied_filter={"eq": ["taxonomy", "hotel"]})
    assert (empty["filter_pass_ok"], empty["filter_pass_n"]) == (0, 0)


# ------------------------------------------------------------------ parse_ok
EXTRA = {"queryPlan": {"taxonomy": {"value": "hotel", "source": "query"},
                       "route": {"origin": "Buôn Ma Thuột", "destinationCity": "Hà Nội", "direction": "explicit", "source": "query"},
                       "mustNot": {"amenities": ["spa", "pool"], "brands": []},
                       "price": {"min": None, "max": 2000000, "source": "query"},
                       "star": {"min": 4, "source": "query"}},
         "appliedFilters": {"hard": {"destination": "Côn Đảo", "destinationSource": "query"}, "soft": {}}}


def test_parse_ok_fields(ctx):
    expected = {"taxonomy": "Hotel", "destination": "Con Dao", "origin": "buon ma thuot", "destination_city": "Hà Nội",
                "must_not": ["pool", "spa"], "price_max": 2000000.0, "price_min": None, "star_min": 4.0}
    row = M.evaluate_query(gq(expected_parse=expected), ["h_pool"], ctx, extra=EXTRA)
    assert json.loads(row["parse_ok"]) == {f: True for f in M.PARSE_FIELDS}
    # chỉ so trường gold nêu; sai một trường
    row = M.evaluate_query(gq(expected_parse={"taxonomy": "flight", "must_not": ["pool"]}), ["h_pool"], ctx, extra=EXTRA)
    assert json.loads(row["parse_ok"]) == {"taxonomy": False, "must_not": False}
    # thiếu expected_parse hoặc không có queryPlan → None
    assert M.evaluate_query(gq(), ["h_pool"], ctx, extra=EXTRA)["parse_ok"] is None
    assert M.evaluate_query(gq(expected_parse={"taxonomy": "hotel"}), ["h_pool"], ctx, extra={"total": 3})["parse_ok"] is None
    assert M.evaluate_query(gq(expected_parse={"taxonomy": "hotel"}), ["h_pool"], ctx)["parse_ok"] is None


def test_plan_fields_destination_fallback():
    extra = {"queryPlan": {"applied": []}, "destinationFilter": {"source": "query", "value": "Hạ Long"}}
    got = M.plan_fields(extra)
    assert got["destination"] == "Hạ Long" and got["taxonomy"] is None and got["must_not"] == [] and got["price_max"] is None
    assert M.plan_fields(None) is None and M.plan_fields({"appliedFilters": {}}) is None


# ------------------------------------------------------------------ aggregate
def test_aggregate_phase_a_values_and_none_safety(ctx, cfg):
    rows = [
        M.evaluate_query(gq("a", slice="neg", forbidden_filter={"contains_any": ["features", ["pool"]]}),
                         ["h_pool", "h_kitchen"], ctx),                                        # hits 1/2
        M.evaluate_query(gq("b", slice="neg", forbidden=["a_golf"]), ["h_plain", "h_kitchen"], ctx),   # hits 0/2
        M.evaluate_query(gq("c", slice="route", origin="Hà Nội"), ["f_hn_dn"], ctx,
                         applied_filter={"eq": ["taxonomy", "flight"]}, extra=EXTRA),          # direction 1, pass 1/1
        M.evaluate_query(gq("d", slice="route", origin="Hà Nội", expected_parse={"taxonomy": "hotel", "price_max": 1}),
                         ["f_bmt_hn", "h_pool"], ctx, applied_filter={"eq": ["taxonomy", "flight"]}, extra=EXTRA),  # direction 0, pass 1/2
    ]
    agg = M.aggregate(rows, cfg.metrics)
    o = agg["overall"]
    assert o["forbidden_at_10"] == pytest.approx(1 / 4)            # (1 + 0) / (2 + 2)
    assert o["forbidden_query_rate"] == pytest.approx(1 / 2)       # a có hit, b không
    assert o["direction_accuracy"] == pytest.approx(1 / 2)         # c đúng, d sai; a, b không định nghĩa
    assert o["filter_pass_rate"] == pytest.approx(2 / 3)           # (1 + 1) / (1 + 2)
    assert o["parse_accuracy"] == {"price_max": 0.0, "taxonomy": 1.0}   # chỉ d có expected_parse
    neg, route = agg["by_slice"]["neg"], agg["by_slice"]["route"]
    assert neg["forbidden_at_10"] == pytest.approx(1 / 4) and neg["direction_accuracy"] is None and neg["filter_pass_rate"] is None
    assert neg["parse_accuracy"] is None
    assert route["forbidden_at_10"] is None and route["forbidden_query_rate"] is None and route["direction_accuracy"] == 0.5
    # cột cũ vẫn có và không đổi nghĩa: c, d có h_pool (nhãn 2) bị filter cứng `flight` loại → filter_recall_loss 1 + 1
    assert o["constraint_precision"] is None and o["filter_recall_loss"] == 2 and agg["n_queries"] == 4


def test_aggregate_old_rows_without_new_columns(cfg):
    """Dòng per_query cũ (trước Phase A) gộp được và mọi metric mới là None; recall cũ không đổi."""
    k = cfg.metrics.k
    old = [{"qid": "q1", "slice": "s", "expected_no_result": False, f"recall@{k}": 0.5, f"ndcg@{k}": 0.4, f"mrr@{k}": 1.0,
            f"judged@{k}": 0.3, **{f"recall@{kk}": 0.2 for kk in cfg.metrics.extra_recall_k},
            "constraint_ok": 0, "constraint_n": 0, "filter_recall_loss": 0, "n_dup_parent": 0, "zero_result": False}]
    agg = M.aggregate(old, cfg.metrics)
    o = agg["overall"]
    assert o[f"recall@{k}"] == 0.5 and o[f"ndcg@{k}"] == 0.4
    for name in ("forbidden_at_10", "forbidden_query_rate", "direction_accuracy", "filter_pass_rate", "parse_accuracy"):
        assert o[name] is None and agg["by_slice"]["s"][name] is None
    # dòng đọc lại từ parquet: NaN thay None cũng phải an toàn
    old[0].update({"forbidden_hits": float("nan"), "forbidden_n": float("nan"), "direction_ok": float("nan"),
                   "filter_pass_ok": float("nan"), "filter_pass_n": float("nan"), "parse_ok": float("nan")})
    assert M.aggregate(old, cfg.metrics)["overall"]["forbidden_at_10"] is None


# ------------------------------------------------------------------ gold v4 fields + forbidden_overrides
def test_load_gold_phase_a_fields_and_name_map(tmp_path):
    rec = {"qid": "c1", "text": "t", "slice": "s", "judgments": {"h_pool": 2},
           "fb": {"contains_any": ["features", ["pool"]]}, "ban": ["a_golf"], "origin": "Hà Nội", "destination_city": " Đà Nẵng ",
           "expected_parse": {"taxonomy": "flight"}, "family": "route", "unknown_key": 1}
    p = tmp_path / "gold.jsonl"
    p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    g = M.load_gold(p, gold_fields={**DEFAULT_GOLD_FIELDS, "forbidden_filter": "fb", "forbidden": "ban"})[0]
    assert g.forbidden_filter == {"contains_any": ["features", ["pool"]]} and g.forbidden == ("a_golf",) and g.has_forbidden
    assert (g.origin, g.destination_city, g.family) == ("Hà Nội", "Đà Nẵng", "route") and g.expected_parse == {"taxonomy": "flight"}
    # tên mặc định: không có trường → None / rỗng; filter sai → MetricsError
    g0 = M.load_gold(p)[0]
    assert g0.forbidden_filter is None and g0.forbidden == () and not g0.has_forbidden and g0.origin == "Hà Nội"
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({**rec, "fb": {"xor": []}}, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(M.MetricsError, match="toán tử lạ"):
        M.load_gold(bad, gold_fields={"forbidden_filter": "fb"})


def test_load_gold_rejects_unknown_expected_parse_keys(tmp_path):
    # khoá gõ sai (price_maximum thay price_max) không được lặng lẽ bỏ qua — báo lỗi nêu tên khoá lạ
    rec = {"qid": "c1", "text": "t", "slice": "s", "judgments": {"h_pool": 2},
           "expected_parse": {"taxonomy": "hotel", "price_maximum": 1, "star_minimum": 4}}
    p = tmp_path / "gold.jsonl"
    p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(M.MetricsError, match=r"gold\.jsonl:1.*price_maximum.*star_minimum"):
        M.load_gold(p)
    # đúng tên trường thì nạp bình thường
    p.write_text(json.dumps({**rec, "expected_parse": {"taxonomy": "hotel", "price_max": 1}}, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    assert M.load_gold(p)[0].expected_parse == {"taxonomy": "hotel", "price_max": 1}


def test_forbidden_overrides_gold_wins(tmp_path):
    ov = tmp_path / "forbidden.yaml"
    ov.write_text("c1: {contains_any: [features, [pool]]}\nc2: {eq: [taxonomy, attraction]}\n", encoding="utf-8")
    over = M.load_forbidden_overrides(ov)
    assert set(over) == {"c1", "c2"}
    gold = [gq("c1", forbidden_filter={"eq": ["taxonomy", "hotel"]}), gq("c2"), gq("c3")]
    assert M.apply_forbidden_overrides(gold, over) == 1
    assert gold[0].forbidden_filter == {"eq": ["taxonomy", "hotel"]}        # gold thắng
    assert gold[1].forbidden_filter == {"eq": ["taxonomy", "attraction"]}   # gắn từ overrides
    assert gold[2].forbidden_filter is None
    assert M.load_forbidden_overrides(tmp_path / "missing.yaml") == {}
    bad = tmp_path / "bad.yaml"
    bad.write_text("c9: {xor: []}\n", encoding="utf-8")
    with pytest.raises(M.MetricsError, match="c9"):
        M.load_forbidden_overrides(bad)


def test_forbidden_overrides_skip_gold_with_explicit_ids():
    # gold đã liệt kê product_id cấm (không có filter) vẫn là "gold thắng": không gắn filter chẩn đoán lên câu đó
    over = {"c1": {"eq": ["taxonomy", "attraction"]}, "c2": {"eq": ["taxonomy", "attraction"]}}
    gold = [gq("c1", forbidden=("a_golf",)), gq("c2")]      # tuple như load_gold trả về
    assert M.apply_forbidden_overrides(gold, over) == 1
    assert gold[0].forbidden_filter is None and gold[0].forbidden == ("a_golf",)
    assert gold[1].forbidden_filter == {"eq": ["taxonomy", "attraction"]}


def test_shipped_forbidden_v3_is_valid_and_matches_catalog_cities():
    from evaluation.search_bench import paths
    over = M.load_forbidden_overrides(paths.PKG_DIR / "config" / "forbidden_v3.yaml")
    assert set(over) == {"c0241", "c0244", "c0247", "c0250", "c0253", "c0373", "c0070", "c0088"}
    assert over["c0241"] == {"contains_any": ["features", ["pool"]]} and over["c0088"] == {"eq": ["taxonomy", "attraction"]}
    # chạy được trên items tự dựng: c0373 cấm tuyến khác BMT→HN, c0070 cấm tuyến không đến Hà Nội
    from evaluation.search_bench.store import filters as F
    assert F.mask(over["c0373"], ITEMS).tolist() == [False, True, True, False, False, False, False]
    assert F.mask(over["c0070"], ITEMS).tolist() == [False, True, False, False, False, False, False]
