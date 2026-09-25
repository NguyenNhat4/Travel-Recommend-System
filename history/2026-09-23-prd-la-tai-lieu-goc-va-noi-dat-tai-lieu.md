# PRD là tài liệu gốc; quy tắc nơi đặt tài liệu prd/spec/plan

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt: dự án chỉ theo PRD. Sửa hoặc thêm gì thì cập nhật PRD; spec ghi vào `docs/spec/`, plan ghi vào `docs/plan/`, không ghi tài liệu ra thư mục khác. Người dùng đã tự xoá `src/ARCHITECTURE.md`, `src/shared/README.md`, `src/shared/contracts/README.md`, `src/shared/contracts/MVP.md` và bỏ các file này khỏi `AGENTS.md` §1.1. Việc còn lại là đưa quy tắc thành văn bản và gỡ các tham chiếu còn trỏ tới file đã xoá.

## File thay đổi

- `AGENTS.md` — sửa: người dùng bỏ `src/ARCHITECTURE.md`, `MVP.md`, `contract-baseline`, README workstream khỏi §1.1. Agent: thêm câu "PRD là tài liệu gốc" ở đầu file; thêm §7 "Nơi đặt tài liệu" (prd/spec/plan); gỡ `src/shared/README.md` và `src/shared/contracts/README.md` khỏi bảng §1.2; thêm dòng `docs/plan/` và dòng cấu trúc repo trỏ `docs/prd/architecture.md` vào bảng §1.2; bỏ `MVP.md` và `src/ARCHITECTURE.md` khỏi thứ tự ưu tiên §2, thêm `docs/prd/architecture.md` và `data-model.md`; đổi §3 và §4 sang tham chiếu `docs/prd/architecture.md`; §4 bắt buộc cập nhật PRD khi thay đổi làm lệch kiến trúc.
- `src/ARCHITECTURE.md`, `src/shared/README.md`, `src/shared/contracts/README.md`, `src/shared/contracts/MVP.md` — xóa (người dùng xoá; entry này ghi nhận).
- `docs/prd/architecture.md` — sửa: §2 vẽ lại cây backend theo repo thật (`domain/<domain>`, `application/<domain>`, `infrastructure/persistence|clients|auth|llm`, `api/v1/routes`, `core`) và thêm quy tắc phụ thuộc từ `src/ARCHITECTURE.md` §5; siết quy tắc 3 (`vota_app` chỉ SELECT `cdp.products`). §3 thêm nhánh `NO_RESULTS` và re-rank tuỳ chọn; thay `content`/`structured_data` (không có trong contract) bằng `ItineraryResponse` theo `status`; thêm quy tắc tổng tiền, fallback, TTL hội thoại. Thêm §6: cấu trúc monorepo, quy tắc frontend, quy ước thêm module, review chéo (lấy từ `src/ARCHITECTURE.md` §4, §6, §11, §12).
- `docs/prd/README.md` — sửa: thêm nguyên tắc 3 về PRD là tài liệu gốc và nơi đặt tài liệu.
- `src/backend/README.md` — sửa: tiêu đề mục "Chỗ nào làm gì" trỏ sang `docs/prd/architecture.md` §2.

## Quyết định

- Nội dung chỉ có trong `src/ARCHITECTURE.md` được đưa sang `docs/prd/architecture.md` để quy tắc dependency, frontend và module mới vẫn có nguồn sau khi file bị xoá.
- Không chép chỉ tiêu hiệu năng (300 ms / 5 s) từ `src/ARCHITECTURE.md` §10. PRD `requirements.md` (NFR-PERF) là nguồn duy nhất.
- Không chép `catalog.product_vectors`: bảng này đã gỡ (`db/migrations/0002_drop_product_vectors.sql`).
- Không khôi phục nội dung `MVP.md` (bộ trường tối thiểu 1.2.0). Required/optional đã nằm trong OpenAPI, là nguồn ưu tiên cao nhất.

## Kiểm tra

- `grep -n "ARCHITECTURE\|MVP.md\|shared/README\|contracts/README" AGENTS.md`: không còn kết quả.
- Không chạy `validate_contract.py`: không đổi contract hay mock.

## Còn lại / rủi ro

- Còn link hỏng tới `src/shared/contracts/MVP.md` trong `docs/spec/contract-baseline-v1.1.md`, `docs/spec/hop-dong-tich-hop-backend.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/mvp-v01.md`. Còn tham chiếu `src/ARCHITECTURE.md` trong `docs/spec/thiet-ke-schema-3-service.md`. Chưa sửa, chờ người dùng quyết định.
- Tài liệu nằm ngoài `docs/` vẫn còn: `src/data_collection/docs/` (`SCHEMA.md`, `bao-cao-schema.md`), `mvp/bao-cao-mvp.md`. Theo `AGENTS.md` §7, các file này chỉ được chuyển vào đúng thư mục khi cần sửa.
- PRD vẫn lệch contract ở `api-contract.md` (đã ghi ở `AGENTS.md` §2) và lệch bộ persona (`AGENTS.md` §6.4).
- Bị thay thế bởi: 2026-09-23-chuyen-tai-lieu-vao-docs-spec.md (phần xoá file và không khôi phục MVP.md)
