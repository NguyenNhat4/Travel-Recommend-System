"""Sinh bộ fixture gold_small. Dữ liệu GIẢ, không phải catalog thật.

Chạy lại khi gold_schema.py đổi:
    cd src && python evaluation/search_bench/tests/fixtures/gold_small/make_fixtures.py

Các nhãn và kết quả kỳ vọng (merge, import, check) được viết TAY theo luật trong
gold-guide và spec Part 5, không sinh từ code của `sb gold`, để làm đáp án chấm code đó.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))  # .../src

from evaluation.search_bench.gold_schema import (  # noqa: E402
    Child,
    GoldRecord,
    LabelRow,
    MergedRow,
    PoolFile,
    PoolMeta,
    PoolRow,
    file_sha256,
    write_gold_jsonl,
    write_labels_csv,
    write_merged_csv,
    write_pool_csv,
    write_pool_meta,
)

TZ = timezone(timedelta(hours=7))
SEED = 42

# ---------------------------------------------------------------------------
# Catalog giả: 11 parent + hạng phòng con
# ---------------------------------------------------------------------------
P = {
    "P001": dict(name="Resort Sóng Biển Nha Trang", taxonomy="hotel_property", destination="Nha Trang", star=5,
                 amenities=["bãi biển riêng", "hồ bơi", "kids club", "spa", "nhà hàng"],
                 snippet="Resort Sóng Biển Nha Trang là khu nghỉ dưỡng 5 sao tại Nha Trang, phù hợp gia đình có trẻ nhỏ. Nổi bật với bãi biển riêng, hồ bơi, kids club, spa.",
                 children=[("R0011", "Deluxe Hướng Biển"), ("R0012", "Family Suite")]),
    "P002": dict(name="Khách sạn Trung Tâm Nha Trang", taxonomy="hotel_property", destination="Nha Trang", star=4,
                 amenities=["nhà hàng", "phòng gym", "phòng họp"],
                 snippet="Khách sạn 4 sao ở trung tâm Nha Trang, phù hợp khách công tác. Có nhà hàng, phòng gym, phòng họp.",
                 children=[("R0021", "Superior"), ("R0022", "Deluxe")]),
    "P003": dict(name="Resort Rừng Dừa Phú Quốc", taxonomy="hotel_property", destination="Phú Quốc", star=5,
                 amenities=["bãi biển riêng", "hồ bơi", "kids club", "công viên nước"],
                 snippet="Resort 5 sao ở Phú Quốc dành cho gia đình, có kids club, công viên nước và bãi biển riêng.",
                 children=[("R0031", "Deluxe"), ("R0032", "Family Suite"), ("R0033", "Villa Hồ Bơi Riêng")]),
    "P004": dict(name="Khách sạn Cầu Rồng Đà Nẵng", taxonomy="hotel_property", destination="Đà Nẵng", star=3,
                 amenities=["nhà hàng", "đưa đón sân bay"],
                 snippet="Khách sạn 3 sao gần cầu Rồng, Đà Nẵng. Có nhà hàng và dịch vụ đưa đón sân bay.",
                 children=[("R0041", "Standard")]),
    "P005": dict(name="Resort Núi Mây Hà Giang", taxonomy="hotel_property", destination="Hà Giang", star=4,
                 amenities=["nhà hàng", "view núi"],
                 snippet="Resort 4 sao giữa núi đồi Hà Giang, không gian yên tĩnh.",
                 children=[("R0051", "Bungalow")]),
    "P006": dict(name="Khách sạn Dương Đông Phú Quốc", taxonomy="hotel_property", destination="Phú Quốc", star=5,
                 amenities=["hồ bơi", "nhà hàng"],
                 snippet="Khách sạn 5 sao ở thị trấn Dương Đông, Phú Quốc. Có hồ bơi và nhà hàng.",
                 children=[("R0061", "Deluxe")]),
    "P007": dict(name="Công viên Sóng Nhạc Nha Trang", taxonomy="attraction", destination="Nha Trang", star=None,
                 amenities=["trò chơi cảm giác mạnh", "công viên nước", "nhạc nước"],
                 snippet="Công viên vui chơi ở Nha Trang với trò chơi cảm giác mạnh, công viên nước và show nhạc nước buổi tối.",
                 children=[]),
    "P008": dict(name="Thủy cung Hòn Mun Nha Trang", taxonomy="attraction", destination="Nha Trang", star=None,
                 amenities=["thủy cung", "phù hợp trẻ em"],
                 snippet="Thủy cung ở Nha Trang, phù hợp đi cùng trẻ em.",
                 children=[]),
    "P009": dict(name="Resort Ngọc Trai Phú Quốc", taxonomy="hotel_property", destination="Phú Quốc", star=4,
                 amenities=["hồ bơi", "spa"],
                 snippet="Resort 4 sao ở Phú Quốc với khu villa hướng vườn, hồ bơi chung và spa.",
                 children=[("R0091", "Villa Hướng Vườn")]),
    "P010": dict(name="Khách sạn Mỹ Khê Đà Nẵng", taxonomy="hotel_property", destination="Đà Nẵng", star=4,
                 amenities=["hồ bơi", "nhà hàng", "phòng gym"],
                 snippet="Khách sạn 4 sao gần biển Mỹ Khê, Đà Nẵng, có hồ bơi trên sân thượng.",
                 children=[("R0101", "Deluxe")]),
    "P011": dict(name="Resort Sơn Trà Đà Nẵng", taxonomy="hotel_property", destination="Đà Nẵng", star=5,
                 amenities=["hồ bơi", "bãi biển riêng", "kids club"],
                 snippet="Resort 5 sao ở bán đảo Sơn Trà, Đà Nẵng, có bãi biển riêng, hồ bơi và kids club.",
                 children=[("R0111", "Villa Hướng Biển")]),
}

# ---------------------------------------------------------------------------
# 7 câu: 2 câu riêng của A, 2 câu riêng của B, 3 câu chung
# ---------------------------------------------------------------------------
FILTER_C9003 = {"and": [{"eq": ["destination", "Phú Quốc"]}, {"eq": ["taxonomy", "hotel_property"]}]}
CHILD_FILTER_C9003 = {"and": [{"lte": ["unit_price", 3000000]}, {"gte": ["max_occupancy", 4]}]}

Q = {
    "c9001": dict(query="resort ở Nha Trang", slice="dest_type", owner="A"),
    "c9002": dict(query="resort ở Sapa", slice="out_of_catalog", owner="A", expected_no_result=True),
    "c9003": dict(query="resort Phú Quốc có kids club dưới 3 triệu cho 4 người", slice="multi_constraint", owner="B",
                  filter_json=FILTER_C9003, child_filter_json=CHILD_FILTER_C9003,
                  filter_text="destination = Phú Quốc · loại = hotel_property · giá ≤ 3.000.000 (kiểm ở cấp room) · số khách ≥ 4 (kiểm ở cấp room)"),
    "c9004": dict(query="Công viên Sóng Nhạc Nha Trang", slice="named_entity", owner="B"),
    "c9005": dict(query="villa hồ bơi riêng Phú Quốc", slice="parent_child", owner="both"),
    "c9006": dict(query="khách sạn Đà Nẵng không có hồ bơi", slice="amenity_negation", owner="both"),
    "c9007": dict(query="nghỉ dưỡng cho gia đình có trẻ nhỏ", slice="audience_style", owner="both"),
}
OVERLAP = ["c9005", "c9006", "c9007"]

# (product_id, from, rank_dense, rank_lex)
CANDIDATES = {
    "c9001": [("P001", "both", 1, 1), ("P002", "lexical", None, 2), ("P003", "dense", 2, None), ("P004", "dense", 3, None)],
    "c9002": [("P001", "dense", 1, None), ("P003", "dense", 2, None), ("P005", "both", 3, 1)],
    "c9003": [("P003", "both", 1, 1), ("P006", "lexical", None, 2), ("P001", "dense", 2, None)],
    "c9004": [("P007", "both", 1, 1), ("P008", "dense", 2, None), ("P001", "lexical", None, 2)],
    "c9005": [("P003", "both", 1, 2), ("P009", "both", 2, 1), ("P006", "dense", 3, None)],
    "c9006": [("P004", "lexical", None, 1), ("P010", "both", 1, 2), ("P011", "dense", 2, None), ("P002", "lexical", None, 3)],
    "c9007": [("P001", "both", 1, 1), ("P003", "dense", 2, None), ("P002", "lexical", None, 2),
              ("P010", "dense", 4, None), ("P011", "dense", 3, None)],
}

# Nhãn viết tay. Luật dùng (đề xuất cho gold-guide):
# - Query có nêu destination: sai destination -> 0, kể cả đúng loại.
# - Đúng destination nhưng sai loại hoặc thiếu điều kiện -> 1.
# - parent_child: không có hạng phòng đúng loại -> 0; gần đúng -> 1; nhãn 2 phải tick hạng phòng.
# - Phủ định: sản phẩm được ghi nhận có tiện ích bị loại trừ -> tối đa 1; không ghi nhận -> có thể 2.
# Ở 3 câu chung có đúng 2 chỗ lệch: c9006/P011 (1 vs 0, lệch 1 bậc) và c9007/P003 (2 vs 0, lệch 2 bậc).
LABELS_A = {
    ("c9001", "P001"): (2, []), ("c9001", "P002"): (1, []), ("c9001", "P003"): (0, []), ("c9001", "P004"): (0, []),
    ("c9002", "P001"): (0, []), ("c9002", "P003"): (0, []), ("c9002", "P005"): (0, []),
    ("c9005", "P003"): (2, ["R0033"]), ("c9005", "P009"): (1, []), ("c9005", "P006"): (0, []),
    ("c9006", "P004"): (2, []), ("c9006", "P010"): (1, []), ("c9006", "P011"): (1, []), ("c9006", "P002"): (0, []),
    ("c9007", "P001"): (2, []), ("c9007", "P003"): (2, []), ("c9007", "P002"): (0, []),
    ("c9007", "P010"): (1, []), ("c9007", "P011"): (2, []),
}
LABELS_B = {
    ("c9003", "P003"): (2, []), ("c9003", "P006"): (1, []), ("c9003", "P001"): (0, []),
    ("c9004", "P007"): (2, []), ("c9004", "P008"): (1, []), ("c9004", "P001"): (0, []),
    ("c9005", "P003"): (2, ["R0032", "R0033"]), ("c9005", "P009"): (1, []), ("c9005", "P006"): (0, []),
    ("c9006", "P004"): (2, []), ("c9006", "P010"): (1, []), ("c9006", "P011"): (0, []), ("c9006", "P002"): (0, []),
    ("c9007", "P001"): (2, []), ("c9007", "P003"): (0, []), ("c9007", "P002"): (0, []),
    ("c9007", "P010"): (1, []), ("c9007", "P011"): (2, []),
}

# Kết quả merge viết tay: (label | None, label_A, label_B, children_ok, needs_discussion, source, note)
MERGED_EXPECTED = {
    ("c9001", "P001"): (2, 2, None, [], False, "A", ""),
    ("c9001", "P002"): (1, 1, None, [], False, "A", ""),
    ("c9001", "P003"): (0, 0, None, [], False, "A", ""),
    ("c9001", "P004"): (0, 0, None, [], False, "A", ""),
    ("c9002", "P001"): (0, 0, None, [], False, "A", ""),
    ("c9002", "P003"): (0, 0, None, [], False, "A", ""),
    ("c9002", "P005"): (0, 0, None, [], False, "A", ""),
    ("c9003", "P001"): (0, None, 0, [], False, "B", ""),
    ("c9003", "P003"): (2, None, 2, [], False, "B", ""),
    ("c9003", "P006"): (1, None, 1, [], False, "B", ""),
    ("c9004", "P001"): (0, None, 0, [], False, "B", ""),
    ("c9004", "P007"): (2, None, 2, [], False, "B", ""),
    ("c9004", "P008"): (1, None, 1, [], False, "B", ""),
    ("c9005", "P003"): (2, 2, 2, ["R0033"], False, "both", ""),
    ("c9005", "P006"): (0, 0, 0, [], False, "both", ""),
    ("c9005", "P009"): (1, 1, 1, [], False, "both", ""),
    ("c9006", "P002"): (0, 0, 0, [], False, "both", ""),
    ("c9006", "P004"): (2, 2, 2, [], False, "both", ""),
    ("c9006", "P010"): (1, 1, 1, [], False, "both", ""),
    ("c9006", "P011"): (0, 1, 0, [], False, "both", "lệch 1 bậc: lấy nhãn thấp hơn"),
    ("c9007", "P001"): (2, 2, 2, [], False, "both", ""),
    ("c9007", "P002"): (0, 0, 0, [], False, "both", ""),
    ("c9007", "P003"): (None, 2, 0, [], True, "both", "lệch 2 bậc: cần thảo luận"),
    ("c9007", "P010"): (1, 1, 1, [], False, "both", ""),
    ("c9007", "P011"): (2, 2, 2, [], False, "both", ""),
}
RESOLUTION = {("c9007", "P003"): (2, "đã thảo luận: resort gia đình có kids club -> 2")}


def build_pool_rows(qids: list[str], rng: random.Random) -> list[PoolRow]:
    rows: list[PoolRow] = []
    for qid in qids:
        q = Q[qid]
        cands = list(CANDIDATES[qid])
        rng.shuffle(cands)  # xáo trong từng câu: người gán không đoán được thứ hạng
        for pid, src, rd, rl in cands:
            p = P[pid]
            rows.append(PoolRow(
                qid=qid, query=q["query"], slice=q["slice"],
                filter_text=q.get("filter_text", ""),
                filter_json=q.get("filter_json"), child_filter_json=q.get("child_filter_json"),
                expected_no_result=q.get("expected_no_result", False),
                product_id=pid, name=p["name"], taxonomy=p["taxonomy"], destination=p["destination"],
                star_rating=p["star"], amenities=p["amenities"], snippet=p["snippet"],
                children=[Child(id=i, name=n) for i, n in p["children"]],
                **{"from": src}, rank_dense=rd, rank_lex=rl, is_overlap=qid in OVERLAP,
            ))
    return rows


def label_rows(table: dict, labeler: str, pool_sha: str, start: datetime) -> list[LabelRow]:
    out = []
    for i, ((qid, pid), (lab, ch)) in enumerate(sorted(table.items())):
        out.append(LabelRow(qid=qid, product_id=pid, label=lab, children_ok=ch, note="",
                            labeler=labeler, labeled_at=start + timedelta(minutes=i), pool_sha=pool_sha))
    return out


def kappa_reference(pairs: list[tuple[int, int]]) -> dict:
    """Cohen kappa 3 lớp: không trọng số, linear, quadratic. Chỉ dùng để ghi đáp án."""
    k = 3
    n = len(pairs)
    conf = [[0] * k for _ in range(k)]
    for a, b in pairs:
        conf[a][b] += 1
    rows = [sum(r) for r in conf]
    cols = [sum(conf[i][j] for i in range(k)) for j in range(k)]

    def weighted(w) -> float:
        obs = sum(w(i, j) * conf[i][j] for i in range(k) for j in range(k))
        exp = sum(w(i, j) * rows[i] * cols[j] / n for i in range(k) for j in range(k))
        return 1 - obs / exp

    return {
        "n_pairs": n,
        "confusion_A_rows_B_cols": conf,
        "unweighted": round(weighted(lambda i, j: 0 if i == j else 1), 6),
        "linear": round(weighted(lambda i, j: abs(i - j) / (k - 1)), 6),
        "quadratic": round(weighted(lambda i, j: ((i - j) / (k - 1)) ** 2), 6),
    }


def main() -> None:
    rng = random.Random(SEED)
    qids_a = sorted([q for q, v in Q.items() if v["owner"] == "A"] + OVERLAP)
    qids_b = sorted([q for q, v in Q.items() if v["owner"] == "B"] + OVERLAP)
    pool_a = build_pool_rows(qids_a, rng)
    pool_b = build_pool_rows(qids_b, rng)
    write_pool_csv(pool_a, HERE / "pool_A.csv")
    write_pool_csv(pool_b, HERE / "pool_B.csv")
    sha_a, sha_b = file_sha256(HERE / "pool_A.csv"), file_sha256(HERE / "pool_B.csv")

    meta = PoolMeta(
        snapshot="2026-09-23", collection="products__T3+R__cohere_v3", depth=15, seed=SEED,
        drafts_sha256=None, overlap_qids=OVERLAP,
        files={
            "A": PoolFile(path="pool_A.csv", sha256=sha_a, labeler="A", n_queries=len(qids_a), n_pairs=len(pool_a)),
            "B": PoolFile(path="pool_B.csv", sha256=sha_b, labeler="B", n_queries=len(qids_b), n_pairs=len(pool_b)),
        },
        created_at=datetime(2026, 9, 25, 17, 0, tzinfo=TZ),
    )
    write_pool_meta(meta, HERE / "pool_meta.json")

    write_labels_csv(label_rows(LABELS_A, "A", sha_a, datetime(2026, 9, 26, 9, 0, tzinfo=TZ)), HERE / "labels_A.csv")
    write_labels_csv(label_rows(LABELS_B, "B", sha_b, datetime(2026, 9, 26, 9, 0, tzinfo=TZ)), HERE / "labels_B.csv")

    merged = [
        MergedRow(qid=q, product_id=p, label=lab, label_A=la, label_B=lb, children_ok=ch,
                  needs_discussion=nd, source=src, note=note)
        for (q, p), (lab, la, lb, ch, nd, src, note) in MERGED_EXPECTED.items()
    ]
    write_merged_csv(merged, HERE / "merged_expected.csv")

    resolved = []
    for m in merged:
        if m.key in RESOLUTION:
            lab, note = RESOLUTION[m.key]
            m = m.model_copy(update={"label": lab, "needs_discussion": False, "note": note})
        resolved.append(m)
    write_merged_csv(resolved, HERE / "merged_resolved.csv")

    # Đáp án của `sb gold import merged_resolved.csv`
    pool_by_q = {}
    for r in pool_a + pool_b:
        pool_by_q.setdefault(r.qid, r)
    records = []
    for qid in sorted(Q):
        head = pool_by_q[qid]
        rows = [m for m in resolved if m.qid == qid]
        records.append(GoldRecord(
            qid=qid, text=head.query, slice=head.slice,
            filter=head.filter_json, child_filter=head.child_filter_json,
            expected_no_result=head.expected_no_result,
            judgments={m.product_id: m.label for m in rows},
            provenance={m.product_id: "pool@gold_v1" for m in rows},
            expected_children={m.product_id: m.children_ok for m in rows if m.children_ok},
        ))
    write_gold_jsonl(records, HERE / "gold_expected.jsonl")

    # Catalog giả: chỉ các trường import cần để kiểm product_id và id hạng phòng
    lines = []
    for pid, p in P.items():
        lines.append({"productId": pid, "parentProductId": None, "name": p["name"]})
        for cid, cname in p["children"]:
            lines.append({"productId": cid, "parentProductId": pid, "name": cname})
    (HERE / "catalog_small.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")

    overlap_pairs = sorted(k for k in LABELS_A if k[0] in OVERLAP)
    pairs = [(LABELS_A[k][0], LABELS_B[k][0]) for k in overlap_pairs]
    expected = {
        "note": "Đáp án cho fixture gold_small. Dữ liệu giả. Nhãn và kết quả merge/import/check viết tay.",
        "overlap_qids": OVERLAP,
        "kappa": {**kappa_reference(pairs), "spec_uses": "linear", "threshold": 0.6, "passes": True},
        "disagreements": [
            {"qid": q, "product_id": p, "A": LABELS_A[(q, p)][0], "B": LABELS_B[(q, p)][0],
             "gap": abs(LABELS_A[(q, p)][0] - LABELS_B[(q, p)][0])}
            for (q, p) in overlap_pairs if LABELS_A[(q, p)][0] != LABELS_B[(q, p)][0]
        ],
        "merge": {
            "output": "merged_expected.csv",
            "n_rows": len(merged),
            "needs_discussion": [["c9007", "P003"]],
            "gap1_takes_lower": [["c9006", "P011", 0]],
            "children_ok_intersection": [["c9005", "P003", ["R0033"]]],
        },
        "import": {
            "merged_expected.csv": "REFUSE (còn needs_discussion ở c9007/P003)",
            "merged_resolved.csv": "OK -> giống gold_expected.jsonl",
        },
        "check": {
            "gold_expected.jsonl --min-per-slice 1": "PASS",
            "gold_expected.jsonl --min-per-slice 10": "FAIL (mỗi slice chỉ có 1 câu)",
        },
        "files": {"pool_A.csv": sha_a, "pool_B.csv": sha_b},
    }
    (HERE / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ok:", sorted(x.name for x in HERE.iterdir() if x.is_file()))


if __name__ == "__main__":
    main()
