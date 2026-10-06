"""06/10 — config/query_annotations.yaml: nạp + kiểm (version, khoá lạ cấp file / cấp câu, AST, kiểu `expected_parse`), thứ tự
ưu tiên (gold thắng từng trường, khối cấm forbidden_filter + forbidden, annotations thắng forbidden_overrides cũ), qid lạ và
`runner.annotate_gold` (annotations + khối rubric). Không Weaviate, không catalog."""
from __future__ import annotations

import json

import pytest

from evaluation.search_bench import metrics as M, paths, runner as R

HEADER = 'version: 1\nannotated_by: "test"\nqueries:\n'


def _write(tmp_path, text: str, name: str = "ann.yaml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def gq(qid: str, **kw) -> M.GoldQuery:
    base = dict(qid=qid, text="t", slice="s", judgments={"a": 2})
    base.update(kw)
    return M.GoldQuery(**base)


# ------------------------------------------------------------------ nạp + kiểm
def test_load_annotations_valid(tmp_path):
    p = _write(tmp_path, HEADER + """\
  c1:
    forbidden_filter: {contains_any: [features, [pool]]}
    origin: " Hà Nội "
    destination_city: null
    expected_parse: {taxonomy: hotel, destination: "Côn Đảo", origin: null, must_not: [pool], must_not_brands: [],
                     price_max: 2000000, star_min: 4.5, party_total: 2}
    family: f1
  c2:
    forbidden: [p1, p2]
  c3:
""")
    ann = M.load_annotations(p)
    assert set(ann) == {"c1", "c2", "c3"}
    c1 = ann["c1"]
    assert c1["forbidden_filter"] == {"contains_any": ["features", ["pool"]]} and c1["origin"] == "Hà Nội" and c1["family"] == "f1"
    assert "destination_city" not in c1                          # null ở cấp câu = không gắn
    assert c1["expected_parse"]["origin"] is None                # null trong expected_parse = kỳ vọng parser không ra gì → giữ
    assert c1["expected_parse"]["price_max"] == 2000000 and c1["expected_parse"]["must_not_brands"] == []
    assert ann["c2"] == {"forbidden": ("p1", "p2")} and ann["c3"] == {}


@pytest.mark.parametrize("body, match", [
    ("version: 2\nqueries: {}\n", "version phải là 1"),
    ("queries: {}\n", "version phải là 1"),
    ("version: 1\nqueries: {}\nextra: 1\n", r"khoá lạ \['extra'\]"),
    ("- a\n", "phải là mapping"),
    ("version: 1\nqueries: [c1]\n", "queries phải là mapping"),
    (HEADER + "  c1: {forbidden_filters: {eq: [taxonomy, golf]}}\n", r"c1: khoá lạ \['forbidden_filters'\]"),
    (HEADER + "  c1: {forbidden_filter: {xor: []}}\n", "c1: forbidden_filter"),
    (HEADER + "  c1: {expected_parse: {price_maximum: 1}}\n", r"c1: expected_parse có khoá lạ \['price_maximum'\]"),
    (HEADER + "  c1: {expected_parse: {price_max: 2tr}}\n", r"expected_parse\.price_max sai kiểu"),
    (HEADER + "  c1: {expected_parse: {must_not: pool}}\n", r"expected_parse\.must_not sai kiểu"),
    (HEADER + "  c1: {expected_parse: {star_min: true}}\n", r"expected_parse\.star_min sai kiểu"),
    (HEADER + "  c1: {expected_parse: [taxonomy]}\n", "expected_parse phải là object"),
    (HEADER + "  c1: {origin: [Hà Nội]}\n", "origin phải là chuỗi"),
    (HEADER + "  c1: {forbidden: p1}\n", "forbidden phải là danh sách"),
    (HEADER + "  c1: [family]\n", "c1: phải là mapping"),
])
def test_load_annotations_rejects(tmp_path, body, match):
    with pytest.raises(M.MetricsError, match=match):
        M.load_annotations(_write(tmp_path, body))


def test_load_annotations_missing_file(tmp_path):
    with pytest.raises(M.MetricsError, match="không thấy"):
        M.load_annotations(tmp_path / "none.yaml")


def test_gold_expected_parse_types_checked_too(tmp_path):
    rec = {"qid": "c1", "text": "t", "slice": "s", "judgments": {"a": 2}, "expected_parse": {"party_total": "hai"}}
    p = tmp_path / "gold.jsonl"
    p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(M.MetricsError, match=r"gold\.jsonl:1: expected_parse\.party_total sai kiểu"):
        M.load_gold(p)


# ------------------------------------------------------------------ thứ tự ưu tiên
def test_apply_gold_wins_per_field_and_forbidden_block():
    ann = {"c1": {"forbidden_filter": {"eq": ["taxonomy", "golf"]}, "origin": "Hà Nội", "destination_city": "Đà Nẵng",
                  "expected_parse": {"taxonomy": "flight"}, "family": "f"},
           "c2": {"forbidden_filter": {"eq": ["taxonomy", "golf"]}, "family": "f"},
           "c3": {"forbidden": ("p9",)},
           "c4": {"forbidden": ("p9",), "forbidden_filter": {"eq": ["taxonomy", "golf"]}}}
    gold = [gq("c1", origin="Huế", expected_parse={"taxonomy": "hotel"}),    # gold có origin + expected_parse
            gq("c2", forbidden=("p1",)),                                      # gold có danh sách cấm → khối cấm không nhận gì
            gq("c3", forbidden_filter={"eq": ["taxonomy", "hotel"]}),         # gold có filter cấm → không nhận danh sách
            gq("c4")]
    n = M.apply_annotations(gold, ann, known_qids={"c1", "c2", "c3", "c4"})
    g1, g2, g3, g4 = gold
    assert g1.origin == "Huế" and g1.expected_parse == {"taxonomy": "hotel"}             # gold thắng từng trường
    assert g1.destination_city == "Đà Nẵng" and g1.family == "f"                         # trường gold thiếu → gắn
    assert g1.forbidden_filter == {"eq": ["taxonomy", "golf"]} and g1.forbidden == ()
    assert g2.forbidden_filter is None and g2.forbidden == ("p1",) and g2.family == "f"
    assert g3.forbidden_filter == {"eq": ["taxonomy", "hotel"]} and g3.forbidden == ()
    assert g4.forbidden == ("p9",) and g4.forbidden_filter == {"eq": ["taxonomy", "golf"]}
    assert n == {"forbidden": 2, "destination_city": 1, "family": 2}


def test_apply_unknown_qids_and_absent_queries():
    ann = {"c1": {"family": "f"}, "c9": {"family": "x"}, "c8": {"family": "y"}}
    with pytest.raises(M.MetricsError, match=r"annotations: 2 qid không có trong gold \(c8, c9\)"):
        M.apply_annotations([gq("c1")], ann, known_qids={"c1"})
    # qid có trong gold chuẩn nhưng không có trong gold đang chấm (fixture / gold cũ) → bỏ qua, không lỗi
    gold = [gq("c1")]
    assert M.apply_annotations(gold, ann, known_qids={"c1", "c8", "c9"}) == {"family": 1}
    # không truyền known_qids → không kiểm
    assert M.apply_annotations([gq("c1")], ann) == {"family": 1}


def _gold_file(tmp_path, qids: list[str]):
    p = tmp_path / "gold.jsonl"
    p.write_text("".join(json.dumps({"qid": q, "text": f"câu {q}", "slice": "s", "judgments": {"a": 2}}) + "\n" for q in qids),
                 encoding="utf-8")
    return p


def _cfg_with(cfg, **upd):
    return cfg.model_copy(update={"metrics": cfg.metrics.model_copy(update=upd)})


def test_annotate_gold_annotations_beat_forbidden_overrides_and_sets_blocks(cfg, tmp_path, monkeypatch):
    ann_p = _write(tmp_path, HEADER + "  c0001:\n    forbidden_filter: {eq: [taxonomy, golf]}\n    family: fam\n")
    ov_p = _write(tmp_path, "c0001: {eq: [taxonomy, attraction]}\nc0002: {eq: [taxonomy, attraction]}\n", "ov.yaml")
    gold_p = _gold_file(tmp_path, ["c0001", "c0002", "c0700"])
    monkeypatch.setattr(paths, "GOLD_JSONL", gold_p)
    monkeypatch.setattr(R, "rubric_v3_qids", lambda: frozenset({"c0001", "c0002"}))
    c = _cfg_with(cfg, annotations=str(ann_p), forbidden_overrides=str(ov_p))
    gold = M.load_gold(gold_p)
    n = R.annotate_gold(gold, c, gold_p)
    by = {g.qid: g for g in gold}
    assert by["c0001"].forbidden_filter == {"eq": ["taxonomy", "golf"]}           # annotations thắng forbidden_overrides
    assert by["c0002"].forbidden_filter == {"eq": ["taxonomy", "attraction"]}     # overrides vẫn gắn câu annotations không nói
    assert by["c0001"].family == "fam" and by["c0700"].forbidden_filter is None
    assert [g.block for g in gold] == ["v3", "v3", "v4"]
    assert n == {"forbidden": 1, "family": 1, "forbidden_overrides": 1}


def test_annotate_gold_unknown_qid_and_disabled(cfg, tmp_path, monkeypatch):
    gold_p = _gold_file(tmp_path, ["c0001"])
    monkeypatch.setattr(paths, "GOLD_JSONL", gold_p)
    monkeypatch.setattr(R, "rubric_v3_qids", lambda: None)              # không đọc được tag → ngưỡng qid dự phòng
    bad = _write(tmp_path, HEADER + "  c0999: {family: x}\n", "bad.yaml")
    with pytest.raises(M.MetricsError, match="c0999"):
        R.annotate_gold(M.load_gold(gold_p), _cfg_with(cfg, annotations=str(bad)), gold_p)
    gold = M.load_gold(gold_p)
    assert R.annotate_gold(gold, _cfg_with(cfg, annotations=None, forbidden_overrides=None), gold_p) == {}
    assert gold[0].block == "v3" and gold[0].family is None
    # gold đang chấm là fixture (qid khác gold chuẩn): annotations hợp lệ với gold chuẩn → không lỗi, không gắn
    fx = tmp_path / "fx"
    fx.mkdir()
    fx_gold = _gold_file(fx, ["q001"])
    ok = _write(tmp_path, HEADER + "  c0001: {family: x}\n", "ok.yaml")
    g = M.load_gold(fx_gold)
    assert R.annotate_gold(g, _cfg_with(cfg, annotations=str(ok)), fx_gold) == {} and g[0].family is None


def test_block_of_fallback_threshold():
    assert M.block_of("c0672", None) == "v3" and M.block_of("c0673", None) == "v4"
    assert M.block_of("c0005", frozenset({"c0005"})) == "v3" and M.block_of("c0006", frozenset({"c0005"})) == "v4"


def test_shipped_annotations_valid_against_canonical_gold():
    """File thật: nạp được và mọi qid có trong gold/gold.jsonl (bắt qid gõ sai khi thêm nhãn)."""
    ann = M.load_annotations(paths.PKG_DIR / "config" / "query_annotations.yaml")
    assert ann
    M.apply_annotations([], ann, known_qids=R.gold_file_qids(paths.GOLD_JSONL))
    assert list(ann) == sorted(ann)                                    # giữ thứ tự qid


def test_default_config_points_to_annotations(cfg):
    assert cfg.metrics.annotations == "config/query_annotations.yaml" and cfg.metrics.forbidden_overrides is None
    assert (paths.PKG_DIR / cfg.metrics.annotations).exists()
