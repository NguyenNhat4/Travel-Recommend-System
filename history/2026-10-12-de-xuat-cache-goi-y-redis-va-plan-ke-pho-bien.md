# Đề xuất cache gợi ý trên Redis và plan sửa gợi ý trang chủ, kệ "Phổ biến"

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation (tạo từ `origin/release-mvp-v2` bab57fa5)
- Trạng thái: dang dở (đề xuất chờ chốt; chưa sửa code)
- Phạm vi: docs

## Mục tiêu

Người dùng báo hai lỗi trên production (praxis.io.vn, nhánh `release-mvp-v2`):

1. Khối gợi ý ở trang chủ tính lại mỗi lần vào trang, không có cache hay tính trước, nên chậm và hay hết thời gian chờ ở frontend.
2. Tab "Tất cả" của kệ "Phổ biến tại các điểm đến Việt Nam" chỉ hiện vé máy bay; cần có thêm khách sạn, vé tham quan, combo, golf.

Người dùng yêu cầu đọc hiểu code rồi brainstorm, sau đó chốt hướng và cho viết đề xuất cùng plan. Phục vụ NFR-PERF-01, FR-REC-01, và giữ nguyên FR-REC-02 cùng AC-REC-01–03.

## File thay đổi

- `docs/prd/update/2026-10-12-cache-goi-y-tren-redis.md` — thêm: đề xuất thêm vai trò cache kết quả gợi ý cho Redis (`architecture.md` §1/§4, `deployment-plan.md` §2), trạng thái chờ chốt.
- `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` — thêm: plan ba giai đoạn (kệ Phổ biến, cold-start và timeout frontend; làm nhanh lượt tính khi trượt cache; cache Redis).
- `history/2026-10-12-de-xuat-cache-goi-y-redis-va-plan-ke-pho-bien.md` — thêm: entry này.

## Quyết định

Người dùng chốt trong trao đổi ngày 2026-10-12:

- Không đưa Weaviate về cùng vùng, không quét vector trong RAM.
- Cache gợi ý đặt trên Redis dùng chung (lệch PRD nên mới có đề xuất), không đặt trong tiến trình.
- Không hiện bản cũ ở frontend; được nới timeout.
- Kệ Phổ biến sửa bằng tham số `diversify=taxonomy` của `GET /products` (sửa contract trước).
- Không thêm tab Golf; golf gộp vào tab "Vé tham quan" và chung nhóm với attraction khi trộn.
- Lệch tương tự ở cold-start `_top_products` sửa cùng đợt.

Căn cứ chẩn đoán (đọc code `origin/release-mvp-v2` và GET chỉ đọc trên prod ngày 12/10):

- **Gợi ý chậm:** `RecommendForUser` đọc toàn bộ `cdp.events` của khách rồi gọi Weaviate Cloud (eu-central-1) 3–5 lượt nối tiếp từ VM ở asia-southeast1. Không có cache nào.
- **Timeout frontend:** bundle đang chạy trên prod dùng 10 s (`1e4`), không phải 3 s. Dòng 136 của `docs/spec/hop-dong-tich-hop-frontend.md` còn sót "3 giây".
- **Kệ Phổ biến:** `GET /products?sort=popular&availableOnly=true&limit=50` trên prod cho hạng 1–10 đều là vé máy bay. Món đầu tiên của các loại khác: khách sạn #11, vé tham quan #12, golf #19, combo #28. Nguyên nhân: lượt mua chuyến bay dồn về 113 tuyến, và `sort_items` không có bước trộn theo loại.

Phân định với PRD:

- Chỉ phần cache Redis lệch PRD.
- `diversify`, `taxonomy` nhiều giá trị, trần theo taxonomy ở cold-start, timeout frontend và nhãn loại trên thẻ chỉ sửa contract (cộng thêm) và spec. PRD không quy định kệ này; spec §4.8 đã ghi "tối đa 2 mỗi taxonomy".
- Nạp sẵn vector sản phẩm vào RAM chỉ đổi spec (`hop-dong-tich-hop-search-recommendation.md:321`) và docstring của port. Bước này vẫn chờ người dùng đồng ý, vì nó đổi thiết kế ghi trong `update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md`.

Nhánh: đã tạo `fix/recommendation` theo yêu cầu, trong worktree riêng `.claude/worktrees/home-recsys-cache`, vì worktree của phiên đang có thay đổi chưa commit của việc khác. `release-mvp-v2` ở máy local hơn origin 2 commit merge nhưng nội dung giống hệt.

## Kiểm tra

- Không đổi code, contract hay mock, nên không chạy `validate_contract.py` và không chạy test.
- Đã kiểm đối chiếu trong code các đường dẫn và số dòng dẫn trong plan (use case recommendation, listing, route catalog, `main.py`, `flights.py`, `.env.example`, e2e `navigation.spec.ts`).

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất `docs/prd/update/2026-10-12-cache-goi-y-tren-redis.md`. Giai đoạn 3 của plan chỉ bắt đầu sau khi đề xuất được chốt.
- Chờ người dùng xác nhận:
  - số timeout frontend (đề xuất 15 s);
  - thứ tự nhóm khi trộn tab "Tất cả" (đề xuất 2 ô mỗi nhóm: khách sạn → vé tham quan và golf → combo → vé máy bay);
  - có cho nạp sẵn vector vào RAM không.
- Số p95 trên cloud sau PR-A/PR-B chưa có. Log backend của VM HA chưa lên Cloud Logging (`history/2026-10-12-monitor-ha-log-va-nhan-nhom.md`), nên muốn đo ngay thì phải dùng log load balancer.
- Dữ liệu purchase tổng hợp dừng ở 05/10, nên cửa sổ 90 ngày của `sort=popular` sẽ co dần. Phương án trộn vẫn đúng khi điểm phổ biến về gần 0.
