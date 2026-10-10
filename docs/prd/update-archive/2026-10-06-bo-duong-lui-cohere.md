# Bỏ đường lui Cohere: embedding chỉ dùng e5-small

- Ngày: 2026-10-06
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-10-06 ("bỏ Cohere, chỉ có e5 small thôi")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` FR-SRC-02; `docs/prd/architecture.md` §1 (cây thư mục), §4 (bảng công nghệ); `docs/prd/deployment-plan.md` §2 (biến môi trường), §5 (readiness)
- Mã FR/NFR: FR-SRC-02

## Lý do

Đề xuất `2026-10-05-fr-src-02-embedding-local-e5-small.md` (chốt cùng ngày) giữ Cohere `embed-multilingual-v3.0` làm đường lui bằng cấu hình (`EMBED_PROVIDER=cohere`). Người dùng quyết bỏ hẳn: một model duy nhất, không cần khoá Cohere, cấu hình và code gọn hơn (không còn bộ ba biến model / collection / cutoff phải đổi đồng bộ khi chuyển provider).

Đánh đổi: nếu e5-small có vấn đề trên VM, không quay lại Cohere bằng đổi biến môi trường được nữa; muốn quay lại phải deploy lại image cũ (collection `Product` chứa vector Cohere vẫn còn trên Weaviate tới khi chủ động xoá).

## Nội dung đề xuất

- `requirements.md` FR-SRC-02: bỏ câu "Cohere `embed-multilingual-v3.0` giữ làm đường lui bằng cấu hình."
- `architecture.md`: bảng công nghệ bỏ "Cohere … giữ làm đường lui (`EMBED_PROVIDER=cohere`)"; cây thư mục `embeddings/ # LocalE5Embedder (multilingual-e5-small)`.
- `deployment-plan.md` §2: bỏ dòng `EMBED_PROVIDER` và `COHERE_API_KEY`; `EMBED_MODEL` / `EMBED_MODEL_REVISION` / `EMBED_DIMENSION` chỉ nhận e5-small, 384; `WEAVIATE_COLLECTION` mặc định `ProductE5Small` (collection `Product` cũ không còn được đọc); `SEARCH_CUTOFF` mặc định 0,84. §5: readiness kiểm model e5 đã tải và embed thử một câu.

## Thay đổi source sau khi chốt

- Xoá `src/backend/app/infrastructure/embeddings/cohere_embedder.py` và test `tests/unit/infrastructure/test_cohere_embedder.py`.
- `core/config.py`: bỏ `embed_provider`, `cohere_*`; model và số chiều cố định (e5-small, 384).
- `infrastructure/embeddings/factory.py`, `main.py`, `jobs/embed_products.py`: chỉ e5-small; job index embed tuần tự (bỏ limiter và chạy song song vốn dành cho hạn mức Cohere), vẫn từ chối ghi vào collection chứa vector model khác.
- `src/data_collection/fresh_catalog.py`: bước index không đòi khoá Cohere.
- `.env.example`, `src/data_collection/.env.example`, `docker-compose.yml`, `Makefile`, `src/backend/README.md`, `docs/spec/hop-dong-tich-hop-search-recommendation.md`: bỏ biến/hướng dẫn Cohere của backend và job index (khoá Cohere riêng của bench `src/evaluation` giữ nguyên).
