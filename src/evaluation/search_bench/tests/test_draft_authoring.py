from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from evaluation.search_bench import draft_authoring as D
from evaluation.search_bench import gold, paths
from evaluation.search_bench.tests.test_catalog_lookup import VOCAB, _items
from evaluation.search_bench import catalog_lookup as C

FILES = ("drafts_raw.tsv", "overrides.tsv", "drafts.txt")


@pytest.fixture()
def gdir(tmp_path) -> Path:
    d = tmp_path / "gold"
    d.mkdir()
    for f in FILES:
        shutil.copyfile(paths.GOLD_DIR / f, d / f)
    return d


@pytest.fixture()
def state(gdir, cfg):
    return D.load_state(gdir, dict(cfg.gold.slices))


@pytest.fixture()
def cat():
    return C.catalog_from(_items(), VOCAB)


def test_state_on_committed_gold(state, cfg, gdir):
    """Đối chiếu với drafts.txt hiện có (số câu đổi theo lựa chọn của người soát — luật 28/09 không cố định 200)."""
    lines = [ln.split("\t") for ln in (gdir / "drafts.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert state.drafts_error is None and len(state.selected) == len(lines)
    summary = {s["slice"]: s for s in D.slice_summary(state, cfg.gold.min_per_slice)}
    per_slice = {sl: sum(1 for ln in lines if ln[1] == sl) for sl in summary}
    assert all(summary[sl]["trong drafts.txt"] == n for sl, n in per_slice.items())
    assert {sl for sl, v in summary.items() if v["dưới tối thiểu"]} == {sl for sl, n in per_slice.items()
                                                                     if n < cfg.gold.min_per_slice}
    ooc = D.intents(state, "out_of_catalog")
    assert sum(i.status == D.STATUS_IN for i in ooc) == per_slice["out_of_catalog"]
    assert any(i.status == D.STATUS_SAME_KEY for i in ooc)             # cùng điểm đến với câu đã chọn
    neg = D.intents(state, "amenity_negation")
    assert any("không có hồ bơi view đẹp" in q for i in neg for q in i.queries)   # c0241 đã sửa qua overrides


def test_next_block_start():
    rows = [{"case_id": f"c{n:04d}"} for n in (1, 2, 5)]
    assert D.next_block_start(rows) == 7
    assert D.next_block_start([{"case_id": "c0672"}]) == 673
    assert D.next_block_start([]) == 1


def test_validate_errors(state, cat):
    def errs(**kw):
        return D.validate(state, D.NewIntent(**kw), cat)[0]
    assert any("đã có" in e for e in errs(slice="amenity_negation", phrasings=["khách sạn Côn Đảo không có hồ bơi view đẹp"],
                                          review_note="x", source_refs=["p1"]))
    assert any("source_refs" in e for e in errs(slice="cross_vertical", phrasings=["câu mới hoàn toàn"], review_note="x"))
    assert any("không phải search unit" in e for e in errs(slice="cross_vertical", phrasings=["câu mới hoàn toàn"],
                                                           review_note="x", source_refs=["zz"]))
    assert any("cần filter_json" in e for e in errs(slice="multi_constraint", phrasings=["khách sạn mới"], review_note="x",
                                                    source_refs=["p1"]))
    assert any("khớp 0" in e for e in errs(slice="multi_constraint", phrasings=["khách sạn mới"], review_note="x",
                                           source_refs=["p1"], filter_json='{"eq": ["destination", "Huế"]}'))
    assert any("filter_json" in e for e in errs(slice="multi_constraint", phrasings=["khách sạn mới"], review_note="x",
                                                source_refs=["p1"], filter_json="{bad"))
    assert any("Hà Giang" in e for e in errs(slice="out_of_catalog", phrasings=["resort ở Hà Giang mới"], place="Hà Giang"))
    assert any("khoá ý định" in e for e in errs(slice="out_of_catalog", phrasings=["homestay Mộc Châu"], place="Mộc Châu"))
    assert any("không có filter_json" in e for e in errs(slice="out_of_catalog", phrasings=["resort ở Côn Sơn"],
                                                         place="Côn Sơn", source_refs=["p1"]))
    assert any("tối đa" in e for e in errs(slice="cross_vertical", phrasings=["a1", "a2", "a3", "a4"], review_note="x",
                                           source_refs=["p1"]))


def test_validate_ok_with_match_warning(state, cat):
    new = D.NewIntent(slice="multi_constraint", phrasings=["khách sạn 3 sao ở Nha Trang dưới 1 triệu"],
                      review_note="star=3;price<=1000000", source_refs=["p2"],
                      filter_json='{"and":[{"eq":["destination","Nha Trang"]},{"gte":["star_rating",3]},'
                                  '{"lte":["unit_price_min",1000000]}]}')
    errors, warns = D.validate(state, new, cat)
    assert errors == []
    assert any("nên 5–40" in w for w in warns) and not any("quota" in w for w in warns)
    ooc = D.NewIntent(slice="out_of_catalog", phrasings=["resort ở Côn Sơn"], place="Côn Sơn")
    assert D.validate(state, ooc, cat)[0] == []


def test_append_intent_writes_block_and_keep(state, gdir, cat, cfg):
    before = (gdir / "drafts_raw.tsv").read_bytes()
    new = D.NewIntent(slice="cross_vertical", phrasings=["đặt vé bay rồi khách sạn Nha Trang", "tìm vé bay và khách sạn Nha Trang"],
                      review_note="flight+hotel:Nha Trang", source_refs=["p1", "p2"],
                      filter_json='{"eq":["destination","Nha Trang"]}')
    assert D.validate(state, new, cat)[0] == []
    ids = D.append_intent(state, new, author="tester", today=date(2026, 9, 28))
    assert ids == ["c0673", "c0674"]
    after = (gdir / "drafts_raw.tsv").read_bytes()
    assert after.startswith(before) and b"\r" not in after
    rows = {r["case_id"]: r for r in gold.read_draft_cases(gdir / "drafts_raw.tsv")}
    assert rows["c0674"]["query"] == "tìm vé bay và khách sạn Nha Trang"
    assert rows["c0673"]["filter_json"] == '{"eq":["destination","Nha Trang"]}'
    assert rows["c0673"]["source_refs"] == "p1|p2" and rows["c0673"]["expected_no_result"] == ""
    assert gold.intent_key("c0673", "cross_vertical") == gold.intent_key("c0674", "cross_vertical")
    over = gold.read_overrides(gdir / "overrides.tsv", set(rows))
    assert over["c0673"]["verdict"] == "KEEP" and "tester" in over["c0673"]["note"] and "2026-09-28" in over["c0673"]["note"]
    st2 = D.load_state(gdir, dict(cfg.gold.slices))
    mine = [i for i in D.intents(st2, "cross_vertical") if i.case_ids[0] == "c0673"]
    assert mine and mine[0].status == D.STATUS_UNUSED and mine[0].case_ids == ["c0673", "c0674"]
    assert any("đã có" in e for e in D.validate(st2, new, cat)[0])        # thêm lại → trùng
    ooc = D.NewIntent(slice="out_of_catalog", phrasings=["resort ở Côn Sơn"], place="Côn Sơn")
    assert D.append_intent(st2, ooc, author="tester", keep=False) == ["c0676"]
    rows = {r["case_id"]: r for r in gold.read_draft_cases(gdir / "drafts_raw.tsv")}
    assert rows["c0676"]["expected_no_result"] == "true" and rows["c0676"]["review_note"] == "absent destination:Côn Sơn"
    assert "c0676" not in gold.read_overrides(gdir / "overrides.tsv", set(rows))


def test_new_keep_intent_is_selected_when_quota_allows(state, gdir, cat, cfg):
    """Ý định tự thêm + KEEP đi đúng luồng `sb gold drafts`: vào drafts khi quota slice còn chỗ."""
    new = D.NewIntent(slice="cross_vertical", phrasings=["combo bay và ở Nha Trang cho 2 người"],
                      review_note="flight+hotel:Nha Trang", source_refs=["p1"])
    ids = D.append_intent(state, new, author="tester")
    cases = gold.read_draft_cases(gdir / "drafts_raw.tsv")
    over = gold.read_overrides(gdir / "overrides.tsv", {r["case_id"] for r in cases})
    decisions = {cid: o for cid, o in over.items()}
    quota = {"cross_vertical": 1}
    rows, _ = gold.select_drafts([r for r in cases if r["slice"] == "cross_vertical"], decisions, quota)
    assert [r["case_id"] for r in rows] == ids                         # chỉ ý định mới có quyết định KEEP
