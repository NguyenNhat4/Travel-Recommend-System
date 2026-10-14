# Kế hoạch: cache phản hồi catalog (đề xuất 1) và tính sẵn thứ tự sắp xếp (đề xuất 2)

- Ngày: 2026-10-13
- Nhánh: `release-mvp-v2` (repo chính)
- Trạng thái: đã duyệt (người dùng, trong chat, 13/10/2026). Tiến độ 14/10: đề xuất 2 (presort) và đề xuất 1 phần backend (LRU trong worker) đã làm, test pass (`history/2026-10-14-presort-va-cache-trang-catalog.md`). Chưa deploy. Chưa sửa contract, chưa đổi cấu hình Cloudflare (việc của người vận hành).
- Phục vụ: NFR-PERF-01 (danh mục và chi tiết sản phẩm p95 ≤ 100 ms; gợi ý p95 ≤ 250 ms) trong `docs/prd/requirements.md` §2.1. Hành vi `GET /products` theo `docs/spec/hop-dong-tich-hop-backend.md` §4.1.
- Không lệch PRD. Thứ tự kết quả, trường trả về và chu kỳ nạp catalog (15 phút, `catalog_refresh_seconds`) giữ nguyên. Không cần đề xuất `docs/prd/update/`.
- Nguồn số liệu: `docs/spec/load-test/2026-10-13-nguyen-nhan-khong-dat-500-rps.md` (báo cáo điều tra 13/10) và `docs/spec/2026-10-12-review-products-endpoint.md` (review `/products` 12/10). Hai file này còn nằm trong worktree `claude/stress-test-design-a749f4`, chưa commit vào nhánh này.

## 1. Bối cảnh (đã kiểm trong repo và trên staging)

| Mục | Hiện trạng | Nguồn |
|---|---|---|
| Header `/products` trong mã | Đã có: `public, max-age=60, s-maxage=300` (`PUBLIC_CATALOG_CACHE`) | `src/backend/app/api/v1/routes/catalog.py` |
| Header trong contract | Đã mô tả cho `/products`, `/products/{id}`, `/products/{id}/similar`. Chưa có cho `/destinations` và `/recommendations` | `src/shared/contracts/paths/catalog.yaml` dòng 12, 88, 114 |
| Edge (Cloudflare) | `cf-cache-status: DYNAMIC` ở cả hai lần gọi thử anonymous, không cache dù có header | Probe staging 13/10 |
| Cache trong backend | Chưa có. Mỗi request chạy lại lọc và sắp xếp | `application/catalog/use_cases.py` `ListProducts` |
| Chi phí sắp xếp | Sắp xếp toàn bộ ~4651 mục mỗi request, ~3,2 ms trong handler ~5,5 ms (đo máy dev) | Review 12/10 H1 |
| Vòng đời `ListProducts` | Dựng lại mỗi lần RecSys nạp bản mới (`build_catalog`, `_on_publish` trong `main.py`) | `main.py` |

Kết luận: phần header cho `/products` đã có trong mã và contract. Việc còn lại là Cloudflare chưa cache, backend chưa có cache, và hai endpoint còn thiếu header.

## 2. Đề xuất 1: cache phản hồi catalog ẩn danh

### 2.1. Edge (Cloudflare), ngoài repo

- Tạo cache rule cho `GET` ẩn danh: `/api/v1/products*`, `/api/v1/destinations`, `/api/v1/recommendations`.
- Rule phải loại request có cookie phiên hoặc header `Authorization`. Danh sách tên cookie lấy từ `src/frontend/src/services/server/bffSession.ts`.
- Nơi quản lý rule Cloudflare chưa xác định trong repo. Cần người vận hành xác nhận và tự đổi rule. Agent không đổi cấu hình bên ngoài repo khi chưa được duyệt.
- Kiểm sau khi bật: lần 1 `cf-cache-status: MISS`, lần 2 `HIT` với `age` tăng. Gửi kèm cookie phiên thì không `HIT`.

### 2.2. Cache trong `ListProducts` (lớp application)

