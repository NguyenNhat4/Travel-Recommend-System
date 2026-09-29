# Lưu hội thoại trợ lý: Redis 24 giờ và Postgres lâu dài

- Ngày: 2026-09-25
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-25
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4; `docs/prd/architecture.md` §1, §3, §4; `docs/prd/data-model.md` §2.2; `docs/prd/user-flow.md` §3.2, §4.2; `docs/prd/deployment-plan.md` §1, §2
- Mã FR/NFR: FR-AGT-01, FR-AGT-05

## Lý do

Hội thoại của trợ lý hiện nằm trong RAM của process backend. Việc này gây ra ba vấn đề:

- Backend khởi động lại (deploy, hoặc tự reload khi dev) là mọi cuộc chat đang dở đều mất. Trợ lý "quên" điểm đến, số ngày và số người vừa được nói.
- Khi chạy nhiều worker hoặc nhiều instance, mỗi lượt chat có thể rơi vào một process khác, nên thỉnh thoảng báo "không tìm thấy hội thoại".
- Không có lịch sử chat nào được giữ lại để phân tích và cải thiện trợ lý.

Phương án chọn: dùng Redis có sẵn làm "trí nhớ làm việc" 24 giờ của trợ lý, và ghi thêm lịch sử chat của người đã đăng nhập vào hai bảng `app.conversations`, `app.conversation_messages`. Hai bảng này đã có trong DDL nhưng chưa được dùng. Bổ sung API đọc danh sách/chi tiết hội thoại và màn hình Web để chọn, xem lại, tiếp tục hội thoại đã lưu.

Phương án thay thế đã cân nhắc là lưu bằng checkpointer Postgres của LangGraph (`update-archive/2026-09-25-luu-hoi-thoai-bang-langgraph-checkpointer.md`). Người dùng không chọn phương án đó.

## Quyết định cần chốt

| Câu hỏi | Chọn |
|---|---|
| Lưu lâu dài chat của khách chưa đăng nhập? | Không. Khách chỉ có trí nhớ 24 giờ trong Redis. |
| Giữ lịch sử trong Postgres bao lâu? | Không giới hạn. Không có job xoá. |
| Có màn hình xem lại chat cũ? | Có. User đăng nhập xem danh sách, chọn một hội thoại để tải transcript và tiếp tục. |

## Nội dung đề xuất

**`docs/prd/architecture.md` §1, sơ đồ tổng thể**

- Hiện tại: `Redis[(Redis 7\nsession, rate limit)]`
- Thay bằng: `Redis[(Redis 7\nsession, rate limit,\nhội thoại trợ lý 24h)]`, thêm cạnh từ Backend tới Redis cho hội thoại.

**`docs/prd/architecture.md` §3, tiêu chuẩn grounding**

- Hiện tại: "**Hội thoại** lưu intent đã chuẩn hóa (TTL mục tiêu 24 giờ); giá và tình trạng còn chỗ luôn được tải lại, không dùng bản lưu trong hội thoại."
- Thay bằng: "**Hội thoại** có hai tầng lưu:
  - Trí nhớ làm việc trong Redis, TTL 24 giờ, gắn với người dùng đã xác thực. Gồm intent đã chuẩn hóa, ràng buộc, lịch sử chat gần nhất và các sản phẩm vừa hiển thị.
  - Với người dùng đã đăng nhập, mỗi lượt được ghi thêm vào `app.conversations` và `app.conversation_messages`, giữ không giới hạn thời gian. Ghi lỗi không làm hỏng lượt chat.

  Giá và tình trạng còn chỗ luôn được tải lại, không dùng bản lưu trong hội thoại."

**`docs/prd/architecture.md` §4, bảng công nghệ, dòng Redis**

- Hiện tại: "**Session store & rate limit** | **Redis 7** … Giữ phiên web, bộ đếm rate limit/lockout, khoá refresh. Mất dữ liệu thì người dùng chỉ phải đăng nhập lại…"
- Thay bằng: thêm vào cuối cột mô tả: "Giữ trí nhớ 24 giờ của trợ lý ở một DB index riêng; mất dữ liệu thì trợ lý bắt đầu lại ngữ cảnh, lịch sử của người đã đăng nhập vẫn còn trong Postgres."

