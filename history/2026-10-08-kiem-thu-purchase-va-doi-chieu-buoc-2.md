# Kiểm thử mất purchase và đối chiếu kết quả RecSys bước 2

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Codex
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Thực hiện ba việc người dùng chọn: thêm test trực tiếp lỗi mất purchase, cập nhật report P2+F7 đã hoàn tất,
và xác minh trạng thái hai job bước 2. Phục vụ FR-REC-01/02/04, AC-REC-02.

## File thay đổi

- `src/evaluation/recsys_bench/tests/test_profile_variants.py` — thêm: kỳ vọng bảo toàn purchase/ngày sử dụng/trạng thái
  chuyến sau ba view; kiểm thứ tự đầu vào, cap chỉ áp dụng weak event, cart không bị coi là purchase.
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: số P2+F7 nguyên văn và checksum nguồn,
  điền hàng còn trống; cập nhật trạng thái job, kết quả từng phần F12b/F13b, caveat và kết quả unit test.
- `history/2026-10-08-kiem-thu-purchase-va-doi-chieu-buoc-2.md` — thêm: entry của task này.

## Quyết định

- Không sửa backend, PRD, scorer hoặc đề xuất chờ chốt; không chạy lại benchmark và không tác động job đang chạy.
- Hai ca production dùng xfail strict: giữ kỳ vọng nghiệp vụ đúng nhưng chỉ rõ engine hiện vẫn lỗi. P1/P4 phải pass.
- Bổ sung trạng thái sau `2026-10-08-tam-dung-buoc-2-recsys.md` và việc còn lại P2+F7 của
  `2026-10-08-do-bien-the-dung-profile-recsys.md`: P2+F7 đã hoàn tất; hai job khác chưa hoàn tất tại lúc kiểm tra.
- File JSON được ghi sau mỗi arm; không dùng sự tồn tại của JSON làm bằng chứng toàn job xong.
- Giữ các sửa đổi có sẵn của người dùng/agent khác; danh sách trên chỉ là phần task này thay đổi.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/recsys_bench/tests/test_profile_variants.py`:
  **7 passed, 2 xfailed**.
- Chạy cùng lệnh với ba file `test_profile_variants.py`, `test_parity.py`, `test_engine_no_leak.py` trong thư mục tests:
  **20 passed, 2 xfailed**. Không DB/model/network.
- Python đối chiếu từng dòng LLBO/temporal/nexttrip trong report với `profile_p2f7.json`: cả ba dòng khớp.
- `git diff --check`: PASS.
- File lúc 16:03 giờ Việt Nam: `profile_p2f7.log` có `done 1207s`; `step2_x.json` có F12b, `step2_y.json` có F13b,
  chưa có F13a/F14 và chưa có `done`. Kiểm tra chỉ-đọc ngoài sandbox bằng `/proc`: PID 403054/403055 ở trạng thái R,
  đúng module eval_profile và đúng file out/scorers của hai job. Không in biến môi trường hoặc DSN.

## Còn lại / rủi ro

- Lỗi production vẫn còn; task chỉ bổ sung kiểm thử, không áp dụng P1/P2/P4.
- Hai job còn chạy tại snapshot; cần đọc F13a/F14 khi hoàn tất. Không lập monitor hoặc hứa thông báo tự động.
- P2+F7 tăng bám chủ đề giả lập nhưng giảm temporal/nexttrip; chưa đủ cơ sở chọn production.
- JSON cũ không lưu revision/config hash đầy đủ; report ghi giới hạn provenance, không suy đoán commit của lần chạy.
