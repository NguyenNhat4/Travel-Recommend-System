# Cache kết quả gợi ý cá nhân hoá trên Redis dùng chung

- Ngày: 2026-10-12
- Người đề xuất: tqanh123 / Claude Code
- Trạng thái: chờ chốt (người dùng đã chọn hướng Redis ngày 2026-10-12; chờ chốt nội dung dưới đây)
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §1 (sơ đồ), §4 (dòng Redis); `docs/prd/deployment-plan.md` §2 (bảng biến môi trường)
- Mã FR/NFR: NFR-PERF-01; giữ nguyên FR-REC-02, AC-REC-02, AC-REC-03, FR-BKG-03 / AC-BKG-04

## Lý do

- Trang chủ gọi `GET /recommendations` mỗi lần người dùng đã đăng nhập vào trang, và backend tính lại từ đầu: đọc toàn bộ event của khách, rồi gọi Weaviate Cloud (eu-central-1) 3–5 lượt nối tiếp từ VM ở asia-southeast1. Số đo trên cloud: p95 1.057 ms ngày 05/10 (`src/evaluation/reports/eval-2026-10-05-recsys-web-latency.md`); log backend ngày 09/10 ghi 3,2–9,6 s. Timeout frontend đã phải nâng từ 3 s lên 10 s chỉ để che độ trễ (`history/2026-10-09-tang-timeout-goi-y-trang-chu-10s.md`). Mục tiêu của NFR-PERF-01 là p95 ≤ 250 ms.
- Hiện không có cache nào cho gợi ý. Ngày 12/10 người dùng quyết định không đưa Weaviate về cùng vùng với VM và không quét vector trong RAM. Vì vậy, ngoài việc làm nhanh chính lượt tính (không lệch PRD, làm riêng theo plan), cần cache để các lần gọi lặp lại không phải tính lại.
- Cache trong tiến trình không hiệu quả trên hạ tầng hiện tại. Mỗi VM chạy 2 worker, nhóm có 1–2 VM, load balancer không có affinity, nên mỗi khách có 2–4 bản cache riêng. Lần "Thử lại" sau khi timeout chỉ có 1/2 đến 1/4 khả năng rơi đúng worker đã tính xong.
- Redis (Memorystore `vota-ha-redis`) đã chạy 24/7 cho phiên và rate limit. Đặt cache ở đó thì mọi worker trên mọi VM dùng chung một kết quả: kết quả của request bị huỷ do timeout phục vụ được lần thử lại, và có thể tính sẵn ngay sau khi đăng nhập.
- PRD hiện chỉ cho Redis giữ phiên, rate limit, khoá refresh và working memory của trợ lý (`architecture.md` §4). Thêm vai trò cache là lệch PRD, nên cần đề xuất này.

## Nội dung đề xuất

### Quy tắc của cache

1. **Phạm vi.** Chỉ cache kết quả `GET /recommendations` của người dùng đã đăng nhập, gồm cả lời gọi trong tiến trình của trợ lý (cùng engine). Khách vãng lai không cache, vì đường này vốn khoảng 10 ms.
2. **Khoá.** Khoá gồm `cdpUserId`, `k`, `destination`, dấu vân tay của toàn bộ event của khách, ngày theo giờ Việt Nam và phiên bản engine (catalog, bảng phổ biến, model, luật). Dấu vân tay được tính từ lịch sử đọc từ CDP **ngay trong request đó**: mỗi request vẫn đọc CDP (cùng vùng, vài ms) để dựng khoá.
3. **Không trả kết quả cũ.** Vì khoá chứa dấu vân tay event, bất kỳ event mới nào (xem, thêm giỏ, mua, huỷ) cũng cho ra khoá mới, và gợi ý được tính lại. Không bao giờ trả gợi ý tính từ lịch sử cũ. Không cần xoá khoá khi mua hay huỷ; vòng K1 và AC-REC-02 giữ nguyên.
4. **TTL.** Mọi khoá bắt buộc có TTL, vì Redis chạy `noeviction`. Mặc định 900 giây. Không ghi giá trị lớn hơn 64 KB.
5. **Khi lỗi.** Redis lỗi hoặc chậm quá 100 ms thì bỏ qua cache và tính trực tiếp như hiện nay; khách không nhận lỗi. Khi CDP lỗi, kết quả lui về gợi ý phổ biến không được ghi vào cache.
6. **Không tính trùng.** Nhiều request cùng khoá cùng lúc thì chỉ một request tính (khoá ngắn bằng `SET NX`). Các request còn lại chờ kết quả trong một giới hạn, quá hạn thì tự tính.
7. **Request bị huỷ.** Frontend huỷ request thì backend vẫn tính xong và ghi cache, để lần "Thử lại" trúng.
8. **Làm ấm.** Ngay sau khi đăng nhập thành công, backend tính nền gợi ý cho đúng request mà trang chủ sẽ gửi (`k = 4`, không có `destination`). Không tính trước sau mỗi lượt xem sản phẩm.
9. **Cấu hình.** Dùng DB index riêng trên cùng instance Redis, với biến môi trường riêng. Để trống biến thì tắt cache (dev/test).

