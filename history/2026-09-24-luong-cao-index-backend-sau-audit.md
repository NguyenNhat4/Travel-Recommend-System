# Luồng cào → Postgres → index Weaviate → backend: sửa theo audit 24/09

- Ngày: 2026-09-24
- Tác giả: Đăng Khôi / agent khác (bản sửa đầu, chưa commit) + Claude Code (review, sửa tiếp)
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend, data, docs, deployment

## Mục tiêu

Audit 24/09 trên commit `b7cc49c` nêu 7 vấn đề của luồng cào mới: job không tự index; đích Weaviate của compose và
job index lệch nhau; backend giữ giá cũ trong RAM; lọc lịch trình không xét ngày hết phòng; kiểm vector chỉ bằng số
lượng; giá Trip quá hạn không hết hạn khi lượt cào lỗi hoặc dòng đã gộp qua `sameAs`; Cloud chạy `hfresh` trong khi
code tạo `hnsw`. Một agent khác đã sửa một phần (working tree, chưa commit). Review bản sửa đó tìm ra lỗi mới: RecSys
tắt toàn bộ mỗi khi DB đi trước Weaviate, nạp lại toàn catalog mỗi 30 giây, bước index trên VM đọc sai biến, kiểm
loại index làm `make index-vectors` fail, compose kéo máy dev sang Cloud, luật giá theo ngày làm AC-AGT-01 mất giá,
2 test hỏng, và loader ghi đè `available_from/to` bằng khoảng ngày thô. Người dùng chốt hướng sửa (mục Quyết định).
Phục vụ FR-SRC-01/02/03, FR-REC-01, FR-CAT-03, NFR-PERF-01/03, NFR-REL-01; AC-SRC-01, AC-REC-01, AC-AGT-01.

## File thay đổi

PRD, đề xuất, spec, hướng dẫn:
- `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` → `docs/prd/update-archive/` — đổi chỗ: đề xuất hfresh
  `đã áp dụng`, chốt bởi Đăng Khôi 24/09 (agent trước chuyển file; dùng `git mv` khi commit).
- `docs/prd/requirements.md` (NFR-PERF-03), `docs/prd/architecture.md` §1/§4, `docs/prd/data-model.md` §2.1/§5,
  `docs/prd/deployment-plan.md` §2 — sửa: nội dung đúng như đề xuất hfresh đã chốt (agent trước).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.4 — sửa: metadata nạp lại theo chu kỳ, lỗi giữ bản cũ,
  kiểm vector theo id/modelVersion/textHash, chỉ từ chối khi dưới một nửa unit có vector đúng model.
- `docs/guide/doc-code-backend.md` §3 — sửa: bỏ "catalog đổi thì phải restart backend".

Backend:
- `src/backend/app/main.py` — sửa: thêm `RecsysRefresher` (nạp lại mỗi `CATALOG_REFRESH_SECONDS`, lỗi giữ bản đang
  phục vụ, chưa nạp được thì thử lại sau 30 giây, dùng chung client giữa các lần nạp); `build_recsys` không đóng client
  dùng chung khi lần nạp lại lỗi (agent trước).
- `src/backend/app/core/config.py` — sửa: thêm `weaviate_vector_index_type`, `catalog_refresh_seconds` (900); bỏ khối
  field khai báo trùng (agent trước); bỏ validator đổi `localhost` sang tên container của agent trước.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa: `normalize_weaviate_url` (URL không scheme → https),
  tạo collection theo loại index cấu hình (agent trước); collection đã có khác loại thì chỉ cảnh báo; `metadata()` đọc
  modelVersion/textHash theo id tất định; `WeaviateVectorStore.load` báo số thiếu/cũ và chỉ từ chối khi dưới 50%;
  bỏ `count()` không còn dùng.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: `connect_timeout=10` (agent trước).
- `src/backend/jobs/embed_products.py` — sửa: nhận `settings`, truyền loại index, embed lại object nằm ở uuid không tất
  định (agent trước).
- `src/backend/jobs/requirements.txt` — thêm: dependency tối giản của job index cho image crawler (agent trước).
- `src/backend/README.md` — sửa: chu kỳ nạp lại, điều kiện tắt RecSys, Weaviate trong compose.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — sửa: 2 test cũ theo chính sách mới; thêm test phục vụ
  khi thiếu/cũ vector, từ chối dưới 50%, sai model, cảnh báo loại index, tạo collection hfresh, chuẩn hoá URL.
