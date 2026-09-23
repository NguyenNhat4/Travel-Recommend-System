# Nối lại chuẩn hóa điểm đến ở HTTP data mode và sửa hai lỗi lộ ra trên catalog thật

- Ngày: 2026-09-23
- Tác giả: người dùng / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, evaluation

## Mục tiêu

Yêu cầu: xác nhận tool của Itinerary Agent chạy đúng trên catalog PostgreSQL thật (10.320 sản phẩm,
2.897 search unit, 35 điểm đến) thay vì fixture 50 sản phẩm.

Khảo sát trước khi chạy phát hiện một lỗ hổng chặn chính việc đó. Entry
`2026-09-22-noi-agent-voi-recsys-backend.md` đặt `ItineraryHttpClients.supports_catalog = False`
vì Backend chưa có endpoint catalog, nên `tool_node` bỏ qua cả khối chuẩn hóa điểm đến
(`nodes.py`, `match_destination` + `_choose_destination`). Hệ quả: chuỗi `destination` do LLM trích ra
đi thẳng vào `UnitIndex.mask()` (`application/ports/recsys.py`), nơi so khớp bằng `==` của numpy —
không bỏ dấu, không casefold. Người dùng gõ "da nang" trong khi catalog ghi "Đà Nẵng" thì mask toàn
`False`, search trả rỗng, agent ra `FALLBACK` **không kèm warning nào** (bước `_drop_reason` thậm chí
không chạy), nhìn giống "hết hàng" chứ không giống lỗi. Đây là loại lỗi chỉ hiện trên dữ liệu thật:
fixture 50 sản phẩm có cổng chuẩn hóa nên che mất.

## File thay đổi

- `src/backend/app/api/v1/routes/catalog.py` — thêm: route `GET /api/v1/destinations` dựng
  `DestinationListResponse` từ `app.state.index`; chưa có index thì trả danh sách rỗng.
