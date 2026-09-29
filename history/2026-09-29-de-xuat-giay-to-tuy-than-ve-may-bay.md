# Đề xuất PRD: thu thông tin giấy tờ tuỳ thân hành khách vé máy bay

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (tạo đề xuất; chưa chốt)
- Phạm vi: docs

## Mục tiêu

Người dùng so sánh checkout thật với artifact mock (`https://claude.ai/artifact/FAmeEkdDFeDUvwzbfe2aji`) và muốn UI thật có đủ khối "Thông tin cho vé máy bay" (danh xưng, quốc tịch, CCCD/hộ chiếu) như trong mock. Đã grep toàn bộ `docs/prd/` (`requirements.md`, `project-brief.md`, `user-flow.md`, `data-model.md`): không có mã FR/NFR nào phủ nội dung này. `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §3.3 (dòng 105) còn ghi rõ đây là "ngoài phạm vi". Theo AGENTS.md mục 1 và mục 8: không có mã tương ứng và lệch PRD thì phải hỏi người dùng và tạo đề xuất trước khi sửa source. Đã hỏi qua AskUserQuestion, người dùng chọn "Có, mở rộng phạm vi".

## File thay đổi

- `docs/prd/update/2026-09-29-ve-may-bay-giay-to-tuy-than.md` — thêm: đề xuất FR-BKG-13, AC-BKG-11/12, khối `documents` cho `data-model.md` §2.2, trạng thái "chờ chốt".

## Quyết định

- Không tự chốt đề xuất (agent không được tự chốt, theo mục 8). Đã trình bày và chờ mihhquan xác nhận nội dung cụ thể trước khi sửa `docs/prd/requirements.md`, `data-model.md`, spec, contract, DDL, backend, frontend.
- Không gộp vào đề xuất hạng vé/khứ hồi (`2026-09-29-ve-may-bay-hang-ve-va-khu-hoi.md`, đã áp dụng) vì hai việc độc lập: giấy tờ tuỳ thân không phụ thuộc dữ liệu catalog, còn hạng vé phụ thuộc Data bổ sung `attributes.fareClasses` (hiện = 0 sản phẩm trên snapshot `2026-09-23` và `2026-09-21`, đã kiểm bằng script Python đếm trực tiếp).

## Kiểm tra

- Không có thay đổi code/schema trong entry này, chỉ tài liệu. Chưa chạy `validate_contract.py` vì contract chưa đổi.

## Còn lại / rủi ro

- Chờ mihhquan chốt đề xuất `2026-09-29-ve-may-bay-giay-to-tuy-than.md` (hoặc yêu cầu sửa) trước khi cập nhật PRD và bắt đầu code.
- FR-BKG-10 (hạng vé, khứ hồi) người dùng cũng muốn triển khai ngay, nhưng đang bị chặn vì catalog thật chưa có `attributes.fareClasses` — cần quyết định dùng dữ liệu minh hoạ tạm (như trong mock) hay chờ Data. Chưa xử lý trong entry này.
