# Đóng gói catalog snapshot và bootstrap database demo

- Ngày: 2026-09-21
- Tác giả: Đặng Khôi / Codex
- Nhánh: mockdata-work
- Trạng thái: hoàn thành
- Phạm vi: data, cdp, insider, docs
- Thay thế: `2026-09-21-hoan-thanh-seed-catalog.md` (chỉ quyết định không phân phối catalog trong Git)

## Mục tiêu

Để thành viên khác clone nhánh và dựng đúng database demo bằng Docker mà không cần repository crawl hay Docker volume của người tạo. Phân phối catalog ở dạng nén, có version/checksum và kèm mapping combo đã duyệt; giữ toàn bộ JSONL đã bung, output seed và volume PostgreSQL ngoài Git.

## File thay đổi

- `.gitignore` — sửa: bỏ Python bytecode/runtime artifact khỏi trạng thái Git.
- `Makefile` — thêm: `demo-db`, `demo-db-reset`, `verify-db`, `backend`; target seed cố định vào hai database Docker local.
- `README.md` — thêm: quickstart dựng database và chạy Backend cho người mới clone.
- `AGENTS.md` — sửa: cập nhật quy tắc dev local và nguồn snapshot catalog chính thức.
- `docs/MOCK_DATA_SPEC.md` — sửa: mô tả snapshot nén, bootstrap một lệnh và fallback tổng hợp mới.
- `src/data_collection/.gitignore` — sửa: phân biệt runtime catalog ignored với snapshot nén được theo dõi.
- `src/data_collection/README.md` — sửa: thêm hướng dẫn `make demo-db`, reset local và vị trí snapshot.
- `src/data_collection/seed/README.md` — sửa: mô tả thứ tự tìm catalog, kiểm checksum và mapping combo đi kèm.
- `src/data_collection/seed/config.py` — sửa: thêm snapshot 2026-09-21 vào danh sách catalog mặc định sau runtime catalog local.
- `src/data_collection/seed/__main__.py` — sửa: materialize snapshot gzip trước khi chạy pipeline hiện hành.
- `src/data_collection/seed/snapshot.py` — thêm: kiểm manifest/SHA-256/số dòng và bung atomically vào thư mục runtime ignored.
- `src/data_collection/snapshots/README.md` — thêm: quy ước version snapshot.
- `src/data_collection/snapshots/2026-09-21/manifest.json` — thêm: metadata, số dòng và checksum catalog/mapping.
- `src/data_collection/snapshots/2026-09-21/products.jsonl.gz` — thêm: catalog 10.320 dòng nén tất định, 5.391.851 byte.
- `src/data_collection/snapshots/2026-09-21/combo_items_manual.jsonl` — thêm: 64 mapping combo đã duyệt cần để tái tạo đúng 218 combo items.
- `src/data_collection/tests/test_seed_snapshot.py` — thêm: test materialize và từ chối archive sai checksum.
- `history/2026-09-21-dong-goi-catalog-snapshot.md` — thêm: entry này.

## Quyết định

- Không commit Docker volume hoặc database dump. Mỗi developer có volume local riêng; DDL + snapshot + seed tạo lại database tất định.
- Không commit JSONL thô 46.741.286 byte. Chỉ commit gzip 5.391.851 byte; catalog bung dưới `src/data_collection/data/snapshots/2026-09-21/` và tiếp tục bị ignore.
- Snapshot gồm cả catalog và mapping combo manual. Chỉ products sẽ làm mất 64 quyết định soát tay và không tái tạo cùng `catalog.combo_items`.
- `make demo-db` dành cho database mới/đang trống; database đã có dữ liệu phải dùng `make demo-db-reset` một cách chủ động.
- Hai target seed ép `SEED_DATABASE_URL`/`INSIDER_DATABASE_URL` về `localhost:5432`, tránh vô tình reset staging nếu shell của developer đang có URL khác.
- Snapshot được kiểm cả hash file gzip, hash nội dung sau giải nén, số dòng products và mapping trước khi pipeline chạy. Thay catalog thì tạo thư mục version mới, không sửa snapshot cũ.
- Snapshot không chứa profile, event, booking, vector, credential hay volume. Những phần đó được tạo từ seed/config hoặc phát sinh lúc chạy ứng dụng.

## Kiểm tra

- Gzip snapshot → **10.320 dòng**, SHA-256 nội dung `89f452e46eec24ae0fe50769037bc84dbb2609dd9c193a49336108f072acbb18`; SHA-256 gzip `c64500ea5e5c56181402e4852d55d31eb271f15fda19384651e322656afb9f6d`.
- `python -m unittest tests.test_seed_snapshot -v` → **2/2 PASS**, gồm từ chối archive sai checksum.
- Seed từ đường dẫn `.jsonl.gz` với `--generate-only` → **PASS**: 10.320 products, 2.897 search units, 218 combo items, 64 mapping manual, 2.000 profiles, 7.511 events; PostgreSQL không đổi trong lần kiểm tra này.
- Toàn bộ data test → **54/54 PASS**.
- `make demo-db-reset AS_OF=2026-09-21` trong conda `vsf` → **PASS**; Docker healthy, seed đủ V-OTA/Insider và tự gọi verify.
- `db/verify.sql` → **16/16 PASS**; `db/verify_insider.sql` → **6/6 PASS**.
- Toàn bộ Backend test sau khi bootstrap lại DB → **30/30 PASS**; còn một warning deprecation từ Starlette/AnyIO.
- `git diff --check` → sẽ chạy lại ở vòng kiểm tra cuối.
- Contract validator không chạy lại vì không thay đổi OpenAPI, response schema hoặc shared mock fixture.

## Còn lại / rủi ro

- Snapshot 5,2 MiB được lưu bằng Git thường vì nhỏ và ít thay đổi. Nếu catalog tăng lớn hoặc cập nhật thường xuyên, chuyển artifact sang GitHub Release/object storage và giữ manifest/checksum cùng bootstrap script.
- `make demo-db-reset` phá huỷ state demo local theo đúng tên lệnh; không dùng khi cần giữ cart/booking mới tạo trên máy.
- Embedding chưa thuộc snapshot: `catalog.product_vectors` vẫn bằng 0 và cần pipeline tuần 2.
- Chưa commit, chưa push theo yêu cầu.
