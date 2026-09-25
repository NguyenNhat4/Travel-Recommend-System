# Bỏ tài khoản demo, kiểm thử bằng luồng đăng nhập thật

- Ngày: 2026-09-24
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-24
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.6 (FR-USR-01), `docs/prd/api-contract.md` §2.1 và §3 mục 2, `docs/prd/user-flow.md` §2 (route `/profile`) và §4.1 (wireframe Home), `docs/prd/implementation-plan.md` §2 (Giai đoạn 2)
- Mã FR/NFR: FR-USR-01

## Lý do

Bộ chọn tài khoản demo (Persona Switcher) được làm cho bản prototype. Dự án đã lên MVP nên cần kiểm thử bằng đúng luồng người dùng thật (đăng ký, đăng nhập qua `/register`, `/login`), không đi đường tắt mô phỏng.

Đề xuất bỏ cả phần giao diện lẫn API phục vụ nó:

- **Web:** bỏ 4 thẻ tài khoản demo (P1–P4) ở trang `/login` và `/register`, trong modal đăng nhập và trong menu tài khoản trên Header.
- **API:** bỏ `GET /api/v1/auth/demo-accounts` khỏi contract và backend.

**Ngoại lệ tương thích ngược cần chốt.** `docs/prd/api-contract.md` §3 mục 2 cấm xoá endpoint trong v1; thay đổi phá vỡ phải lên v2. Đề xuất xoá thẳng trong v1, vì:

- Không có client nào dùng endpoint này. Web hiển thị danh sách persona từ dữ liệu tĩnh (`src/frontend/src/data/personas.ts`) và chưa bao giờ gọi nó. Người dùng duy nhất là contract test và unit test của chính endpoint.
- Endpoint vốn trả `404` khi `APP_ENV=production`, nên ở production nó coi như chưa từng tồn tại.

Cùng ngoại lệ này, bỏ luôn giá trị `DEMO_ONLY` khỏi enum `ErrorCode`: mã này chỉ phục vụ endpoint demo và không nơi nào phát ra.

Nếu không chấp nhận ngoại lệ thì còn cách giữ endpoint trong v1 nhưng đánh dấu `deprecated: true`, rồi xoá ở v2. Người chốt chọn xoá thẳng.

Những gì **không** đổi:

- 4 persona và 50 user test vẫn được seed vào `app.users` như tài khoản bình thường, đăng nhập qua `/login` bằng email và mật khẩu seed. Persona là trạng thái dữ liệu (lịch sử hành vi) để kiểm các nhánh gợi ý, không phải cơ chế đăng nhập riêng. AC-REC-01 ("P1 đăng nhập → Home cá nhân hoá") kiểm theo cách này.

Ảnh hưởng: khi trình diễn, đổi persona phải đăng xuất rồi đăng nhập bằng email của persona kế tiếp. Người trình bày cần có sẵn danh sách email seed.

## Nội dung đề xuất

**`docs/prd/requirements.md` §1.6, FR-USR-01**

> Hỗ trợ đăng ký, đăng nhập an toàn qua email/mật khẩu hoặc cơ chế định danh mô phỏng (Persona Switcher phục vụ kiểm thử và trình diễn).

→

> Hỗ trợ đăng ký, đăng nhập an toàn qua email/mật khẩu.

**`docs/prd/api-contract.md` §2.1** — bỏ dòng:

> | `POST` | `/api/v1/auth/persona-switch` | Chuyển đổi nhanh persona | Nhận `personaTag` (`P1_family`, `P2_biz`,...) → Phiên mới |

**`docs/prd/api-contract.md` §3 mục 2** — thêm một gạch đầu dòng cuối:

> - Ngoại lệ đã chốt: `GET /api/v1/auth/demo-accounts` và mã lỗi `DEMO_ONLY` được gỡ khỏi v1 (2026-09-24) vì không có client sử dụng và endpoint đã tắt ở production.

**`docs/prd/user-flow.md` §2, dòng route `/profile`, cột thành phần chính**

> User Preferences, Booking History, Saved Items, Persona Selector

→

> User Preferences, Booking History, Saved Items

**`docs/prd/user-flow.md` §4.1, wireframe Home, dòng Header**

> `[Persona: P1 v]`

→

> `[Tài khoản v]`

**`docs/prd/implementation-plan.md` §2, Giai đoạn 2, hạng mục công việc**

