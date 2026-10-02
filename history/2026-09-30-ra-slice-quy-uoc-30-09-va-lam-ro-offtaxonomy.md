# Rà slice theo quy ước 30/09 xong; làm rõ quy ước #4 (amenity_offtaxonomy: chưa rõ ràng → 1)

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành — gold sẵn sàng cho merge / import / tag sáng 01/10
- Phạm vi: evaluation, docs

## Mục tiêu

Hoàn thành hai việc "tối 30/09" của `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md` §2: sửa nhãn trong app và rà
các slice bị quy ước chốt 30/09 chạm tới, trước khi merge / tag `gold_v1` (sau tag không sửa nhãn được nữa). Trong lúc
rà, người dùng chốt thêm một điểm làm rõ cho quy ước #4. Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/gold/labels/labels_A.csv`, `provenance_A.csv` — sửa (người gán A, qua app): c0256
  (`8a545d40`, `21cb0fce`, `139eec1e` → 2), c0265 (`330f3c0a`, `3ea9f4c4`, `5dc78ee3` → 2); rà slice theo quy ước
  30/09: c0136, c0178, c0217, c0259, c0268, c0564/c0565, các câu vé máy bay, slice `amenity_negation` (quy 0/1 cũ về
  2/0 theo #7).
- `src/evaluation/search_bench/gold/labels/labels_B.csv`, `provenance_B.csv` — sửa (người gán B, qua app): c0503
  (`5977c2d5`, `057196df` → 2) và phần rà thuộc B.
- `docs/spec/bench/gold-guide.md` — sửa: quy ước #4 thêm làm rõ "thiếu thông tin hoặc mô tả chưa rõ ràng → 1, xử như
  không ghi, không suy đoán từ hạng sao/loại sản phẩm" (kèm ngày trong bảng).
- `history/2026-09-30-ra-slice-quy-uoc-30-09-va-lam-ro-offtaxonomy.md` — thêm: entry này.

## Quyết định

- **Làm rõ quy ước #4** (người dùng chốt tối 30/09): trong `amenity_offtaxonomy`, sản phẩm thiếu thông tin hoặc mô tả
  không kết luận được có/không tiện ích → **1**, cùng nhánh với "không ghi"; chỉ có ghi rõ tiện ích mới được 2. Không
  suy đoán từ hạng sao hay loại sản phẩm.
- Nhãn sửa qua app đúng phạm vi bảng "Slice cần rà" của guide, không sửa hàng loạt ngoài danh sách (đúng ràng buộc
  trong `history/2026-09-30-gold-guide-quy-uoc-chot.md`).

## Kiểm tra

- Người gán tự rà trong app (chế độ Gán nhãn 0/1/2); `git status` xác nhận chỉ 4 file nhãn/provenance đổi.
- Chưa chạy lại `sb gold kappa` / `merge` — thuộc bước sáng 01/10 (plan §2).

## Còn lại / rủi ro

- Sáng 01/10 theo plan §2: `sb gold kappa` (ghi κ sau sửa) → `sb gold merge` → sửa 12 dòng `needs_discussion` +
  c0457, c0565 trong `merged.csv` → import thử ra thư mục tạm + `sb gold check` → import thật → `sb gold retire c0463
  --reason pool_miss` → `sb gold check` xanh → commit → `git tag gold_v1`. **Không** `import --overwrite` sau retire.
- 492 nhãn máy của B chưa duyệt (không chặn merge).
