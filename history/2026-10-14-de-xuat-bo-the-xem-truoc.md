# Đề xuất bỏ thẻ xem trước trong khung tiến trình

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng thấy khối thẻ 2 cột × 3 dòng hiện trước câu trả lời và hỏi có phải lỗi. Đây là thẻ xem trước (AC-AGT-09,
chốt 13/10). Người dùng quyết định bỏ hẳn. Việc này lệch PRD nên viết đề xuất trước (AGENTS.md §8).

## File thay đổi

- `docs/prd/update/2026-10-14-bo-the-xem-truoc-trong-tien-trinh.md` — thêm: đề xuất bỏ thẻ xem trước.
- `history/2026-10-14-de-xuat-bo-the-xem-truoc.md` — thêm: entry này.

## Quyết định

- Bằng chứng: log `.logs/web-demo.log` lượt 14/10 00:13 — `plan_itinerary` c4 xong lúc 00:13:22 (provisional, 7 refs),
  backend phát `preview` (`orc_v2.py`), frontend cắt 6 thẻ (`AssistantProvider.tsx`), hiện ngay vì đã quá 5 giây; lời
  đáp xong 00:13:28 thì khối biến mất. Không phải lỗi code.
- Contract giữ schema sự kiện, chỉ thôi phát, để không phá client cũ (AGENTS.md §3: không xoá trong v1).

## Kiểm tra

- Chưa sửa code; không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất; sau đó cập nhật PRD rồi sửa backend, frontend, spec theo mục "Thay đổi source".

Bị thay thế bởi: `2026-10-14-bo-the-xem-truoc.md`
