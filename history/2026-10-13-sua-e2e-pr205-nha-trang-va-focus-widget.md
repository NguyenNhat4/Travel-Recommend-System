# Sửa 2 e2e fail trên PR #205 (Nha Trang ở /hotels, focus widget)

- Ngày: 2026-10-13
- Tác giả: người dùng (dán log CI của PR #205) / Claude Code
- Nhánh: khoa/flight-hotels-combos-design (PR #205)
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI của PR #205 (`Frontend CI`, run 38373599714) fail 2 test e2e:

1. `navigation.spec.ts:110` — "the hotels search sheet shows results on /hotels itself": `getByRole('option', { name: 'Nha Trang' })` khớp 4 phần tử (strict mode).
2. `widget-opening.spec.ts:93` — "keyboard submission switches to chat…": `Đóng` không nhận focus sau Shift+Tab (flaky, pass ở lần retry).

## File thay đổi

- `src/frontend/tests/e2e/navigation.spec.ts` — sửa: ở `/hotels`, gõ "Nha Trang" vào ô địa điểm rồi chọn option đúng tên `Nha Trang` (`exact: true`), thay vì click option trong danh sách lúc ô còn trống.
- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: trước Shift+Tab, chờ một khung `requestAnimationFrame` chạy xong.
- `history/2026-10-13-sua-e2e-pr205-nha-trang-va-focus-widget.md` — thêm: entry này.

## Quyết định

- **Lỗi 1 là test lệch spec, không phải lỗi UI.** PR #205 đã áp dụng `docs/prd/update-archive/2026-10-13-san-bay-va-khach-san-noi-tieng.md` (người dùng chốt): ô địa điểm trống hiện "Khách sạn nổi tiếng", "Điểm đến" chỉ hiện khi gõ. Test cũ click "Nha Trang" lúc ô trống nên không còn option đó, và locator khớp các khách sạn `Sản phẩm N, Nha Trang`. Không đổi UI; test làm đúng luồng mới (gõ rồi chọn điểm đến). Dòng 79 của cùng file đã kiểm "Điểm đến phổ biến" không còn, khớp spec mới.
- **Lỗi 2 là race giữa test và `useWidgetFocus`.** Sau "Đoạn chat mới", `useWidgetFocus` đặt focus vào textarea bằng `requestAnimationFrame`. Nếu khung đó chạy sau khi test nhấn Shift+Tab (focus đã sang `Đóng`), nó kéo focus về textarea và `Đóng` không bao giờ được focus (`Received: inactive`). Đã tái hiện có kiểm soát: làm chậm rAF 300 ms thì ngay sau Shift+Tab focus ở `Đóng`, 600 ms sau focus về `TEXTAREA`. Sửa ở test (chờ một khung trước Shift+Tab), không đổi `useWidgetFocus`: focus trả về textarea là hành vi đúng, và chưa có bằng chứng người dùng gặp lỗi này.
- Không đổi code ứng dụng.

## Kiểm tra

- Trước sửa, `navigation.spec.ts` trên đúng code PR #205 (`build:web` rồi `playwright test`): `hotels search sheet` fail do strict mode (tái hiện trên máy local).
- Sau sửa, `navigation.spec.ts`: 11/11 pass.
- Sau sửa, toàn bộ e2e (`npx playwright test --project=chromium`, build từ code PR #205): 44 passed.
- `widget-opening` keyboard test, `--repeat-each=20` (trước sửa, không tải): 20/20 pass. `--repeat-each=25` có stress CPU: 25/25 pass. Không tái hiện được flake ở local, nên xác nhận bằng diagnostic.
- Diagnostic rAF trễ 300 ms (spec tạm, đã xoá): trước sửa fail đúng triệu chứng CI; sau sửa (thêm chờ một khung) pass.
- `npx eslint` trên 2 file sửa: pass. `npx tsc --noEmit`: pass.

## Còn lại / rủi ro

- Đã commit và push lên `khoa/flight-hotels-combos-design` (fast-forward từ `9962746e`). CI của PR #205 chạy lại trên commit mới; kết quả CI chưa được kiểm trong entry này.
- Flake của lỗi 2 không tái hiện được ở local, nên fix dựa vào diagnostic. Nếu CI vẫn flake, xem lại thứ tự rAF và focus.
- Nếu muốn widget không bao giờ kéo focus khi người dùng đã chuyển focus, sửa `useWidgetFocus` (chỉ đặt focus khi focus đang ở ngoài dialog) là thay đổi hành vi riêng, chưa làm.
