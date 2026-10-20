# Cấu hình agent giống môi trường local hiện tại

Phục vụ FR-AGT-01/06/07, AC-AGT-06/09, NFR-REL-01. Cấu hình đọc từ Settings và `.env` local ngày 13/10/2026;
không sao chép API key hoặc chuỗi kết nối. Không thay mặc định PRD hay `.env.example`.
Backend local chưa được xác minh qua `/api/v1/assistant/status` trong lần kiểm này; đây là cấu hình trên đĩa,
không phải kết quả kiểm model thật. Hành vi còn phụ thuộc catalog, hội thoại và model.

## Backend

Đặt trong `.env` ở gốc repo, hoặc env của dịch vụ backend khi triển khai. API key dùng khoá riêng của nhóm.

```dotenv
ITINERARY_USE_LLM=true
OPENAI_API_KEY=<khoa-cua-nhom>

ITINERARY_LLM_MODEL=gpt-6-luna
ITINERARY_LLM_REASONING_EFFORT=none
ITINERARY_LLM_TEMPERATURE=1.0

ITINERARY_ORCHESTRATOR_PROVIDER=openai
ITINERARY_ORCHESTRATOR_MODEL=gpt-6-luna
ITINERARY_ORCHESTRATOR_REASONING_EFFORT=low

ITINERARY_DATA_MODE=inprocess
ITINERARY_TOOL_TIMEOUT_SECONDS=20
ITINERARY_LLM_TIMEOUT_SECONDS=30
ITINERARY_REQUEST_TIMEOUT_SECONDS=90
ITINERARY_CONVERSATION_TTL_SECONDS=86400
```

- Model chung phục vụ trích thông tin, tool plan, lời diễn giải; orchestrator có cấu hình riêng.
- Khi chạy backend trực tiếp, để trống `GEMINI_API_KEY` để model chung chọn OpenAI: factory ưu tiên Gemini trước
  OpenAI. `ITINERARY_ORCHESTRATOR_PROVIDER=openai` chỉ quyết định provider của orchestrator.
- `.env.example` hiện chọn orchestrator `gpt-6.1-sol`; block trên dùng `gpt-6-luna` theo `.env` local đã đọc.
- Không cần cờ `ITINERARY_ORCHESTRATOR=on`: cờ này đã gỡ, orchestrator là luồng duy nhất.
- LangSmith là tuỳ chọn quan sát, không quyết định graph. Không cần khoá chẩn đoán stream của Phần B chưa chốt.

## Nguồn dữ liệu và hội thoại

`inprocess` cần Search/Recommendation/Catalog thật đã sẵn sàng: cấu hình `DATABASE_URL`, `CDP_DATABASE_URL`,
`WEAVIATE_URL`, `VECTOR_COLLECTION` đúng môi trường của teammate. Collection hiện dùng e5-small
(`ProductE5Small`, 384 chiều), phải có vector khớp catalog. Dùng cùng snapshot catalog/ngày nạp nếu cần so kết quả;
`fixture` chỉ là bộ mẫu, không tương đương local này.

Local hiện không cấu hình `ITINERARY_REDIS_URL`, nên working memory ở trong process. Dev có thể dùng cùng cách;
staging/production phải đặt Redis riêng cho hội thoại theo PRD (thường DB `/2`), không chép mật khẩu từ máy khác.
Đổi env phải khởi động lại backend vì client LLM được dựng lúc startup.

Kiểm tra `GET /api/v1/assistant/status`: `status=ready`, `dataMode=inprocess`, `llmMode=live`.
Endpoint này không xác nhận tên model đang chạy; cần đối chiếu env của process/container và log khởi động.
Mở hội thoại mới để kiểm yêu cầu nhiều điểm đến → 10 chỗ khác → mở rộng phạm vi; không dùng thẻ từ hội thoại cũ
để suy ra code mới chưa hoạt động. Tiến trình dùng endpoint SSE có sẵn, không cần một cờ frontend mới.

## Frontend

Chạy trực tiếp: `src/frontend/.env.local`:

```dotenv
BACKEND_BASE_URL=http://127.0.0.1:8000
```

Chạy Docker Compose: web đã trỏ tới `http://backend:8000`. Giữ cấu hình auth/Redis/BFF hiện có và dùng đúng
commit backend + frontend của PR #196; không chỉ đổi env trên bản release chưa chứa code mới.

## Docker Compose

Các biến trong block backend được Compose truyền vào container. Task này bổ sung passthrough
`ITINERARY_USE_LLM` và `ITINERARY_LLM_TEMPERATURE`, trước đó chỉ đặt hai biến ở `.env` chưa đưa chúng vào backend.
Sau sửa, Compose vẫn giữ mặc định `true`/`0` khi không nêu; block local ở trên sẽ truyền `true`/`1.0`.
Compose mặc định `fixture` và tool timeout 1 giây nếu thiếu env; phải đặt `inprocess`/20 để khớp block trên.

Staging nhận env từ hệ thống triển khai/secret của nhóm, không tự đọc `.env` trên máy developer.
Chỉ giao cho teammate tên biến và giá trị không bí mật; API key, DSN và Redis password đi qua nơi giữ secret của nhóm.

## CI của PR

Cấu hình model không sửa được cassette đã ghi bằng prompt cũ. Kiểm backend local sau merge đã báo 2 lỗi
ở `test_behavior_snapshot`: prompt hiện tại không có trong cassette. Cần ghi lại bằng
`src.backend.tests.unit.agents.behavior_snapshot.record` với model/tool thật, đọc diff và chạy replay offline theo
plan D6/G4. Không đổi key hash của đáp án cũ, xoá test hay skip để che thay đổi.
Phải đọc log CI của đúng commit để biết còn lỗi nào khác; hướng dẫn env không phải bằng chứng PR đã xanh.
