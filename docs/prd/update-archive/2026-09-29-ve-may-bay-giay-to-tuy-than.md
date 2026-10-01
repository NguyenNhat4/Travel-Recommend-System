# Vé máy bay: thu thông tin giấy tờ tuỳ thân hành khách (danh xưng, quốc tịch, CCCD/hộ chiếu)

- Ngày: 2026-09-29
- Người đề xuất: mihhquan (yêu cầu) / Claude Code (soạn đề xuất)
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.5, §3 · `docs/prd/data-model.md` §2.2 (hành khách)
- Mã FR/NFR: FR-BKG-13 (mới — cần cấp mã)
- Phụ thuộc: `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (đảo ngược dòng loại trừ ở §3.3); không phụ thuộc dữ liệu catalog (khác với đề xuất hạng vé)

Mock giao diện tham khảo (đã có sẵn thiết kế trường, validate): https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji — khối "Thông tin cho vé máy bay" trong mỗi thẻ hành khách ở bước ① Hành khách.

## Lý do

`docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §3.3 (dòng 105) ghi rõ: *"Giấy tờ tuỳ thân, quốc tịch, giới tính, số hộ chiếu... Catalog chỉ có chuyến bay nội địa và hệ thống không xuất vé thật"* là **ngoài phạm vi**. Đây là quyết định spec-level, chưa từng đưa vào PRD (đã grep `requirements.md`, `project-brief.md`, `user-flow.md`, `data-model.md`: không có mã FR/NFR nào nhắc tới CCCD/hộ chiếu/quốc tịch/danh xưng).

Người dùng (mihhquan) muốn giao diện checkout thật giống hệt bản mock đã duyệt trước đó, bản mock có sẵn khối nhập CCCD/hộ chiếu/quốc tịch/danh xưng cho hành khách khi giỏ có vé máy bay, với lý do "hãng bay yêu cầu". Vì catalog thật vẫn chỉ có chuyến bay nội địa và hệ thống không nối hãng bay thật (không đổi §4.2 project-brief), các trường này **không dùng để xuất vé thật** — chỉ mô phỏng trải nghiệm nhập liệu đầy đủ như OTA thật, lưu kèm đơn để hiển thị lại ở trang xác nhận (phối hợp FR-BKG-12 xuất vé mô phỏng).

## Nội dung đề xuất

### `requirements.md` §1.5, thêm

> - **FR-BKG-13 (Thông tin giấy tờ hành khách cho vé máy bay):** Khi giỏ có vé máy bay, mỗi hành khách khai thêm: danh xưng (Ông/Bà/Cô với người lớn; Bé trai/Bé gái với trẻ em, em bé), quốc tịch, và với người lớn: loại giấy tờ (CCCD hoặc hộ chiếu), số giấy tờ, ngày hết hạn (nếu là hộ chiếu). Trẻ em, em bé dùng giấy khai sinh, không nhập số giấy tờ. Dữ liệu chỉ mô phỏng, không dùng để xuất vé thật với hãng bay (giữ nguyên giới hạn ở `project-brief.md` §4.2); không phải giấy tờ hợp lệ cho việc di chuyển thật.

### `requirements.md` §3, thêm

| Mã tiêu chí | Kịch bản / Điều kiện kích hoạt | Hành vi kỳ vọng của hệ thống |
|---|---|---|
| **AC-BKG-11** | Giỏ có vé máy bay cho 1 người lớn quốc tịch Việt Nam, chọn CCCD nhưng bỏ trống số CCCD | Bước Hành khách báo lỗi tại trường "Số CCCD", chặn sang bước Dịch vụ. Chọn hộ chiếu thì bắt buộc thêm ngày hết hạn, phải sau ngày bay cuối cùng của đơn |
| **AC-BKG-12** | Đổi quốc tịch hành khách sang khác Việt Nam khi đang chọn CCCD | Hệ thống tự chuyển loại giấy tờ sang hộ chiếu và yêu cầu nhập lại số giấy tờ, ngày hết hạn |

### `data-model.md` §2.2 (hành khách / `travelers`), thêm khối

```json
"documents": {
  "title": "MS",
  "nationality": "VN",
  "docType": "CCCD",
  "docNumber": "079188001234",
  "docExpiry": null
}
```

Chỉ bắt buộc khi giỏ có mục `flight`; `docExpiry` chỉ bắt buộc khi `docType = PASSPORT`. Trẻ em, em bé không có `docType`/`docNumber`/`docExpiry`.

## Thay đổi source sau khi chốt

- **Spec:** sửa `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §3.3 (bỏ dòng loại trừ giấy tờ tuỳ thân), thêm mục thiết kế chi tiết trường/luật kiểm (đối chiếu bảng `NATS`, `TITLES_ADULT/CHILD`, hàm `validatePax` trong mock) vào §6.4 hoặc phụ lục mới.
- **Contract:** `Traveler` schema (`src/shared/contracts/schemas/booking.yaml` hoặc tương đương) thêm khối `documents` tuỳ chọn.
- **DDL:** `app.booking_travelers` (hoặc bảng hành khách hiện có) thêm cột lưu `documents` (JSONB) hoặc các cột rời; migration idempotent tương ứng.
- **Backend:** validate theo AC-BKG-11, AC-BKG-12 trong bộ luật §5 của spec checkout (thêm mã luật R-TRV-07, R-TRV-08 hoặc tương đương).
- **Frontend:** thêm khối "Thông tin cho vé máy bay" vào `travelerCard` ở bước ① Hành khách, theo đúng bố cục và validate của mock (danh xưng, ngày sinh người lớn, quốc tịch, CCCD/hộ chiếu, người lớn đi kèm em bé).
