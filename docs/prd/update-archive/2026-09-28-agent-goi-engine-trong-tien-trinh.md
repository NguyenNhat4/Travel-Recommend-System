# Agent gọi engine Search/Recommendation trong cùng tiến trình, không gọi ngược HTTP API của chính Backend

- Ngày: 2026-09-28
- Người đề xuất: tqanh123 / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: tqanh123 (người dùng), 2026-09-29 (chốt cả vị trí `engine_tools.py` trong `application`; áp dụng cùng ngày, FR-AGT-02 gộp với đề xuất `2026-09-28-tool-similar-cho-agent.md`)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-02), `docs/prd/architecture.md` §2 (ghi chú cây thư mục), `docs/prd/deployment-plan.md` §2
- Mã FR/NFR: FR-AGT-02, FR-AGT-04, NFR-REL-01, NFR-SEC-01, NFR-MAINT-01, NFR-MAINT-02, NFR-PERF-02

## Lý do

- **Code từng đi vòng.** Trước thay đổi đi kèm đề xuất này, mode `http` là mặc định của `make chat`/`make web`: adapter
  `ItineraryHttpClients` gọi `/api/v1/search`, `/recommendations`, `/destinations` của **chính** Backend, trong khi các
  engine này đã nằm sẵn trong cùng tiến trình. Nay hai lệnh đó mặc định `inprocess` (mục cuối). Cách này có từ lúc RecSys còn là service riêng (history
  `2026-09-22-noi-agent-voi-recsys-backend.md`), không phải quyết định kiến trúc.
- **PRD đã mô tả hướng trong tiến trình.** §1 vẽ `LG → Tools → Ports` bên trong Backend Core. Quy tắc 7 ghi agent
  "chỉ dùng port do `application` cung cấp". §5 không có ranh giới "Backend ↔ chính Backend". Code làm theo các mục
  này nên không phải chờ chốt; đề xuất chỉ sửa chữ PRD cho hết mơ hồ.
- **FR-AGT-02 đọc được hai nghĩa.** "Tương tác trực tiếp với API hệ thống" có thể hiểu là gọi HTTP API. Cần ghi rõ
  để không ai quay lại vòng HTTP.
- **Vòng HTTP tốn và dễ sai.** Mỗi lời gọi tool thêm một lượt HTTP và serialize, và cần một URL cấu hình trỏ về chính
  mình (NFR-PERF-02). Lỗi engine bất ngờ thành 500 dạng text, agent đọc là `INVALID_TOOL_RESPONSE` và không thử lại.
- **Biến môi trường chưa có trong PRD.** `deployment-plan.md` §2 thiếu ba biến điều khiển nguồn dữ liệu của agent.
  Không đặt `ITINERARY_DATA_MODE` thì ngoài dev/test agent bị tắt.

## Nội dung đề xuất

### 1. `requirements.md` §1.4, FR-AGT-02

- Hiện tại: **FR-AGT-02 (Gọi công cụ nghiệp vụ - Tool Calling):** Trợ lý tương tác trực tiếp với API hệ thống thông
  qua các công cụ: tìm kiếm sản phẩm, kiểm tra lịch trống, tính toán chi phí dự kiến.
- Thay bằng: **FR-AGT-02 (Gọi công cụ nghiệp vụ - Tool Calling):** Trợ lý gọi trực tiếp engine nghiệp vụ của hệ thống
  qua các công cụ có schema lấy từ OpenAPI: tìm kiếm sản phẩm, gợi ý cá nhân hoá, kiểm tra lịch trống, tính toán chi
  phí dự kiến. Khi chạy với dữ liệu thật, công cụ gọi engine trong cùng tiến trình với Backend, qua port của tầng
  application, không gọi ngược HTTP API của chính Backend.

### 2. `architecture.md` §2, cây thư mục (chỉ ghi chú, không đổi quy tắc)

- Thêm một dòng ngay dưới dòng `<domain>/` của `application/`:

  ```text
  │   └── <domain>/            # Use case theo domain (auth, booking, catalog, itinerary, recommendation, search, tracking)
  │                            #   itinerary/engine_tools.py: tool itinerary gọi engine search/recommendation/catalog trong tiến trình (ITINERARY_DATA_MODE=inprocess)
  ```

- Dòng `clients/` của `infrastructure/`:
  - Hiện tại: `│   ├── clients/             # HTTP client ra service ngoài, gồm HttpInsiderClient; fixture itinerary cho ITINERARY_DATA_MODE=fixture`
  - Thay bằng: `│   ├── clients/             # HTTP client ra service ngoài, gồm HttpInsiderClient; tool itinerary dạng fixture (=fixture, mặc định dev/test) và HTTP tuỳ chọn (=http)`

`engine_tools.py` hiện thực port `itinerary_tools` nhưng đặt ở `application`, vì nó chỉ điều phối use case có sẵn và
không chứa SDK/DB/HTTP (§6.3 mục 3). Không đặt trong `agents/` (quy tắc 7), cũng không đặt trong
`infrastructure/clients/` (nơi dành cho HTTP/fixture). Không đổi quy tắc phụ thuộc nào; `tests/architecture/` giữ nguyên.

**Cần người review chốt rõ vị trí này.** Dòng `├── infrastructure/          # LỚP 3: hiện thực port` của
`architecture.md` §2 có thể đọc là mọi hiện thực port phải nằm ở `infrastructure/`. Đề xuất này đọc dòng đó là "hiện
thực port chạm SDK/DB/HTTP", và ghi chú ở trên biến cách đọc đó thành chữ trong PRD. Nếu người review không đồng ý,
xem mục "Nếu bị từ chối" bên dưới.

