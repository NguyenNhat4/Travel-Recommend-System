# Fixture `gold_small`

Dữ liệu **giả** (11 sản phẩm, 7 câu) để hai máy test độc lập trước khi có pool thật. Không phải catalog thật; không dùng để đo search.

## Các câu

| qid | Slice | Query | Ai gán |
|---|---|---|---|
| c9001 | dest_type | resort ở Nha Trang | A |
| c9002 | out_of_catalog | resort ở Sapa | A |
| c9003 | multi_constraint | resort Phú Quốc có kids club dưới 3 triệu cho 4 người | B |
| c9004 | named_entity | Công viên Sóng Nhạc Nha Trang | B |
| c9005 | parent_child | villa hồ bơi riêng Phú Quốc | A và B (chung) |
| c9006 | amenity_negation | khách sạn Đà Nẵng không có hồ bơi | A và B (chung) |
| c9007 | audience_style | nghỉ dưỡng cho gia đình có trẻ nhỏ | A và B (chung) |

## File

| File | Vai trò | Ai dùng |
|---|---|---|
| `pool_A.csv`, `pool_B.csv` | Đầu ra mẫu của `sb gold split` (19 và 18 cặp, đã xáo trong từng câu) | Máy 2: input app |
| `pool_meta.json` | Snapshot, sha của hai file pool, 3 câu chung | Cả hai |
| `labels_A.csv`, `labels_B.csv` | Đầu ra mẫu của app | Máy 1: input `kappa`, `merge` · Máy 2: đáp án khi test app |
| `merged_expected.csv` | Đáp án của `sb gold merge labels_A.csv labels_B.csv` | Máy 1 |
| `merged_resolved.csv` | Như trên, sau khi thảo luận xong cặp lệch 2 bậc | Máy 1: input `import` |
| `gold_expected.jsonl` | Đáp án của `sb gold import merged_resolved.csv` | Máy 1 |
| `catalog_small.jsonl` | Catalog giả, chỉ các trường `productId`, `parentProductId`, `name` | Máy 1: `import --catalog` |
| `expected.json` | κ, các chỗ lệch, kết quả merge / import / check kỳ vọng | Máy 1 |
| `make_fixtures.py` | Sinh lại toàn bộ file trên | Chỉ chạy khi `gold_schema.py` đổi |

## Đáp án chính

- 12 cặp chung. Ma trận nhầm (A theo hàng, B theo cột, nhãn 0/1/2): `[[3,0,0],[1,3,0],[1,0,4]]`.
- κ: không trọng số 0,752577 · **linear 0,731343** (spec dùng) · quadratic 0,711538. Đã đối chiếu với `sklearn.metrics.cohen_kappa_score`.
- Hai chỗ lệch: `c9006/P011` A=1, B=0 (lệch 1 → merge lấy 0); `c9007/P003` A=2, B=0 (lệch 2 → `needs_discussion`).
- `c9005/P003`: A tick `R0033`, B tick `R0032;R0033` → merge giữ phần giao `R0033`.
- `import merged_expected.csv` phải **từ chối** (còn `needs_discussion`); `import merged_resolved.csv` phải ra đúng `gold_expected.jsonl`.
- `check gold_expected.jsonl --min-per-slice 1` → PASS; mặc định 10 → FAIL vì mỗi slice chỉ có 1 câu.

Sinh lại (từ `src/`):

```bash
python evaluation/search_bench/tests/fixtures/gold_small/make_fixtures.py
python -m pytest evaluation/search_bench/tests/test_gold_fixtures.py -q
```
