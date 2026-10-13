# Gộp release-mvp-v2 vào PR #174 (Cache-Control catalog), giải xung đột phiên bản contract

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu merge PR 174) / Claude Code (agent)
- Nhánh: Khoa15/khoa-cache-search-product
- Trạng thái: hoàn thành
- Phạm vi: src/backend, src/shared/contracts

## Lý do

PR #174 xung đột với `release-mvp-v2` ở số phiên bản contract: PR dùng `1.24.1` (bản vá thêm Cache-Control), nhánh gốc đã lên `1.26.0`.

## File thay đổi

- `src/shared/contracts/openapi.yaml`, `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py`, `src/backend/tests/contract/test_search_llm_contract.py`: giải xung đột, phiên bản `1.26.1` (bản vá trên 1.26.0, giữ ý định bản vá của PR).
- Các file khác của nhánh gốc được gộp nguyên.

## Kiểm tra

- `validate_contract.py`: xem kết quả thật ở CI của PR (máy local thiếu phụ thuộc backend).
