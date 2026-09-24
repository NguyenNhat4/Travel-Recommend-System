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
| **Session store** | Redis local qua Docker (bind `127.0.0.1`, có mật khẩu) | Redis dùng chung (managed hay tự host: chờ chốt) | Redis managed, `noeviction` |
| **Cơ sở dữ liệu vector** | Weaviate local qua Docker (volume riêng) | Weaviate dùng chung | Weaviate Cloud hoặc self-host có backup |
| **Dữ liệu mẫu** | Snapshot nén hoặc dữ liệu tổng hợp | Toàn bộ dữ liệu snapshot chuẩn hóa | Dữ liệu giao dịch thực tế |
| **Dịch vụ AI** | Local LLM hoặc API dev key | API key chia sẻ nội bộ | Dedicated API quota / Enterprise |

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
| `COHERE_API_KEY` | Khóa gọi Cohere Embed API | Tất cả | Bí mật, không commit. Chỉ backend và job embed giữ — Weaviate **không** nhận khóa này |
| `EMBEDDING_MODEL_NAME`| Tên mô hình vector — mặc định `embed-multilingual-v3.0` | Tất cả | Đổi giá trị này là đổi chiều vector → phải tạo lại collection và chạy lại job embed |
| `WEAVIATE_URL` | Endpoint Weaviate (local: `http://localhost:8080`) | Tất cả | Không mở ra mạng ngoài ở local |
| `WEAVIATE_GRPC_PORT` | Cổng gRPC của Weaviate (mặc định `50051`). Search, Similar và Recommendation truy vấn top-K qua gRPC; Weaviate Cloud tự dùng cổng 443 của host `grpc-<cluster>` nên bỏ qua biến này | Tất cả | Không mở ra mạng ngoài ở local |
| `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` | Khoá RS256 để FastAPI ký và kiểm JWT; public key công bố qua JWKS | Tất cả | Khoá riêng bí mật: không commit, không vào image. Chỉ FastAPI giữ |
| `JWT_ISSUER` / `JWT_AUDIENCE` | Giá trị `iss`/`aud` bắt buộc khớp khi kiểm token | Tất cả | Không bí mật |
| `AUTH_SERVICE_TOKEN` | Header `X-Service-Token` BFF gửi tới nhóm `/auth/session/*` và `/internal/*` | Tất cả | Bí mật, ≥ 32 ký tự, BFF và FastAPI dùng chung giá trị |
| `AUTH_REDIS_URL` / `SESSION_REDIS_URL` | Redis cho rate limit (FastAPI) và session (BFF) | Tất cả | Có mật khẩu; không mở ra mạng ngoài |
| `TRUSTED_PROXIES` | Dải proxy được tin header `X-Forwarded-For` khi tính rate limit | Staging / Prod | Sai giá trị = rate limit bị vượt qua bằng một header |
| `CAPTCHA_PROVIDER` / `CAPTCHA_SECRET` | CAPTCHA khi đăng nhập sai nhiều lần | Tất cả | `noop` ở dev/test; secret chỉ ở FastAPI |
| `WEAVIATE_API_KEY` | Khóa xác thực Weaviate | Staging / Prod | Bí mật. Local dùng anonymous access nên có thể bỏ trống |

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
  - Kiểm tra trạng thái sẵn sàng của Cohere Embed API.
- **Metrics Endpoint (`GET /metrics`):** Xuất các chỉ số độ trễ API, tỷ lệ lỗi HTTP 5xx và thời gian xử lý của Trợ lý AI.

---

## 6. Quy Trình Phát Hành & Kế Hoạch Hoàn Tác (Release & Rollback)

### 6.1. Quy trình phát hành phiên bản mới (Release Process)
```
[Code Push] ──> [CI: Lint & Tests] ──> [DB Migration] ──> [Deploy Backend] ──> [Deploy Frontend] ──> [Smoke Test]
```
1. Xác nhận toàn bộ automated tests và contract validation đều PASS trên CI.
2. Thực thi migration cơ sở dữ liệu bằng `db/migrations/run.py`.
3. Triển khai phiên bản Backend mới (hỗ trợ Zero-downtime rolling update).
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
