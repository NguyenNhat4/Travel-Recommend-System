# Search bench — B0 vs E2.e5 trên `gold_v1` → `gold_v2` (vòng hole D4a)

- Commit: `b4d7968` · nhánh: `bench/m6-trip-ended` · run: `20261001-0623-ec5fbd2`
- Chạy lúc: 2026-10-01 (run 06:23 +07; rescore sau khi tag `gold_v2` ~09:0x +07)
- Gold: `gold_v1` (131 câu active, 3.359 nhãn + retire c0463) → `gold_v2` (+597 nhãn người +15 auto_ooc, verify-append xanh)
- Arm: `B0` = dense-only Cohere `embed-multilingual-v3.0` (collection `products__T3+R__cohere_v3`) · `E2.e5` = dense-only `intfloat/multilingual-e5-base` local (collection `products__T3+R__e5_base`), cùng 3.183 object, k=10, Weaviate local `127.0.0.1:8080`
- Phục vụ: FR-SRC-01..04, AC-SRC-01, test-plan §2.5; spec: `docs/spec/bench/search-eval-local-spec.md` (Part 8, 11)

## 1. Sanity trước khi đọc số (`sb sanity --arms B0,E2.e5`) — PASS 6/6

| Kiểm tra | Kết quả |
|---|---|
| input_type query/document khác nhau (cohere-v3) | mean(1−cos) = 0,184 (> 0,005) |
| input_type query/document khác nhau (e5-base) | 0,075 (> 0,005) |
| cache_recheck cohere / e5 | cos min 0,999942 / 1,000000 (≥ 0,999) |
| collection_counts | 2 × 3.183 object |
| gold_append_ok | gold_v1 → gold.jsonl: chỉ thêm |

## 2. Run trên `gold_v1` (trước khi lấp hole) — vì sao chưa đọc Δ được

| Arm | recall@10 | nDCG@10 | MRR@10 | judged@10 | Cohere mới |
|---|---|---|---|---|---|
| B0 | 0,501 | 0,717 | 0,748 | 0,967 | 0 (131/131 cache) |
| E2.e5 | 0,347 | 0,506 | 0,618 | **0,550** | 0 |

- "LOSE −21,2 điểm nDCG" ở bước này là **thiên lệch pooling**: gold_v1 gán trên pool depth-15 của Cohere, ứng viên e5 kéo về phần lớn chưa có nhãn (bị tính 0). Runner tự chặn bằng gate judged@10 ≥ 0,80 (NEEDS_LABELS).

## 3. Vòng hole D4a

- `sb gold holes --arms B0,E2.e5 --tag D4a`: **597 cặp / 118 câu** (+15 ooc tự gán 0), depth 10.
- Nhãn máy: Claude gán trong phiên (không API), theo `gold-guide.md` + 7 quy ước 30/09; phân bố máy **0 = 193 · 1 = 131 · 2 = 273**; import `machine-import` 597/597, từ chối 0.
- Duyệt: 93 cặp duyệt tay trong app (0 cặp phải sửa), 504 cặp duyệt hàng loạt `accept_all_machine` — cả 597 `accepted`, reviewer **QAnh**. Nhãn cuối = nhãn máy 100%.
- `holes import` → `gold_v2`: +612 nhãn; `gold check` xanh (131 câu, 13 slice, min ≥ 3); `verify-append gold_v1` xanh (+0 câu, +0 retired).

## 4. Kết quả chính — rescore trên `gold_v2` (judged@10 = 1,000 cả hai arm)

| Metric | B0 | E2.e5 | Δ (e5 − B0) | CI95 | p (một phía, n=128) |
|---|---|---|---|---|---|
| recall@10 | 0,443 | 0,441 | −0,25 | [−2,82, +2,27] | 0,575 |
| nDCG@10 | 0,714 | **0,728** | +1,37 | [−2,16, +5,24] | 0,235 |
| MRR@10 | 0,757 | 0,757 | | | |
| constraint_precision | 0,522 | 0,444 | | | |

**Kết luận: TIE thống kê** (CI95 của cả hai Δ đều chứa 0). e5-base (768-d, chạy local CPU, miễn phí) ngang Cohere v3 trên bộ gold này sau khi loại thiên lệch pooling.

### nDCG@10 theo slice (Δ = e5 − B0, điểm %)

| Slice | n | B0 | E2.e5 | Δ |
|---|---|---|---|---|
| audience_style | 11 | 0,743 | 0,872 | **+12,93** |
| amenity_single | 13 | 0,825 | 0,923 | **+9,85** |
| cross_vertical | 10 | 0,879 | 0,935 | +5,59 |
| multi_constraint | 9 | 0,809 | 0,856 | +4,69 |
| no_diacritics | 12 | 0,190 | 0,219 | +2,90 |
| amenity_offtaxonomy | 5 | 0,623 | 0,640 | +1,72 |
| abbrev_typo | 12 | 0,435 | 0,446 | +1,16 |
| named_entity | 18 | 0,863 | 0,860 | −0,31 |
| parent_child | 11 | 0,744 | 0,718 | −2,55 |
| amenity_multi | 10 | 0,851 | 0,815 | −3,52 |
| dest_type | 12 | 0,860 | 0,805 | −5,54 |
| amenity_negation | 5 | 0,664 | 0,433 | **−23,14** |
| out_of_catalog | 3 | – | – | – |

## 5. Caveat bắt buộc khi trích dẫn

- Slice n ≤ 5 (`amenity_negation`, `amenity_offtaxonomy`, `out_of_catalog`) là số **ồn** — Δ −23 của amenity_negation dựa trên 5 câu.
- `no_diacritics` thấp ở cả hai arm (0,19/0,22): cả hai model đều yếu với query không dấu — ứng viên chính cho normalize (arm S) chứ không phải đổi model.
- 15 câu `abbrev_typo` từng dùng viết `QueryNormalizer` → số slice này là đo trong mẫu.
- `sb compare` CLI hiện đọc `results.json` gốc, chưa tự lấy bản `results@gold_v2.json` của rescore — bảng mục 4 tính bằng `runner.read_results_at` + `runner.compare` trên cùng file rescore. Cần vá CLI (TODO tool).
- Hai Δ lớn nhất theo hướng ngược nhau (audience_style +12,9 vs amenity_negation −23,1) đều nằm ở slice mà nhãn hole do máy gán + duyệt mẫu — nếu dùng cho quyết định M3, soát tay lại 2 slice này trước.

## 6. Tái sinh số (từ `src/`, `.venv-sbench`, `WEAVIATE_URL=http://127.0.0.1:8080`)

```
sb sanity --arms B0,E2.e5
sb --run-id 20261001-0623-ec5fbd2 rescore            # đọc gold hiện tại (gold_v2), không gọi Cohere/Weaviate
# bảng so sánh gold_v2: runner.read_results_at(run, arm, "gold_v2") + runner.compare  (compare CLI chưa nối bản rescore)
```