- Khoá cache: `(destination, taxonomy đã sắp xếp, available_only, sort, limit, offset, diversify)`.
- Chỉ cache khi `parent_product_id is None` và `self.units is not None`. Đường đọc DB mỗi request (RecSys tắt) và đường tầng con không cache.
- Vòng đời: cache nằm trong instance `ListProducts`. Mỗi lần RecSys nạp bản mới, `build_catalog` dựng instance mới nên cache tự hết. Độ tươi tối đa vẫn là chu kỳ nạp 15 phút, như hiện tại.
- Giới hạn: LRU, tối đa `N` mục. Chọn `N` sau khi đo RSS (mục 4). Cấu hình qua biến môi trường, đặt `0` để tắt.
- Nội dung cache là `result` không có `requestId`. Route vẫn ghép `requestId` riêng cho từng request (đã có: `{**result, "requestId": ...}`), nên không trả nhầm id của request khác.
- Lỗi 400 được raise trước khi chạm cache, không bị cache.
- Không cần khoá: `ListProducts.__call__` không `await` giữa lúc đọc và ghi cache, và toàn bộ chạy trên event loop của một worker. Nếu sau này thêm `await` vào giữa hai bước này thì phải thêm khoá.
- Lớp: nằm trong `application`, không import `infrastructure` hay `api`. Kiểm bằng `src/backend/tests/architecture/test_import_rules.py`.

### 2.3. Header cho `/destinations` và `/recommendations`

- `/destinations`: thêm `Cache-Control: public, max-age=60, s-maxage=300` (không đọc người dùng).
- `/recommendations`: nếu không có principal (không token) thì `public, max-age=60, s-maxage=300`. Nếu có principal thì `private, no-store`, vì kết quả cá nhân hoá theo hành vi người dùng.
- Trước khi sửa code, cập nhật `src/shared/contracts/paths/catalog.yaml` và `paths/recommendations.yaml` (AGENTS §3). Chạy `validate_contract.py`.

### 2.4. Đo tỷ lệ hit

- Thêm bộ đếm hit và miss vào bộ đo cuộc gọi hiện có (`application/telemetry.py`, `GET /metrics`).
- Tỷ lệ URL lặp lại trên traffic thật chưa biết. Trước khi chọn `N`, đếm trên log `http.request` (trường `query`) của 24 giờ gần nhất ở staging và production. Đây là bước đầu tiên, không phải bước cuối.

## 3. Đề xuất 2: tính sẵn thứ tự sắp xếp

### 3.1. Thiết kế

- Trong `domain/catalog/listing.py`, thêm hàm thuần `precompute_orders(items, popularity) -> dict[str, list[ListingItem]]` cho ba sort `popular`, `price_asc`, `price_desc`. Hàm gọi `sort_items` một lần.
- `ListProducts.__post_init__` gọi `precompute_orders` khi `units` không `None`.
- Mỗi request: lọc trên danh sách đã sắp xếp bằng `filter_items` (giữ thứ tự), rồi cắt `[offset: offset+limit]`. Không gọi `sort_items` trong request.
- Đường `variants=True` (tầng con) giữ nguyên, vì danh sách con đọc từ DB theo từng request.
- Bộ nhớ: chỉ thêm ba danh sách tham chiếu, mỗi danh sách ~4651 phần tử. Không copy sản phẩm.

### 3.2. Vì sao kết quả giống hệt

- `sorted` là sắp xếp ổn định. Khi hai mục có cùng khoá (cùng điểm, cùng tên), chúng giữ thứ tự đầu vào.
- Lọc không đổi thứ tự tương đối của các mục còn lại.
- Hai thứ tự cho cùng kết quả: `sort(filter(items))` và `filter(sort(items))`. Vì vậy `total`, `results` và các trang nối tiếp không đổi.
- Kiểm chứng bằng test so sánh (mục 4), không chỉ dựa vào lập luận.

## 4. Kiểm thử và nghiệm thu

| Tầng | Kiểm | Tiêu chí |
|---|---|---|
| Domain (`tests/unit/domain/test_catalog_listing.py`) | So sánh `sort(filter(items))` với `filter(precomputed)` trên ≥ 1000 tổ hợp ngẫu nhiên: sort, destination, taxonomy, available_only, có khoá trùng | Danh sách giống hệt, kể cả thứ tự |
| Application (`tests/unit/application/test_catalog_use_cases.py`) | Hit trả cùng dữ liệu. `requestId` khác nhau giữa các request. Instance mới (sau nạp lại) không dùng cache cũ. Không cache khi `units is None` hoặc có `parent_product_id`. 400 không vào cache | Pass |
| Contract (`tests/contract/test_catalog_contract.py`, `validate_contract.py`) | Header mới khớp contract sau khi cập nhật | Pass |
| Architecture (`tests/architecture/`) | Quy tắc phụ thuộc | Pass |
| Bộ nhớ | RSS của worker trước và sau khi điền cache đầy `N` mục | RSS tăng không quá 10% trên giới hạn 3 GiB của container backend |
| Benchmark | Handler `ListProducts` với 4651 mục tổng hợp, trước và sau đề xuất 2. Cache hit so với miss | Trước khi làm: đo lại baseline. Kỳ vọng giảm ~3 ms handler cho đề xuất 2 (ước lượng từ số đo sort) |
| Độ phủ | `domain` và `application` | ≥ 80% (DoD) |

