# Stress đọc liên tục trên staging, 13–14/10/2026

- Ngày: 2026-10-14 (giờ Việt Nam, +07)
- Môi trường: `https://praxis.io.vn`, MIG `vota-ha-app`, `asia-southeast1`
- Máy sinh tải: VM `stress-gen-1` (e2-standard-2, k6 v2.3.0) cho R1, R2, cal-200 và các đoạn 20 rps; máy local macOS (16 CPU) cho R9 (đêm 13/10)
- Script: `~/stress/read.js` và `common.js` trên VM; bản copy ở `stress-results/run-20261014-stress-gen-1/stress/`
- Số liệu: `stress-results/run-20261014-stress-gen-1/` (bảng tổng hợp `tong-hop.md`, tái sinh bằng `tong_hop.py`); R9 ở `stress-results/run-20261013-run3/`
- Trạng thái: **hoàn thành.** Run kết thúc 09:30 (+07), đủ 19 đoạn 20 rps. Số liệu chốt sau khi copy lúc 09:31. Còn mở: nguyên nhân chậm lúc 09:21–09:23 và cấu hình autoscaler (mục 6).
- Liên quan: [đợt 3 hôm qua](2026-10-13-run-3.md), [history: stress đến 09:30](../../../history/2026-10-14-stress-doc-lien-tuc-den-930.md), [history: báo cáo tạm](../../../history/2026-10-14-bao-cao-stress-doc-lien-tuc.md)

## 1. Tóm tắt

- **Ở 20 rps, staging ổn định suốt đêm.** 19 đoạn, 671.022 request, 22 lỗi HTTP (0,003%, đều là 5xx hoặc timeout), 191 iteration bị rớt. Health sampler: 557 mẫu, 1 mẫu lỗi.
- **Đoạn cuối `seg019` (09:10–09:30) chậm nhất.** p99 6,2 s, max 27,7 s, và health sampler ghi hai lần chậm lúc 09:21 (`/products` 2,3 s) và 09:23 (`/products` 6,3 s). Hai lần này nằm trong lúc autoscaler gỡ `m66l` (09:18:55) rồi thêm `2ztd` (09:19:46). Health check của `2ztd` báo TIMEOUT lúc 09:21 và UNHEALTHY lúc 09:23, rồi HEALTHY lại lúc 09:24:54.
- **Autoscaler đổi kích thước nhóm 10 lần trong lúc chạy** (12 lần tính từ đầu đêm) (giữa 1 và 2 VM). Log quyết định cho thấy CPU chạm ngưỡng 0,55 khi chỉ có 1 VM, và giảm còn khoảng 0,23–0,25 khi có 2 VM. Với tải 20 rps không đổi, nhóm dao động giữa hai mức này. Autoscaler đạt giới hạn max 2 VM lúc 00:10 và từ 09:33.
- **Latency vượt ngưỡng NFR-PERF-01 ngay cả khi tải nhẹ.** `product_similar` có p95 khoảng 1,7 s ở cả 19/19 đoạn (ngưỡng 250 ms). Danh mục và chi tiết vượt 100 ms ở 5–6/19 đoạn.
- **Từ khoảng 25 rps trở lên, hệ thống không giữ được tốc độ đặt.** Ba run có lỗi cao (R2, R9, cal-200) bị dừng khẩn với lỗi 7,9–13,9%. R1 ở 100 rps chạy hết 2 phút không lỗi, nhưng chỉ đạt 31,8 iter/s và p95 8,5 s.

## 2. Kịch bản

- **Mục đích:** quan sát tải đọc ổn định, dài hạn trên staging: autoscaler, autohealing và độ trễ theo thời gian. Chỉ đọc, ẩn danh; không gọi LLM, không gọi Stripe, không ghi dữ liệu.
- **Tải:** tốc độ cố định 20 iteration/s (k6 `constant-arrival-rate`), chia đoạn 30 phút. Đoạn dừng sớm thì nghỉ 10 phút rồi chạy tiếp. Mỗi request có tham số `_k6` ngẫu nhiên để không bị cache.
- **Tỷ trọng endpoint** (giả định của kế hoạch, không lấy từ traffic thật):

