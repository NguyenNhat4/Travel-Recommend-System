# Đề xuất: bước phân luồng chỉ nhận lịch sử hội thoại và message mới nhất

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Trace LangSmith của node `classify` vẫn có `known_intent`, `known_constraints`, `last_assistant_message`,
`previous_selection` trong message `human` (tên sản phẩm lặp ba lần), trong khi người dùng mong chỉ có system prompt và
lịch sử hội thoại + message mới nhất. Việc này lệch `docs/prd/architecture.md` §3 (mục "Ngữ cảnh cho LLM") nên tạo đề
xuất trước (AGENTS.md §8).

## File thay đổi

- `docs/prd/update/2026-09-30-classify-chi-nhan-lich-su-va-message.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-09-30-de-xuat-classify-chi-nhan-lich-su-va-message.md` — thêm.

## Quyết định

- Chỉ bước phân luồng thu gọn; các node LLM khác giữ ngữ cảnh chung.
- Chưa sửa source: chờ người dùng chốt đề xuất.

## Kiểm tra

- Chưa có thay đổi code nên chưa chạy test.

## Còn lại / rủi ro

- Sau khi chốt: sửa `docs/prd/architecture.md`, chuyển đề xuất sang `docs/prd/update-archive/`, rồi sửa `history.py`, `classification.py`, `prompts.py`, test và spec theo mục "Thay đổi source sau khi chốt" của đề xuất.
- Đề xuất ReAct `docs/prd/update/2026-09-29-vong-react-co-chan-cho-node-tool.md` sửa cùng câu ở §3, cần ghép khi áp dụng.
- Chưa commit.
