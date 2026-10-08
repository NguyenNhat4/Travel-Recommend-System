# Sửa lỗi nạp DB của job cào (ref trùng) và bật lại dòng bị cửa sổ tắt

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl (soạn trên bench_search_recomSys, chuyển sang cùng ngày)
- Trạng thái: dang dở (code chưa deploy lên VM)
- Phạm vi: data, docs

## Mục tiêu

Team Web báo blocker ngày 06/10: vé máy bay mất cân bằng, nhiều địa điểm không có giá. Người dùng nghĩ đã sửa ở `2026-10-02-mo-lich-phong-30-ngay-va-sua-khoa-trinh-duyet.md` nhưng job cào cũ ghi đè. Kiểm tra cho thấy job không ghi đè: **từ lượt 03/10 job lỗi ở bước nạp DB** (`ValueError: sourceRef/sameAs conflict: agoda:hotel:...`), nên DB VM không nhận dữ liệu mới từ 02/10. Phục vụ FR-CAT-02, FR-CAT-03.

## Hiện trạng DB VM trước khi sửa (tunnel 15432, chỉ đọc)

- `lastSeenAt`/`priceObservedAt` lớn nhất = 02/10; lịch phòng `from = 2026-10-02`; 8.693/8.693 phòng đang bán mở đủ 30 ngày (bản sửa 02/10 còn nguyên).
- Monitor `/api/alerts`: lượt 03/10, 04/10, 05/10 đều `Lượt lỗi ... sourceRef/sameAs conflict`.
- 21 khách sạn trùng: dòng `booking:hotel:*` (19) hoặc `vinpearl:hotel:*` (2) đã ghi ref agoda vào `sameAs`, trong khi dòng `agoda:hotel:*` riêng vẫn chưa `mergedInto`. Lỗi bắt đầu ngay sau đợt nạp phòng Agoda bằng tay ngày 02/10 (suy luận theo thời điểm, chưa xác minh trực tiếp).
- Hệ quả 4 ngày không nạp: 116 vé thật + 116 vé thương gia mô phỏng đã bay vẫn `available`; vé khứ hồi thật đặt được chỉ ở 6 điểm đến; 62 vé khứ hồi bay 01–04/11 bị tắt lúc ngoài cửa sổ và không bật lại (nhưng báo giá của chúng đã hết hạn 02/10, nên theo `data-model.md` §3.1 vẫn phải tắt).
- 301 điểm tham quan `unit_price` NULL đang `available`: điểm công cộng không bán vé, đúng thiết kế, không phải lỗi job.

## Sửa DB VM (bước 1, người dùng tự chạy script)

