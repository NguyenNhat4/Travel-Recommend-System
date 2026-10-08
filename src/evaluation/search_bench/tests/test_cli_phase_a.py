"""Phase A (05/10) — `sb topids-diff`, kiểm định nghĩa câu của `sb qu gold-scan` (hàm thuần, plan giả), rescore giữ cột
`extra` và cột RAM của `runner.attach_unit_columns`. Không Weaviate, không fixture gold_small."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest
from typer.testing import CliRunner

from evaluation.search_bench import metrics as M, runner as R
from evaluation.search_bench.__main__ import _scan_checks, app, topids_compare

cli = CliRunner()


# ------------------------------------------------------------------ topids-diff
def test_topids_compare():
    a = [{"qid": "q1", "top_ids": ["a", "b"]}, {"qid": "q2", "top_ids": ["x", "y", "z"]}, {"qid": "q3", "top_ids": []}]
    b = [{"qid": "q1", "top_ids": ["a", "b"]}, {"qid": "q2", "top_ids": ["x", "q", "z"]}, {"qid": "q4", "top_ids": ["k"]}]
    same, total, diffs, only = topids_compare(a, b)
    assert (same, total) == (1, 2) and diffs == [("q2", 1, "y", "q")] and only == ["q3", "q4"]
    # một bên là tiền tố của bên kia → vị trí khác = độ dài ngắn hơn
    _, _, d2, _ = topids_compare([{"qid": "q", "top_ids": ["a"]}], [{"qid": "q", "top_ids": ["a", "b"]}])
    assert d2 == [("q", 1, None, "b")]


def _write_run(home, run_id, arm, rows):
    d = R.arm_dir(run_id, arm)
    (d / R.RESULTS).write_text(json.dumps({"arm": arm, "gold_version": "fixture:x", "overall": {}}), encoding="utf-8")
    pd.DataFrame(rows).to_parquet(d / R.PER_QUERY, index=False)


def test_cli_topids_diff(home):
    rows = [{"qid": "q1", "top_ids": ["a", "b"]}, {"qid": "q2", "top_ids": ["c"]}]
    _write_run(home, "r1", "A", rows)
    _write_run(home, "r1", "B", [rows[0], {"qid": "q2", "top_ids": ["d"]}])
    res = cli.invoke(app, ["topids-diff", "r1", "A"])
    assert res.exit_code == 0 and "2/2 câu trùng" in res.output, res.output
    res = cli.invoke(app, ["topids-diff", "r1", "A", "--arm-b", "B"])
    assert res.exit_code == 1 and "1/2 câu trùng" in res.output and "q2: khác từ vị trí 1: A=c B=d" in res.output
    res = cli.invoke(app, ["topids-diff", "r1", "A", "--run-b", "r9"])
    assert res.exit_code == 2


# ------------------------------------------------------------------ gold-scan: kiểm định nghĩa câu trên plan giả
def plan(**kw):
    base = dict(destination=SimpleNamespace(value=None), taxonomy=None, taxonomy_skipped=None, taxonomy_candidates=(),
                route_origin=None, route_destination=None, route_direction=None, route_skipped=None, must_not_amenities=(),
                unresolved=(), price_max=None, price_min=None, star_min=None)
    base.update(kw)
    return SimpleNamespace(**base)


def gq(**kw):
    base = dict(qid="q", text="t", slice="s", judgments={})
    base.update(kw)
    return M.GoldQuery(**base)


def test_scan_checks_multi_constraint():
    g = gq(slice="multi_constraint", filter={"and": [{"eq": ["destination", "Đà Nẵng"]}, {"gte": ["star_rating", 4]},
                                                     {"lte": ["unit_price_min", 2000000]}]})
    ok = _scan_checks(g, plan(destination=SimpleNamespace(value="Đà Nẵng"), star_min=4.0, price_max=2000000))
    assert [(n, o) for n, o, _ in ok] == [("multi_constraint.destination", True), ("multi_constraint.star_min", True),
                                          ("multi_constraint.price_max", True)]
    bad = _scan_checks(g, plan(destination=SimpleNamespace(value=None), star_min=None, price_max=1500000))
    assert [o for _, o, _ in bad] == [False, False, False] and "price_max=1500000" in bad[2][2]


def test_scan_checks_other_slices_and_route():
    assert _scan_checks(gq(slice="cross_vertical"), plan(taxonomy=None, taxonomy_skipped="multi"))[0][1] is True
    assert _scan_checks(gq(slice="cross_vertical"), plan(taxonomy="hotel"))[0][1] is False
    assert _scan_checks(gq(slice="amenity_negation"), plan(must_not_amenities=("pool",)))[0][1] is True
    assert _scan_checks(gq(slice="amenity_negation"), plan())[0][1] is False
    assert _scan_checks(gq(slice="dest_type"), plan(taxonomy_candidates=("hotel",)))[0][1] is True
    assert _scan_checks(gq(slice="dest_type"), plan(taxonomy_candidates=("hotel", "golf")))[0][1] is False
    # c0373 theo bảng v3; gold v4 có origin / destination_city thì theo gold
    r = _scan_checks(gq(qid="c0373", slice="named_entity"), plan(route_origin="Buôn Ma Thuột", route_destination="Hà Nội"))
    assert r == [("route.origin_destination", True, r[0][2])]
    assert _scan_checks(gq(qid="c0373", slice="named_entity"), plan(route_origin="Hà Nội"))[0][1] is False
    assert _scan_checks(gq(slice="x", destination_city="Hà Nội"), plan(route_destination="Hà Nội"))[0][1] is True
    assert _scan_checks(gq(slice="x"), plan()) == []


# ------------------------------------------------------------------ rescore giữ extra
ITEMS = pd.DataFrame({"product_id": ["a", "b"], "variant": ["hotel_property", "hotel_property"], "taxonomy": ["hotel", "hotel"],
                      "origin_city": ["", ""], "destination_city": ["", ""], "features": [["pool"], []],
                      "unit_price_min": [1.0, 2.0], "star_rating": [4.0, 3.0], "destination": ["X", "Y"],
                      "parent_product_id": [None, None]}).set_index("product_id", drop=False)


def _env(cfg, tmp_path, gold):
    gp = tmp_path / "gold.jsonl"
    gp.write_text("", encoding="utf-8")
    return R.RunEnv(cfg=cfg, dataset="sample", run_id="t", gold_path=gp, gold_version="fixture:x", gold_sha256="0",
                    gold=gold, ctx=M.EvalContext(cfg.metrics, ITEMS, {}), n_items=len(ITEMS))


def test_rescore_row_keeps_extra_and_uses_it(cfg, tmp_path):
    g = gq(qid="q1", judgments={"a": 2}, expected_parse={"taxonomy": "hotel"})
    extra = {"queryPlan": {"taxonomy": {"value": "hotel", "source": "query"}}, "total": 2}
    old = {"qid": "q1", "top_ids": ["a", "b"], "top_scores": [0.9, 0.8], "applied_filter": json.dumps({"eq": ["taxonomy", "hotel"]}),
           "latency_ms": 1.5, "extra": json.dumps(extra, ensure_ascii=False)}
    row = R.rescore_row(g, old, _env(cfg, tmp_path, [g]))
    assert row["extra"] == old["extra"] and row["applied_filter"] == old["applied_filter"] and row["latency_ms"] == 1.5
    assert json.loads(row["parse_ok"]) == {"taxonomy": True} and (row["filter_pass_ok"], row["filter_pass_n"]) == (2, 2)
    # dòng cũ không có extra → None, parse_ok None
    row0 = R.rescore_row(g, {**old, "extra": None}, _env(cfg, tmp_path, [g]))
    assert row0["extra"] is None and row0["parse_ok"] is None
    assert R.extra_of({"extra": "{bad"}) is None and R.extra_of({"extra": "{}"}) is None and R.extra_of({}) is None


def test_rescore_arm_round_trip_keeps_extra(cfg, home, tmp_path):
    g = gq(qid="q1", judgments={"a": 2})
    env = _env(cfg, tmp_path, [g])
    rows = [{"qid": "q1", "slice": "s", "top_ids": ["a"], "top_scores": [0.9], "applied_filter": None, "latency_ms": 1.0,
             "extra": json.dumps({"total": 1})}]
    d = R.arm_dir("t", "ARM")
    (d / R.RESULTS).write_text(json.dumps({"arm": "ARM", "gold_version": "fixture:old", "overall": {"hub_score_max": None}}),
                               encoding="utf-8")
    pd.DataFrame(rows).to_parquet(d / R.PER_QUERY, index=False)
    res, out_rows, info = R.rescore_arm(env, "t", "ARM")
    assert out_rows[0]["extra"] == json.dumps({"total": 1}) and info == {"missing": []}
    back = pd.read_parquet(d / "per_query@fixture_x.parquet")
    assert back["extra"].tolist() == [json.dumps({"total": 1})]
    assert res["overall"]["forbidden_at_10"] is None and res["gold_version"] == "fixture:x"


# ------------------------------------------------------------------ cột RAM
def test_attach_unit_columns_uses_backend_vocabulary(cfg):
    items = pd.DataFrame({"product_id": ["h1", "f1"], "amenities_raw": [["Hồ bơi ngoài trời", "Bếp riêng", "Sân golf 570 m"], []]}
                         ).set_index("product_id", drop=False)
    records = [{"productId": "h1", "attributes": {"amenities": ["Hồ bơi ngoài trời"]}},
               {"productId": "f1", "attributes": {"originCity": "Hà Nội", "destinationCity": "Đà Nẵng"}}]
    out = R.attach_unit_columns(items, records, cfg)
    assert out["origin_city"].tolist() == ["", "Hà Nội"] and out["destination_city"].tolist() == ["", "Đà Nẵng"]
    assert out["features"].tolist() == [["kitchen", "pool"], []]          # "Sân golf 570 m" là POI kèm khoảng cách → bỏ (backend)
    assert cfg.catalog.amenity_scope == "property_plus_rooms"            # nhánh dùng thẳng amenities_raw


def test_attach_unit_columns_property_only_merges_children(cfg):
    only = cfg.model_copy(update={"catalog": cfg.catalog.model_copy(update={"amenity_scope": "property_only"})})
    items = pd.DataFrame({"product_id": ["h1"], "amenities_raw": [["Hồ bơi"]]}).set_index("product_id", drop=False)
    records = [{"productId": "h1", "taxonomy": "hotel", "attributes": {"amenities": ["Hồ bơi"], "level": "property"}},
               {"productId": "r1", "taxonomy": "hotel", "attributes": {"parentProductId": "h1", "level": "room", "amenities": ["Ban công"]}}]
    out = R.attach_unit_columns(items, records, only)
    assert out["features"].tolist() == [["balcony", "pool"]]
