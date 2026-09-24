# Sơ đồ sequence và activity cho luồng xác thực

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng (vai BA) yêu cầu vẽ sequence diagram cho các thành phần tương tác và UML activity diagram mô tả logic xử lý cho Software Architect. Mỗi activity phải có start/end, action, decision, swimlane, data, error path, loop. Đầu ra là file `.md` trong `docs/spec/auth/`, có giải thích dễ hiểu.

## File thay đổi

- `docs/spec/auth/so-do-luong-xac-thuc.md` — thêm: 14 sơ đồ Mermaid (6 sequence, 6 activity, 1 sơ đồ thành phần, 1 state machine) cho đăng nhập, đăng ký hai pha, gọi API có xác thực, refresh token rotation, OTP 2FA (P1), đăng xuất, vòng đời phiên; kèm bảng lỗi.
- `docs/plan/2026-09-23-auth-p0.md` — sửa: thêm dòng trỏ tới file sơ đồ.
- `history/2026-09-23-so-do-luong-xac-thuc.md` — thêm: entry này.

## Quyết định

- **Chỉ vẽ lại spec auth, không thêm hành vi mới.** Mọi ngưỡng, mã lỗi và thứ tự bước lấy từ `docs/spec/hop-dong-tich-hop-auth.md`. Tài liệu ghi rõ spec auth và OpenAPI thắng khi có chỗ khác nhau.
- **Vòng lặp OTP để tối đa 5 lần/15 phút, không phải 3 lần như ví dụ trong yêu cầu.** Con số 5 lấy theo spec auth §9.1 (`rl:mfa`).
- **Không có swimlane Admin hay Payment Service.** Spec auth §1.3 để RBAC ngoài phạm vi, và PRD `project-brief.md` §4.2 để thanh toán thật ngoài phạm vi. Tài liệu có ghi lý do.
- **Lỗi mạng BFF→Backend ghi là `502`**, khớp hành vi hiện tại của `src/frontend/src/app/api/[...path]/route.ts`. Spec auth không quy định mã lỗi cho trường hợp này.
- Đầu file ghi rõ các bước BFF/Redis phụ thuộc đề xuất `docs/prd/update/2026-09-23-auth-hybrid-session.md` (chờ chốt), và mục 2FA là P1.
- Activity diagram vẽ bằng Mermaid `flowchart` với `subgraph` làm swimlane, vì Mermaid không có kiểu activity riêng. Mục 2 của tài liệu có bảng giải thích ký hiệu.

## Kiểm tra

- Đã parse cả 14 khối Mermaid bằng `mermaid@12.0.0` + `jsdom`, cài tạm trong scratchpad: **14 blocks, 0 failed**. Chưa kiểm phần hiển thị trên GitHub hay VS Code bằng mắt.
- Không chạy test hay validator: chỉ thêm tài liệu.

## Còn lại / rủi ro

- Nếu đề xuất `2026-09-23-auth-hybrid-session.md` bị từ chối hoặc sửa phần A, các sơ đồ có BFF/Redis (mục 1, 3, 5, 6, 8) phải vẽ lại.
- Mục 10 (bảng lỗi) chép từ spec auth §17; khi thêm mã lỗi mới vào contract thì phải cập nhật cả hai nơi.
