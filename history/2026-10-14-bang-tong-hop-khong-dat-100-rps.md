# Bảng tổng hợp theo endpoint và yếu tố: vì sao không đạt 100 rps

- Ngày: 2026-10-14
- Tác giả: người dùng (Khoa15) / Claude Code
- Nhánh: khoa/stress-staging-2026-10-14
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu lập bảng báo cáo có số liệu, endpoint rõ ràng và cột lý do, từ kết quả điều tra không đạt 100 rps (PR #212). Trong lúc đối chiếu, tôi phát hiện hai số liệu sai và sửa cùng lúc.

## File thay đổi

- `docs/spec/load-test/2026-10-14-nguyen-nhan-khong-dat-100-rps.md` — thêm: mục "Bảng tổng hợp theo endpoint" (6 endpoint, có tỷ trọng, ngưỡng, số tải nhẹ và tải 100 rps, cột lý do) và mục "Các yếu tố hệ thống" (11 yếu tố, có mức bằng chứng). Sửa: số server của `seg005` đổi từ mẫu 4.000 dòng sang toàn bộ 35.997 dòng (`similar` 776/1.560 → 777/1.641, `recommendations` p50 53 → 54, `products` p50 21 → 20). Sửa: p50 client của `similar` ở `seg005` là 804 ms, không phải 812 ms. Sửa: số lần resize 11 → 10 trong thời gian chạy.
- `docs/spec/load-test/2026-10-14-stress-doc-lien-tuc.md` — sửa: số lần resize của autoscaler trong thời gian chạy 11 → 10 (ở tóm tắt và mục 3.3).
- `history/2026-10-14-bang-tong-hop-khong-dat-100-rps.md` — thêm: entry này.

## Quyết định

- Không sửa entry history cũ. Số "11 quyết định resize" ở `history/2026-10-14-cap-nhat-bao-cao-stress-sau-0930.md` là sai, và đính chính đặt ở đây. Số đúng là 10 trong thời gian chạy, 12 tính từ đầu đêm (log `compute.autoscalers.resize`, đã đổi sang +07).
- Số server ở tải nhẹ lấy từ toàn bộ cửa sổ `seg005` thay vì mẫu. Lấy mẫu 4.000 dòng đầu làm lệch `similar` khoảng 5%.
- `seg019` vẫn chỉ có mẫu 4.000 dòng đầu, nên không đưa vào bảng.
- Mức bằng chứng ghi cho từng yếu tố. Các yếu tố chưa đo trực tiếp (CPU theo route, chi phí kết nối DB, độ dài hàng đợi) ghi là suy luận hoặc chưa đo.
- Không commit trong lần này. Thay đổi nằm trong working tree của nhánh `khoa/stress-staging-2026-10-14`, PR #212 chưa có các sửa này.

## Kiểm tra

- Số client của 19 đoạn 20 rps: tổng hợp lại từ `runs/seg0*.json` (trung vị, min–max, số đoạn vượt ngưỡng). Khớp với bảng `tong-hop.md`.
- Số server `seg005`: `gcloud logging read` không giới hạn 4.000 dòng, nhận 35.997 dòng, 2xx 100%. Khớp với 36.001 request phía client (chênh 4 request).
- Số server R1, R2, R9: đếm dòng đầy đủ (3.697, 2.900, 2.427, dưới giới hạn 4.000 nên không bị cắt).
- Đếm resize: từ `as_log.json`, 12 sự kiện tổng, 10 sự kiện nằm trong 00:10:19–09:30:00 (+07).
- Đã kiểm không còn số cũ (`1.560`, `776`, `812`, `53 / 84`, `21 / 36`, `11 lần`) trong báo cáo điều tra và báo cáo stress.
- Chưa kiểm: CPU theo route, pgbouncer, chi phí kết nối DB, và các giả thuyết H2–H4 (chưa profile).

## Còn lại / rủi ro

- Bảng dùng tỷ trọng mix của kế hoạch, không phải traffic thật.
- Số server 100 rps là một run (R1). Chưa có run 100 rps nào sau khi deploy blue/green.
- Cần commit và push các sửa này lên PR #212 nếu muốn đưa vào review.
- Entry `history/2026-10-14-cap-nhat-bao-cao-stress-sau-0930.md` vẫn ghi 11; đã đính chính trong entry này.
