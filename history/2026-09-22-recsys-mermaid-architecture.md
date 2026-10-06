# Mermaid architecture diagram in Recommender Architecture Lab

- Ngày: 2026-09-22
- Tác giả: người yêu cầu / Codex
- Nhánh: khoa/recsys-research
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Hiển thị sơ đồ Mermaid trong Streamlit để người đánh giá thấy luồng dữ liệu, temporal holdout, 10 phương pháp và metric/report.

## File thay đổi

- `src/evaluation/architecture_diagram.py` — thêm: Mermaid source và iframe HTML renderer, có fallback hiển thị mã nguồn.
- `src/evaluation/streamlit_app.py` — sửa: thêm expander “Kiến trúc 10 recommender”.
- `src/evaluation/README.md` — sửa: mô tả sơ đồ và yêu cầu truy cập CDN.
- `src/evaluation/tests/test_architecture_diagram.py` — thêm: kiểm tra đủ 10 method, các stage chính và nội dung iframe.
- `history/2026-09-22-recsys-mermaid-architecture.md` — thêm: entry lịch sử task.

## Quyết định

- Diagram tĩnh, chỉ chứa mô tả kiến trúc, không đưa dữ liệu người dùng vào HTML.
- Dùng `st.iframe` với Mermaid ES module từ jsDelivr; iframe có fallback source để đọc mã Mermaid khi CDN không tải được.
- Không thêm dependency Python hay thay đổi API/DDL; giữ riêng Streamlit itinerary-agent.

## Kiểm tra

- Test mới được chạy trước implementation và fail do module diagram chưa tồn tại.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/tests/test_architecture_diagram.py` — PASS, 2 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/tests` — PASS, 16 passed.
- `git diff --check` — PASS.
- AST compile cho `architecture_diagram.py` và `streamlit_app.py` — PASS.

## Còn lại / rủi ro

- Mermaid renderer cần trình duyệt truy cập jsDelivr; khi CDN không truy cập được, iframe mở phần mã Mermaid dạng text.