| Endpoint | Trọng số | Ngưỡng p95 |
|---|---|---|
| `GET /api/v1/products?limit=20` | 35 | 100 ms |
| `GET /api/v1/products/{id}` | 30 | 100 ms |
| `GET /api/v1/products/{id}/similar?limit=8` | 10 | 250 ms |
| `GET /api/v1/recommendations?k=5` | 10 | 250 ms |
| `GET /api/v1/destinations` | 5 | 100 ms |
| `GET /api/v1/assistant/status` | 5 | chỉ báo cáo |

- **Dừng khẩn:** lỗi HTTP vượt 5% (sau 10 giây). Mã 4xx không tính là lỗi.
- **Calibration:** `cal-200` lúc 00:08, 200 rps, dừng sau 42 giây vì lỗi 13,88%.
- **Health sampler:** mỗi 60 giây gọi `/health/ready` và `/api/v1/products?limit=20`.

## 3. Kết quả

### 3.1 Hôm qua (13/10)

| Run | Nơi chạy | Giờ (+07) | Đích | Thực đạt | Lỗi HTTP | Request | Rớt | p95 chung | Kết thúc |
|---|---|---|---|---|---|---|---|---|---|
| R1 | VM | 12:39–12:41 | 100 rps | 31,8/s | 0% | 3.890 | 8.111 | 8.542 ms | chạy hết 2 phút; vượt threshold latency |
| R2 | VM | 12:42–12:43 | 500 rps | 25,3/s | 7,89% | 1.065 | 17.784 | 29.561 ms | dừng khẩn sau 42 s |
| R9 | máy local | 23:45–23:46 | 100 rps | 24,9/s | 10,38% | 1.050 | 1.582 | 25.755 ms | dừng khẩn sau 42 s |

p95 theo endpoint (ms):

| Endpoint | R1 (100 rps) | R2 (500 rps) | R9 (100 rps, local) | cal-200 (200 rps) |
|---|---|---|---|---|
| `product_list` | 2.283 | 28.532 | 22.773 | 27.387 |
| `product_detail` | 9.676 | 31.113 | 28.551 | 31.884 |
| `product_similar` | 3.274 | 30.509 | 23.245 | 28.520 |
| `destinations` | 2.926 | 25.291 | 24.967 | 15.609 |
| `recommendations` | 4.123 | 26.993 | 22.592 | 27.706 |

- R1 chỉ đạt 31,8/s vì 100 VU, mỗi iteration mất khoảng 3,1 s, nên tối đa khoảng 32 iter/s. R1 có 210 lỗi ở check `jwks 2xx`, do phiên bản script cũ còn gọi `jwks`. Các check endpoint sản phẩm đều đạt.
- R9 bị dừng khẩn lúc 23:46:37 (+07). Autohealing thay VM `z2wq` lúc 23:46:51, cùng phút đó. Xem mục 3.3.

### 3.2 Sáng nay (14/10)

**Calibration `cal-200`** (00:08–00:09, 200 rps): thực đạt 26,7/s, lỗi HTTP 13,88% (156/1.124), p95 29.462 ms, dừng khẩn sau 42 giây.

**19 đoạn 20 rps** (`seg001`–`seg019`, 00:10–09:30): mỗi đoạn 30 phút, trừ `seg019` dài 19,3 phút. Thực đạt 20,0/s ở 18 đoạn đầu và 19,9/s ở `seg019`.

