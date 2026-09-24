# Cho phép index `hfresh` khi collection `Product` nằm trên Weaviate Cloud

- Ngày: 2026-09-23
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §2.1 (NFR-PERF-03), `docs/prd/architecture.md` §4, `docs/prd/data-model.md` §2.1 (entity `WEAVIATE_PRODUCT`) và §5 mục 3
- Mã FR/NFR: NFR-PERF-03, FR-SRC-02

## Lý do

Job `embed_products` chạy lần đầu vào cluster Weaviate Cloud của nhóm (Weaviate 1.39.5) và bị từ chối khi tạo collection `Product`:

```
422 CONFIG_NOT_ALLOWED: hnsw is not allowed for vector_index_type. Allowed values: hfresh.
```

Gói cloud đang dùng chỉ cho phép index `hfresh`. PRD hiện bắt buộc HNSW, nên muốn đưa vector lên cluster này thì phải chấp nhận `hfresh`. `hfresh` cũng là index xấp xỉ (ANN), không quét tuần tự, và vẫn dùng khoảng cách cosine.

Nếu không muốn lệch PRD thì còn hai cách:

- Dùng Weaviate local trong Docker (`docker compose up -d --wait weaviate`). Cách này đúng PRD vì `deployment-plan.md` §1 ghi môi trường dev là "Weaviate local qua Docker".
- Nâng gói Weaviate Cloud lên gói cho phép HNSW.

## Nội dung đề xuất

- `requirements.md` NFR-PERF-03: "phải đi qua chỉ mục HNSW của Weaviate (cosine, mặc định của collection)" → "phải đi qua chỉ mục ANN của Weaviate, cosine: HNSW khi chạy Weaviate local hoặc self-host, `hfresh` khi gói Weaviate Cloud chỉ cho phép loại này".
- `architecture.md` §4, dòng Weaviate: "HNSW + cosine là mặc định" → "Index ANN + cosine (HNSW ở local/self-host, `hfresh` trên Weaviate Cloud nếu gói chỉ cho phép loại này)".
- `data-model.md` entity `WEAVIATE_PRODUCT`: `"1024 chiều, HNSW + cosine, vectorizer none"` → `"1024 chiều, ANN (HNSW hoặc hfresh) + cosine, vectorizer none"`. §5 mục 3: "Weaviate tự dựng HNSW (cosine)" → "Weaviate tự dựng index ANN (cosine) theo loại mà cluster cho phép".
- `deployment-plan.md` §2: thêm dòng biến `WEAVIATE_VECTOR_INDEX_TYPE` — "Loại index của collection `Product`, mặc định `hnsw`; đặt `hfresh` khi dùng Weaviate Cloud chỉ cho phép loại này. Đổi giá trị thì phải tạo lại collection".

## Thay đổi source sau khi chốt

- `src/backend/app/core/config.py`: thêm `WEAVIATE_VECTOR_INDEX_TYPE` (mặc định `hnsw`).
- `src/backend/app/infrastructure/vectors/weaviate_store.py`: tạo collection bằng loại index lấy từ cấu hình.
- `.env.example`: thêm biến `WEAVIATE_VECTOR_INDEX_TYPE`.
- Chạy `make embed-products` để nạp 2.897 search unit lên cloud.
