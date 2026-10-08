# Bench: sửa `sb app-load` lỗi `NameError: am` sót sau merge gold_v4

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Sau merge `f1324af` (`history/2026-10-05-merge-gold-v4-hop-nhat-cong-app-e5s.md`), dòng in tóm tắt của `sb app-load` còn tham chiếu biến
`am` của lớp `app_model` đã bỏ → `NameError` sau khi nạp xong (collection vẫn được dựng; `sb run` không ảnh hưởng vì `AppContext.open`
tự nạp). Phát hiện khi chạy mốc + arm F3–F6 trên gold_v4 (`2026-10-05-gold-v4-qp`).

## File thay đổi

- `src/evaluation/search_bench/__main__.py` — sửa: dòng tóm tắt `app_load` dùng `PRODUCT_BENCH` (= `app_collection(model)`) và
  `cat.index.model_version` thay `am.*`.

## Quyết định

- Không thêm test CLI riêng: `sb app-load` cần Weaviate; kiểm bằng chạy thật.

## Kiểm tra

- `sb app-load --model e5-small` → `ProductBench__e5_small: 3183 object · khớp textHash 3183 · thiếu 0 · text cũ 0 · nạp mới 0 ·
  modelVersion intfloat/multilingual-e5-small:catalog-text-v2 · 3183 unit, 3182 available`.
- Run `2026-10-05-gold-v4-qp` (gold_v4 chưa tag, `--allow-untagged`; 154 câu active): mốc `APP.e5s.hybrid_norm_nocut` nDCG@10 0,660 (Judged
  0,836); F3 `_neg`: `amenity_negation` (13 câu) 0,261 → 0,450 (+18,95; Judged slice 0,477 → NEEDS_LABELS — sản phẩm mới lọt top-10 chưa có
  nhãn); F5 `_route`: `flight_direction` (6 câu) 0,822 → 0,908 (+8,59), MRR 1,0; F6 `_num`: `multi_constraint` +11,04; F4 `_tax`:
  `taxonomy_collision` 0,702 → 0,642 (−6,04), `flight_direction` −6,72, `abbrev_typo` −6,37 → xác nhận F4 chưa bật được với cue hiện tại;
  `_qp` 0,660 → 0,677. Mọi so cặp TIE theo win rule (Δrecall < 2); đọc theo slice.

## Còn lại / rủi ro

- Gold_v4 chưa có tag → số trên là "untagged"; chờ người dùng tạo tag `gold_v4`. Cần hole labelling cho `amenity_negation` (Judged 0,43–0,48 ở arm
  F3). Mở rộng `config/forbidden_v3.yaml` cho 8 câu phủ định mới / 6 câu chiều bay / 5 câu lẫn loại hoặc nối trường gold khi có.