| Đoạn | Giờ (+07) | Request | Lỗi HTTP | Rớt | p95 chung (ms) | Max (ms) | Thao tác MIG trong đoạn |
|---|---|---|---|---|---|---|---|
| seg001 | 00:10–00:40 | 36.002 | 0 | 0 | 840 | 11.596 | +r9c1 00:29; −v7j4 00:31 |
| seg002 | 00:40–01:10 | 35.989 | 0 | 13 | 865 | 12.930 | — |
| seg003 | 01:10–01:40 | 36.002 | 0 | 0 | 810 | 6.377 | −r9c1 01:14 |
| seg004 | 01:40–02:10 | 36.002 | 0 | 0 | 803 | 3.161 | — |
| seg005 | 02:10–02:40 | 36.001 | 0 | 0 | 807 | 4.891 | — |
| seg006 | 02:40–03:10 | 36.002 | 9 | 0 | 807 | 2.499 | — |
| seg007 | 03:10–03:40 | 36.002 | 0 | 0 | 821 | 9.029 | +j2jn 03:21 |
| seg008 | 03:40–04:10 | 36.001 | 0 | 0 | 820 | 8.931 | −j2jn 04:06 |
| seg009 | 04:10–04:40 | 36.002 | 0 | 0 | 806 | 4.303 | — |
| seg010 | 04:40–05:10 | 36.002 | 1 | 0 | 802 | 3.472 | — |
| seg011 | 05:10–05:40 | 35.976 | 0 | 26 | 806 | 17.209 | — |
| seg012 | 05:40–06:10 | 36.002 | 0 | 0 | 800 | 4.483 | — |
| seg013 | 06:10–06:40 | 36.001 | 12 | 0 | 792 | 7.292 | — |
| seg014 | 06:40–07:10 | 36.002 | 0 | 0 | 796 | 6.009 | — |
| seg015 | 07:10–07:40 | 35.996 | 0 | 6 | 800 | 8.898 | — |
| seg016 | 07:40–08:10 | 36.002 | 0 | 0 | 831 | 4.428 | +swh0 07:45 |
| seg017 | 08:10–08:40 | 35.968 | 0 | 33 | 1.195 | 12.106 | +v00s 08:30; −swh0 08:30 |
| seg018 | 08:40–09:10 | 36.001 | 0 | 0 | 905 | 21.888 | — |
| seg019 | 09:10–09:30 (19,3 phút) | 23.069 | 0 | 113 | 1.475 | 27.705 | +2ztd 09:19; −m66l 09:21 |

Tổng: 671.022 request, 22 lỗi HTTP, 191 iteration rớt.

p theo endpoint, 19 đoạn (ms):

| Endpoint | p95 trung vị | p95 min–max | p99 trung vị | Đoạn vượt ngưỡng p95 |
|---|---|---|---|---|
| `product_list` | 78 | 70–324 | 160 | 5/19 (ngưỡng 100) |
| `product_detail` | 82 | 74–384 | 175 | 6/19 (ngưỡng 100) |
| `product_similar` | 1.695 | 1.529–1.904 | 1.841 | **19/19** (ngưỡng 250) |
| `destinations` | 54 | 49–274 | 114 | 2/19 (ngưỡng 100) |
| `recommendations` | 145 | 125–553 | 283 | 2/19 (ngưỡng 250) |

Health sampler (00:10–09:30): 557 mẫu. Một mẫu lỗi duy nhất lúc 01:00 (mã 000). `/health/ready` p50 0,112 s, p95 0,182 s; `/api/v1/products` p50 0,127 s, p95 0,176 s. Các mẫu chậm nằm ở giai đoạn thay VM:

| Giờ (+07) | `/health/ready` | `/api/v1/products` |
|---|---|---|
| 09:21:06 | 1,313 s | 2,293 s |
| 09:23:16 | 3,746 s | 6,296 s |

Các mẫu từ 09:24 đến 09:30 về lại 0,1–0,2 s.

### 3.3 Thao tác VM và autoscaler qua đêm

Bảng dưới ghép quyết định của autoscaler (đọc từ log `compute.autoscalers.resize`) với thao tác insert/delete trên MIG. Giờ đã đổi sang +07.

