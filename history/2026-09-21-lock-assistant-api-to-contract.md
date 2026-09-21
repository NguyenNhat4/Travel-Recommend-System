# Khóa API assistant vào contract bằng contract test, gỡ route /chat

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, contract

## Mục tiêu

Trước khi Web nối vào, phải chắc **mọi** response agent trả ra đều đúng OpenAPI. Rà soát trước đó
(`history/2026-09-21-merge-agent-into-release-mvp-v1.md`) mới đọc code, chưa chạy thật từng nhánh và
chưa có gì chặn hồi quy: `src/backend/tests/contract/` rỗng dù `src/ARCHITECTURE.md` §10 yêu cầu
tầng test này.

Điểm cần chú ý: `finalize_node` đã validate response của graph, nhưng **lỗi phát sinh tại route**
(request sai schema, tool chưa cấu hình, timeout, exception) không đi qua node đó. Chính những nhánh
ấy chưa từng được kiểm.

## File thay đổi

- `src/backend/tests/contract/test_assistant_contract.py` — thêm: 9 test đi qua biên HTTP thật.
  Kiểm 4 status 200, 10 nhánh lỗi, enum `ErrorCode`, `details` của `UNSUPPORTED_DESTINATION`,
  3 test SSE và bề mặt route.
- `src/backend/app/api/v1/routes/assistant.py` — xóa: route `POST /api/v1/chat` và import
  `ChatRequest`/`ChatResponse`.
- `src/backend/app/domain/itinerary/schemas.py` — xóa: `ChatRequest`, `ChatResponse`.
- `history/2026-09-21-lock-assistant-api-to-contract.md` — thêm: entry này.

Không chạm OpenAPI, không chạm mock, không đổi hành vi của ba endpoint trong contract.

## Quyết định

- **Kiểm cả body lẫn HTTP status.** Một mã lỗi đúng `ErrorResponse` nhưng status chưa khai báo trong
  `paths/itinerary-agent.yaml` vẫn là drift: client sinh từ OpenAPI sẽ không có nhánh xử lý. Test
  assert `str(status) in paths[...].responses` cho từng ca.
- **Gỡ `POST /api/v1/chat`.** Route này không có trong `openapi.yaml`, và `grep` toàn repo
  (`src/`, `docs/`, frontend, Streamlit, test) cho thấy **không consumer nào** gọi nó. Theo AGENTS.md
  §3, giao diện giữa các team phải lên OpenAPI trước; giữ một route ngoài contract là bề mặt không ai
  sinh được client và không ai test được. Xóa thay vì bổ sung vào contract vì không có nhu cầu thật.
- **Đọc bề mặt route qua `app.openapi()` chứ không duyệt `app.routes`.** Bản đầu của test duyệt
  `app.routes`; FastAPI ở đây gộp router con thành `_IncludedRouter` không mang `path`, nên tập
  `served` rỗng và phép so sánh **luôn đúng một cách vô nghĩa** — test pass trong khi `/chat` vẫn còn.
  Phát hiện khi thấy test xanh dù biết chắc phải đỏ. Sau khi đổi sang `app.openapi()`, test đỏ đúng
  ở `/api/v1/chat`, rồi xanh lại sau khi gỡ route.
- **Fake tự chứa trong file test, không import từ `tests/unit`.** Test contract không nên vỡ theo
  thay đổi của harness unit test; đổi lại phải chấp nhận `ScriptedLlm`/`Clients` lặp ở mức tối thiểu.
- **`ScriptedLlm` raise nếu luồng gọi model bằng schema ngoài `Extraction`/`DestinationChoice`/
  `ConversationalAnswer`**, giữ đúng lưới an toàn của
  `history/2026-09-21-deterministic-itinerary-composition.md`.

## Kiểm tra

Chạy thật qua `TestClient`, mỗi ca kiểm body theo schema và status theo `paths`:

| Nhánh | HTTP | Kết quả |
|---|---:|---|
| COMPLETED · NEEDS_CLARIFICATION · NO_RESULTS · FALLBACK | 200 | khớp `ItineraryResponse`, status đã khai báo |
| body rỗng · `intentOverride` thiếu `conversationId` · message > 1000 ký tự | 422 | `VALIDATION_ERROR` |
| yêu cầu ngoài phạm vi | 400 | `VALIDATION_ERROR` |
| số ngày ngoài 1–7 | 400 | `INVALID_TRIP_DURATION` |
| hội thoại không tồn tại | 404 | `CONVERSATION_NOT_FOUND` |
| điểm đến chưa hỗ trợ | 422 | `UNSUPPORTED_DESTINATION`, `details` đủ 3 khóa |
| model lỗi | 503 | `LLM_UNAVAILABLE` |
| search lỗi · tool chưa cấu hình | 503 | `SEARCH_UNAVAILABLE` |

- SSE: event phát ra nằm trọn trong enum `AssistantStreamEvent`, thứ tự `run.started` →
  `graph.topology` → … → `run.completed`; payload `run.completed.response` khớp `ItineraryResponse`;
  không event nào chứa khóa ngoài `{sequence, nodeId, outcome, message, durationMs}` và
  `Authorization` gửi vào không xuất hiện trong stream. Request sai schema trả 422 **trước khi** mở
  stream, không phải `run.failed` trong stream đã mở.
- `GET /assistant/status` khớp `AssistantStatus`.
- Bề mặt route tag `assistant` sau khi gỡ: đúng 3 đường dẫn của contract.
- `pytest src/backend/tests`: **125 passed, 2 skipped** (trước: 116 passed, 2 skipped; +9 test mới).
- `validate_contract.py`: **PASS**.

Kết luận: ở thời điểm này API agent **đúng contract trên mọi nhánh đã liệt kê**.

## Còn lại / rủi ro

- **Chưa phủ 500.** `INTERNAL_ERROR` và `ITINERARY_VALIDATION_FAILED` chưa có ca test vì cần ép graph
  lỗi từ bên trong; hai nhánh này vẫn chỉ được đọc code chứ chưa chạy.
- **Timeout chưa phủ** và vẫn trả `SEARCH_UNAVAILABLE` kể cả khi nghẽn ở LLM hay bước compose —
  sai ngữ nghĩa so với bảng lỗi ở `hop-dong-tich-hop-itinerary-assistant.md` §4.6. Chưa sửa vì đổi mã
  lỗi là thay đổi hành vi mà Web có thể đang dựa vào; cần chốt với người dùng.
- **401 không phát sinh tại endpoint.** Agent chỉ trả 401 khi upstream trả 401; JWT hỏng gửi vào
  endpoint không bị từ chối. Tài liệu §4.6 mô tả 401 như lỗi của chính endpoint.
- Các lệch **tài liệu ↔ code** đã ghi ở entry trước vẫn chưa sửa: `VALIDATION_ERROR` 400 vs 422 trong
  bảng §4.6, `TOTAL_UNKNOWN` vs `UNKNOWN_TOTAL`, `budgetStatus` không bao giờ rời `UNKNOWN`,
  `INTERNAL_ERROR` thiếu trong bảng lỗi. Đây là lệch ở tài liệu, không phải ở OpenAPI.
- **`/api/v1/search` và `/api/v1/recommendations` (team Search/Rec) vẫn ngoài contract**:
  `GET /search?q=` trong khi contract chốt `POST /api/v1/search` với body `query`. Test contract này
  cố ý chỉ soi route tag `assistant`, không mở rộng sang tag khác để không chặn team bạn.