- `src/backend/tests/unit/api/test_recsys_refresher.py` — thêm: giữ bản cũ khi lỗi, dùng chung client, thử lại sớm khi
  chưa nạp được, đóng client.
- `src/backend/tests/unit/infrastructure/test_embed_products_job.py` — thêm: dời object về uuid tất định, xoá mồ côi,
  truyền loại index.
- `src/backend/app/application/itinerary/retrieval.py`, `src/backend/app/domain/itinerary/planning.py`,
  `src/backend/app/domain/catalog/stay_dates.py` — không đổi so với `b7cc49c`: bản sửa giá/ngày của agent trước đã được
  hoàn tác và file `stay_dates.py` (chưa từng commit) đã xoá theo quyết định "không lọc theo ngày".

Data / deployment:
- `src/data_collection/fresh_catalog_db.py` — sửa: `apply_window` (quy tắc #13 và lịch 30 ngày, dùng lại `clip`/
  `pick_flight_date`/`move_flight`/`room_calendar`/`ticket_calendar`/`real_room_calendar` của seed); `maintain_catalog` =
  transaction riêng đầu mỗi lượt: hết hạn giá Trip quá 7 ngày + cuộn cửa sổ và lịch toàn catalog; `prepare_rows` ghi
  `sourceAvailableFrom/To` của lượt cào; `load_into_db` áp cửa sổ và lịch cho dòng ghi; `trip_price_reference` nhận
  alias `sameAs` khi giá thuộc Trip (agent trước).
- `src/data_collection/fresh_catalog.py` — sửa: `index_settings` ghép đích DB/Weaviate như `TARGETS` của `daily.py`, kiểm
  biến trước khi cào; mode `index`; index sau khi nạp và cả khi cào lỗi (agent trước, sửa lại đích).
- `src/data_collection/run_daily_docker.sh`, `src/data_collection/run_fresh_catalog_container.sh` — sửa: thêm mode
  `index` (agent trước).
- `Dockerfile.fresh-catalog` — sửa: cài `jobs/requirements.txt`, chép `src/backend`, `PYTHONPATH=/app:/app/src` (agent trước).
- `Dockerfile.fresh-catalog.dockerignore` — sửa: đưa `src/backend` vào context (agent trước); loại lại `.venv`,
  cache và secret sau dòng `!src/backend/**`.
- `docker-compose.yml` — sửa: backend dùng Weaviate local `http://weaviate:8080`, khoá rỗng; ghi đè bằng
  `BACKEND_WEAVIATE_URL`/`BACKEND_WEAVIATE_API_KEY`/`BACKEND_WEAVIATE_GRPC_PORT`; `CATALOG_REFRESH_SECONDS` 900.
- `.env.example` — sửa: `WEAVIATE_VECTOR_INDEX_TYPE`, `CATALOG_REFRESH_SECONDS`, quy tắc dev dùng Weaviate local.
- `src/data_collection/.env.example` — sửa: job cào mới dùng chung `CLOUD_*` cho bước index; `WEAVIATE_VECTOR_INDEX_TYPE=hfresh`.
- `src/data_collection/README.md` — sửa: bảo trì đầu lượt (hết hạn giá, cuộn cửa sổ và lịch), bước index, biến env VM,
  `run index`.
- `docs/spec/MOCK_DATA_SPEC.md` §2 bước 2 — sửa: job cào mới áp bước 1–2 mỗi lượt; ngày đã hỏi ghi theo kết quả thật,
  dòng chưa khả dụng có lịch toàn `0`.
- `src/data_collection/tests/test_fresh_catalog_job.py` — thêm: cửa sổ (cắt, trọn cửa sổ, giao rỗng, không bật lại,
  cuộn, chuyến bay/tuyến), lịch (ngày mẫu thật trên lịch mô phỏng, lịch thật khi đủ dày, dòng chưa khả dụng, vé theo
  khoảng bán, cuộn), khoảng nguồn của lượt, alias `sameAs`, `maintain_catalog`, thứ tự job, chọn biến theo đích.
- `history/2026-09-24-luong-cao-index-backend-sau-audit.md` — thêm: entry này.

## Quyết định

