# Weaviate fetch dùng REST thay GraphQL

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: backend

## Mục tiêu

Backend khởi động báo `startup.recsys.disabled ... 422 Unprocessable Entity` tại `/v1/graphql`. Gọi thẳng cluster Weaviate Cloud cho thấy `{"error":[{"message":"graphql api is disabled"}]}`. Sửa nhằm hiện thực đúng điều PRD đã ghi (nạp vector từ Weaviate, FR-REC), không lệch PRD.

## File thay đổi

- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa: bỏ `_graphql`; `WeaviateClient.fetch` liệt kê object qua `GET /v1/objects?class=...&include=vector` với phân trang con trỏ `after`.

## Quyết định

- Dùng REST vì cluster tắt GraphQL; REST trả cùng `productId`/`modelVersion`/`textHash` và vector 1024 chiều.

## Kiểm tra

- `pytest src/backend/tests/unit/infrastructure/test_weaviate_store.py`: 3 passed.
- Gọi `fetch(include_vectors=True)` vào cluster thật: trả 5 object, model `embed-multilingual-v3.0:catalog-text-v2`.

## Còn lại / rủi ro

- Collection `Product` trên cluster chỉ có 5 object trong khi catalog có 11387 sản phẩm; `WeaviateVectorStore.load` sẽ báo thiếu search unit cho tới khi chạy `make index-vectors`. Chưa chạy vì gọi Cohere và ghi lên cluster dùng chung.
