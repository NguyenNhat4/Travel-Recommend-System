# Tái cơ cấu bộ tài liệu docs toàn diện cho toàn dự án

- Ngày: 2026-09-22
- Tác giả: mihhquan / Antigravity
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs
- Thay thế: 2026-09-22-khoi-tao-cau-truc-docs.md

## Mục tiêu

Xây dựng bộ tài liệu kỹ thuật và đặc tả sản phẩm hoàn chỉnh trong thư mục `docs/` theo quy chuẩn 9 tài liệu quy trình sản phẩm chuẩn quốc tế, bao quát toàn bộ vòng đời và phạm vi của nền tảng V-OTA Travel Recommendation Platform (không bị giới hạn vào một phiên bản hay sprint ngắn hạn):
1. Project brief: Xác định vấn đề, mục tiêu, tầm nhìn dài hạn và phạm vi hệ thống.
2. Requirements: Mô tả yêu cầu chức năng (FR), yêu cầu phi chức năng (NFR) và tiêu chí nghiệm thu (AC) toàn hệ thống.
3. User flow: Thống nhất trải nghiệm người dùng, hành trình theo Persona, bản đồ route và wireframe trực quan.
4. Data model: Mô hình hóa dữ liệu (3 schema `cdp`, `catalog`, `app` + DB `insider`), sơ đồ ERD Mermaid, thuộc tính JSONB và vòng đời trạng thái.
5. Architecture: Kiến trúc hệ thống tổng thể, Clean Architecture Backend, kiến trúc LangGraph StateGraph cho AI Agent và quy tắc phụ thuộc.
6. API contract: Chuẩn giao tiếp RESTful, Error Envelope, 7 nhóm endpoint cốt lõi, nguyên tắc Grounding và versioning.
7. Test plan: Chiến lược kiểm thử 5 tầng (Unit, Contract, Integration/DB, AI Agent Grounding, Offline RecSys Evaluation).
8. Implementation plan: Lộ trình phát triển toàn dự án qua 6 giai đoạn, phân công theo Workstream và Definition of Done.
9. Deployment plan: Môi trường triển khai, biến môi trường, Docker Compose, di chuyển cơ sở dữ liệu (migrations), giám sát và kế hoạch rollback.

## File thay đổi

- `docs/project-brief.md` — thêm: tầm nhìn, bối cảnh, 4 personas, mục tiêu dài hạn và phạm vi toàn dự án.
- `docs/requirements.md` — thêm: yêu cầu chức năng cho 8 phân hệ, yêu cầu phi chức năng và ma trận tiêu chí nghiệm thu.
- `docs/user-flow.md` — thêm: luồng trải nghiệm, route table, sơ đồ Mermaid và ASCII wireframes các màn hình chính.
- `docs/data-model.md` — thêm: ERD Mermaid, đặc tả 3 schema trong `vota` và DB `insider`, ranh giới phân quyền và vòng đời thực thể.
- `docs/architecture.md` — thêm: sơ đồ kiến trúc tổng thể, Clean Architecture Backend, LangGraph AI Agent, Tech stack.
- `docs/api-contract.md` — thêm: chuẩn API RESTful, Error Envelope, đặc tả 7 nhóm API chính, quy tắc Grounding.
- `docs/test-plan.md` — thêm: tháp kiểm thử 5 tầng, chỉ số đánh giá RecSys & AI Grounding, kịch bản E2E.
- `docs/implementation-plan.md` — thêm: lộ trình 6 giai đoạn phát triển toàn diện, phân công workstream, Definition of Done.
- `docs/deployment-plan.md` — thêm: môi trường, biến môi trường, Docker setup, migration idempotent, health checks và rollback.
- `docs/README.md` — sửa: cổng thông tin tổng hợp, danh mục 9 tài liệu và hướng dẫn tra cứu nhanh theo vai trò.
- `history/2026-09-22-khoi-tao-cau-truc-docs.md` — sửa: thêm ghi chú bị thay thế bởi entry này.

## Quyết định

- Bộ tài liệu được viết ở góc nhìn **toàn bộ hệ thống sản phẩm du lịch thông minh V-OTA**, không gắn cứng vào các hạn chót sprint ngắn hạn hay một phiên bản demo đơn lẻ.
- Timeline và lộ trình kỹ thuật được tập trung duy nhất tại `docs/implementation-plan.md` (chia thành 6 giai đoạn kỹ thuật từ Foundation đến Multi-channel launch).
- Mọi tài liệu bám sát nguồn sự thật kỹ thuật của dự án: Clean Architecture (`src/ARCHITECTURE.md`), OpenAPI contract (`src/shared/contracts/openapi.yaml`), DDL & database isolation rules (`AGENTS.md §6`).

## Kiểm tra

- Đã kiểm tra cấu trúc thư mục `docs/`: Chứa đủ 10 tệp tin (9 tài liệu chuyên đề + 1 tệp index `README.md`).
- Các sơ đồ Mermaid trong `user-flow.md`, `data-model.md`, `architecture.md`, `implementation-plan.md` đều có cú pháp chuẩn xác.
- Không sửa đổi mã nguồn hoặc file contract OpenAPI, không ảnh hưởng đến build hiện tại.

## Còn lại / rủi ro

- Không có rủi ro kỹ thuật.
- Các nhóm phát triển có thể tham chiếu các tài liệu này làm kim chỉ nam xuyên suốt trong quá trình xây dựng tính năng.
