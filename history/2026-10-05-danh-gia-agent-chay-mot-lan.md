# Đánh giá Itinerary Agent chạy 1 lần thay vì 3 lần

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Bỏ khuyến nghị chạy mỗi case `--repeat 3` (pass cả ba lần); chạy một lần là đủ.

## File thay đổi

- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — sửa: lệnh mẫu ở comment đầu file bỏ `--repeat 3`.
- `docs/spec/agent/golden-run.md`, `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa: lệnh ví dụ bỏ `--repeat 3`, "mỗi case 1 lần".
- `.agents/skills/building-itinerary-agent/references/eval-loop.md` — sửa: bước 5 và mục 4 (bỏ quy tắc pass^k, `--repeat` chỉ dùng để đo case chập chờn).
- `.agents/skills/building-itinerary-agent/references/industry-patterns.md`, `.agents/skills/building-itinerary-agent/SKILL.md` — sửa: bỏ `--repeat 3`; SKILL.md đổi `G-0NN` sang `TC-NN`.

## Quyết định

- Code runner không đổi: `--repeat` mặc định đã là 1; cờ vẫn giữ cho trường hợp đo độ ổn định.
- Cái giá: một lần chạy có thể bỏ sót lỗi chập chờn của bước LLM mà ba lần sẽ bắt được.

## Kiểm tra

- Chỉ sửa tài liệu và comment; không chạy test.

## Còn lại / rủi ro

- Không có.
