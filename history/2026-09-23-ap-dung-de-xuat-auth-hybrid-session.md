# Áp dụng đề xuất auth hybrid: chốt phần A, từ chối phần B, C1 cho lịch sử ẩn danh

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất `2026-09-23-auth-hybrid-session.md`, nguyên văn: "Phần B đang ngoài phạm vi, Phần nếu lịch sử ẩn danh cũng nằm ngoài phạm vị hiện tại chỉ cần tracking khi người dùng đăng nhập. Chốt phần A". Việc cần làm theo `AGENTS.md` §8 bước 3–4: cập nhật PRD trước, sửa spec/plan theo PRD mới, sau đó chuyển đề xuất sang lưu trữ.

## File thay đổi

PRD:
- `docs/prd/architecture.md` — sửa: §1 thêm node BFF và Redis, luồng `UI/Tracker → BFF → Router`, schema `app` ghi refresh tokens và login attempts thay cho "Sessions"; §4 thêm dòng Redis 7; §6.2 thêm quy tắc trình duyệt không giữ JWT và vai trò BFF.
- `docs/prd/deployment-plan.md` — sửa: §1 thêm dòng Session store; §2 thêm biến JWT/`AUTH_SERVICE_TOKEN`/Redis/`TRUSTED_PROXIES`/CAPTCHA; §3.1 thêm lệnh khởi động Redis.
- `docs/prd/data-model.md` — sửa: §1 thêm `refresh_tokens`, `login_attempts`; §2.2 ERD thêm hai bảng và cột `email_verified_at`.
- `docs/prd/requirements.md` — sửa: FR-CDP-02 ghi "hoãn, ngoài phạm vi MVP"; chỉ tracking khi người dùng đã đăng nhập.
- `docs/prd/test-plan.md` — sửa: §3 bước 1–3 không sinh event CDP khi ẩn danh; bước 4 bỏ việc gộp lịch sử, thêm kiểm tra trình duyệt không có token.

Đề xuất:
- `docs/prd/update/2026-09-23-auth-hybrid-session.md` → `docs/prd/update-archive/2026-09-23-auth-hybrid-session.md` — đổi tên: trạng thái đã áp dụng (A, C1) / từ chối (B), thêm mục "Kết quả chốt". Dùng `mv` thay cho `git mv` vì file chưa từng được commit.

Spec, plan:
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: ghi chú phạm vi ở đầu file (chỉ P0; §11–§13 và P1/P2 ngoài phạm vi); tiêu đề P1, P2 ở §21 thêm "ngoài phạm vi".
- `docs/spec/auth/so-do-luong-xac-thuc.md` — sửa: ghi chú trạng thái đã chốt; mục 7 (OTP) đánh dấu ngoài phạm vi.
- `docs/plan/2026-09-23-auth-p0.md` — sửa: bỏ các khoá 🔒, bảng câu hỏi mở cập nhật theo quyết định, `mfa/verify` không làm.
- `history/2026-09-23-ap-dung-de-xuat-auth-hybrid-session.md` — thêm: entry này.

## Quyết định

- **Không cấp FR-USR-04..06.** Phần B bị từ chối nên không thêm FR vào `requirements.md`. Spec auth giữ nguyên nội dung P1/P2 để tham khảo, chỉ đánh dấu ngoài phạm vi, không xoá.
- **C1: chỉ tracking khi đã đăng nhập.** Sửa cả bước 2–3 của UAT, không chỉ bước 1 và 4 như đề xuất ghi, vì hai bước đó cũng diễn ra khi đang ẩn danh.
- **A.4 "bỏ `JWT_SECRET`/`JWT_ALGORITHM`" là thay đổi source**, không sửa PRD (PRD chưa từng ghi hai biến này). Việc này thuộc bước 3a của plan, chưa làm trong thay đổi này.
- ERD vẫn giữ `persona_tag` như cũ: lệch persona là tồn đọng đã ghi ở `AGENTS.md` §6.4, không thuộc đề xuất này.

## Kiểm tra

- Parse lại các khối Mermaid bằng `mermaid@12.0.0`: `architecture.md` 2/2 OK, `data-model.md` 2/2 OK.
- `grep -c 🔒 docs/plan/2026-09-23-auth-p0.md` → 0.
- Không chạy test hay validator: chỉ đổi tài liệu, không đổi contract/code.

## Còn lại / rủi ro

- Chưa triển khai code theo plan (bắt đầu từ bước 1 và 3a).
- Redis ở staging (managed hay tự host) vẫn chờ chốt; `deployment-plan.md` §1 ghi rõ điều này.
- `docs/spec/hop-dong-tich-hop-cdp.md` §1.6 vốn đã để ghép lịch sử ngoài phạm vi, nên không cần sửa.
