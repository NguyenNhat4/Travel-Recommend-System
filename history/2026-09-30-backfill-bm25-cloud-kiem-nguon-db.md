# Backfill BM25 Weaviate Cloud: kiểm nguồn DB (chỉ đọc), phần ghi chưa chạy

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/recsys-harness
- Trạng thái: dang dở
- Phạm vi: docs
- Thay thế: `2026-09-29-cloud-backfill-lexical.md` (runbook ở đó chỉ định sai nguồn DB)

## Mục tiêu

Chạy backfill property BM25 cho collection `Product` trên Weaviate Cloud (lịch 10 ngày, Day 1 phần C) sau khi người dùng có khoá Weaviate Cloud và quyền SSH tới VM Postgres.

## File thay đổi

- `history/2026-09-30-backfill-bm25-cloud-kiem-nguon-db.md` — thêm: entry này.
- `history/2026-09-29-cloud-backfill-lexical.md` — sửa: chỉ thêm dòng "Bị thay thế bởi".
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: ghi chú của mục backfill (Day 1 C).

## Đã kiểm (chỉ đọc)

- Tunnel SSH tới VM Postgres (`127.0.0.1:15432`) mở được. Mật khẩu chỉ nằm trong biến môi trường của tiến trình, không ghi vào file nào trong repo; tunnel đã đóng sau khi kiểm.
- DB trên VM: PostgreSQL 18.6; 10.887 `cdp.products`, **3.008 search unit**, 2.139 recommendable, 328 `combo_items`, 7.131 event (event cuối 2026-09-22 → seed `as_of` 2026-09-23). Role `vota_db_dev` là superuser nên mọi truy vấn chạy ở chế độ read-only.
- Weaviate Cloud: 1.39.5, sẵn sàng; collection `Product` `vectorizer: none`, `hfresh`, cosine; **3.183 object**, đều `embed-multilingual-v3.0:catalog-text-v2`; property `nameAscii`/`searchTextAscii` đã có trong schema nhưng **0 object có dữ liệu BM25**; stopwords preset `en`.
- Dry-run chỉ đọc (cùng công thức `changed` / `orphans` / `stale_lexical` của `jobs/embed_products.run`, nhưng không gọi `ensure_collection`, không embed, không ghi):

| Nguồn DB so với 3.183 object trên cloud | Phải embed lại (Cohere) | Vector bị xoá | Object cần backfill |
|---|---:|---:|---:|
| DB trên VM (3.008 unit; 110 chưa có vector, 48 lệch text) | 158 | **285** | 2.850 |
| Postgres compose local, seed snapshot 2026-09-23, `as_of` 2026-09-24 (3.183 unit) | 0 | 0 | 3.183 |

## Quyết định

- **Runbook cũ sai nguồn DB.** Vector trên cloud được sinh từ DB snapshot (nạp 24/09 từ máy dev), không phải DB trên VM. Chạy job trên VM như runbook cũ sẽ xoá 285 vector cloud và gọi Cohere 158 lần — đúng điều kiện "dừng" mà runbook đặt ra. Nguồn đúng là DB có đủ 3.183 search unit của snapshot 2026-09-23 (Postgres compose local sau `make demo-db AS_OF=2026-09-24 SEED=42`), nơi dry-run cho embed 0, xoá 0.
- Phần ghi (đổi stopwords, PATCH 3.183 object) **chưa chạy**: công cụ quyền của phiên làm việc chặn thao tác sửa tài nguyên dùng chung. Người dùng tự chạy hoặc cấp quyền rồi yêu cầu chạy.

## Runbook đã sửa (thay mục Runbook của entry 2026-09-29)

Chạy từ gốc repo trên máy có Postgres compose local đã seed như trên; `WEAVIATE_URL`/`WEAVIATE_API_KEY` trỏ cloud (như `.env` hiện tại). **Luôn truyền `DATABASE_URL` của Postgres local bằng biến môi trường** (DSN dev ở `.env.example`), vì `.env` đang trỏ DB tunnel VM.

1. Lưu schema hiện tại: `GET /v1/schema/Product` (giữ file JSON để khôi phục).
2. Đổi stopwords: sửa `invertedIndexConfig.stopwords.preset` từ `en` thành `none` trong JSON vừa lấy, `PUT /v1/schema/Product` với toàn bộ JSON đó, rồi GET lại để xác nhận.
3. `DATABASE_URL=<Postgres local> python -m src.backend.jobs.embed_products --dry-run` → phải ra `searchUnits 3183, embedded 0, deletedOrphans 0, missingLexical 3183`. Khác thì dừng.
4. `DATABASE_URL=<Postgres local> python -m src.backend.jobs.embed_products --backfill-lexical` → `backfilledLexical 3183` (chỉ PATCH, không gọi Cohere, không xoá).
5. Chạy lại bước 3 → `missingLexical 0`.
6. Xác nhận trên backend VM: `/api/v1/search?q=VinWonders` có `diagnostics.searchMode = HYBRID_CANDIDATE_SCORE` và `lexicalCandidates > 0`.

## Kiểm tra

- Các lệnh ở mục "Đã kiểm" đều chỉ đọc; không có thao tác ghi nào lên Weaviate Cloud hay DB trên VM.

## Còn lại / rủi ro

- **Nguy hiểm với `.env` hiện tại:** `.env` trỏ `WEAVIATE_URL` vào cloud và `DATABASE_URL` vào DB tunnel VM. Chạy `make index-vectors` hoặc `python -m src.backend.jobs.embed_products` với `.env` như vậy khi tunnel mở sẽ xoá 285 vector cloud và embed lại 158.
- Backend VM đang phục vụ 3.008 unit trên vector sinh từ snapshot: 110 unit không có vector, 48 unit có vector của text cũ. Muốn cloud khớp DB VM thì cần một lần index lại có chủ đích (embed 158, xoá 285), tách khỏi việc backfill BM25.
- Mật khẩu SSH và DB đã được dán vào hội thoại; nên đổi sau khi xong.