- Người dùng chốt đề xuất hfresh (Đăng Khôi, 24/09): Cloud `hfresh`, local `hnsw`. Theo PRD đã sửa, loại index chỉ áp
  dụng khi tạo collection: collection đã có khác loại thì job cảnh báo và chạy tiếp, không dừng.
- Làm mới backend (người dùng chọn "giữ phục vụ" + "nạp lại theo chu kỳ"): nạp đầy đủ mỗi 15 phút; lỗi giữ bản đang
  phục vụ; unit thiếu vector vẫn có giá mới nhưng chưa tìm được qua vector, vector text cũ dùng tạm; tắt RecSys chỉ khi
  dưới một nửa unit có vector đúng model. Thay quyết định fail-closed theo số lượng ở
  `history/2026-09-24-recsys-weaviate-top-k.md`. Không chọn "query chữ ký 60 giây" (đo: 306 ms phía DB, 45 byte) hay
  "crawler báo backend" (phải thêm endpoint vào OpenAPI).
- Máy dev dùng Weaviate local (`deployment-plan.md` §1): compose không lấy `WEAVIATE_URL`/khoá của máy host, nên hết lỗi
  401 ghi ở `history/2026-09-24-sua-nut-dang-ky.md`. Collection Cloud chỉ do job trên VM ghi.
- Không lọc theo ngày (người dùng chọn): backend không đọc `availabilityByDate`, lịch trình dùng `unitPrice` làm giá
  tham khảo như Booking/Agoda. PRD giữ nguyên; vấn đề 4 của audit cố ý không làm.
- Quy tắc cửa sổ #13 (`DATABASE_SCHEMA.md`, `MOCK_DATA_SPEC.md` §2 bước 1) áp cho loader mới, người dùng chọn "làm đúng
  ngay": cắt khoảng nguồn vào `[hôm nay, +29]`, thiếu thì lấy cả cửa sổ, chuyến bay theo ngày bay (dời vào cửa sổ như
  seed), tuyến theo chuyến con, giao rỗng → chưa khả dụng. Không bật lại dòng đang chưa khả dụng.
- Lịch `attributes.availability` (người dùng chọn "sinh lịch như seed", 25/09): hạng phòng, điểm tham quan, golf có lịch 30
  ngày phủ cửa sổ mỗi lượt, như `MOCK_DATA_SPEC` §2 bước 2 (lịch thật khi đủ 85% ngày đã hỏi, còn lại lịch mô phỏng).
  Thêm hai điểm: ngày Trip.com đã hỏi trong cửa sổ ghi theo kết quả thật (tránh ghi `1` cho ngày nguồn xác nhận hết
  phòng); dòng `available = false` có lịch toàn `0`. Không sửa PRD: FR-CAT-03 và `data-model.md` §3.1 đã đặt lịch ở
  `attributes.availability`; chỉ bổ sung spec.
- Bước index trên VM dùng đúng cặp đích với bước nạp: `DB_TARGET=cloud` → `CLOUD_DATABASE_URL` (thiếu thì
  `CLOUD_SEED_DATABASE_URL`) + `CLOUD_WEAVIATE_URL`/`CLOUD_WEAVIATE_API_KEY`; thiếu biến thì dừng trước khi cào.
- URL Weaviate được kiểm ở nơi dùng (adapter và bước kiểm của job), không trong `Settings`: URL sai chỉ tắt RecSys,
  không làm cả app không khởi động được.
- Không lệch PRD mới: hfresh đã chốt; giá quay về như `b7cc49c`; cửa sổ theo spec đã chốt; làm mới định kỳ chỉ sửa spec.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider src/backend/tests` (Python 3.11, venv từ vsf2):
  300 passed, 13 skipped. Working tree của agent trước: 288 passed, 2 failed.
- `cd src/data_collection && PYTHONPATH=<repo>/src python -m pytest -q tests`: 311 passed, 3 skipped.
- `validate_contract.py`: PASS (không đổi contract hay mock). `bash -n` hai script, `git diff --check`: sạch.
  `docker compose config` với `.env` đang trỏ Cloud: backend nhận `WEAVIATE_URL=http://weaviate:8080`, khoá rỗng.
