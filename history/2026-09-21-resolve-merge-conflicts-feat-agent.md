# Giải quyết conflict khi merge release-mvp-v1 vào feat/agent

- Ngày: 2026-09-21
- Tác giả: @NguyenNhat4 / Copilot
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, contract, docs

## Mục tiêu

Giải quyết toàn bộ marker conflict còn sót lại sau khi merge `release-mvp-v1` vào `feat/agent` để nhánh build được và không còn file ở trạng thái xung đột.

## File thay đổi

- `.env.example` — sửa: hợp nhất cấu hình local Postgres/CDP với cấu hình runtime itinerary/LLM.
- `.gitignore` — sửa: hợp nhất rule ignore của hai nhánh.
- `Makefile` — sửa: giữ cả nhóm target chat agent và target demo/verify database.
- `src/backend/app/agents/graph.py` — sửa: bỏ marker conflict, giữ implementation graph itinerary hiện hành.
- `src/backend/app/agents/nodes/example_node.py` — xóa: giữ hướng xóa từ nhánh `feat/agent` (file demo không còn được dùng).
- `src/backend/app/main.py` — sửa: hợp nhất wiring itinerary runtime với wiring recsys/Postgres trong composition root.
- `src/backend/requirements.txt` — sửa: hợp nhất dependencies backend từ hai nhánh.
- `src/shared/contracts/schemas/common.yaml` — sửa: hợp nhất mô tả `ErrorResponse.error.details`.
- `history/2026-09-21-resolve-merge-conflicts-feat-agent.md` — thêm: entry này.

## Quyết định

- Ưu tiên giữ đầy đủ hành vi của cả hai nhánh trong các file conflict thay vì chọn một phía, đặc biệt cho `main.py` (itinerary runtime + recsys wiring) và `Makefile` (chat + database targets).
- Với conflict modify/delete ở `example_node.py`, giữ hướng xóa theo nhánh `feat/agent` vì `graph.py` hiện tại không còn phụ thuộc file này.
- Với contract `common.yaml`, giữ các key chi tiết lỗi từ cả hai bên (`conversationId`, `minStay`, `taxonomy`) để tránh mất thông tin đã công bố.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → **fail** (`KeyError: 'priceUnit'`, lỗi dữ liệu/fixture nền, không phát sinh từ lần resolve conflict này).
- `python3 -m pytest src/backend/tests/unit/test_backend_wiring.py src/backend/tests/unit/test_engines.py` → **fail** (`No module named pytest`, môi trường chưa có dependency test).
- `.venv/bin/python -m pytest ...` → không chạy được (không có `.venv`).
- `python3 -m py_compile src/backend/app/main.py src/backend/app/agents/graph.py` → **pass**.
- Secret scanning trên toàn bộ file thay đổi → **pass** (không phát hiện secret).

## Còn lại / rủi ro

- Cần chạy lại test backend/contract trong môi trường đã cài đủ dependency để xác nhận toàn bộ sau merge.
- Contract validator hiện fail do dữ liệu hiện tại thiếu `priceUnit`; cần xử lý ở nhánh phù hợp nếu đây là vấn đề mới của baseline dữ liệu.
