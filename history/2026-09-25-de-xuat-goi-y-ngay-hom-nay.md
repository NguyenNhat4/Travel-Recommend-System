# Đề xuất gợi ý ngày hôm nay khi người dùng chưa chốt ngày đi

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng muốn khi không có ngày đi thì trợ lý gợi ý lấy hôm nay làm ngày khởi hành và chờ xác nhận; sau gợi ý mà người dùng không xác nhận hoặc không nói ngày thì lấy hôm nay luôn, không hỏi lại. Việc này đảo quy tắc "chưa chốt ngày → lập lịch không kèm ngày" vừa áp dụng ở `2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md`, nên phải có đề xuất được chốt (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` — thêm: đề xuất trạng thái `chờ chốt`.

## Quyết định

- Người dùng chọn hai điểm thiết kế qua câu hỏi (gợi ý rồi chờ xác nhận; không xác nhận thì lấy hôm nay). Việc chọn đó chưa phải chốt đề xuất, nên tôi dừng, chưa sửa code, golden hay tài liệu spec của phần này.
- Câu người dùng viết "if user dont confirm then pick, user wont give startday then ask" không rõ nghĩa; đã hỏi lại và đề xuất theo câu trả lời "lấy hôm nay luôn", không hỏi lặp.

## Kiểm tra

- Chỉ viết tài liệu; không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt. Chốt xong: cập nhật AC-AGT-01, chuyển đề xuất vào `update-archive/`, rồi code theo mục "Thay đổi source sau khi chốt".
- Rủi ro chính: ngày hôm nay có thể ngoài cửa sổ mở bán của khách sạn (hiện 15–16/10) nên vẫn dễ ra `FALLBACK`; cần team Data sửa cửa sổ mở bán.