| Giờ (+07) | Quyết định autoscaler (đề xuất; tín hiệu) | Thao tác MIG |
|---|---|---|
| 13/10 23:46 | — | autohealing thay `z2wq` (repair) |
| 13/10 23:47 | — | insert `v7j4` |
| 13/10 23:56 | — | người vận hành patch cấu hình autoscaler |
| 14/10 00:02 | → 1 (bộ nhớ 33%, target 90%) | — (trước khi run) |
| 00:05 | — | delete `z2wq` |
| 00:09 | → 2 (CPU 0,550, target 0,55) | insert `m66l` |
| 00:10 | báo đã đạt max 2 (đến 00:19) | — |
| 00:28 | → 1 (CPU 0,250) | — |
| 00:29 | → 2 (CPU 0,280) | insert `r9c1` (00:29:57); delete `v7j4` (00:31:37) |
| 01:11 | → 1 (CPU 0,223) | delete `r9c1` (01:14:33) |
| 03:21 | → 2 (CPU 0,554) | insert `j2jn` (03:21:52) |
| 04:03 | → 1 (CPU 0,245) | delete `j2jn` (04:06:24) |
| 07:45 | → 2 (CPU 0,568) | insert `swh0` (07:45:32) |
| 08:27 | → 1 (CPU 0,228) | — |
| 08:29 | → 2 (CPU 0,289) | insert `v00s` (08:30:01); delete `swh0` (08:30:04) |
| 09:18 | → 1 (bộ nhớ 41,5%, target 90%) | removeInstances `m66l` (09:18:55); delete `m66l` (09:21:37) |
| 09:19 | → 2 (CPU 0,289) | addInstances `2ztd` (09:19:46) |
| 09:21 | — | `2ztd` health check TIMEOUT |
| 09:23 | — | `2ztd` UNHEALTHY |
| 09:24 | — | `2ztd` HEALTHY (09:24:54) |
| 09:31 | — | patch MIG và setMetadata trên cả hai VM (`vota-backend-image`), sau khi run kết thúc |
| 09:33 | báo đã đạt max 2 | — |

- Trong bảng có 12 thao tác insert/delete từ 00:05 đến 09:21, cộng 10 quyết định resize của autoscaler trong thời gian chạy (00:10–09:30).
- Cấu hình autoscaler hiện tại: CPU target 0,55; tín hiệu bộ nhớ tùy chỉnh target 90%; min 1, max 2; cooldown 360 giây; scale-in tối đa 1 VM mỗi 600 giây. Autohealing dùng health check `vota-ha-app-live`, `initialDelaySec` 360.
- Trạng thái lúc 09:33: MIG có 2 VM RUNNING (`v00s`, `2ztd`), không có thao tác đang chạy.

## 4. Phân tích

1. **Trần thông lượng.** Bốn run cường độ cao chỉ đạt 25–32 iter/s, bất kể đích 100–500 rps. Con số này khớp với ước lượng khoảng 35 rps đã dùng để chọn 20 rps. Tuy vậy VU cũng cạn: R1 100/100, R9 1.500/1.514, R2 2.000/2.000. Vì vậy chưa tách được giới hạn phía server với giới hạn của máy sinh tải.
2. **Đuôi latency ở tải nhẹ.** Trung vị mỗi đoạn 47–72 ms. p99 của 18 đoạn đầu từ 1,1 đến 3,0 s, và `seg019` lên 6,2 s. Có spike ở đoạn không có thao tác nào: seg011 (05:10–05:40) có max 17,2 s, không có thao tác MIG.
3. **`product_similar`.** Trung vị khoảng 800 ms và p95 khoảng 1,7 s ở mọi đoạn, kể cả khi tải nhẹ và không có thao tác MIG. Điều này không do tải, nằm trong đường xử lý của endpoint. Chưa đo nguyên nhân vì chưa có trace hay log phía server.
4. **Thay VM và độ trễ.** Ba đoạn có lỗi HTTP (seg006, seg010, seg013) đều không có thao tác MIG trong khung giờ của đoạn, nên lỗi không trùng với thay VM. Ngược lại, độ trễ tăng đúng lúc thay VM: seg017 (có thao tác lúc 08:30, p95 chung 1.195 ms) và seg019 (gỡ `m66l`, thêm `2ztd`, p99 6,2 s, health chậm 2,3 s và 6,3 s). `2ztd` chưa qua health check trong khoảng 09:19–09:24. Chưa xác định độ trễ là do ít VM khỏe hơn hay do VM mới đang khởi động (nạp dữ liệu, warm-up). Muốn xác nhận cần log của `2ztd` và CPU từng VM trong 09:15–09:30.
5. **Autoscaler dao động giữa 1 và 2 VM.** Với 1 VM, CPU đo được khoảng 0,55, đúng ngưỡng nên autoscaler tăng lên 2 VM (00:09, 03:21, 07:45). Với 2 VM, CPU giảm còn khoảng 0,23–0,25 nên autoscaler giảm về 1 VM (00:28, 01:11, 04:03, 08:27). Ngoại lệ là 09:18: giảm về 1 VM theo tín hiệu bộ nhớ (41,5%). Đây là cách đọc từ lý do autoscaler ghi lại, chưa đối chiếu với CPU của từng VM. Mỗi lần dao động làm thay VM, và mỗi lần thay là một cửa sổ latency cao.
6. **Điều kiện đo.** Staging đang chạy bản cũ, chưa có presort và cache. `CACHE_BUST` bật, nên mọi request đi tới origin. Đây là kịch bản bất lợi cho origin, không phản ánh lưu lượng thật. Chưa có số liệu traffic thật để so sánh. Lúc 09:31 có cập nhật metadata `vota-backend-image` trên MIG và cả hai VM, sau khi run kết thúc, nên không ảnh hưởng số liệu đo.

