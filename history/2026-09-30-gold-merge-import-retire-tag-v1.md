# Đóng gold: merge → sửa merged.csv → import → retire c0463 → check xanh → tag `gold_v1`

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Chạy chuỗi đóng gold của `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md` §2 (dự kiến sáng 01/10, người dùng yêu
cầu chạy tối 30/09 sau khi rà slice xong). Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/gold/labels/merged.csv` — thêm: `sb gold merge` (3.359 cặp; A 1.359 · B 1.360 · both
  640) + 20 dòng sửa tay (dưới).
- `src/evaluation/search_bench/gold/gold.jsonl` — thêm: `sb gold import merged.csv`; sau retire còn 131/132 câu active.
- `src/evaluation/search_bench/gold/changelog.yaml` — thêm: mục `import` + mục `retire` (version `gold_v1`).
- `history/2026-09-30-gold-merge-import-retire-tag-v1.md` — thêm: entry này.
- Cùng commit: 4 file nhãn/provenance + guide + entry rà slice (`history/2026-09-30-ra-slice-quy-uoc-30-09-va-lam-ro-offtaxonomy.md`).

## Quyết định (20 dòng sửa trong merged.csv, note ghi trong file)

- **10 cặp `needs_discussion` (lệch 2 bậc)** quyết bằng quy ước chốt 30/09, không cần thảo luận thêm:
  - c0136/6da8386c, c0178/8a4c5920 → **1** (quy ước #2: đúng nơi sai loại, attraction).
  - c0208/f9718902 (KS Hà Nội ↔ câu Đà Lạt), c0229/3ce04b14 (Hà Tĩnh ↔ Hà Nội), c0433/418374af (ĐAN MY Motel ở
    **Quảng Bình** ↔ câu Pleiku, A gán nhầm), c0433/7eb7ca44, c0433/9e0a21c6 (Mũi Né ↔ Pleiku) → **0** (sai nơi).
  - c0450 ×3 (Hawaii, Gold Coast, Sea Sense) → **2**: resort Phú Quốc, snippet ghi "gần bãi biển"; "giá tốt" là điều
    kiện mềm.
- **Ghi đè theo plan §2** (bước tối 30/09 trong app chỉ làm được c0503; c0256/c0265 timestamp còn 29/09 → chưa chạm):
  c0256 (`8a545d40`, `21cb0fce`, `139eec1e`), c0265 (`330f3c0a`, `3ea9f4c4`, `5dc78ee3`) → **2**; c0457: 4 KS Hà Nội
  A=2 (`6ef1e28a`, `9308644f`, `9b612bf3`, `f11ec8eb`) → **2**, riêng `146c2033` (Múa rối nước — attraction) giữ 1
  theo quy ước #2. c0565 đã được sửa trong app (4 nhãn 2), không ghi đè thêm.
- Retire `c0463` lý do `pool_miss: 5d210e58 (ve HCM-Da Nang) ngoai pool depth 15` — đúng quyết định D1 của plan.

## Kiểm tra

- `sb gold kappa` sau rà slice: 640 cặp chung, **κ linear 0,661** (ngưỡng 0,6; trước rà 0,692), không trọng số 0,553,
  quadratic 0,760; lệch 2 bậc giảm 12 → 10.
- Import thử ra thư mục tạm → `sb gold check`: đỏ đúng 1 lỗi c0463 "không có nhãn 2" (kỳ vọng, retire xử lý).
- Import thật → retire → **`sb gold check` xanh: 131 câu active, 13 slice, min_per_slice = 3**.
- `git tag gold_v1` sau commit (kết quả ghi ở lệnh commit).

## Còn lại / rủi ro

- Sau `gold_v1` không sửa nhãn; mọi bổ sung đi vòng hole: `sb run` → `sb gold holes` → gán app → `holes import` →
  `check` → `verify-append` → tag `gold_v2` (plan §2, 01/10 chiều).
- **Không** chạy `sb gold import --overwrite` sau retire (đặt c0463 về active lại).
- κ giảm 0,692 → 0,661 sau rà slice: A sửa theo quy ước mới trên phần overlap nhiều hơn B — bất đồng còn lại đã được
  quyết trong merged.csv, không ảnh hưởng gold cuối.
- 492 nhãn máy của B chưa duyệt (không chặn merge, đã ghi ở entry gán nhãn xong).
