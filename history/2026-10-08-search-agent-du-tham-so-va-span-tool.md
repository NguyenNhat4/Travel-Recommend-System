# Search của agent: đủ tham số, 50 khách sạn, bỏ golf mặc định, span LangSmith cho từng tool

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, docs

## Mục tiêu

Trace LangSmith project `nhat-10-7`, hội thoại `f403f203-b026-4c42-8165-82eeabdb4958` ("di hcm 3 ngay 2 dem 2 vo chong 1
dua" → "di ngay 15"): lịch đi 36,5 km, 3 vé Grand Park + 3 tour du thuyền gần trùng, không có điểm miễn phí. Phần sửa ở đây
là các lỗi không lệch PRD (Phần 1 của plan); phần lấy thêm điểm tham quan và luật một vé mỗi địa điểm chờ đề xuất
`docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md`.

## File thay đổi

- `src/backend/app/application/itinerary/engine_tools.py` — sửa: `SEARCH_ENGINE_ARGUMENTS` thành bảng map `SearchRequest` →
  kwargs engine (thêm `origin`, `priceMin/Max`, `starRatingMin`, `availableOnly`), thêm `search_engine_kwargs` chuyển
  `travelContext.guests` thành `adults/children`.
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py` — sửa: search gọi `POST /search` với cùng bộ tham số.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: `HOTEL_SEARCH_LIMIT = 50`; `_validated_args` đặt
  `travelContext.guests` cho search hotel từ `intent.party`, bỏ `travelContext` ở loại khác; `wants_golf` và bỏ search golf
  khi người dùng không nhắc.
- `src/backend/app/agents/steps/prompts.py` — sửa: `TOOL_PLAN_PROMPT` mặc định hotel + attraction, golf khi người dùng nhắc.
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa: span `tool` LangSmith cho mỗi `execute` và `list_products`,
  `trace_summary` rút gọn kết quả (id, tên, loại, giá, toạ độ).
- `src/backend/app/domain/itinerary/planning.py` — sửa: `_price_key` tính tham quan tự do là 0 đ.
- `src/backend/requirements.txt` — sửa: khai `langsmith` (đang là phụ thuộc gián tiếp của langchain-core).
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: kỳ vọng POST, golf theo luật mới; thêm
  `HotelSearchArgsTests`, `TraceSummaryTests`, `test_golf_is_searched_only_when_the_user_mentions_it`.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: lưới an toàn còn 2 search.
- `src/backend/tests/unit/agents/test_recsys_agent_integration.py` — sửa: handler giả gọi `search_post`.
- `src/backend/tests/unit/application/test_itinerary_engine_tools.py` — sửa: engine nhận đủ filter và số khách.
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — thêm: điểm tự do không xếp sau vé có giá.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: tham số search của agent (§2), §2.6 category mặc định.
- `docs/spec/agent/nghiep-vu/tim-ung-vien.md`, `docs/spec/agent/nghiep-vu/xep-lich.md` — sửa: golf, 50 khách sạn, tham quan
  tự do 0 đ.

## Quyết định

- **Đổi quyết định cũ "adapter chỉ chuyển taxonomy/destination/limit/offset"** (spec Itinerary §2, ghi lại ở
  `history/2026-10-05-search-query-plan-f3-f6.md`). Engine đã nhận số khách từ contract 1.16.0, và server đã tự đặt
  `priceMax`/`starRatingMin` cho hotel nhưng adapter vứt đi, nên engine cắt top-N trước rồi agent mới lọc. Giữ nguyên tắc
  "mọi mode nhận cùng ứng viên": adapter HTTP chuyển sang `POST /search` (route duy nhất nhận `guests`).
- **Số khách lấy từ intent, không từ LLM**, và chỉ cho hotel (loại khác không có sức chứa). LLM gửi 9 người lớn vẫn bị thay.
- **50 khách sạn** (người dùng chọn mức tối đa contract). Đo thật: compose 5 ms.
- **Golf chỉ khi người dùng nhắc**: "golf", "đánh gôn", "sân gôn" (so không dấu); "gôn" đứng riêng không tính vì trùng "gọn".
- **Span LangSmith ở lớp `agents`** (lớp này được import langsmith theo `tests/architecture/test_import_rules.py`). Span không
  có `authorization`; chỉ gửi khi `LANGSMITH_TRACING=true`.
- Không lệch PRD: đúng contract 1.16.0, spec và glossary "tham quan tự do".

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: 1885 passed, 35 skipped (trước khi thêm test mới).
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/unit/application
  src/backend/tests/architecture src/backend/tests/contract`: 1651 passed (sau khi thêm test mới).
- Test điểm tự do fail trên code cũ (`git stash` planning.py), pass trên code mới.
- Backend thật thứ hai ở cổng 8001 (inprocess, LLM thật, LangSmith bật), hội thoại `876d9071-866a-419e-8ffb-25f1330e8df2`:
  - trace có span `search_products` riêng dưới node `tool`; chỉ 2 search (hotel, attraction), không golf;
  - search hotel mang `limit: 50`, `travelContext.guests {adults 2, children 1}`; lọc sức chứa còn 13/79 khách sạn
    (Lotte không còn trong danh sách);
  - lịch: Hoang Long Son 2 (340.955 ₫/đêm), 33,1 km (trước 36,5 km), tổng 23.001.910 ₫ (trước 43.937.000 ₫);
  - hoạt động vẫn Grand Park + du thuyền: đúng dự kiến, phần ứng viên điểm tham quan nằm ở đề xuất Phần 2.

## Còn lại / rủi ro

- Phần 2 (lấy toàn bộ điểm tham quan qua `list_products`, mỗi địa điểm một vé, tour buổi tối) chờ chốt đề xuất
  `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md`.
- Lúc thử thật, câu "dung roi, di ngay 15" sau câu hỏi "xác nhận điểm đến TP. Hồ Chí Minh?" làm mất điểm đến (hỏi lại điểm
  đến). Không thuộc phần sửa này; cần trace riêng ở bước clarify/extract.
- Chưa chạy golden eval với LLM thật cho thay đổi golf mặc định; golden case nào kỳ vọng golf khi người dùng không nhắc sẽ
  đổi kết quả.
- Prompt hub `vota-itinerary-tool-plan` trên LangSmith cũ hơn `prompts.py` (đã ghi từ entry 2026-10-06).
