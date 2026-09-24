# Tách sơ đồ ASCII của graph thành các luồng một đường thẳng

- Ngày: 2026-09-23
- Tác giả: người dùng (yêu cầu qua chat, chọn dòng trong IDE) / Claude Sonnet 5
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng thấy sơ đồ ASCII dạng cây rẽ nhánh ở mục 3 `langgraph-nodes.md` khó đọc, muốn tách thành các luồng riêng, mỗi luồng một đường thẳng từ `START` tới `END`, không còn ký hiệu `├─`/`│`/`└─`.

## File thay đổi

- `docs/spec/agent/langgraph-nodes.md` — sửa: thay khối "Sơ đồ đầy đủ" (mục 3) từ cây rẽ nhánh thành 8 dòng luồng thẳng (mỗi dòng `START → … → END`, điều kiện ghi trong ngoặc ở cuối dòng), cộng thêm khối phụ tách 3 luồng con của nhánh `retry` theo đúng `route_after_retry` (`src/backend/app/agents/routing.py`).

## Quyết định

- Chỉ mô tả lại đúng cạnh và điều kiện đã có trong `src/backend/app/agents/routing.py` và `graph.py`, không thêm/bớt route — không phải thay đổi lệch PRD, không cần đề xuất trong `docs/prd/update/`.
- Giữ nguyên bảng "Bảy ví dụ" và sơ đồ mermaid (mục 3.1) phía dưới, chỉ thay khối text ASCII ngay trên mermaid.
- Tách riêng luồng `retry` thành khối phụ thay vì nhồi cả 3 nhánh con của nó vào một dòng, vì `route_after_retry` có 3 kết quả khác nhau (`tool` lặp lại, `compose` fallback, `dead_letter`) mà bản cây cũ gộp chung thành một nhánh mờ nghĩa.

## Kiểm tra

- Không có thay đổi contract/schema/seed nên không cần chạy `validate_contract.py` hay `db/verify.sql`.
- Đối chiếu thủ công từng dòng với `src/backend/app/agents/routing.py` hiện tại (đọc trực tiếp, không suy đoán).

## Còn lại / rủi ro

Không có.
