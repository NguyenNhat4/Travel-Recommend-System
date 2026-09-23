# Thêm working context tiết kiệm token cho Itinerary Agent

- Ngày: 2026-09-22
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Tạo một điểm vào context ngắn để lần sau người hoặc coding agent có thể hỗ trợ sửa, tune và đánh giá
Itinerary Agent mà không phải đọc toàn bộ tài liệu và source. Giải thích rõ đường chạy qua các module,
chọn tài liệu theo loại task và tách bằng chứng fixture/local/provider/production.

## File thay đổi

- `docs/agent/working-context.md` — thêm: context tối thiểu, bảng chọn nhánh đọc, bản đồ runtime,
  trách nhiệm module, ba vòng tune, invariant và checklist mở task.
- `docs/agent/README.md` — sửa: đặt working context làm điểm bắt đầu cho task sửa/tune/eval.
- `src/evaluation/agent/README.md` — sửa: trỏ trực tiếp tới working context trước khi mở tài liệu Evaluation.
- `history/2026-09-22-agent-working-context.md` — thêm: entry này.

## Quyết định

- Dùng progressive disclosure: bốn nguồn tối thiểu, sau đó chỉ đọc một hàng theo loại task.
- Không sao chép schema hoặc chi tiết field từ OpenAPI vào working context; chỉ dẫn tới fragment để tránh
  tài liệu nhanh lỗi thời.
- Giữ `docs/agent/README.md` là mục lục chính và `src/evaluation/agent/README.md` là con trỏ của workstream,
  đúng quyết định tổ chức tài liệu ngày 2026-09-20.
- Tách tune Agent, tune retrieval/recommendation và eval end-to-end vì mỗi lớp cần metric và bằng chứng khác nhau.
- Không thay đổi code, runtime, fixture hay contract.

## Kiểm tra

- Kiểm tra toàn bộ path source/contract được liệt kê trong working context: PASS, không có path thiếu.
- Kiểm tra ba điểm vào đều trỏ tới `working-context.md` bằng `rg`: PASS.
- `git diff --check`: PASS.
- Không chạy contract validator hoặc test backend vì thay đổi chỉ là tài liệu, không chạm contract/mock/code.

## Còn lại / rủi ro

- Working context phải được cập nhật nếu topology, đường dẫn module, data mode hoặc quy trình evaluation thay đổi.
- File giúp giảm lượng đọc nhưng không thay thế yêu cầu đọc tài liệu bắt buộc trong `AGENTS.md` khi triển khai feature.
