# Đề xuất tính điểm tham quan tự do là 0 đ vào tổng chi phí lịch trình

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng hỏi vì sao panel lịch trình ghi "Chi phí sản phẩm: Chưa tính được" (FR-AGT-02). Trace LangSmith project
`nhat-10-1`, thread `45befb6c-93d3-4c26-91eb-302df12381dc`, lượt "2 người lớn, 5 triệu" (Phú Quốc 3 ngày, 2 người lớn):
`party` và `budget` trích đúng; `estimatedTotal = null` vì 3 bãi biển (Bãi Dài, Starfish Beach, Bãi tắm Sao) có
`unitPrice = null`, `priceUnit = UNKNOWN`, và `totals()` trong `src/backend/app/domain/itinerary/planning.py` trả `null`
khi có một mục không tính được. Các mục có giá cộng được 4.260.300 ₫. Người dùng xác nhận các điểm đó là nơi vào tự do.

## File thay đổi

- `docs/prd/update/2026-10-01-diem-tham-quan-tu-do-tinh-0-vao-tong.md` — thêm: đề xuất sửa `docs/prd/architecture.md` §3.
- `history/2026-10-01-de-xuat-diem-tham-quan-tu-do-tinh-0-vao-tong.md` — thêm: entry này.

## Quyết định

- Coi điểm không có giá là 0 đ lệch `docs/prd/architecture.md` §3 ("không coi thiếu giá là 0") và
  `docs/spec/data-collection/schema.md` §2 mục 2, nên tạo đề xuất và dừng, chưa sửa code (AGENTS.md mục 8).
- Đề xuất dùng lại luật "tham quan tự do" người dùng đã chốt cho lời diễn giải
  (`history/2026-10-01-tham-quan-tu-do-va-goi-nhieu-ngay.md`), để chữ và tổng tiền không lệch nhau.

## Kiểm tra

- Đếm trên database local: 299/610 điểm tham quan và 1/6 golf không có giá; khách sạn, vé máy bay, combo đều có giá.
- Gọi `/api/v1/assistant/itineraries` trên backend local cho Đà Nẵng, Phú Quốc, Hà Nội có ngân sách: cả 3 có tổng (không
  xếp điểm không giá).
- Không sửa code nên không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất, gồm hai điểm: có loại trừ tour đi thuyền/chèo bè/bảo tàng không, và cảnh báo `FREE_ENTRY_ASSUMED`.
- Sau khi chốt: sửa `docs/prd/architecture.md` §3 trước, rồi code/spec/contract theo mục "Thay đổi source" của đề xuất.
