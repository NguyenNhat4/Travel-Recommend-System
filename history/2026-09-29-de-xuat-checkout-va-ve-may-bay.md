# Đề xuất PRD: checkout nhiều bước và luồng vé máy bay

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: dang dở — 5 đề xuất đang chờ người dùng chốt
- Phạm vi: docs

## Mục tiêu

Người dùng duyệt mock giao diện checkout (https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji, dựng theo spec `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` và tham khảo Mobbin), rồi yêu cầu soạn các đề xuất lệch PRD để chốt trước khi sửa spec, contract, DDL và code (`AGENTS.md` §8). Mock gồm checkout ba bước, người lớn/trẻ em, và luồng vé máy bay mở rộng: thông tin hành khách bay, em bé đi kèm, hạng vé, khứ hồi, chọn ghế, hành lý, suất ăn, bảo hiểm, trang đơn có xuất vé.

## File thay đổi

- `docs/prd/update/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` — thêm: đề xuất nền. Checkout ba bước, đoàn khách 1–9 người, mốc tuổi 12, giá trẻ em hợp lệ, bảng `app.booking_travelers`, sửa `line_total`; FR-BKG-08, AC-BKG-05…07 mới; sửa FR-BKG-02, `user-flow.md` §2, §3.3, §4.3, §4.4, `data-model.md` §2.2.
- `docs/prd/update/2026-09-29-ve-may-bay-thong-tin-hanh-khach.md` — thêm: danh xưng, họ và tên tách không dấu, ngày sinh, quốc tịch, CCCD/hộ chiếu, em bé có người lớn đi kèm; FR-BKG-09, NFR-SEC-04 (bảo vệ số giấy tờ), AC-BKG-08.
- `docs/prd/update/2026-09-29-ve-may-bay-hang-ve-va-khu-hoi.md` — thêm: hạng vé theo chặng từ `attributes.fareClasses`, gộp hai chặng ngược chiều thành khứ hồi; sửa FR-CAT-03, `data-model.md` §3.1; FR-BKG-10, AC-BKG-09.
- `docs/prd/update/2026-09-29-ve-may-bay-dich-vu-them.md` — thêm: hành lý ký gửi và chọn chỗ ngồi theo bảng giá nạp sẵn; suất ăn và bảo hiểm để sau; FR-BKG-11, AC-BKG-10; sửa `project-brief.md` §4.1, §4.2.
- `docs/prd/update/2026-09-29-ve-may-bay-xuat-ve-mo-phong.md` — thêm: trạng thái xuất vé, PNR và số vé mô phỏng trên trang đơn; sửa FR-BKG-04, thêm FR-BKG-12.

## Quyết định

- **Tách năm đề xuất thay vì một**, để người dùng chốt từng phần. Mức rủi ro khác nhau: đề xuất nền sửa lỗi tính tiền có thật; thông tin bay thêm dữ liệu nhạy cảm; hạng vé và dịch vụ thêm cần dữ liệu Data chưa có; xuất vé chạm ranh giới ngoài phạm vi (`project-brief.md` §4.2). Các đề xuất vé máy bay ghi rõ phụ thuộc vào đề xuất nền.
- **Đề xuất agent chọn các phương án bám PRD hiện hành khi có xung đột:**
  - Giữ FR-BKG-07 (hoàn 100% trước hạn) cho vé máy bay, không hiện điều kiện "Không hoàn" theo hạng. Mock đang hiện điều kiện này và cần sửa nếu chốt.
  - Không hiện số ghế còn theo thời gian thực.
  - Tình trạng ghế trên sơ đồ và xuất vé chỉ là mô phỏng, có nhãn.
  - Không bán bảo hiểm (sản phẩm của bên thứ ba).
- **Mã FR/AC mới** (FR-BKG-08…12, NFR-SEC-04, AC-BKG-05…10) đều ghi "cần cấp mã"; người chốt có thể đánh lại số.
- Giá, sơ đồ ghế, thực đơn và quyền lợi bảo hiểm trong mock là minh hoạ; các đề xuất ghi rõ nguồn dữ liệu cần có trước khi code.

## Kiểm tra

- Chỉ thêm tài liệu, không đổi code, contract, DDL; không chạy `validate_contract.py`, `db/verify.sql` hay test.
- Đã đối chiếu trích đoạn PRD trong đề xuất với `requirements.md` §1.1, §1.5, §2.3, §3; `user-flow.md` §2, §3.3, §4.3, §4.4; `project-brief.md` §4; `data-model.md` §2.2, §3.1, §4.1 hiện tại.
- Dữ liệu dẫn trong đề xuất lấy từ snapshot `src/data_collection/snapshots/2026-09-23/products.jsonl.gz`:
  - VJ601 CXR 16:20 → SGN 17:25; VJ1602 SGN 11:00 → CXR 12:00, 661.000 ₫.
  - `roundTripFrom` chỉ có ở sản phẩm cấp tuyến.
  - Chuyến bay không có khoá hạng vé hay hành lý.
- Định dạng mã đơn `VOTA-YYYYMMDD-XXXX` trong mock lấy từ `src/shared/mocks`.

## Còn lại / rủi ro

- **Chờ người dùng chốt** năm đề xuất. Chưa chốt thì không sửa PRD, spec, contract, DDL hay code.
- **Spec `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` bị cụt:** file dừng ở §9.2 (776 dòng), thiếu §10–§16 (Frontend, trường hợp biên, kiểm thử và AC, kế hoạch, quyết định D1–D11, lệch PRD, tham khảo Mobbin), dù entry `2026-09-29-spec-checkout-nhieu-buoc-hanh-khach.md` ghi đã viết. Đề xuất nền dựng lại quyết định từ các mã D còn nhắc trong spec; không tìm thấy nội dung D7. Cần viết lại các mục thiếu sau khi chốt.
- Nếu chốt phương án giữ FR-BKG-07 cho vé máy bay, mock cần bỏ dòng "Không hoàn tiền" và "Hoàn vé" trong điều kiện hạng.
- `src/frontend/package.json` và `package-lock.json` đã bị sửa từ trước, không thuộc thay đổi này.