### `docs/prd/architecture.md` §1 — sơ đồ

Hiện tại:

```text
Redis[(Redis 7\nsession, rate limit,\nhội thoại trợ lý 24h)]
```

Thay bằng:

```text
Redis[(Redis 7\nsession, rate limit,\nhội thoại trợ lý 24h,\ncache gợi ý 15 phút)]
```

và thêm cạnh `RecEngine --> Redis`.

### `docs/prd/architecture.md` §4 — dòng Redis

Hiện tại:

> | **Session store, rate limit & working memory** | **Redis 7** (`maxmemory-policy noeviction`) | Giữ phiên web, bộ đếm rate limit/lockout, khoá refresh và working memory 24 giờ của trợ lý ở DB index riêng. Mất dữ liệu thì trợ lý nạp lại bản archive gần nhất cho user đăng nhập hoặc bắt đầu ngữ cảnh mới cho khách; lịch sử lâu dài vẫn còn trong Postgres. Không dùng `allkeys-lru`. |

Thay bằng:

> | **Session store, rate limit, working memory & cache gợi ý** | **Redis 7** (`maxmemory-policy noeviction`) | Giữ phiên web, bộ đếm rate limit/lockout, khoá refresh và working memory 24 giờ của trợ lý ở DB index riêng. Mất dữ liệu thì trợ lý nạp lại bản archive gần nhất cho user đăng nhập hoặc bắt đầu ngữ cảnh mới cho khách; lịch sử lâu dài vẫn còn trong Postgres. Cache kết quả gợi ý cá nhân hoá (`GET /recommendations`) nằm ở DB index riêng, TTL 15 phút. Khoá chứa dấu vân tay lịch sử event của khách, nên event mới luôn cho khoá mới; không bao giờ trả gợi ý tính từ lịch sử cũ. Mất cache hoặc Redis lỗi thì tính trực tiếp. Mọi khoá phải có TTL. Không dùng `allkeys-lru`. |

### `docs/prd/deployment-plan.md` §2 — biến môi trường

Thêm hai dòng sau `BOOKING_REDIS_URL`:

> | `RECOMMEND_CACHE_REDIS_URL` | Redis cho cache kết quả gợi ý cá nhân hoá, DB index riêng (ví dụ `/4`) | Tất cả | Có mật khẩu; không mở ra mạng ngoài. Để trống thì tắt cache (dev/test) |
> | `RECOMMEND_CACHE_TTL_SECONDS` | Thời gian sống của một mục cache gợi ý, mặc định `900` | Tất cả | Không bí mật |

## Thay đổi source sau khi chốt

- **Contract:** `src/shared/contracts/schemas/recommendations.yaml`.
  - `diagnostics.userVectorCacheHit` đổi mô tả thành "true khi kết quả lấy từ cache gợi ý".
  - Bỏ nhãn `[CHỜ DUYỆT: P3]` ở trường này và ở dòng 4.
  - Không đổi shape response. Chạy `validate_contract.py`.
- **Spec:** `docs/spec/hop-dong-tich-hop-search-recommendation.md`.
  - §5 (K1): thay "vô hiệu hoá cache user vector" bằng khoá theo dấu vân tay event.
  - §7.1: ngân sách khi trúng và khi trượt cache.
  - §10: chốt S5.
  - Mục Recommendation của `docs/spec/hop-dong-tich-hop-backend.md`.
- **Backend:**
  - `application/ports/recommendation_cache.py`: port mới.
  - `application/recommendation/`: lớp bọc engine (đọc event, dựng khoá, tra và ghi cache, chống tính trùng, làm ấm sau đăng nhập).
  - `infrastructure/persistence/redis_recommendation_cache.py`: adapter dùng client redis đồng bộ (route `/recommendations` là hàm sync), có timeout, TTL và giới hạn kích thước.
  - `core/config.py`, `main.py`: nối dây; lớp bọc đặt trước `traced` để route và trợ lý dùng chung.
  - Bản giả trong `tests/fakes/`; unit test và integration test.
  - `.env.example`.
- **Hạ tầng:**
  - Secret `vota-ha-backend-env` thêm `RECOMMEND_CACHE_REDIS_URL`, dùng một DB index chưa có ai dùng.
  - `infra/terraform/environments/staging-ha/compose.ha.yml` truyền biến này vào container backend.
- **Kế hoạch chi tiết:** `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md`.
