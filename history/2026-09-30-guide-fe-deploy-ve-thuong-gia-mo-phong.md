# Cập nhật guide FE và deploy cho vé Thương gia (thật, mô phỏng) và khứ hồi 3/5/7

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người yêu cầu: "cập nhật vào 2 file của doc guild của FE và deploy". Nối tiếp `2026-09-30-ap-dung-ve-thuong-gia-mo-phong.md`
và `2026-09-30-khu-hoi-3-5-7-va-thuong-gia-nhieu-ngay.md`. Phục vụ FR-CAT-01, FR-CAT-03, NFR-REL-01; không đổi PRD/contract.

## File thay đổi

- `docs/guide/hien-thi-hang-ve-may-bay.md` — sửa: ví dụ `fareClasses` thêm phần tử `BUS`; số sản phẩm seed 12.515; bỏ câu
  "Chưa có giá thương gia"; mục mới "Vé Thương gia" (bảng thật / mô phỏng, cách nhận biết qua `productId` →
  `attributes.simulated` hoặc hậu tố tên, bắt buộc nhãn "Giá minh hoạ", trạng thái theo vé gốc, vé thật thắng, điều kiện có trên
  staging).
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: dòng CI/CD trong bảng (CD không tự cào, khởi động lại monitor); điều kiện VM
  nêu `SIMULATED_BUSINESS_FARES`; thay mục cuối lỗi thời (CD import 43 vé, yêu cầu cào full) bằng mục thương gia / khứ hồi 3/5/7 /
  quota (giới hạn robots + 432, `tripFlights.fareMinutes`); mục mới "Vé Thương gia mô phỏng trên VM" (bật, chạy một lần bằng
  image fresh hoặc qua tunnel, kiểm SQL, tắt).
- `history/2026-09-30-guide-fe-deploy-ve-thuong-gia-mo-phong.md` — thêm: entry này.

## Quyết định

- Đối chiếu contract `schemas/catalog.yaml`: `FareClass` không có cờ mô phỏng; `ProductSummary`/`ProductDetail` có `name` và
  `attributes` (backend trả `attributes` qua `public_attributes`), nên FE nhận biết bằng `productId` → sản phẩm.
- Tên vé Thương gia thật lấy từ `normalise.trip_business_products`: "… — Thương gia (YYYY-MM-DD)".

## Kiểm tra

- `docker build -f Dockerfile.fresh-catalog` (tag local `vota-fresh-catalog:simbiz-check`): exit 0. Trong image:
  `python -m src.data_collection.seed.simulated_business --help` chạy; import `fresh_catalog_db` và
  `data_collection.seed.simulated_business`, `database`: ok. Chưa chạy lệnh ghi lên DB VM.
- Ví dụ giá trong guide FE: 1.320.000 × 2,65 = 3.498.000.

## Còn lại / rủi ro

- Deploy tự động chỉ cập nhật code; bật vé mô phỏng trên VM cần thêm `SIMULATED_BUSINESS_FARES=1` vào env VM (hoặc đề xuất đổi
  mặc định — chờ người yêu cầu chọn).
- Chưa commit.
