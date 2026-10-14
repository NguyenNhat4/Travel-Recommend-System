# Báo cáo stress đọc liên tục 13–14/10 (bản tạm)

- Ngày: 2026-10-14
- Tác giả: người dùng (Khoa15) / Claude Code
- Nhánh: khoa/catalog-presort-cache
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu báo cáo kết quả stress đọc liên tục đêm 13/10 đến sáng 14/10, chạy trên VM `stress-gen-1` và máy local. Báo cáo ghi vào `docs/spec/load-test/` theo quy ước đã có. Run kết thúc 09:30 (+07), nên báo cáo là bản tạm theo snapshot 09:11.

## File thay đổi

- `docs/spec/load-test/2026-10-14-stress-doc-lien-tuc.md` — thêm: báo cáo tạm, gồm kịch bản, kết quả R1/R2/R9/cal-200, 18 đoạn 20 rps, lịch thao tác MIG, phân tích, đính chính.
- `history/2026-10-14-bao-cao-stress-doc-lien-tuc.md` — thêm: entry này.
- `stress-results/run-20261014-stress-gen-1/` — thêm (ngoài git, chưa commit): copy `runs/` và `stress/` từ VM, `tong-hop.md`, `tong_hop.py`.

## Quyết định

- Viết báo cáo tạm thay vì chờ 09:30. Bản cuối cập nhật sau khi `seg019` xong.
- Không sửa `docs/spec/load-test/2026-10-13-run-3.md` dù số lỗi R9 ở đó sai (ghi 89,6%, đúng là 10,38%). Đính chính nằm trong báo cáo mới. Sửa tài liệu cũ cần người dùng đồng ý.
- Không gán nguyên nhân cho các thao tác MIG. Nhật ký chỉ cho thấy dịch vụ Google thực hiện insert/delete, không phân biệt được autoscaler với autohealing.

## Kiểm tra

- `python3 -I tong_hop.py` trên snapshot 09:11: 18 đoạn 20 rps, 647.953 request, 22 lỗi HTTP (cộng từ `http_req_failed` của từng JSON).
- R9 đối chiếu với log gốc: `http_req_failed` 109/1050 (10,38%), `checks_succeeded` 940/1049 (89,60%).
- Thao tác MIG đối chiếu bằng `gcloud compute operations list` từ 13/10 16:00 UTC.
- Chưa chạy: đọc cấu hình autoscaler (lệnh `gcloud compute autoscalers` không có trên máy này), truy vấn Cloud Logging.

## Còn lại / rủi ro

- `seg019` (09:10–09:30 +07) đang chạy. Cần copy lại dữ liệu và cập nhật báo cáo sau 09:30, rồi đổi trạng thái entry này thành hoàn thành.
- Nguyên nhân các thao tác MIG qua đêm chưa xác định.
- Cấu hình autoscaler hiện tại chưa đọc được.
- Sai số ở `2026-10-13-run-3.md` chưa sửa.
- Staging chạy bản cũ (chưa presort và cache), nên số liệu là baseline trước tối ưu.
