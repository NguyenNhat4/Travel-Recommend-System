# Cập nhật báo cáo stress đọc liên tục sau 09:30

- Ngày: 2026-10-14
- Tác giả: người dùng (Khoa15) / Claude Code
- Nhánh: khoa/catalog-presort-cache
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu cập nhật báo cáo stress sau 09:30, khi run kết thúc. Entry này đóng phần việc còn lại của `history/2026-10-14-bao-cao-stress-doc-lien-tuc.md`, là bản tạm theo snapshot 09:11. Entry cũ không được sửa.

## File thay đổi

- `docs/spec/load-test/2026-10-14-stress-doc-lien-tuc.md` — sửa: thay bản tạm bằng bản cuối. Thêm `seg019` (19 đoạn, 671.022 request, 22 lỗi HTTP, 191 rớt). Thêm lịch thao tác VM và quyết định autoscaler ghép từ log, số liệu health các mẫu chậm lúc 09:21 và 09:23, và phần đính chính số liệu cũ. Đổi trạng thái thành hoàn thành, còn mở mục 6.
- `history/2026-10-14-cap-nhat-bao-cao-stress-sau-0930.md` — thêm: entry này.
- `stress-results/run-20261014-stress-gen-1/` — copy lại `runs/` và `stress/` sau 09:30; viết lại `tong-hop.md` và `tong_hop.py` (ngoài git, chưa commit).

## Quyết định

- Giữ tên file báo cáo như đã hẹn trong entry 09:30, không tạo file mới.
- Không sửa entry cũ. Entry bản tạm vẫn ghi "dang dở" theo đúng thời điểm của nó.
- Không sửa `docs/spec/load-test/2026-10-13-run-3.md` dù số lỗi R9 ở đó sai (ghi 89,6%, đúng là 10,38%). Đính chính nằm trong báo cáo mới. Sửa tài liệu cũ cần người dùng đồng ý.
- Không đổi cấu hình autoscaler. Ngưỡng CPU 0,55 với max 2 đang gây dao động giữa 1 và 2 VM, nhưng quyết định thuộc người vận hành.
- Nguyên nhân chậm lúc 09:21–09:23 chưa xác định. Báo cáo nêu hai giả thuyết là ít VM khỏe hơn và VM mới khởi động. Không chọn một trong hai.
- Báo cáo gọi nguyên nhân các thao tác MIG là dịch vụ Google thực hiện. Không gán là autohealing hay autoscaler, trừ khi có lý do ghi trong log autoscaler.

## Kiểm tra

- `python3 -I tong_hop.py` trên dữ liệu sau 09:30: 19 đoạn, 671.022 request, 22 lỗi HTTP (cộng từ `http_req_failed` của từng JSON), 191 iteration rớt, 557 mẫu health.
- Đối chiếu log autoscaler (`gcloud logging read`, `compute.autoscalers.resize`): 11 quyết định resize trong thời gian chạy. Mỗi quyết định có tín hiệu CPU hoặc bộ nhớ ghi trong payload.
- Đối chiếu sự kiện health của `2ztd` (TIMEOUT 09:21:07, UNHEALTHY 09:23:37, HEALTHY 09:24:54) bằng `gcloud logging read`.
- Cấu hình autoscaler và autohealing đọc bằng `gcloud beta compute instance-groups managed describe`.
- Đối chiếu lại số lỗi R9 với log gốc: `http_req_failed` 109/1050, `checks_succeeded` 940/1049.
- Chưa kiểm: CPU từng VM (chưa đọc từ Cloud Monitoring), log riêng của instance `2ztd`, và nguồn của cập nhật `vota-backend-image` lúc 09:31.

## Còn lại / rủi ro

- Nguyên nhân chậm lúc 09:21–09:23: cần log `2ztd` và CPU từng VM trong 09:15–09:30.
- Cấu hình autoscaler (CPU target 0,55, max 2): chờ người vận hành quyết định.
- Cập nhật `vota-backend-image` lúc 09:31: cần xác nhận đã xong và VM nào đang chạy image nào trước khi chạy lại.
- Sai số ở `2026-10-13-run-3.md` và ghi chú "10 giây" trong entry 09:30 chưa sửa.
- Staging chạy bản cũ (chưa presort và cache), nên số liệu là baseline trước tối ưu.
- Không có số liệu traffic thật để đối chiếu tỷ trọng endpoint.
