# Slide và kịch bản thuyết trình Itinerary Agent

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng cần bộ slide HTML và kịch bản nói để trình bày feature Itinerary Agent (FR-AGT-01…05, NFR-REL-01), lưu cùng tài liệu agent.

## File thay đổi

- `docs/spec/agent/presentation-slides.html` — thêm: 14 slide tự chứa (font Google Fonts, không thư viện), chuyển bằng phím/vuốt, co giãn theo màn hình, sáng/tối.
- `docs/spec/agent/presentation-script.md` — thêm: lời nói theo từng slide, phần demo trực tiếp, câu hỏi dễ gặp.
- `docs/spec/agent/README.md` — sửa: thêm hai file mới vào bảng mục lục.

## Quyết định

- Đặt trong `docs/spec/agent/` vì đây là thư mục tài liệu agent sẵn có (AGENTS.md mục 7 chỉ cho tài liệu nằm trong `docs/`).
- Nội dung lấy nguyên từ `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/README.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/prd/requirements.md` §1.4 và `src/evaluation/reports/eval-2026-09-24-golden.md`; không thêm hành vi mới nên không lệch PRD.
- Bản publish riêng tư cùng nội dung: https://claude.ai/artifact/PkbuBPmhSo6sSVth7rU2A8

## Kiểm tra

- Không có code hay contract thay đổi; không chạy test.
- Chưa xem trước bản render bằng trình duyệt headless (chromium bản snap không đọc được thư mục tạm).

## Còn lại / rủi ro

- Slide 11–12 và kịch bản gắn với số liệu golden commit `601f112`; chạy golden mới thì cập nhật cả hai.
