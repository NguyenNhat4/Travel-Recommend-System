# Deployment & Operations Plan — V-OTA Platform

Tài liệu này hướng dẫn chi tiết quy trình đóng gói, cấu hình môi trường, triển khai phát hành (Release), giám sát vận hành và kế hoạch hoàn tác sự cố (Rollback) cho toàn bộ hệ thống V-OTA.

---

## 1. Môi Trường Triển Khai (Deployment Environments)

Hệ thống được thiết kế để vận hành trên ba cấp môi trường đồng nhất:

```
[Local Development] ──> [Staging Cloud (Shared)] ──> [Production Environment]
  (Mỗi kỹ sư 1 DB)       (Kiểm thử tích hợp & Demo)   (Vận hành chính thức)
```

| Đặc điểm | Local Development | Staging Cloud | Production |
|---|---|---|---|
| **Mục đích** | Phát triển tính năng, debug | Tích hợp liên tục, kiểm thử E2E | Phục vụ người dùng thực tế |
| **Cơ sở dữ liệu** | PostgreSQL 16 local qua Docker | PostgreSQL Cloud | Managed Cloud Database Cluster |
| **Session store** | Redis local qua Docker (bind `127.0.0.1`, có mật khẩu); hội thoại dùng DB index riêng | Redis dùng chung, hội thoại dùng DB index riêng | Redis managed, `noeviction`; hội thoại dùng DB index riêng |
| **Cơ sở dữ liệu vector** | Weaviate local qua Docker (volume riêng) | Weaviate Cloud (cluster chung của nhóm, eu-central-1) | Weaviate Cloud hoặc self-host có backup |
| **Cổng thanh toán** | Stripe test mode, `stripe listen` chuyển webhook về máy | Stripe test mode, webhook trỏ về URL staging | Ngoài phạm vi (live mode) |
| **Dữ liệu mẫu** | Snapshot nén hoặc dữ liệu tổng hợp | Toàn bộ dữ liệu snapshot chuẩn hóa | Dữ liệu giao dịch thực tế |
| **Dịch vụ AI** | Local LLM hoặc API dev key | API key chia sẻ nội bộ | Dedicated API quota / Enterprise |

### 1.1. Tầng DB HA riêng cho `staging-ha`

`staging-ha` là Terraform root và state riêng (`infra/staging-ha`), tách khỏi root/state `infra/staging`. Vì hai root có state khác nhau, thay đổi Patroni không làm thay đổi tài nguyên do workflow `infra-terraform-staging.yml` quản lý; các workflow CI/CD ứng dụng và crawler cũng không bị sửa trong phạm vi này.

Khi được bật có chủ đích bằng `create_patroni = true`, staging-ha tạo hai node PostgreSQL + Patroni ở hai zone, một witness etcd ở zone thứ ba và một ILB private. ILB chỉ gửi kết nối ghi tới node trả HTTP `200` ở `/primary`; Patroni tự bầu leader khi mất node. `create_patroni = false` vẫn là mặc định, nên việc merge mã không tự dựng cụm.

Di trú từ primary cũ là một cửa sổ vận hành riêng: dừng ghi, clone một lần vào node `a`, để node `b` gia nhập cụm qua DCS, đối chiếu dữ liệu và xác nhận replication lag trước khi đổi `db.vota.internal` sang ILB. Primary cũ giữ nguyên cho rollback có điều kiện. Vì clone là một điểm thời gian, do đó mọi ghi phát sinh sau clone phải bị dừng cho tới khi cutover hoàn tất mà không được mở lại ghi sớm.

---

## 2. Quản Trị Cấu Hình & Biến Môi Trường (Environment Variables)

Hệ thống phân tách ranh giới bảo mật bằng các chuỗi kết nối và API key riêng biệt:

