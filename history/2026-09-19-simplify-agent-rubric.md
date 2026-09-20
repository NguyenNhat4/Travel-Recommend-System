# Rút gọn rubric đánh giá Agent

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Rút gọn rubric Itinerary Agent để team dễ đọc và dùng khi test/demo, đồng thời cập nhật nhánh hội thoại chung đi qua LLM `answer`.

## File thay đổi

- `src/evaluation/agent/agent_rublic.md` — sửa: thay tài liệu dài bằng flow, bảng điểm và checklist ngắn gọn.

## Quyết định

- Giữ thang 100 điểm nhưng gom thành sáu nhóm dễ chấm.
- Nêu rõ lời chào/gợi ý chung dùng LLM để dẫn vào lập lịch, không gọi tool trước khi có `destination` và `days`.
- Giữ grounding 100%, giới hạn read-only, contract validation và ranh giới bằng chứng fixture/production.

## Kiểm tra

- Kiểm tra Markdown và liên kết nội bộ bằng đọc source: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Rubric là tiêu chí đánh giá, không phải kết quả nghiệm thu; cần runner và artifact thực tế để chấm điểm.
