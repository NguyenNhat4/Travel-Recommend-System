# Kế hoạch auth P0 và đề xuất PRD cho cơ chế hybrid

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành (tài liệu); triển khai theo plan chưa bắt đầu
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu lập kế hoạch hoàn chỉnh từ `docs/spec/hop-dong-tich-hop-auth.md`. Các entry auth ngày 21/09 đều `dang dở` và chia việc theo "bước 1–7" nhưng chưa có plan trong `docs/plan/`. Ngoài ra, sau khi tái cấu trúc backend và merge release, hiện trạng code đã khác những gì các entry đó mô tả.

## File thay đổi

- `docs/plan/2026-09-23-auth-p0.md` — thêm: bảng hiện trạng, 7 bước P0 và các bước bị chặn bởi đề xuất, câu hỏi mở.
- `docs/prd/update/2026-09-23-auth-hybrid-session.md` — thêm: đề xuất `chờ chốt`, gồm phần A (BFF + Redis + biến môi trường + ERD), phần B (cấp mã FR cho P1/P2) và phần C (mâu thuẫn FR-CDP-02).
- `history/2026-09-23-ke-hoach-auth-p0.md` — thêm: entry này.

## Quyết định

- **Plan chỉ gồm P0.** P1/P2 (2FA, OAuth, xác minh email) chưa có mã FR trong PRD, nên đưa vào phần B của đề xuất thay vì tự lập kế hoạch cho chúng.
- **Tách các bước lệch PRD ra khỏi các bước không lệch** (`AGENTS.md` §8). Các bước cần Redis/BFF bị khoá cho tới khi phần A được chốt. Các bước làm ngay được: contract bổ sung, hợp nhất JWT về RS256, route v1, `seed_auth`, test.
- **Ghi rõ hai đường JWT song song**: `core/security.py` (HS256, `JWT_SECRET`, từ release) và `infrastructure/auth/jwt_issuer.py` (RS256). Spec §10.2 loại HS256, nên plan gỡ đường HS256. Việc này không lệch PRD vì PRD không quy định thuật toán.
- **Đường dẫn theo PRD, không theo spec** khi hai bên khác nhau: dependency đặt ở `api/deps.py` (PRD §2) thay cho `api/v1/dependencies/auth.py`; test đặt theo lớp thay cho `tests/unit/auth/`.
- **FR-CDP-02 và spec §3.7 mâu thuẫn.** Không tự chọn; đưa ra phương án C1 (hoãn) và C2 (spec CDP riêng), agent đề xuất C1.

## Kiểm tra

- Đã đọc: `AGENTS.md`, `docs/prd/README.md`, `requirements.md`, `implementation-plan.md`, `architecture.md` §1–§6, `data-model.md` §1–§2.2, `deployment-plan.md` §1–§2, `test-plan.md` §3, `user-flow.md` §2, `project-brief.md` §4, toàn bộ spec auth, `history/README.md`, 4 entry auth/migration ngày 21/09 và 3 entry backend ngày 23/09.
- Đã đối chiếu hiện trạng bằng lệnh đọc file: danh sách route, port, adapter auth, `core/security.py`, contract `paths/auth.yaml`, `.env.example`, proxy Next.js, và các chỗ frontend dùng storage.
- Không chạy test hay validator: chỉ thêm tài liệu, không đổi contract/code.

## Còn lại / rủi ro

- Đề xuất `2026-09-23-auth-hybrid-session.md` chờ người dùng chốt ba phần A/B/C.
- `CdpClient.ensure_profile` vẫn chờ reviewer Data/Integration.
- Các entry `dang dở` ngày 21/09 vẫn giữ nguyên trạng thái; entry của từng bước khi triển khai sẽ ghi tiến độ.
