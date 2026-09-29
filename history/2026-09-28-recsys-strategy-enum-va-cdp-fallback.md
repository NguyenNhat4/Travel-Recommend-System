# Bổ sung enum Strategy và fallback popular khi đọc CDP lỗi

- Ngày: 2026-09-28
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: contract, backend, docs, frontend

## Mục tiêu

Hai lỗi sẵn có được người dùng chốt sửa kèm việc đưa agent gọi engine trong tiến trình (quyết định 4, 2026-09-28):

- Engine Recommendation (`domain/recommendation/profile.py:47-54`) trả `long_term` và `cold_start_content`, nhưng enum `Strategy` trong contract thiếu hai giá trị này. Response hợp lệ của engine vì vậy trượt kiểm contract (FR-REC-01, FR-REC-03, AC-REC-01), và tool `get_recommendations` của agent báo `INVALID_TOOL_RESPONSE`.
- Đọc lịch sử CDP lỗi (sập, timeout) làm `/recommendations` trả 500, trong khi `hop-dong-tich-hop-cdp.md` §6 mục 3 và §7 yêu cầu lui về `popular`. Reader cũng chưa dùng `CDP_TIMEOUT_SECONDS`.

## File thay đổi

- `src/shared/contracts/schemas/common.yaml` — sửa: `Strategy` thêm `long_term`, `cold_start_content`, mỗi giá trị một câu mô tả theo điều kiện của engine; giá trị cũ giữ nguyên.
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.6.0 → 1.8.0, một lần cho cả đợt (chung với thay đổi `dataMode` của entry `2026-09-28-agent-goi-engine-trong-tien-trinh.md` và tool Similar của entry `2026-09-29-tool-similar-cho-agent.md`).
- `src/shared/mocks/recommendations/getRecommendations.200-long-term.json` — thêm: mock `strategy: long_term`, `coldStart: false`, `because` không rỗng.
- `src/shared/mocks/recommendations/getRecommendations.200-cold-start-content.json` — thêm: mock `strategy: cold_start_content`, `coldStart: true`, `because: []` theo quy tắc 4 của contract.
- `src/shared/mocks/index.json` — sửa: đăng ký hai mock mới (case `long-term`, `cold-start-content`).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types`; chỉ đổi union `Strategy` và `dataMode`, JSDoc của hai enum và `@description` của hai operation `/search`.
- `src/backend/app/infrastructure/cdp/postgres_cdp_reader.py` — sửa: nhận `timeout_seconds`; `connect_timeout = max(2, ceil(t))`; `statement_timeout` đặt bằng `set_config(..., true)` trong transaction, chỉ cho `events_for_user`; `OperationalError`/`InterfaceError`/`OSError` → `CdpUnavailableError` với message một dòng, cắt ngắn, đã xoá DSN/mật khẩu; `ProgrammingError` vẫn nổi lên.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: `RecommendForUser` bắt `CdpUnavailableError` quanh `events_for_user`, log WARNING `recommend.cdp_unavailable` (không log `cdp_user_id`) và trả kết quả `popular` như khách.
- `src/backend/app/application/ports/cdp_client.py` — sửa: docstring `CdpHistoryReader` ghi rõ lỗi `CdpUnavailableError` và nơi bắt nó.
- `src/backend/tests/unit/application/test_recommendation_strategy_contract.py` — thêm: mọi nhánh của `Profile.strategy` thuộc `enum_values("Strategy")`; body kiểu route cho `long_term` và `cold_start_content` qua `RecommendationResponse`.
- `src/backend/tests/unit/application/test_recommendation_cdp_fallback.py` — thêm: CDP sập → `popular`, `coldStart` true, `eventsUsed` 0, `because` rỗng, giống kết quả khách; WARNING không chứa user id; `ValueError` vẫn ném; route trả 200 và qua `assert_contract`.
- `src/backend/tests/unit/infrastructure/test_postgres_cdp_reader.py` — thêm: map lỗi (gồm `QueryCanceled`), `InsufficientPrivilege` vẫn ném, message không chứa DSN/mật khẩu kể cả khi driver in lại, giá trị timeout, `set_config` chỉ ở đường theo request, DSN truyền nguyên vẹn không kèm `options`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.4 thêm hai dòng strategy mới và ghi chú chỗ lệch nghĩa giữa spec và engine; kèm các câu transport của agent (§1.2, §3.2, §11) thuộc entry `2026-09-28-agent-goi-engine-trong-tien-trinh.md`.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §6.2 thêm hai giá trị kèm ghi chú 2026-09-28, §6.5 dòng "<3 event" trỏ tới ghi chú lệch, §9 dòng strategy và D1 ghi "bổ sung `long_term`, `cold_start_content` 2026-09-28"; kèm §1.2 và §5.1 về transport của agent (entry agent).
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: §7 thêm khối "Adapter đọc tuần 1 (`PostgresCdpReader`)" (timeout, lỗi nào thành fallback, lỗi xác thực lúc kết nối, message đã xoá DSN); kèm §1.4 và dòng §11 về tìm kiếm không gắn danh tính (entry agent).
- `docs/spec/data-collection/bao-cao-schema.md` — sửa: bảng enum Phụ lục B thêm `long_term`, `cold_start_content`; kèm §8.6 về cách agent gọi Search/Recommendation qua port (entry agent).

`src/backend/app/main.py` cũng có hai dòng thuộc entry này (`PostgresCdpReader(..., timeout_seconds=settings.cdp_timeout_seconds)` và `version="1.8.0"`), nhưng file được liệt kê ở entry `2026-09-28-agent-goi-engine-trong-tien-trinh.md` vì phần lớn thay đổi của nó thuộc đó.

## Quyết định

- Enum chỉ **thêm** giá trị, không định nghĩa lại giá trị cũ (`AGENTS.md` §3: không đổi semantics trong v1). Hai giá trị mới lấy đúng điều kiện `profile.py:47-54`. Version tăng minor vì thay đổi tương thích ngược; cả đợt chỉ tăng một lần lên 1.8.0 vì `origin/release-mvp-v1` đã dùng 1.7.0 cho thay đổi khác (commit `dbc22c1`); `main.py` phản chiếu cùng số.
- Mock `cold_start_content` theo quy tắc 4 (`coldStart: true` thì `because: []`). Id, tên, giá của sản phẩm trong hai mock lấy lại từ các mock UI sẵn có (`nt-h-01`, `nt-a-01`, `pq-g-01`...).
- `api.gen.ts` chỉ sinh lại bằng lệnh, không sửa tay (`AGENTS.md` §3).
- Fallback nằm trong engine (`RecommendForUser`), nên route công khai và tool agent cùng hưởng. Chỉ bọc `events_for_user`; đường `events=` truyền sẵn và đường khách không chạm CDP.
- Chỉ lỗi kết nối/timeout (`OperationalError`, `InterfaceError`, `OSError`) thành `CdpUnavailableError`, theo `hop-dong-tich-hop-cdp.md` §6–§7. Lỗi quyền/SQL lúc chạy câu lệnh (`ProgrammingError`) là lỗi cấu hình nên vẫn nổi lên.
- `statement_timeout = max(1, int(t*1000))` ms, vì 0 nghĩa là không giới hạn. Chỉ áp cho đọc theo request; `purchase_events` (đọc lô lúc khởi động) không bị cắt.
- Sau review cuối, `statement_timeout` chuyển từ tham số khởi động `options` sang `set_config('statement_timeout', …, true)` trong transaction. Cách cũ ghi đè `options` sẵn có trong `CDP_DATABASE_URL` (đã kiểm bằng `make_conninfo`) và bị pooler chế độ transaction từ chối, khiến mọi lượt đọc lịch sử lặng lẽ rơi về `popular`.
- Cũng sau review, message của `CdpUnavailableError` xoá DSN và mật khẩu (lấy từ `conninfo_to_dict`) trước khi cắt dòng đầu, thay vì dựa vào việc libpq không in lại chúng; test canary mật khẩu nay có ca driver in lại DSN/mật khẩu nên có thể thất bại thật.
- Lỗi xác thực lúc kết nối (sai mật khẩu, `pg_hba`) libpq báo là `OperationalError` thường, không có `sqlstate`, nên không tách được khỏi sự cố và cũng rơi về `popular`. Không lọc theo chuỗi thông điệp vì dễ vỡ. Ghi rõ trong CDP spec §7 và docstring reader: lúc khởi động lỗi này vẫn làm RecSys hỏng rõ ràng vì bảng phổ biến đọc qua cùng đường kết nối.
- `load_history` giữ nguyên, không nối lại (ngoài phạm vi). `PostgresCdpReader.purchase_events` nay ném `CdpUnavailableError` thay cho lỗi psycopg thô khi không kết nối được; `RecsysRefresher` đã bắt `Exception` chung nên hành vi khởi động không đổi (RecSys vẫn fail closed).
- WARNING ghi `reason=` là tên kiểu lỗi gốc (`type(exc.__cause__ or exc).__name__`), để log cho thấy lỗi ở tầng driver.

## Kiểm tra

- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python src/shared/contracts/tests/validate_contract.py`: PASS — 83 schemas, all local refs, 50 grounded products, 4 itinerary statuses, negative checks, 64 existing fixtures (trước thay đổi 62, thêm 2 mock); CDP clone 12 schemas, 7 fixtures, 11 negative checks.
- `cd src/frontend && npm run generate:api-types`: OK (openapi-typescript 7.13.0); bản sinh lại giống byte với bản trong working tree; `git diff --stat src/types/api.gen.ts`: 1 file, 9 insertions, 6 deletions.
- `npm run typecheck`: exit 0. `npm run lint`: 0 lỗi, 4 cảnh báo `react-hooks/exhaustive-deps` có sẵn ở file không bị chạm. `npm run test`: 20 file, 119 test passed. `npm run build`: exit 0; `next build` tự sửa `src/frontend/next-env.d.ts` và tạo `dist-api/` (gitignored), cả hai đã được khôi phục/xoá, không nằm trong thay đổi.
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -m pytest -q -p no:cacheprovider src/backend/tests src/evaluation/tests/test_golden.py`: 611 passed, 19 skipped (baseline 537 passed, 19 skipped).
- Test tập trung sau các sửa của review cuối (engine tools, CDP reader, wiring, integration, CDP fallback, architecture): 63 passed.
- Coverage (`coverage run -m pytest -q src/backend/tests`: 569 passed, 19 skipped; `coverage report --include="src/backend/app/application/*,src/backend/app/domain/*"`): tổng 95% (3060 stmts, 145 miss); `application/*` 95% (1807/99), `domain/*` 96% (1253/46), đạt DoD ≥ 80%. `application/recommendation/use_cases.py` 95% (148 stmts, 8 miss ở code cũ; nhánh fallback mới được phủ). Ngoài phạm vi DoD: `infrastructure/cdp/postgres_cdp_reader.py` 95% (38/2, hai dòng nhánh DSN hỏng trong `_redact`).
- `git diff -U1 -- src/backend/tests`: các file test sẵn có chỉ được thêm dòng, không assertion nào bị xoá.
- Chưa chạy trên Postgres thật: máy này không có Postgres local và Docker daemon không chạy, nên `set_config('statement_timeout', …, true)` mới được kiểm qua `psycopg.connect` giả. Chưa chạy tay `/recommendations` với `CDP_DATABASE_URL` trỏ vào port chết.

## Còn lại / rủi ro

- **Lệch nghĩa Strategy chờ RecSys + Web quyết** (ghi ở `hop-dong-tich-hop-search-recommendation.md` §4.4): `recent_activity` của engine cần chuyến đang mở (event cuối trong 60 ngày, `ACTIVE_TRIP_MAX_AGE_DAYS`); ngưỡng dormant 90 ngày ở spec so với 180 ngày ở engine; dòng "<3 event → popular" của backend spec §6.5; quy tắc 4 — engine có thể trả `coldStart: true` kèm `because` không rỗng vì `coldStart = n_events < 3` còn `because` lấy từ `explain()`, và mock sẵn có `getRecommendations.200-p2-recent-activity.json` cũng vi phạm quy tắc này (validate_contract không kiểm quy tắc 4).
- Contract ghi "Thêm giá trị mới phải thông báo trước": cần báo Web. Frontend không vỡ (`src/frontend/src/types/travel.ts:75` để kiểu mở `| string`), nhưng `WhyPopover.tsx` và `docs/spec/product.md` §5.3 chưa có câu chữ riêng cho `long_term`/`cold_start_content`, và `travel.ts` dùng `recent_views` thay cho `recent_activity` (lệch có sẵn).
- Reviewer cần duyệt: Web + Backend (enum, mock, `api.gen.ts`); Data & RecSys (nghĩa Strategy, `RecommendForUser`, `PostgresCdpReader`); Team Recommendation/Search (search-rec §4.4); Data/Integration (docstring port `CdpHistoryReader`, CDP spec §7).
- Một lần đọc lịch sử có thể mất khoảng connect + statement timeout (khoảng 4 giây ở mặc định 2 giây), không đúng hẳn "2 giây mỗi lời gọi" của CDP spec §7.
- Mật khẩu CDP bị đổi khi backend đang chạy: gợi ý cá nhân hoá lặng lẽ thành `popular`; dấu hiệu duy nhất là WARNING `recommend.cdp_unavailable reason=OperationalError` lặp lại.
- `events_for_user` vẫn chưa có `LIMIT 500` như `hop-dong-tich-hop-cdp.md` §6.1 yêu cầu (lỗ hổng có sẵn, ngoài phạm vi).
