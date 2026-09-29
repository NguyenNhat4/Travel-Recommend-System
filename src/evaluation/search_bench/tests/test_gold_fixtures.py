"""Kiểm hợp đồng gold_schema + fixture gold_small. Chạy từ src/:

    python -m pytest evaluation/search_bench/tests/test_gold_fixtures.py -q

Máy 1 viết thêm test cho 4 lệnh `sb gold` trong file riêng và so với expected.json.
Máy 2 dùng các hàm đọc/ghi ở đây; không tự viết parser CSV.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.search_bench.gold_schema import (
    DISPLAY_COLUMNS,
    HIDDEN_COLUMNS,
    POOL_COLUMNS,
    LabelRow,
    PoolRow,
    SchemaError,
    file_sha256,
    missing_pairs,
    read_gold_jsonl,
    read_labels_csv,
    read_merged_csv,
    read_pool_csv,
    read_pool_meta,
    upsert_label,
    validate_label_against_pool,
    write_labels_csv,
)

FIX = Path(__file__).parent / "fixtures" / "gold_small"
EXPECTED = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def meta():
    return read_pool_meta(FIX / "pool_meta.json")


@pytest.fixture(scope="module")
def pools(meta):
    return {x: read_pool_csv(FIX / meta.files[x].path) for x in ("A", "B")}


@pytest.fixture(scope="module")
def labels():
    return {x: read_labels_csv(FIX / f"labels_{x}.csv") for x in ("A", "B")}


# --- pool -------------------------------------------------------------------

def test_pool_sha_and_counts_match_meta(meta, pools):
    for x in ("A", "B"):
        f = meta.files[x]
        assert file_sha256(FIX / f.path) == f.sha256
        assert len(pools[x]) == f.n_pairs
        assert len({r.qid for r in pools[x]}) == f.n_queries


def test_overlap_queries_identical_in_both_pools(meta, pools):
    for x in ("A", "B"):
        for r in pools[x]:
            assert r.is_overlap == (r.qid in meta.overlap_qids)
    for qid in meta.overlap_qids:
        a = {r.product_id for r in pools["A"] if r.qid == qid}
        b = {r.product_id for r in pools["B"] if r.qid == qid}
        assert a == b and a


def test_hidden_columns_never_displayed():
    assert HIDDEN_COLUMNS <= set(POOL_COLUMNS)
    assert not HIDDEN_COLUMNS & set(DISPLAY_COLUMNS)
    assert not any("price" in c or "gia" == c for c in POOL_COLUMNS), "pool không được có cột giá"


def test_pool_rejects_unknown_slice_and_rank_mismatch():
    base = dict(qid="x", query="q", slice="dest_type", product_id="p", name="n", taxonomy="attraction")
    with pytest.raises(ValidationError):
        PoolRow(**{**base, "slice": "slice_la"}, **{"from": "dense"}, rank_dense=1)
    with pytest.raises(ValidationError):
        PoolRow(**base, **{"from": "both"}, rank_dense=1)  # thiếu rank_lex


# --- nhãn -------------------------------------------------------------------

def test_labels_valid_complete_and_tied_to_pool(meta, pools, labels):
    for x in ("A", "B"):
        by_key = {r.key: r for r in pools[x]}
        for lab in labels[x]:
            assert lab.labeler == x
            assert lab.pool_sha == meta.files[x].sha256
            assert validate_label_against_pool(lab, by_key[lab.key]) == []
        assert missing_pairs(pools[x], labels[x]) == []


def test_parent_child_rules(pools):
    pc = next(r for r in pools["A"] if r.slice == "parent_child" and r.children)
    other = next(r for r in pools["A"] if r.slice != "parent_child")
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    mk = lambda row, label, ch: LabelRow(qid=row.qid, product_id=row.product_id, label=label, children_ok=ch,
                                         labeler="A", labeled_at=now, pool_sha="x")
    assert validate_label_against_pool(mk(pc, 2, []), pc)            # 2 mà không tick hạng phòng
    assert validate_label_against_pool(mk(pc, 2, ["KHONG_CO"]), pc)  # id lạ
    assert validate_label_against_pool(mk(other, 2, [next(iter(pc.child_ids()))]), other)  # sai slice
    assert validate_label_against_pool(mk(pc, 2, [sorted(pc.child_ids())[0]]), pc) == []
    with pytest.raises(ValidationError):
        mk(pc, 1, [sorted(pc.child_ids())[0]])  # children_ok chỉ đi với nhãn 2


def test_upsert_keeps_one_row_per_pair_and_blocks_other_labeler(tmp_path):
    p = tmp_path / "labels_A.csv"
    t = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)
    row = LabelRow(qid="c1", product_id="P1", label=0, labeler="A", labeled_at=t, pool_sha="s")
    upsert_label(p, row)
    upsert_label(p, row.model_copy(update={"label": 2}))
    rows = read_labels_csv(p)
    assert len(rows) == 1 and rows[0].label == 2
    with pytest.raises(SchemaError):
        upsert_label(p, row.model_copy(update={"labeler": "B", "product_id": "P2"}))


def test_read_labels_rejects_duplicates(tmp_path):
    t = datetime(2026, 9, 26, tzinfo=timezone.utc)
    row = LabelRow(qid="c1", product_id="P1", label=1, labeler="A", labeled_at=t, pool_sha="s")
    p = tmp_path / "dup.csv"
    write_labels_csv([row], p)
    text = p.read_text(encoding="utf-8-sig")
    p.write_text(text + text.splitlines()[1] + "\n", encoding="utf-8-sig")
    with pytest.raises(SchemaError):
        read_labels_csv(p)


# --- đáp án kappa / merge / import ------------------------------------------

def _overlap_pairs(meta, labels):
    a = {r.key: r.label for r in labels["A"] if r.qid in meta.overlap_qids}
    b = {r.key: r.label for r in labels["B"] if r.qid in meta.overlap_qids}
    assert a.keys() == b.keys()
    return [(a[k], b[k]) for k in sorted(a)]


def test_expected_kappa_matches_reference(meta, labels):
    pairs = _overlap_pairs(meta, labels)
    k = 3
    conf = [[0] * k for _ in range(k)]
    for x, y in pairs:
        conf[x][y] += 1
    n = len(pairs)
    rows = [sum(r) for r in conf]
    cols = [sum(conf[i][j] for i in range(k)) for j in range(k)]
    obs = sum(abs(i - j) / 2 * conf[i][j] for i in range(k) for j in range(k))
    exp = sum(abs(i - j) / 2 * rows[i] * cols[j] / n for i in range(k) for j in range(k))
    assert conf == EXPECTED["kappa"]["confusion_A_rows_B_cols"]
    assert round(1 - obs / exp, 6) == EXPECTED["kappa"]["linear"]


def test_merged_expected_follows_rules(meta, labels):
    a = {r.key: r for r in labels["A"]}
    b = {r.key: r for r in labels["B"]}
    merged = {m.key: m for m in read_merged_csv(FIX / "merged_expected.csv")}
    assert set(merged) == set(a) | set(b)
    for key, m in merged.items():
        la, lb = a.get(key), b.get(key)
        if la and lb:
            gap = abs(la.label - lb.label)
            if gap == 2:
                assert m.needs_discussion and m.label is None
            else:
                assert m.label == min(la.label, lb.label)
                if m.label == 2:
                    assert m.children_ok == sorted(set(la.children_ok) & set(lb.children_ok))
        else:
            only = la or lb
            assert m.label == only.label and m.children_ok == only.children_ok


def test_gold_expected_matches_resolved_merge():
    resolved = read_merged_csv(FIX / "merged_resolved.csv")
    assert not any(m.needs_discussion for m in resolved)
    gold = {g.qid: g for g in read_gold_jsonl(FIX / "gold_expected.jsonl")}
    for m in resolved:
        assert gold[m.qid].judgments[m.product_id] == m.label
        assert gold[m.qid].provenance[m.product_id] == "pool@gold_v1"
    for g in gold.values():
        if g.slice == "out_of_catalog":
            assert g.expected_no_result and 2 not in g.judgments.values()
        else:
            assert 2 in g.judgments.values()
