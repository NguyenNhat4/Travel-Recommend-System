# CP3: phân loại lỗi và chiến thuật cho từng loại (thử lại, bỏ qua nguồn bị chặn, chặn chất lượng)

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

CP3 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`. Người dùng muốn "lỗi thì tự retry, hoặc có chiến thuật
khác theo log". Trước đây mọi lỗi như nhau: không thử lại ở mức nguồn/bước, lượt dừng.
- Ví dụ 28/09: `database is locked` ở trip → lượt không nạp DB.
- Trip trả 0 khách sạn → cả nhóm trip dừng.

Phục vụ FR-CAT-01..04.

## File thay đổi

- `src/data_collection/pipeline_errors.py` — thêm: loại lỗi (`transient`, `blocked`, `code`, `quality`, `infra`, `unknown`), exception tương ứng, `classify_exit` (mã thoát + log cuối của `crawl.py`), `classify_exception`, `strategy`.
- `src/data_collection/fresh_catalog.py` — sửa:
  - `run_source` giữ 80 dòng log cuối của mỗi nguồn;
  - `crawl_sites` phân loại lỗi từng nguồn: tạm thời → thử lại (chờ tăng gấp đôi); bị chặn → đánh dấu, không thử lại, nguồn khác chạy tiếp; code/chưa phân loại → dừng ngay;
  - bước trong tiến trình (tìm ID khách sạn Trip) ném `BlockedError` khi trả 0 khách sạn → bỏ bước hỏi giá, nhóm trip vẫn cào vé máy bay và điểm tham quan; lượt coi như không có khách sạn Trip;
  - `with_retry` cho bảo trì DB, nạp DB, index (lỗi hạ tầng/tạm thời);
  - normalize lỗi → `CodeError`;
  - bước validate lỗi → `QualityGateError`, thêm `quality_drop_check`;
  - `run.json` có `errorKind` của lượt.
- `src/data_collection/fresh_run_log.py` — sửa: bước lỗi lấy trạng thái từ exception (`BlockedError` → `blocked`) và ghi `errorKind`.
- `src/data_collection/fresh_settings.py` — sửa: nhóm cấu hình "Thử lại và kiểm chất lượng" gồm `retry.transientAttempts` (2), `retry.transientDelay` (30 s), `retry.infraAttempts` (3), `retry.infraDelay` (60 s), `quality.maxDropPercent` (50, 0 = tắt); chuyển `normalise.maxErrorPercent` vào nhóm này.
- `src/data_collection/monitor.py` — sửa: bước trả `errorKind`; bảng nguồn ghi chú số lần đã thử lại.
- `src/data_collection/monitor_ui/index.html` — sửa: cột "Lỗi / thử lại" (loại lỗi + chiến thuật, các lần thử lại) trong bảng bước; loại lỗi của lượt ở đầu trang.
- `src/data_collection/tests/test_pipeline_errors.py` — thêm: 11 test (phân loại mã thoát/log và exception; chiến thuật theo cấu hình; thử lại rồi thành công; hết lượt thử; lỗi code dừng ngay; nguồn bị chặn không dừng nguồn khác; tìm ID bị chặn bỏ bước giá nhưng giữ vé máy bay/điểm tham quan; thử lại lỗi hạ tầng; cổng giảm mạnh; bước `blocked` trong `run.json`).
- `history/2026-09-28-cp3-phan-loai-loi-va-thu-lai.md` — thêm: entry này.

## Quyết định

- "Trip trả 0 khách sạn" được xếp vào *bị chặn*, xử lý **như mã 75 hiện có**: nguồn đó bị bỏ, lượt vẫn chuẩn hoá/nạp phần còn lại và trả mã 3 (partial). Trước đây lỗi này làm cả lượt không nạp DB. Quy tắc "một nguồn *lỗi* thì không nạp DB" (quyết định A/B) **giữ nguyên** cho lỗi code/tạm thời hết lượt thử.
- Không đoán lỗi chưa phân loại là tạm thời: dừng ngay để người vận hành xem log, tránh thử lại vô ích.
- Cổng "catalog giảm mạnh" chỉ so với lượt thành công gần nhất **cùng chế độ, cùng phạm vi điểm đến, cùng bộ nguồn**, vì đổi phạm vi thì số dòng khác là bình thường.
- Chờ giữa các lần thử lại kiểm tra nút Dừng mỗi 0,5 giây.

## Kiểm tra

- `pytest tests` (env `vsf`): **380 passed, 3 skipped** (thêm 11). Test cũ của runner vẫn pass.
- CP3 không đổi logic normalize nên không cần so `sha256`.
- `git diff --check`: sạch.

## Còn lại / rủi ro

- Mẫu nhận diện lỗi trong `pipeline_errors.py` dựa trên log hiện có; loại lỗi mới sẽ rơi vào "chưa phân loại" (dừng) cho tới khi thêm mẫu.
- CP4 tiếp theo. Chưa commit.
