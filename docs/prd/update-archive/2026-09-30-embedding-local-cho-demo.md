# Embedding local cho môi trường demo thiếu quota Cohere

- Ngày: 2026-09-30
- Người đề xuất: Đăng Khôi / Codex
- Trạng thái: từ chối
- Chốt bởi / ngày: Đăng Khôi, 2026-09-30 — chọn tiếp tục dùng Cohere với key mới và hoãn index khi hết quota; không triển khai local embedding.
- PRD bị ảnh hưởng: `docs/prd/requirements.md` FR-SRC-02, NFR-PERF-03; `docs/prd/architecture.md` §4–5; `docs/prd/data-model.md` §1; `docs/prd/deployment-plan.md` §2
- Mã FR/NFR: FR-SRC-02, NFR-PERF-01, NFR-PERF-03, NFR-REL-01

## Lý do

Lượt 29/09 đã ghi 1.321 dòng DB nhưng index Cohere trả 429. Log chưa có response body nên chưa phân biệt giới hạn tốc độ với quota tháng. Tài liệu Cohere hiện công bố Embed 2.000 inputs/phút và Trial 1.000 API calls/tháng: https://docs.cohere.com/v2/docs/rate-limits . Tăng song song/retry không tạo thêm quota tháng.

Hoãn riêng index, giữ checkpoint và giảm tốc độ là sửa vận hành phù hợp PRD, có thể làm ngay. Muốn bỏ phụ thuộc quota cần đổi mô hình được ghi đích danh trong PRD.

## Nội dung đề xuất

- `requirements.md` FR-SRC-02 hiện bắt buộc Cohere embed-multilingual-v3.0/1024 chiều → cho phép thêm provider local **intfloat/multilingual-e5-small**, 384 chiều, dành cho demo. Query và document luôn cùng provider/model/version; E5 dùng tiền tố `query: ` / `passage: `, chuẩn hóa L2. Cohere vẫn là cấu hình hiện có, không tự đổi khi API lỗi.
- `architecture.md` §4–5 hiện Cohere là embedding duy nhất → thêm adapter local cho job và truy vấn. Model tải một lần, pin revision; CPU một worker làm mặc định để kiểm tài nguyên trước. Không dùng vector local để truy vấn collection Cohere.
- `data-model.md` §1 hiện collection Product/1024 chiều → demo local dùng collection mới `ProductE5Demo`/384 chiều, giữ collection cũ. Nạp lại toàn bộ search units vào collection mới theo batch và checkpoint; không trộn hai không gian vector.
- `deployment-plan.md` §2 → thêm cấu hình provider/model/cache/collection. Chuẩn bị và kiểm riêng trước khi chuyển backend sang model mới; **không restart hoặc đổi backend VM đang chạy trong task này**. Đổi cấu hình runtime cần bước triển khai riêng theo yêu cầu người dùng.
- NFR-PERF-01 và NFR-PERF-03 giữ ngưỡng hiện có: phải đo chất lượng retrieval và p95 trên máy đích, không tuyên bố đạt khi chưa đo. Cutoff phải hiệu chỉnh với model mới, không sao chép ngưỡng Cohere.

Nguồn model: https://huggingface.co/intfloat/multilingual-e5-small (MIT, có tiếng Việt). Chưa benchmark dữ liệu dự án; chất lượng/tốc độ là điểm cần nghiệm thu.

## Thay đổi source sau khi chốt

- PRD các mục trên trước, rồi `src/backend/app/core/config.py`, adapter mới trong `src/backend/app/infrastructure/embeddings/`, composition root `src/backend/app/main.py`, `src/backend/jobs/embed_products.py`.
- `src/data_collection/fresh_catalog.py` và image/dependency cho job đọc cấu hình provider.
- Tests model identity, query/document prefix, tránh trộn collection, integration index/retrieval; hướng dẫn chuyển/hoàn tác trong `docs/guide/`.
- Không sửa sản phẩm, booking hoặc DDL Postgres. Không xóa collection Cohere.
