# Làm ấm cache gợi ý trang chủ sau đăng nhập

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: backend, tài liệu log
- Liên quan: `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` (đã chốt; mục làm ấm sau đăng nhập cho `(k=4, không destination)`), `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 3), `history/2026-10-12-recsys-cache-goi-y-redis.md`

## Mục tiêu

Đăng nhập xong, trình duyệt mở trang chủ và hỏi `/recommendations?k=4`. Tính trước đúng request đó ngay lúc đăng nhập, để lần mở trang chủ đầu tiên:

- trúng cache; hoặc
- chờ lần tính đang chạy (`wait_hit`) thay vì tính thêm một lần.

Phục vụ NFR-PERF-01; không đổi contract.

## File thay đổi

- `src/backend/app/application/recommendation/warm.py` — thêm `WarmRecommendations(engine, executor, k=4, max_pending=32)`:
  - gửi `engine(cdp_user_id, k=4, destination=None)` vào pool rồi trả ngay;
  - không bao giờ ném lỗi;
  - bỏ trùng theo người dùng; tối đa 32 việc đang chờ hoặc đang chạy;
  - bỏ qua khi engine chưa nạp hoặc cache tắt;
  - lúc chạy lấy engine đang phục vụ (`RecsysRefresher` có thể đã nạp lại);
  - log `recsys.cache.warm`: `outcome` lấy từ `cacheOutcome` của engine (`miss`, `hit`, `wait_hit`…) hoặc `duplicate`/`busy`/`no_engine`/`cache_off`/`uncached`/`failed`, kèm `duration_ms`, `error_kind`.
- `src/backend/app/application/recommendation/__init__.py` — sửa: export `WarmRecommendations`.
- `src/backend/app/main.py` — sửa: khi cache bật, lifespan dựng pool `recsys-warm` (2 thread, đóng cùng app) và gắn `app.state.warm_recommendations`. Cache tắt thì giá trị là `None`.
- `src/backend/app/api/deps.py` — sửa: thêm `get_warm_recommendations`.
- `src/backend/app/api/v1/routes/auth.py` — sửa: `login` và `create_session` gọi `_warm_home(warm, outcome)` sau khi đăng nhập thành công. Đăng nhập lỗi thì use case ném lỗi trước nên không làm ấm. Lỗi của bước làm ấm chỉ ghi WARNING, không làm hỏng đăng nhập.
- `src/backend/tests/unit/application/test_warm_recommendations.py` — thêm, 8 test:
  - gọi đúng tham số trên pool và log outcome;
  - bỏ trùng tới khi lần trước xong;
  - giới hạn số việc;
  - bỏ qua khi không có người dùng, engine hoặc cache;
  - engine lỗi thì ghi WARNING và nhả người dùng;
  - pool đã đóng không làm hỏng đăng nhập;
  - chạy engine đang phục vụ lúc chạy;
  - đầu-cuối với engine thật, cache trong bộ nhớ và `ThreadPoolExecutor`: làm ấm xong, request trang chủ `cacheOutcome = hit`.
- `src/backend/tests/fakes/auth_app.py` — sửa: `AuthWorld.warm` ghi người dùng được làm ấm và giả lập lỗi qua `warm_error`; được gắn vào `app.state.warm_recommendations`.
- `src/backend/tests/contract/test_auth_contract.py` — sửa, thêm 2 test:
  - chỉ đăng nhập thành công (`/auth/login`, `/auth/session`) mới làm ấm;
  - làm ấm lỗi thì đăng nhập vẫn 200 và đúng contract.
- `src/backend/tests/unit/api/test_recommend_settings_wiring.py` — sửa: thêm test lifespan thật. Cache tắt thì `warm_recommendations` là `None`; cache bật thì là `WarmRecommendations`.
- `src/backend/README.md` — sửa: thêm dòng làm ấm sau đăng nhập và log `recsys.cache.warm`.
- `docs/spec/logging-schema.md` — sửa:
  - liệt kê giá trị `cache` của `recsys.recommend`;
  - thêm `recsys.cache.error`, `recsys.cache.disabled` (từ entry `2026-10-12-recsys-cache-goi-y-redis.md`, lần đó chưa ghi vào tài liệu) và `recsys.cache.warm`.
- `history/2026-10-12-lam-am-cache-goi-y-sau-dang-nhap.md` — thêm: entry này.

## Quyết định

- **Pool riêng 2 thread, không dùng `BackgroundTasks` của FastAPI.** `HttpLogMiddleware` đo trọn lời gọi app, nên thời gian làm ấm sẽ bị tính vào request đăng nhập.
- **Tách khỏi pool `recsys-io`.** Engine dùng `recsys-io` bên trong; một việc trong pool chờ việc khác gửi vào chính pool đó thì khoá chết khi pool đầy.
- **Gửi việc không chép contextvars của request.** Số đo (`note`) và `request_id` của engine không lẫn vào log của request đăng nhập.
- **Chỉ làm ấm `(k=4, không destination)`,** đúng request của `HomeView.tsx` với người dùng thường. Persona demo P1–P3 gửi kèm destination nên không được làm ấm; người dùng đã chấp nhận ngày 2026-10-12.
- **Không làm ấm khi đăng ký hay xoay token.** Đề xuất chỉ chốt "sau đăng nhập". Luồng của BFF đi qua `/auth/session`.
- **Làm ấm vẫn đọc CDP và tạo khoá như request thật.** Có event mới giữa lúc làm ấm và lúc mở trang chủ thì khoá khác nhau và request tính lại. Không bao giờ trả kết quả cũ.

## Kiểm tra

- `pytest -q -p no:cacheprovider` trên `test_warm_recommendations.py`, `test_auth_contract.py`, `tests/architecture`, `test_itinerary_engine_tools.py`, `test_auth_bearer.py`: 90 passed.
- `pytest -q -p no:cacheprovider src/backend/tests/unit/api/test_recommend_settings_wiring.py`: 7 passed. Test lifespan mất 7,4 s vì chạy lifespan thật hai lần.
- `pytest -q -p no:cacheprovider src/backend/tests src/evaluation/recsys_bench/tests`:
  - lần 1: 3109 passed, 46 skipped, 1 failed. Test fail là `unit/agents/test_itinerary_runtime.py::RuntimeTests::test_catalog_hydration_is_concurrent_and_bounded`; test này kiểm số lời gọi đồng thời bằng `asyncio.sleep(0.01)` và không chạm phần thay đổi này.
  - Chạy riêng test đó: 3/3 passed. Chạy `src/backend/tests/unit/agents`: 583 passed.
  - lần 2, cùng code: **3110 passed, 46 skipped**, không có test fail. Lỗi ở lần 1 là chập chờn do thời gian, không liên quan thay đổi này.
- Kiểm thêm: luồng trong `ThreadPoolExecutor` không thấy contextvars của request (Python 3.13.14, giá trị `None`). Vì vậy số đo của lần làm ấm không lẫn vào log đăng nhập.

## Còn lại / rủi ro

- **Tài liệu spec cache:** search-recommendation, backend, CDP, auth. Làm ở bước kế tiếp.
- **Thêm tải cho Weaviate:** mỗi lần đăng nhập có thêm một lần tính nếu cache chưa có. Giới hạn 2 thread và 32 việc mỗi worker.
