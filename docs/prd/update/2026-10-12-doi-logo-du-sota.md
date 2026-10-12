# Đổi logo hiển thị trên giao diện sang "Dự Sota", ký hiệu chữ S

- Ngày: 2026-10-12
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §3 (wireframe header `[LOGO] V-OTA`). PRD vẫn ghi V-OTA; đề xuất trước (`2026-10-09-doi-ten-hien-thi-x-ota.md`) đã chốt giữ nguyên PRD, đề xuất này theo cùng cách.
- Mã FR/NFR: không đổi FR/NFR nào; chỉ đổi tên thương hiệu hiển thị ở logo.

## Lý do

Người dùng yêu cầu đổi các logo liên quan thành **Dự Sota**, ô biểu tượng là chữ **S**. Logo hiện hiển thị "X-OTA" với ô chữ "X" (sau đợt đổi V-OTA → X-OTA ngày 2026-10-09). Đổi tên logo là lệch PRD nên cần chốt trước (AGENTS.md mục 8).

## Nội dung đề xuất

Phạm vi mặc định (hẹp, chỉ logo): ba chỗ vẽ logo trong `src/frontend/src/components/common/`.

| Vị trí | Hiện tại | Đề xuất |
|---|---|---|
| `Header.tsx` (header trang thanh toán, dòng 200–205) | ô `X` + chữ `X-OTA` | ô `S` + chữ `Sota` |
| `Header.tsx` (header chính, dòng 251–260) | ô `X`, chữ `X-OTA`, `aria-label="X-OTA, về trang chủ"` | ô `S`, chữ `Sota`, `aria-label="Dự Sota, về trang chủ"` |
| `Footer.tsx` (dòng 31–35) | ô `X` + chữ `X-OTA` | ô `S` + chữ `Sota` |

Lưu ý: chữ logo header chính đang `uppercase` nên sẽ hiện "DỰ SOTA"; footer cũng `uppercase`. Đề xuất giữ kiểu in hoa như hiện tại.

**Câu hỏi cần người dùng trả lời khi chốt**

1. Chỉ đổi 3 logo trên (mặc định), hay đổi luôn mọi chữ "X-OTA" còn lại trên giao diện (tiêu đề trang, `metadata.json`, đăng nhập, chân trang, widget trợ lý, thông báo… khoảng 50 chỗ trong `src/frontend`) để tên thống nhất?
2. Giữ nguyên dòng phụ "Resorts & Hotels" dưới logo?
3. Có cần đổi favicon/ảnh logo không? Hiện frontend không có file logo ảnh; logo là chữ và ô màu vẽ bằng CSS.

## Thay đổi source sau khi chốt

- `src/frontend/src/components/common/Header.tsx`, `Footer.tsx` (và các file khác nếu chốt phạm vi rộng, đối chiếu bằng `grep -rn "X-OTA" src/frontend`).
- `src/frontend/tests/**` nếu có test khớp chuỗi logo.
- Không sửa backend, mock, PRD, `docs/spec` (như quyết định 2026-10-09), tên kỹ thuật `vota`.
- Kiểm tra: `tsc --noEmit`, `vitest run`, `eslint` trong `src/frontend`.
