# Kế hoạch cache phản hồi catalog và tính sẵn thứ tự sắp xếp

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: release-mvp-v2
- Trạng thái: dang dở (chỉ có kế hoạch, chờ người dùng duyệt; chưa sửa mã, chưa sửa contract, chưa đổi cấu hình Cloudflare)
- Phạm vi: docs

## Mục tiêu

Lập kế hoạch cho hai đề xuất giảm thời gian phản hồi của `GET /products` và các endpoint catalog công khai khi tải cao. Người dùng nhận xét các đề xuất trước đó chỉ tập trung vào số lượng VM và health check, không giải quyết thời gian xử lý mỗi request.

## File thay đổi

- `docs/plan/2026-10-13-cache-va-presort-catalog.md` — thêm: kế hoạch cho đề xuất 1 (cache phản hồi) và đề xuất 2 (tính sẵn thứ tự).
- `history/2026-10-13-ke-hoach-cache-va-presort-catalog.md` — thêm: entry này.

Không đổi mã, contract, DDL hay cấu hình nào.

## Quyết định

- **Không lệch PRD.** Thứ tự kết quả, trường trả về và chu kỳ nạp catalog (15 phút) giữ nguyên. Không cần `docs/prd/update/`.
- **Header `Cache-Control` cho `/products` đã có trong mã và contract.** Review 12/10 ghi là chưa có, nên kế hoạch ghi rõ để không làm trùng. Phần còn thiếu: Cloudflare vẫn trả `DYNAMIC`, `/destinations` và `/recommendations` chưa có header.
- **Cache trong `ListProducts` gắn với instance của nó.** Mỗi lần RecSys nạp bản mới, `build_catalog` dựng instance mới, nên cache tự hết hạn đúng lúc catalog đổi.
- **Đề xuất 2 cho kết quả giống hệt.** Lý do: sắp xếp ổn định và lọc không đổi thứ tự tương đối. Sẽ kiểm bằng test so sánh, không dựa vào lập luận.
- **Cloudflare không đổi từ repo.** Cần người vận hành xác nhận nơi quản lý rule và tự đổi.

## Kiểm tra

- Đã kiểm trên staging: `curl -I` tới `/api/v1/products?limit=20&sort=popular` cho `cache-control: public, max-age=60, s-maxage=300` và `cf-cache-status: DYNAMIC` ở hai lần gọi.
- Đã đọc: `src/backend/app/api/v1/routes/catalog.py`, `src/backend/app/application/catalog/use_cases.py` (`ListProducts`), `src/backend/app/domain/catalog/listing.py`, `src/backend/app/main.py` (`RecsysRefresher`, `build_catalog`), `src/backend/app/api/v1/routes/recommendations.py`, `src/shared/contracts/paths/catalog.yaml`, `docs/prd/architecture.md` §2, `docs/prd/requirements.md` (NFR-PERF-01).
- Chưa chạy: test, benchmark, `validate_contract.py`. Không có thay đổi để kiểm.

## Còn lại / rủi ro

- Chờ người dùng duyệt kế hoạch và trả lời bốn câu hỏi ở mục 7 của kế hoạch.
- Tỷ lệ URL lặp lại trên traffic thật chưa biết. Quyết định kích thước cache phụ thuộc số liệu này.
- Mục tiêu p95 ≤ 100 ms ở 100 rps chưa được đảm bảo, phụ thuộc tỷ lệ hit đo được.
- Hai báo cáo `docs/spec/load-test/2026-10-13-nguyen-nhan-khong-dat-500-rps.md` và `docs/spec/2026-10-12-review-products-endpoint.md` còn nằm trong worktree `claude/stress-test-design-a749f4`, chưa commit vào nhánh này.
