# Lưu hội thoại trợ lý bằng checkpointer Postgres của LangGraph

- Ngày: 2026-09-25
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: từ chối
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-25 — chọn Redis + Postgres (`2026-09-25-luu-hoi-thoai-redis-va-postgres.md`)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (dòng "Hội thoại lưu intent đã chuẩn hóa…"), `docs/prd/data-model.md` §2.2 (ERD `app`), `docs/prd/deployment-plan.md` §4 (migration)
- Mã FR/NFR: FR-AGT-01, FR-AGT-05

## Lý do

Hiện backend giữ hội thoại của trợ lý trong RAM của process (`InMemoryConversationStore`), nên có hai hậu quả:

- Backend khởi động lại (deploy, hoặc `--reload` khi dev) là mọi hội thoại đang dở đều mất. Người dùng thấy trợ lý "quên" điểm đến và số ngày vừa nói.
- Khi chạy nhiều worker hoặc nhiều instance, mỗi lượt chat có thể rơi vào một process khác. Lượt đó không tìm thấy hội thoại và báo lỗi ngẫu nhiên.

Bảng `app.conversations` trong DDL chưa từng được dùng, và không có chỗ lưu `constraints` và `previous_selection` mà agent cần. Người dùng chọn dùng tính năng lưu có sẵn của LangGraph (checkpointer) thay vì tự viết adapter cho bảng đó.

## Nội dung đề xuất

**`docs/prd/architecture.md` §3**

- Hiện tại: "**Hội thoại** lưu intent đã chuẩn hóa (TTL mục tiêu 24 giờ); giá và tình trạng còn chỗ luôn được tải lại, không dùng bản lưu trong hội thoại."
- Thay bằng: "**Hội thoại** lưu bằng checkpointer Postgres của LangGraph, mỗi `conversationId` là một thread gắn với chủ đã xác thực. Chỉ lưu state cuối mỗi lượt, gồm intent, ràng buộc, lịch sử chat đã giới hạn và các sản phẩm vừa hiển thị. TTL 24 giờ, có job dọn định kỳ. Giá và tình trạng còn chỗ luôn được tải lại, không dùng bản lưu trong hội thoại."

**`docs/prd/data-model.md` §2.2**

Thêm vào ERD và bảng mô tả bốn bảng của checkpointer, nằm trong schema `app`: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`. Ghi rõ đây là cấu trúc do thư viện quy định: không sửa tay, không JOIN từ code nghiệp vụ, chỉ đọc/ghi qua checkpointer.

`app.conversations` và `app.conversation_messages` giữ nguyên, chưa dùng ở bước này.

**`docs/prd/deployment-plan.md` §4**

DDL của checkpointer được chép vào `db/` và một migration, **không** gọi `PostgresSaver.setup()` lúc chạy. Như vậy vẫn giữ quy tắc "bảng chỉ tạo từ DDL viết tay trong `db/`". Khi nâng phiên bản `langgraph-checkpoint-postgres` phải kiểm tra thư viện có đổi schema không.

## Đánh đổi cần biết khi chốt

- **Được:** ít code tự viết; đúng cách LangGraph khuyến nghị; về sau làm "tiếp tục giữa chừng" hoặc "người duyệt trước khi chạy tiếp" dễ hơn.
- **Mất:**
  - Thêm một thư viện (`langgraph-checkpoint-postgres`).
  - Thêm bốn bảng có cấu trúc do thư viện quyết định.
  - Dữ liệu lưu nặng hơn cách tự lưu, vì checkpointer lưu cả state của graph. Giảm bằng cách chỉ ghi khi kết thúc lượt (`durability="exit"`) và dọn dữ liệu cũ.
- **Phải tự làm thêm:**
  - Thư viện bản mã nguồn mở không có TTL, nên cần job xoá thread quá 24 giờ.
  - Kiểm tra quyền sở hữu vẫn do mình làm: đặt tên thread theo chủ, người khác đọc thì coi như không có.

## Thay đổi source sau khi chốt

- `requirements.txt`: thêm `langgraph-checkpoint-postgres`.
- `db/vota_schema.sql`, `db/init/01_vota.sql`, `db/migrations/0005_langgraph_checkpoints.sql`: bốn bảng checkpointer và quyền cho `vota_app`.
- `docs/spec/DATABASE_SCHEMA.md`: ERD, bảng, DDL.
- `src/backend/app/infrastructure/persistence/langgraph_checkpointer.py`: thêm kiểu `postgres` (dùng `DATABASE_URL`). Test và dev không có database vẫn dùng `memory`.
- `src/backend/app/main.py`, `src/backend/app/agents/runtime_dependencies.py`, `src/backend/app/agents/graph.py`, `src/backend/app/agents/nodes.py`: truyền checkpointer vào graph; thread id = chủ + `conversationId`; `intake` báo `CONVERSATION_NOT_FOUND` khi thread không có state; bỏ `InMemoryConversationStore` và port `ConversationStorePort`.
- `src/backend/app/core/config.py`: cấu hình kiểu checkpointer và TTL.
- Job dọn thread quá hạn, chạy trong tiến trình backend như job đối soát booking.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §6, `docs/spec/agent/state-fields.md`, `docs/spec/agent/langgraph-nodes.md`: cập nhật cách lưu.
- Test: unit cho adapter, integration với Postgres thật (lưu → khởi động lại process → nạp lại được), test chủ khác không đọc được.
