# Sửa e2e widget-opening theo nhãn nút "Thanh toán tất cả"

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI fail ở `tests/e2e/widget-opening.spec.ts:102` (completed results still open the timeline and map): không tìm thấy nút `Thanh toán` (exact). Nút trong widget đã đổi nhãn thành "Thanh toán tất cả" ở commit `071df7b` nhưng test không được cập nhật.

## File thay đổi

- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: locator nút ở dòng 119 từ `Thanh toán` thành `Thanh toán tất cả` (exact).

## Quyết định

- Sửa test cho khớp UI hiện tại, không đổi UI. Nhãn "Thanh toán tất cả" nằm ở `WidgetPlanPanel.tsx`.
- Giữ `exact: true` để không trùng nút khác.
- Log `ECONNREFUSED 127.0.0.1:8000` trong CI là nhiễu (CI không chạy backend, các request không mock đi qua proxy Next), không phải nguyên nhân lỗi.

## Kiểm tra

- `npm run build:web` rồi `playwright test tests/e2e/widget-opening.spec.ts --project=chromium --retries=0`: 6 passed.
- Chưa chạy toàn bộ e2e suite và chưa chạy lại trên CI.

## Còn lại / rủi ro

- Đã grep `tests/`: không còn test nào tìm nút `Thanh toán` (exact) khác.
