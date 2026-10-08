# Persona là 4 trạng thái cold-start; phong cách du lịch là đặc trưng của khách

- Ngày: 2026-10-09
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã áp dụng (2026-10-09: PRD, AGENTS.md §6.4, engine `DORMANT_AFTER_DAYS = 365`, spec, seed P3)
- Chốt bởi / ngày: tqanh123, 2026-10-09 (quyết định Q7, Q8 của plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §0)
- PRD bị ảnh hưởng: `docs/prd/project-brief.md` §5; `docs/prd/data-model.md` §2.2 (`APP_USERS`); `docs/prd/api-contract.md` §2.1
  (`/auth/me`); `docs/prd/user-flow.md` §1; `docs/prd/requirements.md` §3 AC-REC-01; `docs/prd/test-plan.md` (bảng E2E, dòng 4)
- Mã FR/NFR: FR-REC-01, FR-REC-03

## Lý do

1. Hai bộ persona đang lệch (AGENTS.md §6.4). PRD mô tả persona theo phong cách du lịch: `P1_family`, `P2_biz`, `P3_explorer`,
   `P4_deal` (cột `persona_tag`, trường `personaTag`). DDL, seed và engine dùng 4 trạng thái cold-start: `P1_frequent`,
   `P2_first_time`, `P3_dormant`, `P4_no_history` (`db/vota_schema.sql:186`). Contract không có trường persona nào.
2. Trạng thái cold-start mới là thứ quyết định nhánh gợi ý (có chuyến mở, chỉ xem chưa mua, ngủ đông, chưa có lịch sử).
   Phong cách du lịch (thích biển, núi, thành phố…) là **sở thích**, không phải nhánh. Một khách `P1_frequent` có thể thích
   biển hoặc thích núi.
3. Ngưỡng dormant đang có ba giá trị: spec 90 ngày tính từ event gần nhất, engine 180 ngày tính từ chuyến
   (`profile.py:17`), brainstorm 365 ngày. Với du lịch, khách đi một hai lần mỗi năm là bình thường; chốt **365 ngày**.

## Nội dung đề xuất

### `docs/prd/project-brief.md` §5 — thay bảng persona

Thay bảng P1–P4 hiện tại (gia đình / công tác / tự túc / săn ưu đãi) bằng:

> | Persona | Định danh | Định nghĩa | Gợi ý trang chủ |
> |---|---|---|---|
> | **P1** | `P1_frequent` | Đã mua, có chuyến đã đặt hoặc vừa đi | Hoàn thiện chuyến đang mở (vé bay, hoạt động tại điểm đến) |
> | **P2** | `P2_first_time` | Có xem / tìm kiếm, chưa mua | Gợi ý theo các sản phẩm vừa xem |
> | **P3** | `P3_dormant` | Đã mua, không có chuyến mở, chuyến gần nhất cách hơn **365 ngày** | Chào mừng quay lại, gợi ý theo sở thích dài hạn và mức phổ biến |
> | **P4** | `P4_no_history` | Chưa có lịch sử | Sản phẩm được đặt nhiều |
>
> **Phong cách du lịch** (biển, núi, thành phố, …) là một **đặc trưng của khách**, suy ra từ lịch sử tương tác, không phải
> persona. Gợi ý cá nhân hoá phải bám phong cách này (FR-REC-01, FR-REC-04).

### `docs/prd/data-model.md` §2.2 — `APP_USERS`

> `string persona_tag "P1_family, P2_biz, P3_explorer, P4_deal"` → `string persona "P1_frequent, P2_first_time, P3_dormant, P4_no_history"`

### `docs/prd/api-contract.md` §2.1 — `/auth/me`

> Trả về `userId`, `email`, `fullName`, `phone`, `personaTag` → Trả về `userId`, `email`, `fullName`, `phone` (khớp contract).

### `docs/prd/user-flow.md` §1

Đổi tiêu đề hai hành trình mẫu từ "Persona P1 / P3" sang theo phong cách du lịch ("Khách thích nghỉ dưỡng biển cùng gia
đình", "Khách thích khám phá văn hoá, ẩm thực"); nội dung hành trình giữ nguyên.

### `docs/prd/requirements.md` §3 — AC-REC-01

Hiện tại:

> | **AC-REC-01** | Người dùng P1 (Gia đình) đăng nhập vào hệ thống | Trang chủ hiển thị khu vực gợi ý với tiêu đề và nội dung phù hợp cho gia đình, mỗi thẻ sản phẩm hiển thị lý do `because` tương ứng. |

Thay bằng:

> | **AC-REC-01** | Người dùng có lịch sử (vd `P1_frequent` thường đặt resort biển) đăng nhập | Trang chủ hiển thị khu vực gợi ý phù hợp phong cách du lịch của khách (vd biển), mỗi thẻ sản phẩm hiển thị lý do `because` tương ứng. |

### `docs/prd/test-plan.md` — bảng E2E, dòng 4

> "Đăng nhập tài khoản Persona P1 (Gia đình) … giao diện cá nhân hóa cho gia đình" → "Đăng nhập tài khoản demo `P1_frequent` … gợi ý cá nhân hoá theo lịch sử của khách".

## Ngoài phạm vi đề xuất này

- Không thêm cột hay trường API cho phong cách du lịch. Muốn lưu hoặc trả ra (vd trong `/auth/me`) thì cần đề xuất và đổi
  contract riêng.
- `cdp.profiles.lifecycle_stage` là trường mirror CDP (`new`/`active`/`dormant`/`churned`, seed dùng 181–365 ngày cho
  `dormant`) — không đổi.
- `diagnostics.dormant` của contract ("event gần nhất cách trên 90 ngày", `src/shared/contracts/schemas/recommendations.yaml:135-137`)
  không đổi nghĩa, vì không được đổi semantics trong v1.

## Thay đổi source sau khi chốt

- PRD theo các mục trên (trước), rồi:
- `AGENTS.md` §6.4: bỏ mục "Bộ persona lệch giữa PRD và bản đã triển khai".
- `src/backend/app/domain/recommendation/profile.py`: `DORMANT_AFTER_DAYS = 365`, tăng `ENGINE_RULES_VERSION`; test unit theo.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4, §4.8 và bảng tham số (`dormantDays`): ngưỡng `strategy = dormant`
  là 365 ngày tính từ chuyến gần nhất; ghi rõ `diagnostics.dormant` vẫn 90 ngày. Kiểm `docs/spec/hop-dong-tich-hop-backend.md` §6.2.
- Seed: `src/data_collection/seed/config.py` `P3["trip_days_ago"]` (470, 190) → chuyến cuối > 365 ngày (vd (700, 400)) để tài
  khoản demo P3 vẫn ra `dormant`; `docs/spec/DATABASE_SCHEMA.md` §8 bảng persona ("chuyến cuối 6 tháng trước"),
  `docs/spec/MOCK_DATA_SPEC.md` nếu có ghi; chạy lại `db/verify.sql`.
- Bench: plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` dùng segment `P3_dormant` 365 ngày; baseline gate mới vì
  `configHash` đổi.
