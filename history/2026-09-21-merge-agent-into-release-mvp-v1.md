# Gộp nhánh agent với recsys/seed trên release-mvp-v1 và chốt `priceUnit`

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, data, contract, docs

## Mục tiêu

Đưa API itinerary agent lên `release-mvp-v1` để team Web dùng. Kiểm tra cho thấy **việc merge
`feat/agent` đã xong từ trước**: `git cherry release-mvp-v1 feat/agent` cho thấy toàn bộ commit của
`feat/agent` đã có mặt (replay có sửa), và `git diff release-mvp-v1 feat/agent` chỉ còn deletion —
merge lại sẽ xoá phần frontend/contract mới hơn. Việc thật sự còn lại là hai phần:

1. Local đi trước origin 16 commit (toàn bộ agent API, **chưa push** nên Web chưa thấy) và đi sau
   origin 9 commit (recsys engine, PostgreSQL adapters, seed catalog).
2. `validate_contract.py` fail từ 2026-09-21 vì `priceUnit` — việc dang dở ghi ở
   `history/2026-09-21-resolve-contract-refs-in-enum-bounds.md` và
   `history/2026-09-21-fix-conflict-marker-common-yaml.md`, cần người dùng quyết trước khi sửa.

Người dùng chốt: merge origin vào local rồi push, suy `priceUnit` theo `taxonomy`, **giữ
`ITINERARY_DATA_MODE=fixture`**.

## File thay đổi

### Gỡ conflict merge (6 file)

- `.gitignore` — sửa: gộp hai phía (python cache + eval reports của HEAD, `.DS_Store` + `.embcache/`
  của origin). Không phía nào mâu thuẫn phía nào.
- `Makefile` — sửa: gộp hai phía, target không trùng tên (`chat*`/`test-llm` và
  `demo-db*`/`verify-db`/`backend`); giữ `SHELL`/`.SHELLFLAGS`/`.ONESHELL` của HEAD, gộp `.PHONY`.
- `src/backend/requirements.txt` — sửa: gộp, lấy ràng buộc chặt hơn ở phần trùng.
- `src/backend/app/agents/graph.py` — sửa: giữ import của HEAD, bỏ phía origin.
- `src/backend/app/agents/nodes/example_node.py` — xóa: giữ quyết định xoá của HEAD.
- `src/backend/app/main.py` — sửa: gộp hai composition root (wiring itinerary + wiring recsys/Postgres).

### `priceUnit`

- `src/data_collection/normalise.py` — thêm: `PRICE_UNIT_BY_TAXONOMY` và `price_unit()`; `priceUnit`
  vào `PRODUCT_FIELDS`; `write_outputs` chốt giá trị sau dedupe.
- `src/data_collection/sample/products-sample.jsonl` — sửa: backfill 50 bản ghi.
- `src/data_collection/sample/products-sample.csv` — sửa: sinh lại, thêm cột `priceUnit`.
- `src/data_collection/make_sample.py` — sửa: thêm `priceUnit` vào `flat_fields` của CSV.
- `src/shared/mocks/itinerary-agent/products.json` — sửa: 50 fixture, `UNKNOWN` → giá trị theo taxonomy.
- `src/shared/mocks/{assistant,booking,catalog,recommendations,search}/*.json` — sửa: 22 fixture UI,
  backfill `priceUnit` cho mọi object có hình dạng `ProductSummary` (71 object).
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: 2 test hỏng từ trước.
- `src/data_collection/docs/SCHEMA.md` — sửa: thêm dòng `priceUnit` vào bảng trường; 13 → 14 trường;
  thêm mục 3 trong "Bốn chỗ dễ hiểu sai".
- `src/data_collection/README.md` — sửa: mục "Schema đầu ra" ghi 14 trường và lý do.
- `history/2026-09-21-merge-agent-into-release-mvp-v1.md` — thêm: entry này.

Phần còn lại trong `git status` là 9 commit của origin được merge vào, không do thay đổi này sinh ra.
**Không chạm OpenAPI.**

## Quyết định

- **Không chạy `git merge feat/agent`.** Nhánh đó không còn nội dung nào mới so với `release-mvp-v1`;
  merge sẽ mang về deletion của frontend và contract. Đã báo người dùng và người dùng xác nhận hướng
  merge `origin/release-mvp-v1` thay thế.
- **`main.py` gộp chứ không chọn một phía.** Wiring itinerary (conversation store, fixture/http client,
  handler `RequestValidationError`) và wiring recsys/Postgres là hai phần độc lập, chỉ tình cờ cùng nằm
  trong `lifespan`. Giữ `try/except` của origin quanh `build_recsys` để thiếu database hoặc thiếu model
  embedding không kéo sập app — assistant chạy fixture vẫn phục vụ được (`hop-dong-tich-hop-cdp.md` §6).
- **`langgraph`/`langchain-openai` giữ `>=1,<2`, không hạ xuống `>=0.2` của origin.** Code agent dùng API
  1.x; hạ trần sẽ cho phép cài bản không chạy được.
