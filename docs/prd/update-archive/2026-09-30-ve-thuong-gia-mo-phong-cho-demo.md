# Vé hạng Thương gia mô phỏng cho demo (cả DB VM)

- Ngày: 2026-09-30 (sửa lần 1 cùng ngày: mở rộng từ seed demo local sang DB VM)
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-09-30
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1 FR-CAT-03 (khi áp dụng: câu nằm ở FR-CAT-03, không phải FR-CAT-01; câu "không đổi ID vé cũ, không suy hạng hoặc tự tạo giá"),
  `docs/prd/data-model.md` §3 (đoạn vé báo giá theo ngày cố định)
- Mã FR/NFR: FR-CAT-01, FR-CAT-03; liên quan NFR-REL-01

## Lý do

Team web cần hạng Thương gia ở nhiều ngày bay để làm và demo UI chọn hạng (`fareClasses`). Web đọc từ DB trên VM.

Hiện chỉ có 43 vé Thương gia thật, cùng bay ngày 15/10/2026. Không có nguồn hợp lệ để cào tự động thêm (kiểm 30/09/2026):

- trang tìm vé của trip.com (`/flights/showfarefirst*`, `/flights/ShowFareNext*`) bị `robots.txt` cấm, và trả `HTTP 432`
  ("whaleguard block") cho trình duyệt tự động;
- booking.com và trang đặt vé Vietnam Airlines chặn bot;
- trang tuyến công khai của Vietnam Airlines có giá thương gia nhưng không có số hiệu chuyến.

Bản trước của đề xuất chỉ cho seed demo local có vé mô phỏng. Bản này cho cả DB VM, vì web đọc từ đó.

## Nội dung đề xuất

`docs/prd/requirements.md` FR-CAT-01, sau câu "không đổi ID vé cũ, không suy hạng hoặc tự tạo giá" → thêm:

> Ngoại lệ duy nhất: vé Thương gia mô phỏng cho demo UI chọn hạng, sinh từ vé thật, luôn gắn nhãn "giá minh hoạ" và
> `simulated: true` (xem `data-model.md` §3). Bật bằng cấu hình; tắt thì các vé này không đặt được nữa.

`docs/prd/data-model.md` §3, đoạn vé báo giá ngày cố định → thêm:

> **Vé Thương gia mô phỏng (demo).**
>
> - Bật bằng biến môi trường `SIMULATED_BUSINESS_FARES=1` (mặc định tắt) cho job cào trên VM (fresh và `daily.py`); seed
>   demo local (`make demo-db`) luôn bật.
> - Sau mỗi lần nạp catalog: mỗi vé máy bay thật `level: flight` có số hiệu chuyến (một chiều và khứ hồi), hạng khác
>   `BUSINESS`/`FIRST`, sinh một vé cùng hành trình, `cabinClass: BUSINESS`.
>   - Không sinh khi đã có vé Thương gia thật cùng hành trình và ngày: giá thật luôn thắng.
> - Giá = giá vé gốc × 2,65, làm tròn nghìn đồng. 2,65 là tỉ lệ Thương gia / Phổ thông trên bảng "Giá vé tham khảo" công
>   khai của Vietnam Airlines, chặng Hà Nội – TP.HCM (3.957.000 / 1.494.000 một chiều; 7.914.000 / 2.988.000 khứ hồi).
> - `sourceRef` là `demo:business:<sourceRef vé gốc>`; `productId` sinh cố định từ `sourceRef` này.
> - Đánh dấu: `attributes.simulated = true`; `attributes.fieldSources.unitPrice = "mô phỏng"`; tên có hậu tố
>   "(giá minh hoạ)"; mô tả ghi rõ giá minh hoạ, không phải giá nguồn báo.
> - Ngày, giờ, chiều về, `available`, cửa sổ đặt chỗ và `priceValidUntil` chép từ vé gốc, cập nhật lại mỗi lần nạp.
> - Vé gốc hết đặt được, có vé Thương gia thật thay thế, hoặc tắt cấu hình → vé mô phỏng chuyển `available = false`. Không
>   xoá dòng, vì đơn cũ có thể trỏ tới.

Không đổi contract: `fareClasses` đã có `code: BUS` / "Thương gia", và FE nhận ra vé mô phỏng qua hậu tố tên. Không đổi 13
cột, ID vé cũ hay cách thêm giỏ.

## Ảnh hưởng

- Có lợi: web có hai hạng Phổ thông / Thương gia trên cùng hành trình ở mọi ngày có vé thật. DB VM hiện có khoảng 1.053 vé
  (560 khứ hồi, 493 một chiều) → thêm tối đa khoảng 1.053 vé mô phỏng.
- Đánh đổi (grounding):
  - giá thương gia mô phỏng không phải giá nguồn báo. Giá thật có thể lệch xa: ví dụ HAN–SGN đi 10/10 về 13/10, Trip báo
    Phổ thông 2.083.000₫ và Thương gia 21.621.000₫ khứ hồi (khoảng ×10, vé tách hai hãng);
  - AI Assistant vẫn chỉ dùng sản phẩm có trong catalog (NFR-REL-01 giữ), nhưng có thể đề xuất và cho đặt vé mô phỏng trên
    DB VM (thanh toán Stripe test).
- Tắt được: đặt `SIMULATED_BUSINESS_FARES=0` (hoặc bỏ biến) trong env job trên VM; lần nạp kế tiếp khoá toàn bộ vé mô phỏng.

## Thay đổi source sau khi chốt

- Module sinh vé mô phỏng trong `src/data_collection/seed/` dùng chung cho seed demo và bước nạp DB của job
  (`src/data_collection/fresh_catalog_db.py`, `src/data_collection/daily.py`); đọc `SIMULATED_BUSINESS_FARES`.
- `src/data_collection/.env.example`: thêm biến. Env file trên VM (`/etc/vota/fresh-catalog.env`): người có quyền VM bật.
  Muốn có ngay thì chạy lệnh sinh một lần qua tunnel DB (insert/update chỉ các dòng `demo:business:*`).
- Test `src/data_collection/tests/`: giá, ID cố định, đánh dấu; vé thật thắng; tắt cấu hình thì khoá; `fareClasses` gom ECO +
  BUS cùng thẻ.
- Tài liệu: `docs/spec/MOCK_DATA_SPEC.md` §2 bước 1, `docs/spec/data-collection/schema.md` (khoá `simulated`),
  `src/data_collection/snapshots/README.md`, `docs/guide/hien-thi-hang-ve-may-bay.md`, `docs/guide/ve-thuong-gia-va-index-cho.md`.
