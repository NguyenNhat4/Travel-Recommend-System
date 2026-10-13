# Áp dụng đề xuất cache gợi ý trên Redis vào PRD

- Ngày: 2026-10-12
- Tác giả: tqanh123 (chốt đề xuất) / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: docs
- Liên quan: `2026-10-12-de-xuat-cache-goi-y-redis-va-plan-ke-pho-bien.md` (entry tạo đề xuất), `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md`

## Mục tiêu

Ngày 2026-10-12 người dùng chốt đề xuất cache kết quả gợi ý cá nhân hoá trên Redis dùng chung. Theo AGENTS.md §8 (bước 3–4), PRD phải được cập nhật đúng nội dung đã chốt trước khi sửa source, và đề xuất chuyển sang `update-archive`. Phục vụ NFR-PERF-01. Giữ nguyên FR-REC-02, AC-REC-02, AC-REC-03 và FR-BKG-03/AC-BKG-04.

## File thay đổi

- `docs/prd/architecture.md` — sửa:
  - §1, sơ đồ: nhãn node Redis thêm "cache gợi ý 15 phút"; thêm cạnh `RecEngine --> Redis`.
  - §4, dòng Redis: thay bằng đúng văn bản đã chốt (DB index riêng, TTL 15 phút, khoá chứa dấu vân tay lịch sử event, Redis lỗi thì tính trực tiếp, mọi khoá có TTL).
- `docs/prd/deployment-plan.md` — sửa: §2 thêm hai biến `RECOMMEND_CACHE_REDIS_URL` và `RECOMMEND_CACHE_TTL_SECONDS` sau `BOOKING_REDIS_URL`.
- `docs/prd/update/2026-10-12-cache-goi-y-tren-redis.md` → `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` — đổi tên (`git mv`); trạng thái "đã áp dụng", chốt bởi tqanh123 ngày 2026-10-12.
- `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` — sửa:
  - trỏ sang `update-archive`;
  - thêm quyết định 7–10;
  - timeout giữ 10 s;
  - nhãn loại chỉ ở tab "Tất cả";
  - cache nằm trong engine;
  - không cần sửa `compose.ha.yml`;
  - mục "Còn chờ" để trống.
- `history/2026-10-12-ap-dung-cache-goi-y-redis-vao-prd.md` — thêm: entry này.

## Quyết định

Người dùng chốt ngày 2026-10-12:

- Đề xuất Redis: "đã chốt".
- Timeout frontend giữ 10 s, chỉ sửa dòng spec cũ.
- Thứ tự trộn tab "Tất cả": khách sạn → vé tham quan và golf → combo → vé máy bay.
- Được nạp sẵn vector sản phẩm vào RAM.
- Nhãn loại trên thẻ chỉ ở tab "Tất cả".
- Làm ấm sau đăng nhập giữ như đề xuất `(k=4, không destination)`. Persona demo P1–P3 không được làm ấm; chấp nhận.

Chỉ sửa PRD đúng phần văn bản đã chốt. `deployment-plan.md:20` (dòng session store) không sửa, vì không nằm trong nội dung đề xuất.

Hai điểm hiện thực khác phần "Thay đổi source sau khi chốt" của đề xuất, ghi lại trong plan:

- **Cache đặt trong engine** (`application/recommendation/cache.py` + field `RecommendForUser.cache`) thay vì lớp bọc riêng. Lý do: đường CDP lỗi trả cùng dạng với cold-start, nên lớp bọc bên ngoài không phân biệt được để tránh ghi cache.
- **Không cần sửa `compose.ha.yml`.** Container backend đọc mọi biến từ `env_file` chép từ secret `vota-ha-backend-env`.

Phần contract của đề xuất (mô tả `userVectorCacheHit`, bỏ `[CHỜ DUYỆT: P3]`) làm cùng lần nâng contract 1.25.0.

## Kiểm tra

- `git status`: đề xuất hiện là rename `update/` → `update-archive/`.
- `git grep "prd/update/2026-10-12-cache"` trong `docs/` không còn kết quả.
- Không đổi code, contract hay mock, nên không chạy test.

## Còn lại / rủi ro

- Source (contract, backend, hạ tầng, spec) làm theo plan, mỗi bước một entry riêng.
- Người vận hành phải thêm `RECOMMEND_CACHE_REDIS_URL` vào secret `vota-ha-backend-env`, dùng DB index chưa dùng, sau khi code được merge.