- Đầu-cuối trên Postgres 16 + Weaviate 1.27 tạm (embedder giả, không gọi Cohere hay Cloud): nạp → cửa sổ cắt đúng,
  chuyến bay/tuyến đúng ngày; index 3/3; backend nạp; lượt cào mới (thêm phòng, thêm điểm tham quan, giá 900.000 →
  1.200.000) khi chưa index: RecSys vẫn phục vụ, giá mới lên ngay, `missing=1 staleText=1`; index 2 unit → hết lệch;
  hôm sau không cào: cửa sổ cuộn, phòng Trip quá hạn chưa khả dụng; lần hai không đổi gì; `run_job('index')` mã 0.
- Seed đủ snapshot 11.387 dòng vào Postgres tạm (không ghi `README.md` hay `data/`): `verify.sql` 16/16 PASS,
  `verify_insider.sql` 6/6 PASS. Sau `maintain_catalog` sang ngày mai (2.092 dòng cuộn, 1,1 giây; lần hai 0) và nạp một
  lượt cào có chuyến bay trải 35 ngày: `window = 30 days` PASS, `future purchases inside window` PASS;
  `room calendars 30 chars` FAIL (1) — phòng Trip mới chưa có lịch (trước khi thêm phần lịch).
- Sau khi thêm lịch (25/09): seed đủ snapshot với `--as-of` hôm qua → `verify.sql` 16/16 PASS; chạy như job hôm nay:
  `maintain_catalog` cuộn 8.963 dòng (3,1 giây; lần hai 0), nạp lượt cào có 2 phòng Trip (một phòng có giá, một phòng hết
  phòng ở ngày +14) và chuyến bay trải 35 ngày → lịch ghi `1`/`0` đúng ngày +14, 7.740/7.740 phòng có lịch từ hôm nay;
  `verify.sql` 16/16 PASS, `verify_insider.sql` 6/6 PASS.
- Weaviate Cloud: chỉ đọc schema (GET) trong lúc review: `hfresh`, cosine, vectorizer none.
- `docker build -f Dockerfile.fresh-catalog -t vota-fresh-catalog:review-fix .`: pass (chưa push). Trong image: không
  có `tests`, `.env`, `.venv`, `.pem`; import được `src.backend.jobs.embed_products` và `fresh_catalog`.
  `docker run --init … index` và `… daily` với đích cloud thiếu `CLOUD_WEAVIATE_URL`/`COHERE_API_KEY`: dừng sau 1 giây,
  mã 3, in tên hai biến. Chạy tay không `--init` thì `xvfb-run` làm PID 1 và treo chờ Xvfb; runner đã có `--init`.

## Còn lại / rủi ro

- Lịch mô phỏng là dữ liệu demo: ngoài các ngày đã hỏi, trạng thái từng đêm không phải của nguồn và có thể đổi khi
  cuộn (như seed). Backend hiện chưa đọc lịch; luồng nào dùng lịch để kiểm chỗ trống phải biết điều này.
- `.env` local của người dùng trỏ Weaviate Cloud (không scheme) và thiếu `WEAVIATE_VECTOR_INDEX_TYPE`. Theo quyết định,
  dev đổi sang `http://localhost:8080`, khoá rỗng, rồi `make index-vectors` vào Weaviate local (khoảng 34 lần gọi
  Cohere cho 3.183 unit). Không chạy index vào Cloud từ máy dev: job xoá vector không có trong DB của máy chạy.
- VM: thêm `COHERE_API_KEY`, `CLOUD_WEAVIATE_URL`, `CLOUD_WEAVIATE_API_KEY` vào `/etc/vota/fresh-catalog.env`, build và
  push image mới. Chưa chạy trên VM thật, chưa ghi Weaviate Cloud.
- Dòng do các bản loader mới trước đây chèn vào không có `sourceAvailableFrom/To` nên nhận cả cửa sổ 30 ngày.
- Chuyến bay ngày giả dời theo cửa sổ mỗi ngày như seed: đơn thật đặt vào chuyến ngày giả có thể lệch `future purchases
  inside window` sau khi cuộn (seed chạy lại cũng vậy).
- `/recommendations`, `/similar` vẫn trả 500 khi RecSys chưa nạp được lần nào (có từ trước).
- Mỗi lần nạp lại đọc toàn bảng (~41 MB) và dựng text 3.183 unit (~3 giây CPU trên máy dev); chưa đo trên VM 2 vCPU.
- Chưa commit.