## 5. Đính chính số liệu cũ

- [Đợt 3](2026-10-13-run-3.md), mục 1 và 3, ghi R9 là "941/1050 lỗi (89,6%)" và "đợt 3 lỗi 90%". Log k6 ghi `http_req_failed 10,38% (109/1050)`. Số 89,6% là tỷ lệ check thành công (940/1049), không phải tỷ lệ lỗi. Số đúng là 10,38%.
- [History stress đến 09:30](../../../history/2026-10-14-stress-doc-lien-tuc-den-930.md) ghi cal-200 dừng sau khoảng 10 giây. Log k6 ghi 42 giây.
- Bản báo cáo tạm trước đó ghi "9 thao tác insert/delete" và "cấu hình autoscaler chưa đọc được". Số đúng là 12 thao tác từ 00:05 đến 09:21, và cấu hình đã đọc được (mục 3.3).
- Hai chỗ đầu chưa được sửa trong tài liệu gốc. Sửa cần người dùng đồng ý và có entry history riêng.

## 6. Việc còn lại

1. **Quyết định cấu hình autoscaler (người vận hành).** CPU target 0,55 với max 2 đang gây dao động giữa 1 và 2 VM. Chưa đổi. Có thể nâng min lên 2, đổi target, hoặc giữ nguyên, tùy mục tiêu.
2. **Xác nhận nguyên nhân chậm lúc 09:21–09:23.** Đọc log của `2ztd` và CPU từng VM trong 09:15–09:30 để tách "ít VM khỏe" với "VM mới khởi động". Chưa làm.
3. **Trước khi chạy lại:** kiểm tra lần cập nhật `vota-backend-image` lúc 09:31 đã xong và VM nào đang chạy image nào.
4. **Đo `product_similar` phía server** bằng trace hoặc log.
5. **Chạy lại sau khi deploy bản presort và cache** (theo `docs/plan/2026-10-13-cache-va-presort-catalog.md`) để có baseline so sánh.
6. **Tách giới hạn server và giới hạn máy sinh tải:** thêm máy sinh tải hoặc tăng số VU để biết trần 25–32 iter/s nằm ở đâu.

## 7. Kiểm tra

- Mọi số trong báo cáo lấy từ `runs/*.json`, `runs/*.log` và `health.csv` qua `tong_hop.py`. Không ước tính.
- Tổng 19 đoạn và 22 lỗi HTTP được cộng lại trực tiếp từ `http_req_failed` và `http_reqs` của từng JSON.
- Mốc thời gian UTC từ log, MIG và autoscaler đã đổi sang +07 (cộng 7 giờ).
- Số lỗi R9 đối chiếu lại với log gốc: `http_req_failed` 109/1050 và `checks_succeeded` 940/1049.
- Thao tác MIG đối chiếu bằng `gcloud compute operations list`, và sự kiện health, autoscaler, instance group bằng `gcloud logging read` (từ 13/10 17:00 UTC).
- Chưa kiểm: CPU từng VM (chưa đọc từ Cloud Monitoring), log riêng của `2ztd`, và nguyên nhân cập nhật `vota-backend-image` lúc 09:31.
