# Cache gợi ý: đọc lại sau khi giữ khoá để không tính trùng

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: hoàn thành
- Phạm vi: backend (application/recommendation)

## Mục tiêu

CI backend của PR #191 fail: `test_recommendation_cache.py::test_concurrent_requests_for_one_key_compute_once` (`assert 2 == 1`). Test này đến từ cache gợi ý của release (PR #190, `application/recommendation/cache.py`), không do thay đổi monitor của PR. Test đúng: PRD `docs/prd/architecture.md` §4 và đề xuất `2026-10-12-cache-goi-y-tren-redis.md` yêu cầu request cùng khoá không tính trùng (request sau chờ kết quả của request đầu).

## Nguyên nhân

Trong `get_or_compute`, nhánh chờ làm: `_load` (chưa có kết quả) → `try_lock`. Giữa hai bước này, người giữ khoá trước có thể `_store` và `unlock`. Khi đó follower giữ được khoá và tính lại lần thứ hai. Cùng một lỗi tồn tại ở nhánh leader lần đầu (`_load` miss rồi `try_lock`).

## File thay đổi

- `src/backend/app/application/recommendation/cache.py` — sửa: sau khi giữ khoá (cả nhánh lần đầu và nhánh chờ), đọc lại cache. Nếu đã có kết quả thì nhả khoá và trả `hit` hoặc `wait_hit`. Tách `_release` để dùng chung.
- `src/backend/tests/unit/application/test_recommendation_cache.py` — sửa: assertion của follower chấp nhận `hit` hoặc `wait_hit` (xem Quyết định).
- `history/2026-10-13-cache-goi-y-khong-tinh-trung.md` — thêm: entry này.

## Quyết định

- Sửa ở cache: test khẳng định đúng yêu cầu tính một lần (PRD §4), và cache cũ vi phạm yêu cầu đó.
- Thí nghiệm A/B (cùng kịch bản, 300 lần mỗi bản, 3 tiến trình song song): bản cũ tính trùng 33, 48, 32 lần (≈ 11%); bản mới 0 lần trên 900 lần chạy.
- Assertion `follower == wait_hit` là phụ thuộc thời gian: nếu leader đã ghi xong trước khi follower gọi `get_or_compute`, follower trả `hit`. Đây đúng và không tính trùng, nên assertion chỉ kiểm kết quả và nhãn thuộc `{hit, wait_hit}`. Phần kiểm "tính đúng một lần" (`len(computed) == 1`) giữ nguyên.
- Đọc lại chỉ tốn thêm một lệnh `GET` trên đường leader; đường trúng cache và đường lỗi không đổi.
- Lỗi Redis sau khi giữ khoá vẫn rơi vào nhánh `error` như cũ (`compute()` trực tiếp), khoá tự hết hạn theo `lock_ttl_ms`.

## Kiểm tra

- `pytest src/backend/tests/unit/application/test_recommendation_cache.py`: 14/14 pass.
- Thí nghiệm A/B như trên.
- Chạy file `test_recommendation_cache.py` 30 lần liên tiếp: kết quả xem trong phần trả lời của phiên.

## Còn lại / rủi ro

- Test concurrency vẫn dựa vào thời gian (`Event.wait(5)`). Nếu máy quá tải, test có thể chậm nhưng kết quả không đổi, vì thứ tự được khoá bằng event.
