# Cố định limit của search và k của recommendations ở tầng planning

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Tăng số sản phẩm mỗi lời gọi tool của agent lên 10 và gom giá trị này về một chỗ dễ đọc, dễ sửa. Trước đó `limit` của search do LLM tự chọn (thiếu thì theo default contract là 20), `k` của recommendations luôn là 5 (default contract do `normalize_arguments` điền). Vì vậy sửa default `k` trong adapter `engine_tools.py` không có tác dụng.

## File thay đổi

- `src/backend/app/agents/steps/tool_planning.py` — sửa: thêm hằng `SEARCH_LIMIT = 10`, `RECOMMENDATION_K = 10` và hàm `_result_size` (gom luôn `limit` của Similar); `_validated_args` ép số lượng qua hàm này; lời gọi recommendations do server chèn đi qua `_validated_args` như lời gọi của planner.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: thêm test giá trị do server cố định và nằm trong `maximum` của contract; cập nhật 2 test kỳ vọng giá trị default cũ.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §2.1 ghi rõ server cố định `limit`/`k`, không lấy từ LLM.

## Quyết định

- Đặt giá trị ở tầng planning, không đặt ở adapter: mọi lời gọi đều qua `_validated_args` nên cả ba mode `inprocess`, `http` và `fixture` nhận cùng số ứng viên. Cách này giống cách Similar đang làm với `limit`.
- Adapter `engine_tools.py` giữ default `k=5`, trùng default của API, để hai mode cho cùng kết quả khi được gọi trực tiếp.
- 10 nằm trong `maximum` của contract (search ≤ 50, recommendations ≤ 20), nên không đổi contract và không lệch PRD. Spec đã dùng ví dụ `limit=10` và `k=10`.

## Kiểm tra

- `python3 -m pytest src/backend/tests/unit/agents src/backend/tests/unit/application/test_itinerary_engine_tools.py src/backend/tests/architecture`: 245 passed, 1 failed.
- Test fail là `test_itinerary_runtime.py::test_abbreviation_is_resolved_by_llm_from_catalog_names_only`. Test này cũng fail trên HEAD khi chưa có thay đổi (đã kiểm bằng `git stash`), nên không liên quan.

## Còn lại / rủi ro

- Search giảm từ 20 xuống 10 ứng viên khi planner không tự chọn `limit`. Sau truy xuất còn bước lọc (sai điểm đến, bị loại trừ), nên `NO_RESULTS` có thể tăng. Cần chạy thử vài truy vấn thật.
- Test `test_abbreviation_...` đang fail sẵn, cần người phụ trách agent xem lại.
