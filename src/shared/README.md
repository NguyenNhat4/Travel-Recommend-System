# Shared assets

Chỉ chứa artifact trung lập công nghệ được dùng giữa các service, chủ yếu là OpenAPI contract và mock fixtures. Không đặt business logic dùng chung tại đây.

- `contracts/openapi.yaml` — nguồn sự thật cho mọi API `/api/v1`. Phần `assistant` là đề xuất, chờ Team Agent duyệt.
- `mocks/index.json` — danh mục fixture: `operationId`, `method`, `path`, `status`, `case`, `file`.
- `mocks/<domain>/<operationId>.<status>-<case>.json` — response mẫu; mọi file phải hợp lệ với schema response tương ứng trong `openapi.yaml`.

Mô tả nghiệp vụ: `docs/spec/hop-dong-tich-hop-backend.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