- Sao lưu trước: `src/data_collection/data/vm-repair-20261006/backup-conflict-rows.jsonl` (42 dòng), `backup-children-rooms.jsonl` (59 phòng), `merge-plan.jsonl` (21 cặp; mỗi cặp cùng tên, cùng điểm đến; không giỏ/đơn/combo nào trỏ tới dòng agoda).
- Script `src/data_collection/data/vm-repair-20261006/apply.py` (thư mục ignored): một transaction, `pg_advisory_xact_lock(7791024)`; dòng agoda nhận `mergedInto`, bỏ `availability`, `available = false`; 59 phòng con chuyển `parentProductId` sang dòng giữ; assert đủ số dòng và 0 xung đột trước commit. Lệnh ghi của agent bị auto mode chặn nên người dùng chạy: in `merged 21 rooms reparented 59 conflicts left 0`, `COMMITTED`.
- Kiểm lại: 0 ref trùng; 0 phòng trỏ vào dòng đã gộp; khách sạn có phòng đặt được 2.142/2.445 → 2.121/2.424 (cùng bớt đúng 21 bản trùng).

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa:
  - `resolve_ref_conflicts` (mới): hai dòng chưa gộp cùng nhận một ref thì giữ dòng ghi ref trong `sameAs` (cùng loại thì `product_id` nhỏ hơn), dòng kia vào danh sách gộp thay vì `raise`. `prepare_rows` dùng hàm này; đếm `refConflicts`.
  - Dòng bị gộp (cả gộp do ref trùng lẫn gộp L4 cũ): phòng con cũ chuyển `parentProductId` sang dòng giữ ở cuối `prepare_rows`.
  - Vòng đánh dấu phòng Trip "missing" bỏ qua dòng vừa gộp, tránh ghi một `product_id` hai lần trong cùng lô.
  - `apply_window`: dòng đang bán bị cửa sổ tắt nhận `windowClosed`; cửa sổ cuộn tới thì bật lại nếu còn giá, chưa gộp, không có `priceFreshness`. Vé ngày cố định hết hạn báo giá vẫn có giao rỗng nên vẫn tắt. Dòng tắt vì lý do khác không có dấu nên không bị bật.
  - `price_attributes`: dòng được lượt cào làm mới bỏ `windowClosed` (nguồn quyết định `available`).
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa/thêm: đổi test "never reopens" thành chỉ không bật dòng tắt vì lý do khác; thêm test bật lại theo cửa sổ, test không bật vé hết hạn/đã gộp/stale/không giá, test ref trùng trong DB (gộp, chuyển phòng con, lượt sau hết xung đột), test dòng mới của dòng bị gộp ánh xạ về dòng giữ.
- `src/data_collection/README.md` — sửa: quy tắc bật lại theo cửa sổ và cách job xử lý ref trùng.
- `docs/spec/data-collection/schema.md` — sửa: mô tả `mergedInto` khi ref trùng; thêm khoá `windowClosed`.

## Quyết định

- Không lệch PRD: `data-model.md` §3.1 chỉ quy định vé ngày cố định ngoài cửa sổ hoặc hết hạn báo giá thì không đặt được; câu "không bật lại" chỉ ở docstring và README, đã sửa cùng code. `windowClosed` là khoá nội bộ của `cdp.products` như `mergedInto`, ghi vào spec, không thêm cột.
- Không bật lại 62 vé khứ hồi đang kẹt: báo giá hết hạn 02/10. Chúng mở lại khi được cào báo giá mới.
- Dòng tắt bởi cửa sổ trước thay đổi này không có `windowClosed` nên code mới không bật lại; chạy thử trên dữ liệu VM không thấy dòng nào cần bật (xem Kiểm tra).

## Kiểm tra

- `pytest tests/test_fresh_catalog_job.py tests/test_stream_feed.py` (vsf2, `PYTHONPATH=src:src/data_collection`): 57 passed.
- `pytest src/data_collection/tests`: 482 passed, 21 skipped, 4 failed. Bốn test fail (`test_live_monitor` ×2 preview, `test_normalise_steps`, `test_normalise_stream`) cũng fail trên HEAD `c47fc35` trong worktree sạch: lỗi có sẵn.
- Chạy thử code mới trên dữ liệu DB VM sau khi gộp, trong bộ nhớ, không ghi (`prepare_rows([], existing)` + `apply_window`, as_of 06/10): `refConflicts = 0`; 12.704 dòng đổi cửa sổ; 386 vé tắt và nhận `windowClosed` (đã bay hoặc hết hạn báo giá); 0 dòng bật lại.

## Còn lại / rủi ro

- **Code chưa deploy.** Commit này và các sửa ngày 02/10 (`bb41479`) chưa có trên nhánh deploy (`main`/`release-mvp-v2`). Lượt cron tối 06/10 chạy image cũ: không còn ref trùng nên bước nạp kỳ vọng qua được, nhưng chưa có bật lại theo cửa sổ.
- Cần xem monitor sau lượt cron 19:00 UTC 06/10 để xác nhận bước nạp và index chạy được.
- 21 khách sạn agoda đã gộp có thể còn trong Weaviate tới lượt index thành công kế tiếp.
- Chưa commit (chờ người dùng).