- `src/backend/app/main.py` — sửa: import và `include_router` cho router catalog (router tự mang
  prefix `/api/v1`, mount thẳng vào app như hai router recsys).
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py` — sửa: `supports_catalog = True`
  kèm ghi chú giới hạn (`/products/{id}` vẫn chưa có route).
- `src/backend/app/agents/nodes.py` — sửa: (1) `_validated_plan` điền `query` từ điểm đến đã chuẩn hóa
  khi planner bỏ quên trường bắt buộc này; (2) bỏ phép kiểm lệch `destination` giữa plan và intent,
  giữ nguyên dòng ghi đè; bỏ import `normalized` không còn dùng.
- `src/backend/tests/unit/test_catalog_destinations.py` — thêm: 5 test cho route mới (khớp contract,
  tổng `productCount` bằng số unit, phủ đủ điểm đến của index, `match_destination` chuẩn hóa được
  biến thể dấu/hoa, rỗng khi recsys chưa sẵn sàng).
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — thêm: 2 test hồi quy cho hai sửa đổi ở
  `nodes.py`.
- `src/evaluation/tests/check_real_data_grounding.py` — thêm: script kiểm grounding trên Postgres thật;
  6 case gồm biến thể không dấu, viết tắt và một điểm đến không hỗ trợ; exit code khác 0 khi có FAIL.
- `history/2026-09-23-noi-lai-chuan-hoa-diem-den-o-http-mode.md` — thêm: entry này.

Không chạm contract, không chạm mock, không chạm `db/`.

## Quyết định

- **Không đổi OpenAPI.** `GET /destinations` và `DestinationListResponse` đã có sẵn trong
  `paths/catalog.yaml:95` và `schemas/catalog.yaml:368`; `schemas/catalog.yaml:129-131` còn ghi thẳng
  "Nhãn du lịch đã chuẩn hóa... Lấy danh sách hiện hành qua GET /api/v1/destinations". Việc thiếu chỉ là
  Backend chưa hiện thực route. Làm đúng contract có sẵn thay vì thêm quy ước mới (AGENTS.md §2).
- **Bật `supports_catalog = True` thay vì thêm cờ hẹp hơn.** Cờ này cũng hàm ý có `get_product_detail`,
  mà `/products/{id}` chưa có route. Chấp nhận được vì chính entry 2026-09-22 đã xác định Search và
  Recommendation trả đủ `DETAIL_FIELDS` (`description`, `attributes`, `availableFrom`, `availableTo`)
  nên `hydrate()` không bao giờ gọi tới. Không thêm route `/products/{id}` chỉ để cờ "đúng nghĩa" —
  đó là endpoint không ai dùng. Rủi ro ghi ở mục cuối.
- **`productCount` đếm trên index (search unit), không đếm `cdp.products`.** Danh sách này để agent
  chuẩn hóa tên và để người đọc biết quy mô; đếm cái mà search thực sự trả được thì trung thực hơn.
  Tổng 2.897 khớp `startup.recsys.ready search_units=2897`.
- **Chỉ `destination` cần cơ chế này; các trường bắt buộc khác đã có nguồn hợp lệ.** Soi lại toàn bộ
  tham số đi vào bộ lọc: `taxonomy` là enum trong `schemas/common.yaml:6` (đúng 5 giá trị có trong DB)
  nên sai sẽ thành `INVALID_ARGUMENTS` rõ ràng; `days` là integer 1–7; `startDate` có format date.
  Chỉ `destination` là chuỗi tự do không ràng buộc. Đúng nguyên tắc đã chốt ở entry
  `2026-09-20-resolve-destination-from-catalog.md`: giá trị hợp lệ đến từ catalog hoặc OpenAPI,
  không chép tay trong code.
- **Điền `query` thay vì để cả request hỏng.** Chạy thật cho thấy planner LLM thỉnh thoảng sinh
  `search_products` thiếu `query` — trường `required` của `SearchRequest` (`schemas/search.yaml:42-49`).
  `normalize_arguments` ném `INVALID_ARGUMENTS`, `nodes.py` quy về `LLM_UNAVAILABLE` 503, hỏng toàn bộ
  lịch trình. Dùng điểm đến đã chuẩn hóa làm fallback tất định: đó đúng là giá trị planner tự điền ở các
  lần chạy thành công (log `GET /api/v1/search?q=Đà Nẵng&...`), và ARCHITECTURE §8 yêu cầu "khi LLM lỗi,
  dùng rule-based fallback hoặc trả lỗi có kiểm soát". Không nới lỏng schema.
- **Bỏ phép kiểm lệch `destination` trong `_validated_plan`.** Dòng ngay sau đó đã ghi đè
  `args["destination"] = intent["destination"]`, nên phép kiểm chỉ biến một cách diễn đạt khác
  ("Hồ Chí Minh" so với tên catalog "TP. Hồ Chí Minh") thành lỗi 503 mà không bảo vệ thêm gì về
  grounding. Không có test hay entry history nào phủ dòng này. **Đây là dọn mâu thuẫn, không phải
  nguyên nhân của lỗi 503 đã gặp** — nguyên nhân thật là thiếu `query` ở trên; giả thuyết ban đầu về
  lệch tên đã bị chính log planner bác bỏ.

## Kiểm tra

- `pytest src/backend/tests/unit` (LANGSMITH_TRACING=false): **156 passed**, 115 s. Trước thay đổi là 154.
- `python src/shared/contracts/tests/validate_contract.py`: **PASS** — 70 schema, 50 fixture, negative checks.
- Test hồi quy `test_planner_wording_of_the_destination_does_not_fail_the_plan` đã được xác nhận **fail
  trên code cũ** (IndexError vì plan rỗng) và pass sau sửa.
- Chạy thật, `ITINERARY_DATA_MODE=http` + Postgres local đã seed (`cdp.products` 10.320, `cdp.profiles`
  2.000, `cdp.events` 7.131), model LLM thật, embedding `intfloat/multilingual-e5-base`:
  - `GET /api/v1/destinations` → 35 điểm đến, tổng 2.897 sản phẩm.
  - `src/evaluation/tests/check_real_data_grounding.py` chạy **3 lần liên tiếp: 22/22 sản phẩm khớp
    `cdp.products` về `name`, `destination`, `unit_price`; 0 lỗi** (exit 0).
  - Chuẩn hóa: `da nang 2 ngay` → `Đà Nẵng` (cùng danh sách sản phẩm với câu viết đủ dấu),
    `ha long 2 ngay` → `Hạ Long`, `tphcm 2 ngày` → `TP. Hồ Chí Minh`, `sài gòn 2 ngày` →
    `TP. Hồ Chí Minh`, `tokyo 2 ngày` → **422 `UNSUPPORTED_DESTINATION`**.
  - Trước khi sửa `query`, cùng bộ case này fail chập chờn 1–2 ca mỗi lần chạy (503 `LLM_UNAVAILABLE`).
- Độ trễ quan sát trong log: `itinerary.completed ... latencyMs` khoảng 3.0–5.4 s với
  `ITINERARY_LLM_TIMEOUT_SECONDS` của `.env` local. Vượt mục tiêu 5 s ở ca chậm nhất; **không dùng làm
  bằng chứng SLA** vì timeout môi trường demo lớn hơn ngân sách spec §7.2.

## Còn lại / rủi ro

- `GET /api/v1/products/{productId}` vẫn chưa có route dù `supports_catalog = True`. Hiện không nổ vì
  `hydrate()` không gọi tới, nhưng đây là **bất biến mong manh**: ai lược bớt trường khỏi `hit()`
  (`application/search/use_cases.py:14`) sẽ làm agent gọi product detail và nhận 404 hàng loạt.
- `sài gòn 2 ngày` chuẩn hóa đúng nhưng có lần trả lịch trống; chưa tìm nguyên nhân, nghi ở chất lượng
  truy vấn semantic khi `query` là tên viết khác. Chưa mở task riêng.
- Chưa đo lại độ trễ với timeout đúng ngân sách spec §7.2 (classify 2 s, composition 3 s).
- Bộ case trong `check_real_data_grounding.py` mới phủ chuẩn hóa điểm đến và grounding. Chưa phủ:
  `context.language=en`, `INVALID_TRIP_DURATION`, `CONVERSATION_NOT_FOUND`, sửa intent giữa chừng,
  `LLM_UNAVAILABLE` khi key sai. Các nhánh này vẫn chỉ có unit test bảo vệ.
- Script cần Postgres truy cập được: mặc định gọi `docker compose exec postgres psql`; đặt
  `SEED_DATABASE_URL` để dùng psycopg trực tiếp (ví dụ khi trỏ staging cloud).
- `docs/agent/evaluation-plan.md` vẫn viết cho chế độ fixture 50 sản phẩm. Chưa cập nhật cho chế độ
  dữ liệu thật; số liệu §7 của tài liệu đó không áp dụng cho catalog 10.320 sản phẩm.
