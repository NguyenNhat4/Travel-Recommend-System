# Job cào dời ngày vé máy bay vào cửa sổ 30 ngày, vé luôn đặt được như hạng phòng

- Ngày: 2026-10-06
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-10-06
- PRD bị ảnh hưởng: `docs/prd/data-model.md` §3.1 (đoạn "Vé có báo giá theo ngày cố định")
- Mã FR/NFR: FR-CAT-01, FR-CAT-03

## Lý do

Team Web (daily 06/10) báo dữ liệu vé máy bay không đủ để làm và demo. Đo trên DB VM ngày 06/10:

- Vé ngày cố định của job cào giữ ngày thật, nên ra khỏi cửa sổ là tắt: 540 vé khứ hồi thật có giá đang tắt, 62 vé bay 01–04/11 hết hạn báo giá từ 02/10.
- Vé khứ hồi thật còn đặt được chỉ ở 6 điểm đến (TP.HCM, Hà Nội, Đà Nẵng, Phú Quốc, Nha Trang, Đà Lạt); các điểm khác chỉ có 6–16 vé một chiều.
- Trang tìm kiếm của Trip chặn crawler, nên không cào thêm báo giá mới đủ dày để bù.

Seed demo đã dời ngày vé vào cửa sổ từ 29/09 (`update-archive/2026-09-29-seed-demo-doi-ngay-ve-khu-hoi.md`). Hạng phòng của job cào cũng đã lấy nguyên cửa sổ, giá giữ làm giá tham khảo (02/10). Đề xuất này áp cùng quy tắc của seed cho job cào.

## Nội dung đề xuất

`docs/prd/data-model.md` §3.1, đoạn "Vé có báo giá theo ngày cố định":

- Hiện tại: "Job cào (dữ liệu thật) không dời ngày của vé này; ngoài cửa sổ hoặc hết hạn báo giá thì không đặt được. Riêng seed demo (`make demo-db`, snapshot có version): vé có ngày đi ngoài cửa sổ được dời vào cửa sổ như vé không cố định ngày (`as_of + crc32(productId) % 30`), …"
- Thay bằng: "Job cào và seed demo dùng cùng quy tắc: vé có ngày đi ngoài cửa sổ (đã bay, sau cửa sổ, hoặc hết hạn báo giá) được dời vào cửa sổ như vé không cố định ngày (`as_of + crc32(productId) % 30`), …" (phần còn lại của câu giữ nguyên: hai chặng dời cùng số ngày, giữ giờ bay và `stayDays`, `returnDate` và ngày trong tên/mô tả đổi theo; vé có ngày đi trong cửa sổ giữ ngày thật; giá giữ nguyên từ nguồn và chỉ là giá tham khảo; `priceValidUntil` giữ nguyên nên `fareClasses` báo `EXPIRED` khi hết hạn nhưng vé vẫn đặt được).
- Thêm: "Job cuộn cửa sổ mỗi ngày: vé đã dời giữ ngày mới cho tới khi ngày đó qua, rồi được dời lại. Lượt cào lấy được báo giá mới thì ngày và giá thật thay thế."

Vé Thương gia mô phỏng chép ngày, `available` và cửa sổ từ vé gốc (data-model §3.1), nên tự theo quy tắc mới. Không đổi contract, 13 cột hay ID sản phẩm.

## Ảnh hưởng

- Có lợi: mọi vé thật có giá (khoảng 1.100 vé thật cùng khoảng 1.100 vé mô phỏng trên VM) luôn đặt được, ngày nằm trong 30 ngày tới, giống hạng phòng.
- Đánh đổi (grounding, NFR-REL-01): giá của vé bị dời là giá nguồn báo cho ngày gốc, không phải ngày mới. Giá vẫn lấy từ nguồn (không tự tạo giá). `priceValidUntil` giữ nguyên nên `fareClasses` có thể báo `EXPIRED`.
- Lịch bay hiển thị không còn là lịch thật của hãng cho ngày đó.

## Thay đổi source sau khi chốt

- `src/data_collection/fresh_catalog_db.py` `apply_window`: vé `fixedDepartureDate` dùng đường dời ngày của seed (`load_products.seed_fixed_flight_date` và hàm dời hai chặng) thay cho `fixed_flight_window`. Vé có giá luôn `available = true`; bỏ `windowClosed` cho vé.
- Job ghi thêm `name`/`description` của vé đã dời (câu UPDATE hiện chỉ ghi attributes, giá, available, cửa sổ).
- `src/data_collection/seed/load_products.py`: bỏ nhánh `real_flight_dates` của `daily.py` nếu không còn dùng.
- Test trong `src/data_collection/tests/` (job dời đủ hai chặng, giữ `stayDays`, giữ ngày khi đã trong cửa sổ, dời lại khi ngày qua).
- `docs/spec/data-collection/schema.md` (dòng `fixedDepartureDate`, `windowClosed`), `docs/spec/MOCK_DATA_SPEC.md` §2.1, `src/data_collection/README.md`.
- Áp lên DB VM: chạy `maintain_catalog` một lần sau deploy, hoặc để lượt cron kế tiếp tự áp.

## Điều chỉnh khi chốt (2026-10-06)

- Người chốt: "không cần ghi hiển thị giá tham khảo" → không thêm yêu cầu hiển thị nào cho FE; vé dời ngày dùng đúng các trường hiện có.