| Tên biến | Mục đích sử dụng | Môi trường áp dụng | Ràng buộc bảo mật |
|---|---|---|---|
| `DATABASE_URL` | Kết nối chính cho Backend (`app` & `catalog`) | Tất cả | Sử dụng role `vota_app`, chỉ đọc `cdp.products` |
| `CDP_DATABASE_URL` | Kết nối dành riêng cho Adapter `LocalCdpClient` | Tất cả | Sử dụng role `cdp_writer`, không truy cập `app` |
| `SEED_DATABASE_URL` | Kết nối nạp dữ liệu định kỳ (Seed / Loader) | CI / Local Setup | Quyền superuser, chỉ dùng cho job nạp dữ liệu |
| `INSIDER_BASE_URL` | URL kết nối dịch vụ Insider Clone | Tất cả | Giao tiếp qua HTTP REST |
| `INSIDER_REQUEST_TOKEN`| Token xác thực gọi sang Insider | Staging / Prod | Bí mật, không commit vào repository |
| `LLM_API_KEY` | Khóa xác thực mô hình AI (OpenAI / Claude) | Tất cả | Bí mật, quản lý qua Vault hoặc Secret Manager |
| `ITINERARY_ORCHESTRATOR` | `off` (mặc định) hoặc `on`; giữ đường cũ tới bộ đo đạt ngưỡng | Tất cả | Không bí mật |
| `ITINERARY_ORCHESTRATOR_MODEL` / `ITINERARY_ORCHESTRATOR_PROVIDER` | Model riêng và provider `gemini|openai|anthropic`; bỏ trống dùng model chung; lựa chọn GPT-6.1 Sol/OpenAI | Tất cả | Không bí mật; dùng khoá provider hiện có |
| `ITINERARY_ORCHESTRATOR_REASONING_EFFORT` | Mức reasoning tuỳ chọn; chọn theo số đo, không gửi khi để trống | Tất cả | Không bí mật |
| `ITINERARY_DATA_MODE` | Nguồn dữ liệu cho tool của trợ lý: `fixture` (dữ liệu mẫu, mặc định dev/test), `inprocess` (gọi engine trong cùng tiến trình; dùng khi chạy dữ liệu thật), `http` (gọi qua HTTP tới `ITINERARY_SERVICE_BASE_URL`; tuỳ chọn, để hoàn tác hoặc khi tách agent thành service riêng), `disabled` | Tất cả | Không bí mật. Không đặt thì ngoài dev/test là `disabled`, nên staging/production phải đặt tường minh |
| `ITINERARY_SERVICE_BASE_URL` | Gốc URL backend mà adapter HTTP gọi tới | Chỉ khi `ITINERARY_DATA_MODE=http` | Không bí mật. Bắt buộc ở mode `http`, bỏ qua ở mode khác |
| `ITINERARY_TOOL_TIMEOUT_SECONDS` | Thời hạn (giây) cho mỗi lời gọi tool của trợ lý, áp dụng mọi mode | Tất cả | Không bí mật |
| `EMBED_MODEL` / `EMBED_MODEL_REVISION` / `EMBED_DIMENSION` | Model vector — chỉ `intfloat/multilingual-e5-small`, revision ghim, 384 chiều (chạy local trong backend và job index, không cần khoá) | Tất cả | Không bí mật. Thường không đặt (mặc định trong `core/config.py`); đổi revision = chạy lại job embed |
| `VECTOR_COLLECTION` | Collection vector — mặc định `ProductE5Small` (vector e5-small). Biến cũ `WEAVIATE_COLLECTION` (collection `Product`, vector Cohere) không còn được đọc | Tất cả | Không bí mật. Job embed từ chối ghi vào collection đang chứa vector của model khác |
| `SEARCH_CUTOFF` / `SEARCH_LEXICAL_CUTOFF` | Ngưỡng cosine của Search — mặc định 0,84 (hiệu chỉnh cho e5-small) / 0,50; `SEARCH_NO_DIACRITICS_CUTOFF` **0,80** cho câu không dấu (chỉ khi `SEARCH_NO_DIACRITICS_MODE=relax`, mặc định production) | Tất cả | Không bí mật. Hiệu chỉnh trên gold khi đổi model. Cutoff tuyệt đối không làm câu ngoài catalog trả rỗng — giới hạn đã biết |
| `SEARCH_LLM_FALLBACK` / `SEARCH_LLM_FALLBACK_MIN_CONFIDENCE` / `SEARCH_LLM_FALLBACK_TIMEOUT_MS` | LLM fallback của query plan: `off` (mặc định) \| `shadow` \| `on`; ngưỡng độ tin cậy kích hoạt; hạn thời gian mỗi lượt | Tất cả | Không bí mật; dùng khoá LLM có sẵn (`LLM_API_KEY`) |
| `WEAVIATE_URL` | Endpoint Weaviate (dev: `http://localhost:8080`; staging: URL cluster Weaviate Cloud, dạng `https://<cluster>.weaviate.cloud`) | Tất cả | Không mở ra mạng ngoài ở local |
| `WEAVIATE_GRPC_PORT` | Cổng gRPC của Weaviate (mặc định `50051`). Search, Similar và Recommendation truy vấn top-K qua gRPC; Weaviate Cloud tự dùng cổng 443 của host `grpc-<cluster>` nên bỏ qua biến này | Tất cả | Không mở ra mạng ngoài ở local |
| `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` | Khoá RS256 để FastAPI ký và kiểm JWT; public key công bố qua JWKS | Tất cả | Khoá riêng bí mật: không commit, không vào image. Chỉ FastAPI giữ |
| `JWT_ISSUER` / `JWT_AUDIENCE` | Giá trị `iss`/`aud` bắt buộc khớp khi kiểm token | Tất cả | Không bí mật |
| `AUTH_SERVICE_TOKEN` | Header `X-Service-Token` BFF gửi tới nhóm `/auth/session/*` và `/internal/*` | Tất cả | Bí mật, ≥ 32 ký tự, BFF và FastAPI dùng chung giá trị |
| `AUTH_REDIS_URL` / `SESSION_REDIS_URL` | Redis cho rate limit (FastAPI) và session (BFF) | Tất cả | Có mật khẩu; không mở ra mạng ngoài |
| `ITINERARY_REDIS_URL` | Redis cho working memory 24 giờ của trợ lý, dùng DB index riêng (ví dụ `/2`) | Tất cả | Có mật khẩu; để trống ở dev/test thì dùng memory trong process; bắt buộc ở production |
| `TRUSTED_PROXIES` | Dải proxy được tin header `X-Forwarded-For` khi tính rate limit | Staging / Prod | Sai giá trị = rate limit bị vượt qua bằng một header |
| `CAPTCHA_PROVIDER` / `CAPTCHA_SECRET` | CAPTCHA khi đăng nhập sai nhiều lần | Tất cả | `noop` ở dev/test; secret chỉ ở FastAPI |
| `WEAVIATE_VECTOR_INDEX_TYPE` | Loại index của collection `Product`, mặc định `hnsw`; đặt `hfresh` khi dùng Weaviate Cloud chỉ cho phép loại này. Đổi giá trị không chuyển đổi collection đã có; cần kế hoạch tạo lại và index lại riêng | Tất cả | Không bí mật |
| `WEAVIATE_API_KEY` | Khóa xác thực Weaviate | Staging / Prod | Bí mật. Local dùng anonymous access nên có thể bỏ trống |
| `STRIPE_SECRET_KEY` | Khoá API Stripe (`sk_test_…`) | Tất cả | Bí mật, chỉ Backend giữ, không commit. Backend từ chối khởi động nếu nhận khoá `sk_live_` |
| `STRIPE_WEBHOOK_SECRET` | Khoá kiểm chữ ký webhook (`whsec_…`); ở local lấy từ `stripe listen` | Tất cả | Bí mật |
| `PAYMENT_PROVIDER` | `stripe` hoặc `fake` (test/offline, không gọi mạng) | Tất cả | Không bí mật |
| `BOOKING_HOLD_MINUTES` | Thời gian giữ chỗ, mặc định `30`, không được nhỏ hơn 30 | Tất cả | Không bí mật |
| `BOOKING_DRAFT_TTL_MINUTES` | Thời gian hiệu lực của đơn nháp (Đặt ngay), mặc định `30` | Tất cả | Không bí mật |
| `GUEST_BOOKING_TTL_DAYS` | Thời gian Redis giữ giỏ và đơn nháp của khách chưa đăng nhập, mặc định `3` | Tất cả | Không bí mật |
| `BOOKING_REDIS_URL` | Redis cho giỏ và đơn nháp của khách chưa đăng nhập, dùng DB index riêng | Tất cả | Có mật khẩu; không mở ra mạng ngoài |
| `PAYMENT_MAX_FAILED_ATTEMPTS` | Số lần thẻ bị từ chối tối đa, mặc định `3` | Tất cả | Không bí mật |
| `PUBLIC_WEB_URL` | Gốc URL web để dựng `success_url`, `cancel_url` | Tất cả | Không bí mật |

