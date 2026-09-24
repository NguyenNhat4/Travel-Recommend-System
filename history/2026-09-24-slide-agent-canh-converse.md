# Slide agent: tách cạnh classify → converse trên sơ đồ graph

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng báo sơ đồ thiếu đường đi qua `converse`. Cạnh `classify → converse` ở slide 5 xuất phát cùng điểm với cạnh `classify → clarify` nên nhìn như một đường.

## File thay đổi

- `docs/spec/agent/presentation-slides.html` — sửa: cạnh `classify → converse` đi ra từ đỉnh node `classify`, lên thẳng rồi sang `converse`.

## Quyết định

- Chỉ đổi cách vẽ, không đổi cạnh nào; sơ đồ vẫn khớp `agents/graph.py` theo `docs/spec/agent/langgraph-nodes.md` §3.1.

## Kiểm tra

- Chụp slide 5 bằng chromium headless: cạnh `classify → converse` tách riêng, không chồng lên cạnh khác.

## Còn lại / rủi ro

- Không có.
