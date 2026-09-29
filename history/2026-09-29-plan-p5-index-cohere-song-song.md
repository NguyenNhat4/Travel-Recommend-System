# Plan P5: gọi Cohere song song khi index, có giới hạn tốc độ

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs (backend, data)

## Mục tiêu

Người yêu cầu muốn phần gọi Cohere chạy song song ("Phần gọi COhere, tôi muốn song song luôn"; key hiện là Trial, hết
thì đổi key), và yêu cầu viết plan P5 trước khi code.

## File thay đổi

- `docs/plan/2026-09-29-index-cohere-song-song.md` — thêm. Plan P5:
  - P5.1: giới hạn tốc độ dùng chung (số lượt gọi mỗi phút; 429 làm mọi luồng cùng chờ);
  - P5.2: nhúng song song trong `embed_products.run()`, chỉ luồng chính ghi Weaviate, kết quả phải giống hệt tuần tự;
  - P5.3: tài liệu, cấu hình VM, đo thật;
  - mục "Cần chốt".
- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — sửa: dòng tiến độ trỏ tới plan P5.
- `history/2026-09-29-plan-p5-index-cohere-song-song.md` — thêm: entry này.

## Quyết định

- Plan riêng vì phạm vi là `src/backend` (job index, adapter Cohere, Settings), khác plan P1–P4 (`src/data_collection`).
- Chỉ song song trong job index. Search lúc chạy API (`embed_query`) không đổi, không bị giới hạn mới.
- Không đổi port `EmbedderPort`, contract, DDL, model, `input_type` → không lệch PRD.
  - Riêng việc ghi hai biến env mới vào `docs/prd/deployment-plan.md` §2 là mục cần chốt. Đề xuất không ghi, như
    `SEARCH_CUTOFF`.
- Plan nêu rõ lợi ích thật (số đo 29/09):
  - catalog đầy đủ 3.183 search unit = 34 lô, tuần tự ≈ 1 phút, song song 4 lô ≈ 15–20 s;
  - lượt hằng ngày 1–3 lô, gần như không đổi;
  - không tiết kiệm quota.
- Mặc định đề xuất (key Trial): 4 lô cùng lúc, 90 lượt gọi mỗi phút. Là đề xuất của agent, chờ chốt.

## Kiểm tra

- Chỉ viết tài liệu; không chạy test.
- Đã đọc:
  - `src/backend/jobs/embed_products.py`, `app/infrastructure/embeddings/cohere_embedder.py`, `app/core/config.py`;
  - `fresh_catalog.index_settings` / `index_catalog`;
  - `src/backend/README.md`, `docs/prd/architecture.md` §2, `docs/prd/requirements.md` (FR-SRC-02, NFR-PERF-03),
    `docs/prd/deployment-plan.md` §2, mục lục `docs/spec/hop-dong-tich-hop-backend.md`.
- Số đo:
  - `catalog.product_meta` trên DB `vota` local: 3.183 / 11.387 là search unit; `vota_crawl`: 290 / 440;
  - log lượt `index-20260929T033719Z-57914`: 3 lô trong 6,1 s.

## Còn lại / rủi ro

- Chờ người yêu cầu duyệt plan và chốt 3 mục.
- Trước khi code P5.2 phải đọc hết `docs/spec/hop-dong-tich-hop-search-recommendation.md` (plan đã ghi).
- Chưa commit.
