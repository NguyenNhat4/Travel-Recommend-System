# Slide HTML trình bày Project Brief

- Ngày: 2026-09-22
- Tác giả: người dùng / Claude Code (Opus 5)
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu tạo một bộ slide HTML 6 trang dựa trên `docs/project-brief.md` (qua skill `ui-ux-pro-max:slides`), dùng để trình bày tầm nhìn, vấn đề, kiến trúc, chỉ số và ràng buộc của V-OTA cho người ngoài team.

## File thay đổi

- `docs/slides/v-ota-project-brief.html` — thêm: deck 6 slide, HTML tĩnh một file, điều hướng bằng phím/nút/dot/swipe, một biểu đồ Chart.js (ngân sách độ trễ).

## Quyết định

- **Nội dung chỉ lấy từ `docs/project-brief.md`**, không thêm số liệu mới. Các chỉ số chưa có ngưỡng trong brief (NDCG@10, CTR, cross-sell) được trình bày dạng danh sách định nghĩa, không dựng biểu đồ giả; biểu đồ duy nhất dùng đúng 4 ngưỡng latency ở §3.2 và có caption ghi rõ "chưa phải số đo thực tế". Lý do: tuân thủ chính nguyên tắc Grounding của dự án (AGENTS.md mục 3).
- **Đặt ở `docs/slides/`**, không tạo thư mục mới ở gốc repo, và không đụng `src/` — đây là tài liệu trình bày, không phải feature. Vì vậy không áp dụng quy trình đọc tài liệu bắt buộc ở AGENTS.md mục 1.1/1.2 (chỉ dành cho feature/endpoint/module/thay đổi hành vi); nguồn nội dung duy nhất là project-brief.
- **Một file HTML tĩnh, không build step**: Chart.js nạp từ cdn.jsdelivr.net (pin 4.4.1), font từ Google Fonts; phần còn lại inline. Mở trực tiếp bằng trình duyệt, không cần server.
- **Font có dấu tiếng Việt**: Be Vietnam Pro (body), Archivo (display), IBM Plex Mono (nhãn/số) — đều có subset vietnamese.
- **Biểu đồ latency dùng một màu cho cả 4 cột** (4 bề mặt là danh mục danh định, không có thứ tự), trục x duy nhất, nhãn giá trị vẽ trực tiếp cạnh đầu cột nên không phụ thuộc tooltip; canvas được tune lại theo bề rộng stage khi resize để không vỡ tỷ lệ.
- **Hai chế độ layout**: ≥861px là sân khấu 16:9 letterbox, mỗi slide một màn; ≤860px deck trải thành tài liệu cuộn dọc (ẩn điều hướng) để đọc được trên điện thoại. Có thêm `@media print` để xuất PDF mỗi slide một trang.
- Deck cố định một bảng màu tối (nền "hải đồ đêm"), không theo light/dark của người xem, vì đây là mặt trình chiếu.

## Kiểm tra

- Render bằng `google-chrome-stable --headless --screenshot` ở 1600×900 cho slide 1, 3, 4, 5: bố cục đúng, chữ tiếng Việt đủ dấu, biểu đồ sắc nét, không tràn nội dung. Sau đó sửa một lượt: biểu đồ lấp đầy thẻ chứa, sơ đồ engine chiếm phần chiều cao trống, cột nhãn metric thẳng hàng, trục x bước 1000ms.
- Người dùng báo slide 6 lỗi. Nguyên nhân: (1) `.close p` có specificity cao hơn `.tag` nên nhãn mono góc phải bị phóng to bằng câu chốt; (2) 4 hàng `.rules > div{flex:1}` cộng lại cao hơn khoảng trống còn lại, `.rules` tràn ra và chồng lên khối kết. Sửa: tách câu chốt thành `.close-line`, trả hàng về chiều cao tự nhiên + căn giữa khối, giảm padding hàng, tiêu đề slide 6 về một dòng, rút gọn hai đoạn dài nhất. Render lại slide 6: không còn chồng chữ, nội dung vừa khung 16:9.
- Không chạy `validate_contract.py`: thay đổi không chạm contract, mock hay `src/`.

## Còn lại / rủi ro

- Deck chốt ở 6 slide theo yêu cầu; nếu cần thêm trang (timeline, phân rã kiến trúc 3 service, kế hoạch triển khai) thì lấy từ `docs/architecture.md` và `docs/implementation-plan.md`.
- Nội dung deck là bản chụp của `docs/project-brief.md` tại 2026-09-22; brief đổi thì phải cập nhật tay, không có cơ chế sinh tự động.
