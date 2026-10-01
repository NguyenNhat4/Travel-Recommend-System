# Soạn note gửi mentor về ba điểm lệch handbook

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/recsys-harness
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Lịch 10 ngày, Day 1 phần C: note một trang gửi mentor về các điểm lệch handbook, xin xác nhận bằng văn bản trước Day 5. Đây là điều kiện tiên quyết còn mở của checklist bench (`search-eval-checklist.md`, mục trước ngày 1).

## File thay đổi

- `docs/spec/bench/note-mentor-lech-handbook.md` — thêm: bối cảnh, bảng ba điểm lệch (backend, vector store, embedding) kèm lý do và chỗ chốt trong PRD, rủi ro (độ trễ Cohere so với NFR-PERF-01 250 ms, arm E so e5-base trước 02/10, quota Cohere, Weaviate Sandbox), hai điều đề nghị mentor xác nhận.
- `docs/spec/bench/search-eval-checklist.md` — sửa: chú thích ở dòng "Mentor xác nhận…" trỏ tới note; chưa tick.

## Quyết định

- Nêu đủ ba điểm so với **bản handbook gốc** (`e33bdb6^`: Java 21 + Spring Boot, pgvector, ONNX trong JVM), vì bản trong repo đã được nhóm sửa ngày 16/09 (`e33bdb6`) và mentor có thể đang cầm bản gốc. Ghi rõ điều này trong note.
- Đặt note cạnh checklist trong `docs/spec/bench/` (`AGENTS.md` §7), có dòng "Phục vụ" FR-SRC-02, NFR-PERF-01/03.
- Nếu mentor đòi quay về embedding cục bộ hoặc pgvector thì đó là lệch PRD (FR-SRC-02 pin Cohere + Weaviate) → đề xuất `docs/prd/update/` theo `AGENTS.md` §8; note nói rõ hạn 02/10.

## Kiểm tra

- `grep -n "Phục vụ\|e33bdb6" docs/spec/bench/note-mentor-lech-handbook.md`: có.
- Đối chiếu dòng stack của handbook trước/sau `e33bdb6` bằng `git show e33bdb6^:docs/spec/recsys-internship-handbook-v3-vi.md`.

## Còn lại / rủi ro

- Người dùng gửi note cho mentor (ngoài repo). Khi mentor trả lời: tick checklist và tạo entry history mới ghi ngày xác nhận.
- Bản handbook trong repo còn ghi SQLAlchemy + Alembic cho truy cập dữ liệu, trong khi repo dùng psycopg và DDL viết tay (`AGENTS.md` §6.5). Không đưa vào note vì bản gốc không có dòng này; nếu mentor dùng bản trong repo thì cần nói thêm.
