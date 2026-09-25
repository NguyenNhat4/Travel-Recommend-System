# Bỏ tài khoản demo, kiểm thử bằng luồng đăng nhập thật

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs, contract, backend, frontend

## Mục tiêu

Dự án đã chuyển từ prototype lên MVP, nên người dùng yêu cầu bỏ bộ chọn tài khoản demo (4 thẻ P1–P4) và kiểm thử bằng luồng đăng ký/đăng nhập thật. Việc này lệch PRD (FR-USR-01 có Persona Switcher; `api-contract.md` cấm xoá endpoint trong v1). Vì vậy đã làm đề xuất `docs/prd/update-archive/2026-09-24-go-bo-chon-tai-khoan-demo.md`, và mihhquan đã chốt ngày 2026-09-24. Lúc chốt, người dùng yêu cầu bỏ thêm mã lỗi `DEMO_ONLY`.

## File thay đổi

- `docs/prd/update-archive/2026-09-24-go-bo-chon-tai-khoan-demo.md` — thêm: đề xuất, trạng thái `đã áp dụng` (tạo ở `docs/prd/update/`, chuyển sang archive trong cùng thay đổi).
- `docs/prd/requirements.md` — sửa: FR-USR-01 chỉ còn "đăng ký, đăng nhập an toàn qua email/mật khẩu".
- `docs/prd/api-contract.md` — sửa: bỏ dòng `/auth/persona-switch` ở §2.1; thêm ngoại lệ tương thích ngược đã chốt ở §3 mục 2.
- `docs/prd/user-flow.md` — sửa: bỏ "Persona Selector" ở route `/profile`; wireframe Home `[Persona: P1 v]` → `[Tài khoản v]`.
- `docs/prd/implementation-plan.md` — sửa: Giai đoạn 2 bỏ "chuyển đổi Persona".
- `src/shared/contracts/paths/auth.yaml`, `schemas/auth.yaml`, `openapi.yaml` — sửa: bỏ `/auth/demo-accounts` và `DemoAccountListResponse`.
- `src/shared/contracts/schemas/common.yaml` — sửa: bỏ `DEMO_ONLY` khỏi `ErrorCode`.
- `src/shared/mocks/auth/listDemoAccounts.200-default.json` — xóa; `src/shared/mocks/index.json` — sửa: bỏ mục tương ứng.
- `src/backend/app/api/v1/routes/auth.py` — sửa: bỏ route `demo_accounts` và import không còn dùng.
- `src/backend/app/api/v1/schemas/auth.py` — sửa: bỏ `DemoAccountOut`, `DemoAccountListResponse`.
- `src/backend/app/application/auth/use_cases.py` — sửa: bỏ `DemoAccount`, `_PERSONA_CARDS`, `ListDemoAccounts`.
- `src/backend/app/application/ports/auth.py`, `app/infrastructure/auth/postgres_user_repository.py`, `tests/fakes/auth.py` — sửa: bỏ `list_personas` (chỉ endpoint demo dùng).
- `src/backend/app/main.py`, `tests/fakes/auth_app.py` — sửa: bỏ wiring `list_demo_accounts`.
- `src/backend/tests/contract/test_auth_contract.py`, `tests/unit/application/test_auth_use_cases.py` — sửa: bỏ test của endpoint demo.
- `src/backend/README.md` — sửa: bỏ endpoint khỏi danh sách; ghi tài khoản seed đăng nhập qua `/login`.
- `src/frontend/src/components/common/DemoAccountSwitcher.tsx` — xóa.
- `src/frontend/src/components/auth/LoginView.tsx`, `common/LoginModal.tsx`, `common/Header.tsx`, `home/HomeView.tsx` — sửa: bỏ switcher, mục "Thử nghiệm hồ sơ mẫu (Demo)" và import.
- `src/frontend/src/context/TravelContext.tsx` — sửa: `switchPersona(id | null)` → `signOut()`.
- `src/frontend/src/services/auth.ts`, `src/frontend/.env.example` — sửa: bỏ `DEMO_PASSWORD` / `NEXT_PUBLIC_DEMO_PASSWORD`.
- `src/frontend/src/data/personas.ts` — sửa: comment; giữ `SEED_PERSONAS`/`PERSONA_LOGIN` cho `personaFromUser`.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types`.
- `docs/spec/product.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-backend.md`, `docs/spec/hop-dong-tich-hop-auth.md` — sửa: bỏ mô tả switcher, endpoint demo và `DEMO_ONLY`. §3.4 backend và §4.7.3 product giữ số mục dưới dạng "đã gỡ".
- `AGENTS.md` — sửa: danh sách lệch đã biết ở §2 và §6.4 không còn nhắc `/auth/persona-switch`, `/auth/demo-accounts`, `personaLabel`.

## Quyết định

- Xoá thẳng endpoint và `DEMO_ONLY` trong v1, không lên v2. Đây là ngoại lệ tương thích ngược đã chốt, ghi vào `api-contract.md` §3 mục 2. Lý do: không client nào gọi endpoint, và nó vốn trả 404 ở production.
- Giữ 4 persona và 50 user test trong seed như tài khoản bình thường (mật khẩu `Demo@2026`), vì AC-REC-01 và các nhánh gợi ý cold-start cần dữ liệu này. Seed và DDL không đổi.
- Giữ số mục §3.4 (backend spec) và §4.7.3 (product spec) dưới dạng "đã gỡ", để các tham chiếu chéo không lệch.
- Không sửa `docs/spec/data-collection/bao-cao-schema.md` và các báo cáo rà soát cũ nhắc `demo_accounts`/`DEMO_ONLY`: đó là báo cáo theo thời điểm, không phải hợp đồng hiện hành.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (77 schemas, 53 fixture; CDP clone 12 schemas, 7 fixture).
- `python -m pytest -q src/backend/tests`: 281 passed, 13 skipped. Trước thay đổi là 283; chênh 2 test vì đã bỏ 2 test của endpoint demo. Test kiến trúc vẫn xanh.
- Frontend: `npx tsc --noEmit` không lỗi; `npx vitest run` 76/76 pass. `npx eslint` trên các file đã sửa: 0 lỗi, 1 warning có sẵn (`HomeView.tsx:470`, exhaustive-deps, không liên quan).
- Chưa chạy Playwright e2e; `tests/e2e` không có test nào dùng switcher.

## Còn lại / rủi ro

- Đổi persona khi trình diễn giờ phải đăng xuất rồi đăng nhập bằng email seed; người trình bày cần có sẵn danh sách email (`src/data_collection/seed/config.py`).
- Client nội bộ nào tự gọi `GET /api/v1/auth/demo-accounts` (ngoài repo) sẽ nhận 404.
- Chưa sửa lỗi nút "Đăng ký" trên Header: nút này gọi `openLoginModal()` giống nút "Đăng nhập", và `/register` render `LoginView` ở chế độ đăng nhập. Lỗi không lệch PRD, đang chờ người dùng xác nhận có sửa hay không.
