# Áp dụng đề xuất vé máy bay: dịch vụ thêm (hành lý ký gửi, chỗ ngồi)

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất `2026-09-29-ve-may-bay-dich-vu-them.md` (Q1–Q7 theo đề xuất). Áp dụng vào PRD theo AGENTS.md mục 8 bước 3–4.

## File thay đổi

- `docs/prd/project-brief.md` — sửa: §4.1 thêm dịch vụ thêm của hãng bay; §4.2 thêm ngoài phạm vi bảo hiểm và suất ăn.
- `docs/prd/requirements.md` — sửa: thêm FR-BKG-11 và AC-BKG-10.
- `docs/prd/data-model.md` — sửa: §2.2 metadata mục vé bay; §3.1 cấu trúc bảng giá dịch vụ thêm, loại tàu bay, sơ đồ ghế.
- `docs/prd/user-flow.md` — sửa: §4.4 wireframe mục "Chỗ ngồi" và màn hình sơ đồ ghế.
- `docs/prd/update/2026-09-29-ve-may-bay-dich-vu-them.md` → `docs/prd/update-archive/` — đổi trạng thái `đã áp dụng`, chuyển lưu trữ.

## Quyết định

- Giai đoạn này chỉ hành lý ký gửi và chọn ghế; suất ăn, bảo hiểm để sau (Q1). Giá từ bảng giá tĩnh theo hãng (Q2), sơ đồ ghế tĩnh, tình trạng ghế mô phỏng (Q3), luật ghế lối thoát hiểm (Q4), không bán phần hạng vé đã gồm (Q5), mỗi loại là một dòng giá `BAG`/`SEAT` (Q6), huỷ và hoàn theo cả đơn (Q7).
- Đề xuất phụ thuộc `2026-09-29-checkout-nhieu-buoc-hanh-khach.md` vẫn đang chờ chốt trong `docs/prd/update/`; FR-BKG-11 chỉ có hiệu lực thực thi khi checkout nhiều bước được chốt.

## Kiểm tra

- Chưa chạy `validate_contract.py` (chưa đổi contract).

## Còn lại / rủi ro

- Source chưa sửa: nạp bảng giá và sơ đồ ghế (Data, `docs/spec/data-collection/schema.md`); mục dịch vụ thêm trong `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (bỏ "chọn ghế, hành lý" khỏi §3.3 ngoài phạm vi); contract `FareType` thêm `BAG`, `SEAT`, `CheckoutItemDetail` thêm ghế/hành lý theo `travelerRef`; backend `fares.py`, `party_rules.py`, Stripe line item; frontend sơ đồ ghế.
- Contract phải sửa trước code (mục 3 AGENTS.md).