---

## 3. Khởi Chạy & Đóng Gói Hệ Thống (Containerized Setup)

### 3.1. Khởi chạy môi trường nội bộ với Docker Compose
Môi trường hoàn chỉnh có thể khởi chạy nhanh chóng bằng các lệnh tiêu chuẩn:
```bash
# Khởi động cơ sở dữ liệu PostgreSQL (chạy tự động initdb trên volume rỗng)
docker compose up -d --wait postgres

# Khởi động Redis (session web + rate limit auth)
docker compose up -d --wait redis

# Khởi động Weaviate (volume riêng — KHÔNG bị xóa khi seed lại Postgres)
docker compose up -d --wait weaviate

# Nạp dữ liệu seed chuẩn hóa (nếu là lần chạy đầu tiên)
python -m data_collection.seed --as-of 2026-09-22 --seed 42

# Khởi động Backend API
uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Khởi động Frontend Web
cd src/frontend && npm run dev
```

Seed quan hệ và nạp vector là **hai vòng đời tách rời**: `make demo-db` dựng lại database `vota`, còn vector nằm trong volume của Weaviate nên chỉ chạy lại job embed khi catalog hoặc model đổi (so `textHash` / `modelVersion`).

---

## 4. Chiến Lược Di Chuyển Cơ Sở Dữ Liệu (Database Migrations)

