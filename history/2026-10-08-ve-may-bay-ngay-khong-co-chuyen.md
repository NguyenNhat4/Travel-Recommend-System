# Vé máy bay: ngày đã tìm không có chuyến thì báo rõ, không tự đổi sang ngày khác

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend | docs
- Thay thế: phần quyết định "ngày `checkIn` không có chuyến thì mở ngày gần nhất kèm câu báo" của 2026-09-30-ket-qua-ve-may-bay-duoi-tim-kiem.md

## Mục tiêu

mihhquan báo: ở `/flights`, tìm một ngày không có chuyến thì trang lại hiện chuyến của ngày khác; đúng ra phải thông báo không có. Phương án được chọn sau khi xem ba phương án trên artifact (https://claude.ai/artifact/PHvCrzbEr3VbxQr22PyVJv): thông báo kèm nút ngày gần nhất để khách tự bấm, dải ngày vẫn hiện và chưa ngày nào được chọn. Mã yêu cầu: FR-SRC-03, FR-CAT-03, FR-BKG-10.

## File thay đổi

- `src/frontend/src/features/flights/results/flightModel.ts` — sửa: `pickDate` không còn trả ngày gần nhất; ngày mong muốn không có chuyến thì `date: null` và `nearest` (ngày có chuyến gần nhất trước và sau).
- `src/frontend/src/features/flights/results/FlightResultsView.tsx` — sửa: bỏ câu báo "đang hiển thị ngày gần nhất"; thêm trạng thái "Không có chuyến bay … ngày …" kèm nút ngày gần nhất; chiều về không nhập ngày thì mở ngày đầu tiên có chuyến nối được.
- `src/frontend/src/features/flights/results/FlightDateStrip.tsx` — sửa: chỉ chú thích (dải ngày có thể không có ngày nào được chọn).
- `src/frontend/tests/unit/flightModel.test.ts` — sửa: ca của `pickDate` theo hành vi mới (2 test thay cho 1).
- `src/frontend/tests/unit/flightResultsView.test.tsx` — sửa: thay test "mở ngày gần nhất" bằng test thông báo và nút gợi ý; thêm test chiều về.
- `src/frontend/tests/unit/flightsPage.test.tsx` — sửa: chuyến mẫu bay đúng ngày mặc định của tấm tìm kiếm (ngày mai), vì trang chỉ hiện chuyến của đúng ngày đã tìm.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.1b, mục "Dải ngày" và mục mới về ngày không có chuyến.
- `history/2026-09-30-ket-qua-ve-may-bay-duoi-tim-kiem.md` — sửa: thêm dòng `Bị thay thế một phần bởi`.
- `history/2026-10-08-ve-may-bay-ngay-khong-co-chuyen.md` — thêm.

## Quyết định

- **Không lệch PRD, không cần đề xuất.** PRD chỉ ghi tìm vé theo điểm đi, điểm đến, ngày ở `/flights` (FR-SRC-03, `user-flow.md` bảng route); quy tắc "mở ngày gần nhất" chỉ nằm ở spec frontend §4.1b nên sửa spec trong cùng thay đổi.
- **Không tự đổi ngày.** Hiện chuyến của ngày khác dưới một dòng báo nhỏ dễ làm khách đặt nhầm ngày. Ngày gần nhất chỉ là nút để khách tự chọn (một ngày trước, một ngày sau).
- **Chiều về không nhập ngày:** trước đây lấy ngày của chuyến chiều đi làm ngày mong muốn; với quy tắc mới việc đó sẽ báo "không có chuyến" cho một ngày khách chưa từng chọn, nên chuyển sang mở ngày đầu tiên có chuyến nối được.
- Chỉ sửa Web: ngày vẫn lọc phía client trên các chuyến của tuyến; không đổi contract, Backend, DDL.

## Kiểm tra

Chạy từ `src/frontend`:

- `node_modules/.bin/tsc --noEmit`: sạch.
- `node_modules/.bin/eslint .`: 0 lỗi, 2 cảnh báo có sẵn ở `components/assistant/ItineraryMap.tsx`.
- `node_modules/.bin/vitest run tests/unit`: 68 file, 726 test pass.
- Trình duyệt thật (script Playwright tạm, dev server `localhost:3000`, Backend `:8000`, dữ liệu database local), tuyến Hà Nội → TP. Hồ Chí Minh có chuyến các ngày 09, 12, 14, 15, 20, 21, 31/10 và 05/11:
  - tìm 13/10/2026 (ngày trống ở giữa): 0 thẻ chuyến, không ngày nào được chọn, thông báo đúng ngày, hai nút 12/10 và 14/10;
  - tìm 04/08/2027 (sau ngày cuối): thông báo, một nút 05/11; bấm nút thì ra 1 chuyến của 05/11 và thông báo mất;
  - tìm 15/10/2026 (có chuyến): 2 thẻ chuyến, ngày 15/10 được chọn, không thông báo.
  - Đã xem ảnh chụp ở khổ 1440 px và 390 px.
- Không đổi contract hay mock nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Tấm tìm kiếm luôn gửi ngày đi, mặc định là ngày mai. Catalog chuyến bay thưa nên khách không đổi ngày sẽ thường gặp thông báo này trước khi thấy chuyến; đây là hệ quả của quy tắc mới, cần xem lại nếu dữ liệu chuyến bay vẫn thưa.
- Chiều về trên trình duyệt thật chưa kiểm (chỉ có test đơn vị).
- Chưa có Playwright e2e cho `/flights`.
