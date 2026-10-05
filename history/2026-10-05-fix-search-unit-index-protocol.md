# Sửa import `Protocol` thiếu ở `ports/unit_index.py` (nhánh `fix/search`)

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `fix/search` (tách từ `bench_search_recomSys` @ `942f5aa`)
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Trên `bench_search_recomSys` backend không import được: `src/backend/app/application/ports/unit_index.py` khai hai lớp
`VectorStorePort`, `CdpClientPort` kế thừa `Protocol` nhưng không import `Protocol` (vào từ merge `3a11433`). `ports/__init__.py`
import module này nên mọi test backend và `src/evaluation/search_bench/app_adapter.py` đều hỏng. Phải sửa trước khi làm phần search
của Day 6 (plan `fix/search`). Phục vụ FR-SRC-01..04 (điều kiện tiên quyết).

## File thay đổi

- `src/backend/app/application/ports/unit_index.py` — sửa: thêm một dòng `from typing import Protocol`. Không xoá, không đổi gì khác
  (người dùng chốt 05/10: không sửa ngoài phạm vi).

## Quyết định

- Chỉ thêm import, giữ hai lớp nguyên trạng dù `VectorStorePort` đã có ở `ports/vector_store.py` và `CdpClientPort` chưa có nơi dùng —
  việc dọn trùng lặp để người sở hữu merge `3a11433` quyết định.

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/backend/tests/unit/domain src/backend/tests/unit/application src/backend/tests/architecture`
  → **514 passed** (trước khi sửa: `NameError: name 'Protocol' is not defined` ngay khi import).

## Còn lại / rủi ro

- `release-mvp-v2` không có hai lớp này trong `unit_index.py`; khi merge nhánh vào release, giữ bản của release.
