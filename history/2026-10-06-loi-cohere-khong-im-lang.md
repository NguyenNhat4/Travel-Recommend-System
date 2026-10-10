# Lỗi Cohere không còn im lặng

- Ngày: 2026-10-06
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent

## Mục tiêu

Trợ lý trả "Chưa thể lấy dữ liệu sản phẩm" mà cả nhóm không biết vì sao. Nguyên nhân thật: key Cohere Trial hết hạn
mức 1.000 lượt/tháng, mọi lời gọi `/v2/embed` trả 429 trong < 1 s. `CohereEmbedder` coi mọi 429/5xx là giới hạn theo
phút, thử lại 6 lần với `time.sleep` ~62 s và **không ghi log**; agent cắt ở `ITINERARY_TOOL_TIMEOUT_SECONDS` nên trace
chỉ thấy `TOOL_TIMEOUT`, còn `GET /api/v1/search` treo > 40 s. Yêu cầu: lỗi phải hiện ra, nhanh, có tên.
Phục vụ NFR-PERF-02 và đường lỗi của FR-SRC/FR-AGT; giới hạn bởi NFR-SEC-01. `/search` đã khai báo 503
`SEARCH_UNAVAILABLE` trong contract (`paths/search.yaml`) nên không đổi contract, không lệch PRD.

## File thay đổi

- `src/backend/app/application/ports/embedder.py` — sửa: thêm `EmbeddingUnavailableError(reason, status, retryable)`.
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — sửa: phân loại lỗi (`quota_exhausted`, `rate_limited`, `upstream_5xx`, `timeout`, `http_error`), log WARNING mỗi response lỗi + ERROR khi bỏ cuộc, hết hạn mức thì dừng ngay, tham số `max_wait_seconds` giới hạn tổng thời gian chờ backoff.
- `src/backend/app/core/config.py` — sửa: `cohere_query_max_wait_seconds` (mặc định 2.0).
- `src/backend/app/main.py` — sửa: embedder lúc chạy API nhận ngân sách chờ; prewarm lỗi embedding ghi `reason=`, hết hạn mức ghi ERROR `search.embed.unavailable`.
- `src/backend/app/application/itinerary/engine_tools.py` — sửa: `EmbeddingUnavailableError` → `ToolError("SEARCH_UNAVAILABLE", 503, reason="embed:<lý do>")`.
- `src/backend/app/application/ports/itinerary_tools.py` — sửa: `ToolError` nhận `reason`; `as_dict()` chỉ thêm khoá khi có.
- `src/backend/app/domain/itinerary/types.py` — sửa: `ToolErrorPayload.reason: NotRequired[str]`.
- `src/backend/app/api/errors.py` — sửa: handler `EmbeddingUnavailableError` → 503 `SEARCH_UNAVAILABLE`, `details.reason`.
- `src/backend/tests/unit/infrastructure/test_cohere_embedder.py` — sửa: 4 test (hết hạn mức dừng sau 1 lần gọi và không lộ key/câu truy vấn, ngân sách chờ, job index vẫn thử đủ lượt, 4xx/timeout có tên).
- `src/backend/tests/unit/application/test_itinerary_engine_tools.py` — sửa: test lý do tới trace và route `/search` trả 503.
- `.env.example` — sửa: `COHERE_QUERY_MAX_WAIT_SECONDS=2`.
- `src/backend/README.md` — sửa: mô tả ngân sách chờ và các dòng log `cohere.embed.*`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §7.3 thêm `reason: embed:<lý do>` trong `tool_results`.

## Quyết định

- `reason` là từ cố định do adapter đặt; không log hay trả key, câu truy vấn hay thông điệp của Cohere (NFR-SEC-01).
  Nhận diện hết hạn mức tháng bằng chuỗi `/ month`/`per month` trong `message` của 429; lệch thì rơi về `rate_limited`
  (vẫn có log, chỉ chờ thêm tối đa 2 s).
- Hết hạn mức thì không thử lại ở mọi nơi, kể cả job index: chờ không giúp gì và chỉ tốn lượt.
- Job index giữ `max_wait_seconds=None` (thử đủ 6 lượt như trước), chỉ embedder phục vụ request có ngân sách 2 s.
- `ToolError.reason`: entry `2026-10-06-ly-do-loi-tool` (cùng ngày) đã thêm field này nhưng thay đổi đó bị mất khỏi
  working tree trước khi commit (rebase bị huỷ). Entry này thêm lại đúng phần `ToolError`/`ToolErrorPayload` cần cho
  `embed:<lý do>`; các phần khác của thay đổi kia (lý do từ `validate()`, lý do timeout, `reason=` trong log gateway)
  **không** được thêm lại.

## Kiểm tra

- `.venv/bin/python -m pytest src/backend/tests/unit src/backend/tests/architecture -q`: 1100 passed.
- Gọi thật `CohereEmbedder(key, max_wait_seconds=2).embed_query(...)` với key trong `.env`: raise `quota_exhausted`
  sau 1,21 s, log `cohere.embed.failed status=429 reason=quota_exhausted ...` và `cohere.embed.gave_up ...` (trước đây ~62 s, không log).
- Chưa khởi động lại backend đang chạy, chưa chạy lại lượt chat trên UI.

## Còn lại / rủi ro

- Thay `COHERE_API_KEY` bằng key còn hạn mức (việc của người dùng); tạm thời có thể tắt `SEARCH_PREWARM` để đỡ tốn lượt.
- Đưa tình trạng embedding lên `/assistant/status` cần sửa contract trước — làm riêng.
- Một lỗi vĩnh viễn làm các timeout retryable cùng lượt không được thử lại (`_decision`, `steps/evaluation.py`) — bàn riêng.