> Triển khai phân hệ xác thực tài khoản và chuyển đổi Persona phục vụ kiểm thử.

→

> Triển khai phân hệ xác thực tài khoản (đăng ký, đăng nhập, phiên).

## Thay đổi source sau khi chốt

Contract (sửa trước, `AGENTS.md` §3):

- `src/shared/contracts/paths/auth.yaml` — bỏ `/auth/demo-accounts`.
- `src/shared/contracts/schemas/auth.yaml` — bỏ `DemoAccountListResponse` và schema con.
- `src/shared/contracts/openapi.yaml` — bỏ `$ref` path và schema tương ứng.
- `src/shared/contracts/schemas/common.yaml` — bỏ `DEMO_ONLY` khỏi `ErrorCode`.
- `src/shared/mocks/auth/listDemoAccounts.200-default.json` — xoá; bỏ mục tương ứng trong `src/shared/mocks/index.json`.
- Chạy `validate_contract.py`; sinh lại `src/frontend/src/types/api.gen.ts`.

Backend (`src/backend`):

- `app/api/v1/routes/auth.py` — bỏ route `demo_accounts`.
- `app/api/v1/schemas/auth.py` — bỏ `DemoAccountOut`, `DemoAccountListResponse`.
- `app/application/auth/use_cases.py` — bỏ `DemoAccount`, `ListDemoAccounts`, `_PERSONA_CARDS`.
- `app/application/ports/auth.py`, `app/infrastructure/auth/postgres_user_repository.py` — bỏ `list_personas` (chỉ endpoint này dùng).
- `app/main.py`, `tests/fakes/auth_app.py` — bỏ wiring `list_demo_accounts`.
- `tests/contract/test_auth_contract.py`, `tests/unit/application/test_auth_use_cases.py` — bỏ test của endpoint.
- `README.md` — bỏ `GET /auth/demo-accounts` khỏi danh sách endpoint.

Frontend (`src/frontend`):

- `src/components/common/DemoAccountSwitcher.tsx` — xoá.
- `src/components/auth/LoginView.tsx`, `src/components/common/LoginModal.tsx`, `src/components/common/Header.tsx`, `src/components/home/HomeView.tsx` — bỏ switcher và import.
- `src/context/TravelContext.tsx` — thay `switchPersona` bằng `signOut()`, bỏ nhánh đăng nhập persona.
- `src/services/auth.ts`, `.env.example` — bỏ `DEMO_PASSWORD` / `NEXT_PUBLIC_DEMO_PASSWORD`.
- `src/data/personas.ts` — giữ `SEED_PERSONAS`/`PERSONA_LOGIN` vì `personaFromUser` vẫn dùng để hiển thị thẻ persona sau khi đăng nhập; sửa comment không còn nhắc switcher.
- `tests/api/bff-auth.test.ts` đăng nhập bằng email + mật khẩu seed qua BFF, đúng luồng thật, giữ nguyên.

Spec (bỏ mô tả switcher và endpoint demo):

- `docs/spec/product.md` — K2, §4.7.1 wireframe, §4.7.3, menu tài khoản, bảng component, banner khách vãng lai ("Dùng tài khoản demo"), bảng Login/Register.
- `docs/spec/hop-dong-tich-hop-frontend.md` — dòng "Tài khoản demo" ở bảng API, dòng `DEMO_ONLY` ở bảng lỗi, mục kiểm thử số 10.
- `docs/spec/hop-dong-tich-hop-auth.md` — bảng §2 (dòng backend §3.1–§3.5), dòng F (§3.8), đoạn `DemoAccountSwitcher` ở §4.2, câu "nhóm v1 cũ giữ nguyên", dòng "Ẩn DemoAccountSwitcher ở production", danh sách schema giữ nguyên, mục kiểm thử "Đổi tài khoản demo".
- `docs/spec/hop-dong-tich-hop-backend.md` — §3.4 `GET /auth/demo-accounts`; dòng `DEMO_ONLY` ở bảng mã lỗi; lý do lưu giỏ phía server (bỏ nhắc switcher, giữ quyết định).
- `docs/spec/hop-dong-tich-hop-auth.md` §17 — bỏ `DEMO_ONLY` khỏi câu "giữ nguyên ý nghĩa cũ".

Không đổi: DDL, migration, seed.