- **`priceUnit` suy từ `taxonomy`, chốt sau dedupe.** `hotel` → `PER_NIGHT`; `flight`/`attraction`/`golf`
  → `PER_PERSON`; `combo` → `PER_PACKAGE`; `unitPrice = null` → `UNKNOWN`. Tính ở `write_outputs` chứ
  không ở `make_product` vì bước gộp OTA (`normalise.py`) ghi đè `unitPrice` sau khi bản ghi đã dựng —
  suy sớm hơn sẽ lệch với giá cuối cùng.
- **`unitPrice = null` → `UNKNOWN` chứ không theo taxonomy.** Không có giá thì không có đơn vị để nói.
  Trong sample đúng 1 sản phẩm rơi vào nhánh này: điểm công cộng `ticketed=false`.
- **Fixture mock backfill bằng chính `price_unit()`**, không gõ tay. `validate_contract.py` so từng
  trường required của fixture với nguồn (`products-sample.jsonl`), nên hai bên phải dùng cùng một hàm.
- **Mâu thuẫn tài liệu, xử lý theo AGENTS.md §2:** `MVP.md` viết "`priceUnit` thiếu là UNKNOWN, không tự
  thêm /người hoặc /đêm", trong khi `schemas/catalog.yaml:118` đã đưa `priceUnit` vào required (quyết
  định C1). OpenAPI có thứ tự ưu tiên cao hơn MVP.md nên làm theo OpenAPI. Câu của MVP.md vẫn đúng ở vế
  hiển thị: Web không được tự suy đơn vị khi nhận `UNKNOWN`. Không sửa MVP.md — cần chủ dự án quyết.
- **Giữ `ITINERARY_DATA_MODE=fixture`** theo yêu cầu người dùng. Agent vẫn chạy trên 50 sản phẩm mock,
  không dùng catalog 10.320 sản phẩm của recsys.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: **PASS** —
  70 schemas, all local refs, 50 grounded products, 4 itinerary statuses, negative checks, 50 fixtures;
  CDP clone 12 schemas, 7 fixtures, 11 negative checks. Lần pass đầu tiên kể từ 2026-09-21.
- `pytest src/backend/tests`: **116 passed, 2 skipped**. Trước merge là 106 passed + 2 failed; 2 test
  hỏng đã sửa, phần tăng còn lại là test của origin. 2 skip là integration Postgres, cần
  `RUN_POSTGRES_INTEGRATION=1`.
- `pytest data_collection/tests` (chạy từ `src/`): **53 passed, 1 skipped**.
- Chạy thật bằng `TestClient` với LLM scripted, `APP_ENV=test`:
  - `GET /api/v1/assistant/status` → `ready`, `dataMode=fixture`, 50 sản phẩm, graph 1.4.0.
  - `POST /api/v1/assistant/itineraries` → 200 `COMPLETED`, 3 ngày, sản phẩm mang `priceUnit` đúng
    (`attraction` → `PER_PERSON`).
  - `POST /api/v1/assistant/itineraries/stream` → 200, 9 event SSE đủ `run.started` → `run.completed`.
  - `RecSys disabled: No module named 'sentence_transformers'` — đúng nhánh degrade, app vẫn phục vụ.
- **Chưa chạy** `make demo-db`, chưa chạy với Postgres đã seed, chưa chạy với model LLM thật.

## Còn lại / rủi ro

- **`/api/v1/search` và `/api/v1/recommendations` của origin chưa theo OpenAPI.** Route là
  `GET /search?q=` trong khi contract chốt `POST /api/v1/search` với body `query`
  (`paths/search.yaml`), và response không có `priceUnit`. Hệ quả: (a) Web **không được** coi hai
  endpoint này là endpoint contract; (b) agent không thể chuyển sang `ITINERARY_DATA_MODE=http` trỏ vào
  chúng. Thuộc phạm vi team Search/Recommendation, không tự sửa.
- **Snapshot `src/data_collection/snapshots/2026-09-21/products.jsonl.gz` (10.320 sản phẩm) chưa có
  `priceUnit`** — nó được tạo trước thay đổi này. `make demo-db` sẽ nạp catalog thiếu field required.
  Cần team Data sinh lại snapshot bằng `normalise.py` mới, hoặc backfill lúc seed.
- `priceUnit` của `combo` là `PER_PACKAGE` cho mọi combo, kể cả combo mà nội dung tính theo người. Đây
  là suy luận theo taxonomy, không phải dữ liệu nguồn; phần "Data + Booking" trong
  `contract-baseline-v1.1.md` vẫn đang chờ chủ dự án xác nhận đơn vị giá thật.
- **Chưa push.** 16 commit local + merge commit này vẫn chỉ ở máy; Web chưa dùng được cho tới khi push.
- Các lệch giữa code và `hop-dong-tich-hop-itinerary-assistant.md` đã rà soát trước đó (VALIDATION_ERROR
  400 vs 422, `TOTAL_UNKNOWN` vs `UNKNOWN_TOTAL`, `budgetStatus` không bao giờ rời `UNKNOWN`,
  `INTERNAL_ERROR` thiếu trong bảng lỗi, `/api/v1/chat` ngoài contract) **chưa sửa** trong thay đổi này.