Nghiệm thu trên staging (sau khi được duyệt và có 2 VM ổn định, xem mục 6):
- Chạy `ops/loadtest/stress/read.js` ở 100 rps, hai chế độ: `CACHE_BUST=1` (đo origin và cache trong backend) và `CACHE_BUST=0` (đo đường đi qua edge).
- Ghi báo cáo mới trong `docs/spec/load-test/`. So sánh với R1 (13/10).
- Mục tiêu: p95 `/products` và `/products/{id}` ≤ 100 ms (NFR-PERF-01). Đây là mục tiêu, chưa phải cam kết. Mức đạt phụ thuộc tỷ lệ hit đo được ở mục 2.4.
- Không tăng 5xx so với R1.

## 5. Rủi ro và cách lùi

| Rủi ro | Cách giảm | Cách lùi |
|---|---|---|
| Cache công khai nhầm dữ liệu cá nhân | Cache rule loại cookie và Authorization. `/recommendations` có principal thì `private, no-store`. Test cho cả hai nhánh | Tắt rule Cloudflare. Đặt `CATALOG_RESPONSE_CACHE_SIZE=0` |
| Bộ nhớ worker tăng | Giới hạn `N` theo đo RSS. Đo trước khi bật | Đặt `N = 0` |
| Giá cũ | Đã có: chu kỳ nạp 15 phút và `s-maxage=300` trong contract. Không thêm độ cũ mới ngoài hai giới hạn này | Không cần |
| Miss hàng loạt sau mỗi lần nạp (mỗi worker dựng lại cache) | Đo độ trễ ngay sau nạp. Nếu xấu thì cân nhắc làm nóng cache | Không cần |
| Thứ tự khác nhau do khoá trùng | Test so sánh ở mục 4 | Revert đề xuất 2 |

Mỗi VM tự có cache riêng. Không cần đồng bộ giữa các VM. Thay đổi triển khai qua pipeline hiện có (`slot-deploy`), không chạy tay.

## 6. Thứ tự thực hiện

1. Đọc tài liệu theo AGENTS §1: `docs/spec/hop-dong-tich-hop-backend.md` §4.1, `docs/prd/architecture.md` §2, `docs/prd/api-contract.md` phần cache, `docs/prd/requirements.md` NFR-PERF-01. Đọc đầy đủ các mục liên quan trước khi sửa mã.
2. **Người dùng duyệt kế hoạch này.**
3. Làm đề xuất 2 trước: domain, test so sánh, benchmark trước và sau. Không đổi contract, không cần Cloudflare.
4. Cập nhật contract cho `/destinations` và `/recommendations`. Chạy `validate_contract.py`.
5. Làm đề xuất 1 phần origin: cache trong `ListProducts`, bộ đếm hit và miss, test bộ nhớ.
6. Cloudflare cache rule: người vận hành làm, không phải agent. Kiểm `cf-cache-status`.
7. Ghi entry `history/` cho từng bước (AGENTS §5). Cập nhật `docs/plan/` này khi có số liệu.
8. Deploy staging qua pipeline, sau khi người dùng duyệt. Đo lại (mục 4), ghi báo cáo mới.

Lưu ý: bước 3 và 5 là thay đổi trong `src/backend/`, nên cần entry `history/` và đối chiếu PRD trước khi sửa. Bước 4 là thay đổi contract, nên phải sửa OpenAPI trước code (AGENTS §3).

## 7. Câu hỏi cần người dùng trả lời

1. Duyệt đề xuất 2 làm trước không?
2. Ai quản lý cache rule Cloudflare, và có cho phép đổi cấu hình bên ngoài repo không?
3. Đo tỷ lệ hit bằng log staging (chủ yếu là test) hay cần log production? Log production ảnh hưởng quyết định `N` và cách đọc mục tiêu p95.
4. Chấp nhận mức bộ nhớ cache nào trên mỗi worker?

## 8. Ghi chú về review 12/10

Mục H3 trong review 12/10 ghi `/products` chưa có `Cache-Control`. Trong mã hiện tại và contract đã có header này. Phần còn thiếu nằm ở Cloudflare và ở hai endpoint `/destinations` và `/recommendations`. Cập nhật lại mục H3 trong review để tránh làm trùng.
