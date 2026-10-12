# Plan chia việc sửa lỗi chat thử 16 kiểu người dùng; bộ chạy hội thoại

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, evaluation

## Mục tiêu

Người dùng có thêm một agent coding trên laptop, muốn chia các lỗi tìm thấy trong
`src/evaluation/reports/eval-2026-10-10-chat-thu-16-kieu-nguoi-dung.md` để hai bên làm song song.

## File thay đổi

- `docs/plan/2026-10-10-chia-viec-sua-loi-chat-thu-16-kieu.md` — thêm: hai luồng L (agent local) và C (Claude Code cloud),
  luồng S (Search), bảng file thuộc mỗi luồng, quy tắc, thứ tự merge.
- `src/evaluation/agent/chat_replay.py` — thêm: chạy lại hội thoại thử với backend, ghi toàn văn ra markdown (không chấm).
- `src/evaluation/datasets/chat_messy_v1.json` — thêm: 16 hội thoại, 49 lượt của đợt chat thử 10/10.
- `history/2026-10-10-plan-chia-viec-chat-thu-16-kieu.md` — thêm: entry này.

## Quyết định

- Chia theo file để ít xung đột: luồng L giữ guardrails, extract, converse, `place_destination`; luồng C giữ fares, nodes,
  compose/narrate, phần còn lại của exploration. `messages.py` và `prompts.py` dùng chung nhưng mỗi luồng sửa khối riêng.
- Lỗi Search chưa lọc theo ngày đi tách thành luồng S, chưa giao.

## Kiểm tra

- `.venv/bin/python -m src.evaluation.agent.chat_replay --help` chạy được; dataset nạp được (16 hội thoại, 49 lượt).

## Còn lại / rủi ro

- Hai luồng chưa bắt đầu.
