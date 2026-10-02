# Hồ sơ gold Search — bản chờ tag `gold_v3`

- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01.
- Gold cuối có SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`.
- Đây là hồ sơ dữ liệu đánh giá; kết quả benchmark nằm trong `src/evaluation/reports/`.

## Lịch sử version và nguồn nhãn

| Version/vòng | Thay đổi | Tổng nhãn |
|---|---|---:|
| gold_v1 | Pool hợp dense Cohere v3 top-15 + BM25; 132 câu, sau đó retire `c0463` | 3.359 |
| gold_v2 / D4a | +597 nhãn người đã được QAnh duyệt, +15 auto-OOC; append-only | 3.971 |
| gold_v3 / D4b | +278 nhãn người cho APP dense/hybrid/normalize | 4.249 |
| gold_v3 / D5a | +700 nhãn người cho 7 arm E, +72 auto-OOC | **5.021** |

Gold cuối có 131 câu active / 13 slice / 4.991 nhãn active và 1 câu retired / 30 nhãn. D4b và D5a cùng nằm trong version `gold_v3` vì đều được import trước commit/tag cuối; changelog giữ hai entry riêng.

Pool ban đầu có κ tuyến tính 0,692 trước rà soát và 0,661 sau khi thống nhất quy ước trên 640 cặp chung, đều trước adjudication. `c0463` bị retire vì pool depth 15 bỏ sót vé đúng.

D5a hợp top-10 của 7 arm, có 2.024 human hole trước cap. Thuật toán cap phân phối round-robin theo slice/query với seed 42, tạo 700 cặp / 128 câu. Người dùng gán đủ: 190 nhãn 0, 170 nhãn 1, 340 nhãn 2. Có thêm 72 auto-OOC nhãn 0.

## Phân bố 131 câu active sau D5a

| Slice | Câu | Nhãn 0 | Nhãn 1 | Nhãn 2 |
|---|---:|---:|---:|---:|
| abbrev_typo | 12 | 239 | 142 | 137 |
| amenity_multi | 10 | 75 | 54 | 217 |
| amenity_negation | 5 | 51 | 32 | 94 |
| amenity_offtaxonomy | 5 | 41 | 106 | 76 |
| amenity_single | 13 | 60 | 125 | 334 |
| audience_style | 11 | 102 | 124 | 166 |
| cross_vertical | 10 | 94 | 39 | 297 |
| dest_type | 12 | 110 | 128 | 197 |
| multi_constraint | 9 | 12 | 103 | 208 |
| named_entity | 18 | 464 | 89 | 29 |
| no_diacritics | 12 | 250 | 95 | 163 |
| out_of_catalog | 3 | 171 | 0 | 0 |
| parent_child | 11 | 102 | 147 | 118 |
| **Tổng active** | **131** | **1.771** | **1.184** | **2.036** |

Tổng active là 4.991. Cộng 30 nhãn của `c0463` retired thành 5.021. `out_of_catalog` có `expected_no_result=true` và không có nhãn 2.

## Kiểm tra và giới hạn

- `gold check` PASS: 131 active, 13 slice; mọi câu in-catalog có ít nhất một nhãn > 0.
- `gold verify-append gold_v2` PASS: +0 query, +1.050 nhãn, +0 retired; không sửa nhãn cũ.
- D5a đã chạm cap 700 theo plan. Sau D5a vẫn có 1.324 human hole nếu hợp toàn bộ 7 arm, tập trung nhiều ở `no_diacritics`.
- Vì vậy arm chưa đạt cổng được báo full cùng `Judged@10` và condensed cùng retained ratio. Không dùng condensed một mình.
- Các slice chỉ có 3–18 câu nên CI theo slice còn rộng. Báo version, n, CI và coverage khi trích dẫn.

Từ `src/`:

```bash
python -m evaluation.search_bench gold check
python -m evaluation.search_bench gold verify-append gold_v2
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local rescore
```
