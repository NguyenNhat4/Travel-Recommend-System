# Vé hạng Thương gia mô phỏng cho seed demo

- Ngày: 2026-09-30
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1 FR-CAT-01 (dòng "Hạng vé có bằng chứng… không suy hạng hoặc tự tạo giá"),
  `docs/prd/data-model.md` §3 (đoạn vé báo giá theo ngày cố định)
- Mã FR/NFR: FR-CAT-01, FR-CAT-03; liên quan NFR-REL-01

## Lý do

Team FE cần hạng Thương gia để làm và demo UI chọn hạng (`fareClasses`). Hiện chưa có nguồn hợp lệ nào cho giá thương gia kèm
số hiệu chuyến:

- trip.com chỉ ghi hạng Phổ thông trên trang tuyến; trang tìm kiếm có hạng bị `robots.txt` cấm;
- booking.com và trang đặt vé Vietnam Airlines (`booking.vietnamairlines.com`) chặn bot;
- trang tuyến công khai của Vietnam Airlines có giá thương gia nhưng không có số hiệu chuyến.

Luồng cào hạng thương gia (API đối tác…) làm sau. Trước mắt cần dữ liệu dùng được cho demo.

## Nội dung đề xuất

`docs/prd/requirements.md` FR-CAT-01, câu "không đổi ID vé cũ, không suy hạng hoặc tự tạo giá" → thêm:

> Ngoại lệ duy nhất: seed demo (`make demo-db`, snapshot có version) sinh thêm biến thể hạng Thương gia mô phỏng cho vé máy bay
> để demo UI chọn hạng. Dữ liệu thật (job cào, DB trên VM) không bao giờ có vé mô phỏng.

`docs/prd/data-model.md` §3, đoạn vé báo giá ngày cố định → thêm:

> **Vé Thương gia mô phỏng (chỉ seed demo).**
>
> - Nguồn: mỗi vé máy bay thật có số hiệu chuyến (khứ hồi và một chiều, `level: flight`) sinh thêm một sản phẩm cùng hành trình,
>   `cabinClass: BUSINESS`.
> - Giá = giá vé thật × 2,65, làm tròn nghìn đồng. 2,65 là tỉ lệ Thương gia / Phổ thông trên bảng "Giá vé tham khảo" công khai
>   của Vietnam Airlines, chặng Hà Nội – TP.HCM, cả một chiều lẫn khứ hồi.
> - `sourceRef` là `demo:business:<sourceRef vé gốc>`; `productId` sinh cố định từ `sourceRef` này.
> - Đánh dấu:
>   - `attributes.fieldSources.unitPrice = "mô phỏng"`;
>   - `attributes.simulated = true`;
>   - tên có hậu tố "(giá minh hoạ)".
> - Các trường khác (ngày, giờ, chiều về, `priceValidUntil`) chép từ vé gốc.

Không đổi contract: `fareClasses` đã có `code: BUS` / "Thương gia". Không đổi 13 cột, ID vé cũ hay cách thêm giỏ.

## Ảnh hưởng

- Có lợi:
  - FE có đủ hai hạng Phổ thông / Thương gia trên cùng thẻ hành trình, ở mọi ngày seed;
  - khoảng 290 vé khứ hồi và 507 vé một chiều / vé cũ có thêm hạng Thương gia.
- Đánh đổi (grounding):
  - giá thương gia không phải giá nguồn báo;
  - AI Assistant vẫn chỉ dùng sản phẩm có trong catalog (NFR-REL-01 giữ), nhưng có thể đề xuất vé mô phỏng trên máy demo.
  - Đánh dấu `simulated` và hậu tố tên để FE / agent nhận ra.
- Không ảnh hưởng dữ liệu thật: `daily.py` nạp bằng `seed --catalog-only --real-flight-dates`, cờ này tắt việc sinh vé mô phỏng.

## Thay đổi source sau khi chốt

- `src/data_collection/seed/load_products.py`: sinh biến thể Thương gia mô phỏng trong `convert` khi không bật
  `real_flight_dates`.
  - Snapshot giữ nguyên dữ liệu thật; không cần snapshot mới.
- Test: `src/data_collection/tests/`:
  - sinh đúng giá, ID cố định, đánh dấu;
  - `--real-flight-dates` không sinh;
  - `fareClasses` gom ECO + BUS cùng thẻ.
- `docs/spec/MOCK_DATA_SPEC.md` §2 bước 1, `docs/spec/data-collection/schema.md` (khoá `simulated`),
  `src/data_collection/snapshots/README.md`, `docs/guide/hien-thi-hang-ve-may-bay.md`.
