# Khởi tạo cấu trúc tài liệu docs chuẩn

- Ngày: 2026-09-22
- Tác giả: mihhquan / Antigravity
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs
- Bị thay thế bởi: 2026-09-22-tai-co-cau-truc-docs-toan-du-an.md

## Mục tiêu

Tái cấu trúc và khởi tạo bộ khung tài liệu kỹ thuật chuẩn trong thư mục `docs/` gồm 8 tệp tài liệu chính để định hướng phát triển, kiến trúc, kiểm thử và triển khai toàn bộ dự án.

## File thay đổi

- `docs/README.md` — thêm: mục lục và điều hướng toàn bộ hệ thống tài liệu.
- `docs/requirements.md` — thêm: đặc tả yêu cầu phần mềm (SRS), phân tích personas và luồng tính năng.
- `docs/design.md` — thêm: kiến trúc hệ thống, phân tầng Clean Architecture, LangGraph AI Agent và ranh giới tích hợp.
- `docs/database.md` — sửa: mô tả thiết kế PostgreSQL, pgvector, schemas `app`, `catalog`, `cdp` và phân quyền.
- `docs/api.md` — sửa: đặc tả API RESTful, quy chuẩn OpenAPI contract và xác thực.
- `docs/development.md` — thêm: hướng dẫn thiết lập môi trường phát triển local, Makefile và coding standards.
- `docs/testing.md` — thêm: chiến lược kiểm thử đa tầng (contract, unit, integration, DB verification).
- `docs/deployment.md` — sửa: hướng dẫn đóng gói Docker, biến môi trường và quy trình triển khai Staging/Production.

## Quyết định

- Chuẩn hóa cấu trúc thư mục `docs/` gồm đúng 8 file theo yêu cầu người dùng: `README.md`, `requirements.md`, `design.md`, `database.md`, `api.md`, `development.md`, `testing.md`, `deployment.md`.
- Nội dung mỗi tài liệu được khởi tạo dưới dạng khung (skeleton) chi tiết, bám sát kiến trúc hiện hành tại `src/ARCHITECTURE.md`, quy chuẩn `AGENTS.md` và hợp đồng `src/shared/contracts/`.
- Dọn dẹp các tệp tạm/rỗng 0-byte không thuộc cấu trúc được yêu cầu (`architecture.md`, `project-brief.md`, `user-flow.md`).

## Kiểm tra

- Đã kiểm tra danh sách file trong `docs/` bằng `list_dir`, khớp chính xác 8 tệp tin theo sơ đồ cây yêu cầu.
- `git status -s docs/` xác nhận 8 tệp tin hợp lệ.

## Còn lại / rủi ro

- Không có rủi ro kỹ thuật. Các nhóm phụ trách từng domain có thể tiếp tục bổ sung chi tiết nội dung sâu hơn vào từng file khi có cập nhật mới.
