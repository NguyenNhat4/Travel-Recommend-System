# Hồ sơ gold Search — bản chờ tag `gold_v4`

- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01.
- Gold cuối có SHA-256 `721f164d37fd11e77b8a8c84b183fb06335c9935a5a378501f350c465b1dfe1a` (`gold_v3`: `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`).
- Đây là hồ sơ dữ liệu đánh giá; kết quả benchmark nằm trong `src/evaluation/reports/`.
- Kế hoạch và quyết định của đợt gold_v4: `docs/plan/2026-10-05-gold-v4a-mo-rong.md`; luật gán: `docs/spec/bench/gold-guide.md` (mục "Rubric v4").

## Lịch sử version và nguồn nhãn

| Version/vòng | Thay đổi | Tổng nhãn |
|---|---|---:|
| gold_v1 | Pool hợp dense Cohere v3 top-15 + BM25; 132 câu, sau đó retire `c0463` | 3.359 |
| gold_v2 / D4a | +597 nhãn người đã được QAnh duyệt, +15 auto-OOC; append-only | 3.971 |
| gold_v3 / D4b | +278 nhãn người cho APP dense/hybrid/normalize | 4.249 |
| gold_v3 / D5a | +700 nhãn người cho 7 arm E, +72 auto-OOC | 5.021 |
| gold_v4 / v4a | +23 câu mới (`import --append`): pool B0 dense ∪ BM25 depth 15, 559 nhãn máy QAnh duyệt | 5.580 |
| gold_v4 / D8a | Hole top-10 của B0, E2.e5, APP.hybrid_norm trên 23 câu mới: +59 nhãn máy QAnh duyệt, +27 auto-OOC | **5.666** |

Gold cuối có 154 câu active / 15 slice / 5.636 nhãn active và 1 câu retired / 30 nhãn.

Pool ban đầu có κ tuyến tính 0,692 trước rà soát và 0,661 sau khi thống nhất quy ước trên 640 cặp chung, đều trước adjudication. `c0463` bị retire vì pool depth 15 bỏ sót vé đúng; ý định của nó có lại ở gold_v4 dưới qid `c0712` (pool lọc `variant = flight_route` nên có đủ tuyến).

D5a hợp top-10 của 7 arm, có 2.024 human hole trước cap. Thuật toán cap phân phối round-robin theo slice/query với seed 42, tạo 700 cặp / 128 câu. Người dùng gán đủ: 190 nhãn 0, 170 nhãn 1, 340 nhãn 2. Có thêm 72 auto-OOC nhãn 0.

## Đợt gold_v4 (v4a, 05/10)

- **Rubric khác v3.** 23 câu mới (qid `c0673`–`c0733`) gán theo rubric v4: "đúng nơi nhưng sai loại" = 0 (v3: 1), loại trừ rõ và chiều bay là ràng buộc cứng. Câu v1–v3 giữ nhãn cũ. Khi báo số trên gold_v4, tách khối 131 câu cũ và khối 23 câu mới, hoặc ghi rõ đang gộp hai rubric.
- **Nguồn nhãn.** Toàn bộ là nhãn máy được người duyệt: luật tất định `rule:v4a` (phủ định theo tiện ích đã làm sạch, tuyến bay và combo khứ hồi, out_of_catalog) và Claude (2 máy gán độc lập + trọng tài cho `taxonomy_collision`; soát lại nhãn luật phủ định). QAnh duyệt 618 / 618 nhãn máy, giữ nguyên cả 618, sửa 0. Một người duyệt, không có câu chung, **không có κ** — đây là giới hạn khi trích dẫn.
- **Provenance:** `pool:machine@gold_v4` (559), `holes:D8a:machine@gold_v4` (59), `auto_ooc:D8a@gold_v4` (27).
- **Catalog bench đổi trong đợt:** matcher tiện ích bỏ chuỗi "Không có …", "… : no", chuỗi khoảng cách và tiện ích tạm ngừng hoạt động (`items_sha256` 90e9ae51… → 14e13076…). Nhãn cũ không đổi; run cũ vẫn `rescore` được từ `top_ids`.

| Slice (câu mới) | Câu | Nhãn 0 | Nhãn 1 | Nhãn 2 |
|---|---:|---:|---:|---:|
| amenity_negation | 8 | 130 | 68 | 51 |
| taxonomy_collision | 5 | 66 | 9 | 38 |
| flight_direction | 6 | 102 | 6 | 28 |
| out_of_catalog | 4 | 147 | 0 | 0 |
| **Tổng 23 câu mới** | **23** | **445** | **83** | **117** |

## Phân bố 154 câu active (gold_v4)

| Slice | Câu | Nhãn 0 | Nhãn 1 | Nhãn 2 |
|---|---:|---:|---:|---:|
| abbrev_typo | 12 | 239 | 142 | 137 |
| amenity_multi | 10 | 75 | 54 | 217 |
| amenity_negation | 13 | 181 | 100 | 145 |
| amenity_offtaxonomy | 5 | 41 | 106 | 76 |
| amenity_single | 13 | 60 | 125 | 334 |
| audience_style | 11 | 102 | 124 | 166 |
| cross_vertical | 10 | 94 | 39 | 297 |
| dest_type | 12 | 110 | 128 | 197 |
| flight_direction | 6 | 102 | 6 | 28 |
| multi_constraint | 9 | 12 | 103 | 208 |
| named_entity | 18 | 464 | 89 | 29 |
| no_diacritics | 12 | 250 | 95 | 163 |
| out_of_catalog | 7 | 318 | 0 | 0 |
| parent_child | 11 | 102 | 147 | 118 |
| taxonomy_collision | 5 | 66 | 9 | 38 |
| **Tổng active** | **154** | **2.216** | **1.267** | **2.153** |

Tổng active là 5.636. Cộng 30 nhãn của `c0463` retired thành 5.666. `out_of_catalog` có `expected_no_result=true` và không có nhãn 2.

## Kiểm tra và giới hạn

- `gold check` PASS: 154 active, 15 slice; mọi câu in-catalog có ít nhất một nhãn 2.
- `gold verify-append gold_v3` PASS: +23 câu, +645 nhãn, +0 retired; không sửa nhãn cũ.
- D5a đã chạm cap 700 theo plan. Sau D5a vẫn có 1.324 human hole nếu hợp toàn bộ 7 arm, tập trung nhiều ở `no_diacritics`. Hole của 23 câu mới chỉ quét B0, E2.e5, APP.hybrid_norm: arm khác chạy trên gold_v4 cần xem `Judged@10` của khối câu mới.
- Vì vậy arm chưa đạt cổng được báo full cùng `Judged@10` và condensed cùng retained ratio. Không dùng condensed một mình.
- Các slice chỉ có 3–18 câu nên CI theo slice còn rộng; hai slice mới có 5–6 câu. Báo version, n, CI và coverage khi trích dẫn.

Từ `src/`:

```bash
python -m evaluation.search_bench gold check
python -m evaluation.search_bench gold verify-append gold_v3
python -m evaluation.search_bench --run-id <run> rescore      # câu mới chưa có trong run cũ → chạy lại arm, không chỉ rescore
```
