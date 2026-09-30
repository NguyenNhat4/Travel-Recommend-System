# Rule mới: report chạy bench (search / embed / recommendation) lưu vào `src/evaluation/reports/`

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/m6-trip-ended
- Trạng thái: hoàn thành
- Phạm vi: docs (AGENTS.md)

## Mục tiêu

Người dùng chốt quy ước: mọi lượt chạy bench search, embed hay recommendation phải lưu report kết quả vào
`src/evaluation/reports/`. Ghi thành rule trong `AGENTS.md` để các agent/phiên sau áp dụng. Phục vụ FR-SRC-01..04,
FR-REC-01..04 (report của test-plan §2.4–2.5).

## File thay đổi

- `AGENTS.md` — sửa §7: thêm `src/evaluation/reports/` vào ngoại lệ vị trí tài liệu + rule mới: report bench lưu
  `src/evaluation/reports/eval-YYYY-MM-DD-<slug>.md`, nội dung tối thiểu (commit, run id, gold/split version, cấu hình
  arm, bảng số nguyên văn, caveat, lệnh tái sinh); phân tích tổng hợp vẫn ở `docs/spec/bench/`.
- `history/2026-10-01-rule-bench-report-vao-evaluation-reports.md` — thêm: entry này.

## Quyết định

- Rule đặt trong `AGENTS.md` (quy tắc làm việc của agent nằm ở file này theo §8), không đưa vào PRD; không lệch PRD —
  chỉ chuẩn hoá nơi lưu kết quả chạy job vốn đã có tiền lệ (`eval-2026-09-23/24-golden.md`,
  `eval-2026-10-01-search-bench-gold-v2.md`).

## Kiểm tra

- Không có code. Đối chiếu format với các report sẵn có trong `src/evaluation/reports/`.

## Còn lại / rủi ro

- `src/evaluation/README.md` vẫn chưa tồn tại (bảng §1.2 AGENTS.md đã ghi chú); khi tạo thì nhắc lại quy ước này ở phần
  cấu trúc thư mục.
