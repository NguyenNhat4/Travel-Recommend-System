# CDP append-v1 — bàn giao đo lại RecSys

- Ngày: 2026-10-05
- Phạm vi: FR-CDP-01/03, FR-REC-01/02; dữ liệu hoàn toàn tổng hợp
- Batch: `20261005-recsys-v1`
- Artifact SHA-256: `d5bd456a6a87aa2264f2e61b7ec18e51bf5003e7bcf1df1050426af9f58c93a9`

## Trạng thái nạp primary

Đã append trong một transaction qua tunnel SSH mới, không thay thế lịch sử cũ:

| Hạng mục | Kết quả |
|---|---:|
| Profile mới | 5.000 |
| Event mới | 32.896 |
| Tổng profile / event sau nạp | 7.003 / 40.048 |
| Dữ liệu cũ giữ nguyên | PASS — fingerprint của CDP, catalog, app users, booking, booking items, payments trùng trước nạp |
| Nạp lại cùng artifact | PASS — `already_applied`, không thêm dòng |

Batch dùng namespace `VPX:20261005-recsys-v1:` và chỉ chứa khách tổng hợp mới. Không thêm `app.users`, booking, Insider hay schema.
Primary không chứa dữ liệu khách thật theo xác nhận của người dùng.

`db/verify.sql` sau nạp đạt 20/23 mục. Ba mục FAIL là ngưỡng demo cũ (`profiles = 2000`, `events 6000-8000`, `max events/user <= 15`),
không phải lỗi dữ liệu; profile append có tối đa 37 event theo cấu hình eval.

## Nội dung tín hiệu mới

Batch có 3.750 khách mua, 1.564 khách quay lại từ hai chuyến, 6.122 chuyến có mua, 4.075 chuyến đa vertical và 2.455 event bỏ giỏ.
Đây là số mô tả generator, không phải điểm chất lượng production.

Snapshot tái lập nằm ở `src/data_collection/snapshots/2026-10-05-recsys-append-v1/` với catalog, profiles, events và manifest checksum.
Không commit receipt chứa thông tin đăng nhập; receipt chỉ có ID/đếm/hash.

## Đo lại RecSys

Đã đóng băng bốn split mới, không dùng lại split eval-v2:

| Split | Số khách test |
|---|---:|
| LLBO | 4.021 |
| Temporal | 774 |
| Next trip | 1.835 |
| Cold start | 5.231 |

Các file freeze là `split-{llbo,temporal,nexttrip,coldstart}-append-v1-asof20261005.json`. Chưa có điểm engine sau append;
tqanh cần chạy đủ engine, MPD và các arm CF với vector khớp snapshot rồi ghi report mới. `vectorsMissing` phải bằng 0.
Hướng dẫn dựng DB local, kiểm checksum, sinh vector/split và chạy benchmark nằm ở
`docs/guide/recsys-append-v1-snapshot.md`.

Kết quả eval-v2 cũ vẫn giữ nguyên trong `eval-2026-10-05-recsys-eval-v2.md`; không gộp hai bộ số liệu.