### 3. `deployment-plan.md` §2, thêm ba dòng sau `LLM_API_KEY`

| Tên biến | Mục đích sử dụng | Môi trường áp dụng | Ràng buộc bảo mật |
|---|---|---|---|
| `ITINERARY_DATA_MODE` | Nguồn dữ liệu cho tool của trợ lý: `fixture` (dữ liệu mẫu, mặc định dev/test), `inprocess` (gọi engine trong cùng tiến trình; dùng khi chạy dữ liệu thật), `http` (gọi qua HTTP tới `ITINERARY_SERVICE_BASE_URL`; tuỳ chọn, để hoàn tác hoặc khi tách agent thành service riêng), `disabled` | Tất cả | Không bí mật. Không đặt thì ngoài dev/test là `disabled`, nên staging/production phải đặt tường minh |
| `ITINERARY_SERVICE_BASE_URL` | Gốc URL backend mà adapter HTTP gọi tới | Chỉ khi `ITINERARY_DATA_MODE=http` | Không bí mật. Bắt buộc ở mode `http`, bỏ qua ở mode khác |
| `ITINERARY_TOOL_TIMEOUT_SECONDS` | Thời hạn (giây) cho mỗi lời gọi tool của trợ lý, áp dụng mọi mode | Tất cả | Không bí mật |

## Thay đổi source sau khi chốt

- Sửa ba chỗ PRD ở trên, đúng nội dung đã chốt.
- Đổi trạng thái đề xuất sang `đã áp dụng`, ghi người chốt và ngày, `git mv` sang `docs/prd/update-archive/`, ghi
  entry `history/`.
- Không cần sửa code, contract hay spec thêm: phần đó làm song song (mục dưới) và đã khớp PRD §1, quy tắc 7.
- Nếu bị từ chối: giữ PRD như cũ; đặt `ITINERARY_DATA_MODE=http` để quay về cách gọi cũ (mode `http` vẫn được giữ).
  Sau đó hoàn tác phần đã làm song song:
  - `Makefile`: `chat` và `web` mặc định lại `http`.
  - Bỏ `application/itinerary/engine_tools.py` cùng nhánh `inprocess` trong `main.py` và `core/config.py`, hoặc chuyển
    adapter sang `infrastructure/` nếu người review chỉ phản đối vị trí.
  - Viết lại các đoạn mô tả cách gọi trong tiến trình: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§1.1, §2,
    §2.1, §2.4, §4.1 dòng `dataMode`, §4.6, §5, §7.2, §7.3, §9 mục 9, §11), `hop-dong-tich-hop-backend.md` §1.2 và §5.1,
    `hop-dong-tich-hop-search-recommendation.md` §1.2 và §3.2, `hop-dong-tich-hop-auth.md` §3.5,
    `hop-dong-tich-hop-cdp.md` §1.4, `docs/spec/agent/README.md`, `working-context.md`, `golden-run.md`,
    `docs/spec/data-collection/bao-cao-schema.md` §8.6, `src/backend/README.md`.
  - Giá trị `inprocess` của `AssistantStatus.dataMode` giữ lại trong contract (không xoá giá trị enum ở v1) nhưng
    không còn được dùng.

## Phần đã làm song song (không lệch PRD, không chờ chốt)

Ghi để người review nắm bối cảnh. Các mục này đi cùng PR code, reviewer theo `architecture.md` §6.4.

- **Mode `inprocess`** là giá trị mới của `ITINERARY_DATA_MODE` và `AssistantStatus.dataMode` (chỉ thêm). Adapter lấy
  engine trên `app.state` mỗi lần gọi nên theo kịp mỗi lần RecSys làm mới. `fixture` vẫn là mặc định dev/test, `http`
  giữ làm mode phụ, `make chat`/`make web` chuyển sang `inprocess`.
- **Kiểm JWT** chuyển từ `api/deps.py` sang `application/auth/bearer.py` để route và tool dùng chung một chỗ. Token
  hỏng trả 401, không hạ thành khách. Token không vào state, log hay trace (NFR-SEC-01).
- **RecSys chưa nạp xong hoặc tắt, hoặc engine lỗi bất ngờ:** tool trả `SEARCH_UNAVAILABLE` 503, **được thử lại**.
  Đây là thay đổi có chủ đích theo quyết định của người dùng (2026-09-28): ở mode `http`, cùng lỗi đó thành 500 dạng
  text và agent không thử lại. Hành vi của route công khai khi RecSys tắt giữ nguyên.
- **Enum `Strategy`** trong contract thêm `long_term` và `cold_start_content`. Engine đã trả hai giá trị này nhưng
  contract thiếu (bổ sung, OpenAPI 1.8.0). Chỗ lệch nghĩa của các giá trị cũ giữa spec và engine (ngưỡng 90/180 ngày,
  điều kiện `recent_activity`) để RecSys và Web quyết riêng.
- **CDP fallback:** đọc lịch sử CDP lỗi kết nối thì gợi ý rơi về `popular` (`coldStart: true`) thay vì lỗi 500.
  Reader dùng `CDP_TIMEOUT_SECONDS` theo spec CDP.
- **Quan sát:** mỗi lời gọi tool kết thúc trong hạn ghi một dòng log `itinerary.tool` (thay access log mất đi khi bỏ
  vòng HTTP); lời gọi quá hạn chỉ ghi `itinerary.tool.timeout`. Không ghi tham số hay token.
