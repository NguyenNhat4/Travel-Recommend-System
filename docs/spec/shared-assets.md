# Shared assets

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](mvp-minimal-fields-1.2.0.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

Chỉ chứa artifact trung lập công nghệ được dùng giữa các service, chủ yếu là OpenAPI contract và mock fixtures. Không đặt business logic dùng chung tại đây.

- `contracts/openapi.yaml` — nguồn sự thật cho mọi API `/api/v1`. Phần `assistant` là đề xuất, chờ Team Agent duyệt.
- `mocks/index.json` — danh mục fixture: `operationId`, `method`, `path`, `status`, `case`, `file`.
- `mocks/<domain>/<operationId>.<status>-<case>.json` — response mẫu; mọi file phải hợp lệ với schema response tương ứng trong `openapi.yaml`.

Mô tả nghiệp vụ: `docs/spec/hop-dong-tich-hop-backend.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.

- `contracts/assistant-v2.openapi.yaml` — contract assistant v2, FR-AGT-01–07, NFR-REL-01/NFR-MAINT-02.
- `mocks/assistant-v2/index.json` — fixture index riêng theo entry v2, tránh dùng cùng path với v1.
  Thẻ lấy từ sample 50 sản phẩm; số tiền/giờ fixture lập lịch minh họa phép kiểm, không là giá thật.
  Kiểm schema không chứng minh tính khả thi thời gian hoặc grounding của model; runtime/eval có cổng riêng.