### Nguyên tắc sống còn:
- **Tuyệt đối không chạy lại các file `db/init/*.sql` trên cơ sở dữ liệu đã có dữ liệu.**
- Các file trong `db/init/` chỉ được chạy tự động bởi PostgreSQL khi volume hoàn toàn rỗng.
- Mọi thay đổi schema trên môi trường Staging và Production phải được áp dụng qua bộ điều phối migration chuyên dụng:
  ```bash
  python db/migrations/run.py --database-url "$DATABASE_URL"
  ```

### Quy trình áp dụng Migration an toàn:
1. Viết script SQL migration trong `db/migrations/` theo định dạng `NNN_ten_thay_doi.sql`.
2. Đảm bảo mọi câu lệnh đều có tính chất **Idempotent** (Ví dụ: `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
3. Chạy thử nghiệm trên database local:
   ```bash
   make db-migrate
   ```
4. Kiểm tra lại tính toàn vẹn hệ thống bằng bộ script thẩm định:
   ```bash
   psql "$SEED_DATABASE_URL" -f db/verify.sql
   ```

---

## 5. Giám Sát Hệ Thống & Kiểm Tra Sức Khỏe (Health Checks)

Hệ thống cung cấp các endpoint kiểm tra trạng thái sức khỏe định kỳ:

- **Liveness Probe (`GET /health/live`):** Phản hồi HTTP 200 nếu tiến trình Backend đang chạy. Dùng cho bộ điều phối container (Kubernetes / Docker) quyết định việc khởi động lại pod.
- **Readiness Probe (`GET /health/ready`):** Kiểm tra trạng thái sẵn sàng phục vụ:
  - Kết nối tới PostgreSQL (`DATABASE_URL`).
  - Kết nối tới CDP (`CDP_DATABASE_URL`).
  - Kết nối tới Weaviate (`WEAVIATE_URL`) và sự tồn tại của collection `Product`.
  - Model embedding e5-small đã tải và embed thử được một câu.
- **Metrics Endpoint (`GET /metrics`):** Xuất các chỉ số độ trễ API, tỷ lệ lỗi HTTP 5xx và thời gian xử lý của Trợ lý AI.
- **Xem DB trên monitor job cào (tab "DB"):** danh sách schema / bảng kèm số dòng; xem từng bảng có phân trang, lọc, sắp xếp; xem một dòng kèm **liên kết** theo khoá ngoại: bấm sang dòng được trỏ tới (vd. `booking_items.product_id` → sản phẩm) và xem các dòng trỏ về nó (vd. sản phẩm → `booking_items`, `cart_items`, `booking_draft_items`, `combo_items`; hồ sơ CDP → `events`, `users`, `bookings`). Quan hệ lấy từ khoá ngoại khai báo trong PostgreSQL (tự theo migration mới), cộng hai quan hệ theo quy ước không có khoá ngoại: `attributes.parentProductId` (vé / phòng → tuyến / khách sạn) và `demo:business:<sourceRef>` (vé mô phỏng → vé gốc). Dùng kết nối DB sẵn có của job, mỗi yêu cầu trong transaction chỉ đọc, `statement_timeout` 5 giây. Chỉ database `vota`; database `insider` không có (monitor không có kết nối tới nó). Monitor chưa có đăng nhập: trong lúc chờ, nên giới hạn IP nguồn cổng 8765.
- **Sơ đồ và hoạt động DB realtime trên monitor (tab "DB"):**
  - *Sơ đồ quan hệ:* mỗi bảng / view của `cdp`, `catalog`, `app` là một ô (nhóm theo schema) kèm số dòng; đường nối là khoá ngoại (nét liền) và quan hệ quy ước (nét đứt: sản phẩm cha–con, vé mô phỏng–vé gốc); bấm ô mở bảng.
  - *Luồng dữ liệu:* ai đọc / ghi bảng nào — job cào → `cdp.products`, `catalog.combo_items`; backend nạp catalog vào bộ nhớ (chu kỳ `CATALOG_REFRESH_SECONDS`) → web / agent; agent → công cụ backend → catalog trong bộ nhớ + Weaviate; web / agent → giỏ, đơn nháp, đơn, thanh toán, đăng nhập, hội thoại (`app.*`); sự kiện hành vi qua `CdpClient` → `cdp.events`, `cdp.profiles`. Bảng ánh xạ đọc / ghi giữ trong một file khai báo của monitor, đối chiếu code backend.
  - *Realtime (làm mới 2 giây):* số dòng đọc / thêm / sửa / xoá mỗi giây của từng bảng (chênh lệch `pg_stat_user_tables`), tô lên sơ đồ; kết nối đang mở theo role (`pg_stat_activity`) và câu SQL đang chạy (cắt 200 ký tự, tham số dạng `$1`); dòng mới nhất của các bảng ghi nhiều, che cột bí mật như tab DB.
- **Đo lần gọi của web / agent (backend):** `GET /metrics` theo mục trên (độ trễ, lỗi 5xx, thời gian trợ lý theo route) và luồng sự kiện gọi nội bộ để monitor hiện **từng lần gọi** realtime. Đo ở tầng use case (search, recommendation, catalog) qua một port, gắn nguồn `web` (qua HTTP) hoặc `agent` (công cụ itinerary gọi trong tiến trình); thời gian từng bước dùng chung cách đo `stageMs` của `/search` (`StageTimer`). Sự kiện gồm route / use case, nguồn, trạng thái, thời gian, `stageMs`, số kết quả và `productId` trả về; không có câu tìm kiếm, dữ liệu cá nhân hay bí mật. Kèm thời điểm và số sản phẩm của lần nạp catalog vào bộ nhớ gần nhất.

---

## 6. Quy Trình Phát Hành & Kế Hoạch Hoàn Tác (Release & Rollback)

### 6.1. Quy trình phát hành phiên bản mới (Release Process)
```
[Code Push] ──> [CI: Lint & Tests] ──> [DB Migration] ──> [Deploy Backend] ──> [Deploy Frontend] ──> [Smoke Test]
```
1. Xác nhận toàn bộ automated tests và contract validation đều PASS trên CI.
2. Thực thi migration cơ sở dữ liệu bằng `db/migrations/run.py`.
3. Triển khai phiên bản Backend mới. Staging-HA cập nhật image không gián đoạn: trên mỗi VM chạy bản mới (slot blue/green) song song bản cũ, đợi `/health/ready` của bản mới, đổi proxy cục bộ (cổng 3000) sang bản mới rồi rút bản cũ sau khi drain; bản mới không sẵn sàng thì bản cũ vẫn phục vụ. Terraform chỉ đổi template (MIG `OPPORTUNISTIC`, không thay VM). Mỗi lần chỉ một deploy chạy (khoá concurrency `staging-ha-app` và `flock` trên VM). Cổng sẵn sàng là LB báo đủ VM HEALTHY và `/health/ready` qua public endpoint đạt 6 lần liên tiếp. Quyết định này áp dụng cho staging-HA; production chưa có quyết định riêng. *(Thay quyết định 2026-10-09 "chấp nhận downtime" của `update-archive/2026-10-09-rut-ngan-cd-chap-nhan-downtime.md`; cập nhật 2026-10-12 theo chỉ đạo trực tiếp, chi tiết vận hành ở `docs/guide/van-hanh-cd-staging-ha.md`.)*
4. Triển khai phiên bản Frontend mới tương ứng.
5. Thực hiện kịch bản Smoke Test trên Staging/Production để xác nhận luồng tìm kiếm và đặt hàng hoạt động bình thường.

### 6.2. Kế hoạch hoàn tác khi phát sinh sự cố (Rollback Strategy)
Khi phát hiện lỗi nghiêm trọng sau phát hành:
1. **Rollback Ứng dụng (Application Rollback):**
   - Chuyển hướng lưu lượng truy cập (traffic) trở lại container của phiên bản trước đó ngay lập tức.
   - Do tuân thủ nguyên tắc backward-compatible, phiên bản code cũ vẫn hoạt động bình thường với schema cơ sở dữ liệu đã migration (vì chỉ thêm cột tùy chọn).
2. **Rollback Dữ liệu (Data Rollback):**
   - Nếu migration tạo ra lỗi dữ liệu, thực thi script hoàn tác tương ứng `NNN_ten_thay_doi.down.sql`.
   - Trong trường hợp lỗi đơn hàng giao dịch, sử dụng cơ chế bù trừ sự kiện của CDP (`cancel_purchase`) để bảo toàn tính toàn vẹn của hồ sơ khách hàng.

### 6.3. Hoàn tác có điều kiện khi di trú DB `staging-ha`

Vì primary cũ không bị promote hay xoá trong giai đoạn dựng cụm, do đó có thể đưa `db.vota.internal` về IP primary cũ nếu kiểm tra leader Patroni, dữ liệu hoặc replication không đạt. Việc này chỉ an toàn trước khi mở lại ghi trên primary cũ: mọi ghi đã nhận sau cutover trên Patroni không tự quay ngược về primary cũ, nên phải giữ cửa sổ bảo trì và ghi nhận rõ điểm dữ liệu trước khi rollback.

Lệnh rollback DNS phải dùng đúng private zone của staging-ha và được kiểm tra từ một app VM trước khi mở lại ứng dụng:

```bash
gcloud dns record-sets update db.vota.internal. \
  --zone=vota-ha-internal --type=A --ttl=30 \
  --rrdatas=<old-primary-private-ip>
```

Không chạy `terraform apply` của root `infra/terraform/environments/staging` để rollback Patroni; hai state có ranh giới riêng.