**`docs/prd/deployment-plan.md` §1, dòng Session store**

- Thêm: "Hội thoại trợ lý dùng cùng Redis, DB index riêng."

**`docs/prd/deployment-plan.md` §2, bảng biến môi trường**

- Thêm dòng: `ITINERARY_REDIS_URL` | Redis cho trí nhớ hội thoại của trợ lý (DB index riêng, ví dụ `/2`) | Tất cả | Có mật khẩu; để trống ở dev/test thì dùng bộ nhớ của process; bắt buộc ở production.

**`docs/prd/user-flow.md` §3.2 và §4.2**

- Người dùng đăng nhập thấy danh sách hội thoại của chính mình ở màn hình `/assistant`.
- Chọn một hội thoại tải lại transcript đã lưu và đặt nó làm hội thoại đang hoạt động; có thể tiếp tục gửi tin nhắn.
- Khách chưa đăng nhập không thấy lịch sử lâu dài.

**API v1**

- `GET /api/v1/assistant/conversations?page=&pageSize=`: danh sách hội thoại của user hiện tại, mới nhất trước.
- `GET /api/v1/assistant/conversations/{conversationId}`: transcript và response có cấu trúc của một hội thoại thuộc user hiện tại.
- Cả hai endpoint bắt buộc Bearer hợp lệ; truy cập hội thoại của user khác trả `404 CONVERSATION_NOT_FOUND`.

## Ảnh hưởng và rủi ro

- **Dữ liệu cá nhân:** nội dung chat của người đã đăng nhập được giữ vô thời hạn và tích luỹ dần.
- **Redis mất dữ liệu:** Redis hiện tắt lưu xuống đĩa, nên Redis khởi động lại vẫn mất trí nhớ 24 giờ, dù việc này hiếm hơn backend khởi động lại nhiều. Lịch sử trong Postgres không bị ảnh hưởng.
- **Bộ nhớ Redis dùng chung với đăng nhập:** giới hạn 256MB, `noeviction`. Mỗi hội thoại khoảng ≤ 30KB, vì lịch sử đã giới hạn 8.000 ký tự. Nếu đầy thì cả hội thoại lẫn đăng nhập đều lỗi ghi, nên cần theo dõi.
- **Id hội thoại đổi sang UUID** (PK của `app.conversations` là `uuid`). Contract chỉ yêu cầu chuỗi nên không đổi. Id cũ trong trình duyệt sẽ được Web tự thay bằng hội thoại mới.

## Thay đổi source sau khi chốt

- `src/backend/app/infrastructure/persistence/conversation_store.py`: thêm `RedisConversationStore`.
- `src/backend/app/application/ports/itinerary_tools.py`: thêm `ConversationArchivePort`.
- `src/backend/app/infrastructure/persistence/postgres_conversation_archive.py`: thêm adapter ghi `app.conversations`, `app.conversation_messages` qua `DATABASE_URL`.
- `src/shared/contracts/paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml`: thêm API danh sách/chi tiết lịch sử có phân trang.
- `src/frontend/src/services/assistantHistory.ts`, provider/state và UI `/assistant`: tải danh sách, chọn và tiếp tục hội thoại.
- `src/backend/app/core/config.py`, `src/backend/app/main.py`, `docker-compose.yml`: biến `ITINERARY_REDIS_URL` và nối adapter.
- `src/backend/app/agents/nodes.py`, `graph.py`, `runtime_dependencies.py`: id UUID; `finalize` ghi lịch sử cho người đã đăng nhập.
- Test unit và integration (Redis thật, Postgres thật) cho hai adapter.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §6, `docs/spec/DATABASE_SCHEMA.md`, `docs/spec/agent/langgraph-nodes.md`, `src/backend/README.md`, slide và kịch bản agent.
