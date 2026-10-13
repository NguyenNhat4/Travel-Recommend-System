# Tìm nhanh trên toàn database ở tab DB của monitor

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: fix/crawl-stall-watchdog (worktree `~/code/trp-crawl-stall`)
- Trạng thái: dang dở — code + test + kiểm trên monitor local xong, đã commit + push nhánh, chưa PR/deploy (người dùng: mai merge)
- Phạm vi: data, docs
- Đề xuất: `docs/prd/update-archive/2026-10-13-tim-nhanh-tab-db-monitor.md` (chốt bởi Phạm Nguyễn Đăng Khôi 2026-10-13, đã áp dụng)

## Mục tiêu

Người dùng: tab DB "hơi gò bó", muốn "search data nào là ra nó ngay"; chốt đề xuất ("chốt, làm phần tìm nhanh tab DB luôn đi").
Trước đó phải chọn bảng rồi bấm Tìm; ô tìm ghép mọi cột `ILIKE`, phân biệt dấu, đếm cả bảng.

## File thay đổi

- `docs/prd/deployment-plan.md` — sửa: mục "Xem DB trên monitor job cào (tab "DB")" thêm ô tìm nhanh, ô lọc không phân biệt dấu
  (đúng nội dung đề xuất đã chốt), cập nhật trước khi sửa source.
- `docs/prd/update/2026-10-13-tim-nhanh-tab-db-monitor.md` → `docs/prd/update-archive/` — đổi tên (chuyển): trạng thái "đã áp
  dụng".
- `src/data_collection/db_browser.py` — sửa: `fold`, `accent_regex`; `search()` (tìm chung, mỗi bảng một câu lệnh, lỗi / quá giờ
  chỉ ở bảng đó), `_search_plan`, `_search_group`; ô lọc của bảng (`_where`) không phân biệt dấu và cần đủ mọi từ; `rows()` có
  chuỗi tìm thì đếm tới `COUNT_CAP` 10.000 (`totalCapped`).
- `src/data_collection/monitor.py` — sửa: route `GET /api/dbx/search?q=&limit=`.
- `src/data_collection/monitor_ui/index.html` — sửa: thẻ "Tìm nhanh trong cả database" ở tab DB (tìm 250 ms sau phím cuối, bỏ
  kết quả cũ khi có kết quả mới, tô sáng mọi từ, bấm khoá mở dòng, nút "Mở bảng, lọc theo chuỗi này"); ô lọc bảng lọc khi đang
  gõ (400 ms) và giữ con trỏ; "hơn N dòng"; chuỗi tìm trên địa chỉ trang `#page=db&q=…` (`replaceState`, không thêm lịch sử
  mỗi phím); đổi bảng / bỏ lọc giữ kết quả tìm.
- `src/data_collection/tests/test_db_browser.py` — sửa: 2 test thuần (`fold`, `accent_regex`) + 6 test PostgreSQL (không dấu và
  xếp hạng; đủ mọi từ; UUID / email / mã đơn; không đọc cột bí mật; bảng quá giờ được báo, bảng khác vẫn trả; ô lọc không dấu,
  đủ mọi từ, trần đếm).
- `src/data_collection/README.md` — sửa: đoạn "Tìm nhanh ở tab DB".
- `history/2026-10-13-tim-nhanh-tab-db-monitor.md` — thêm: entry này (bản đầu tên `2026-10-13-de-xuat-tim-nhanh-tab-db.md`, đổi
  tên trước khi commit).

## Quyết định

- Không bỏ dấu dữ liệu trong DB: đo trên `vota_dbx_test_20260930` (12.515 sản phẩm) `lower(translate())` mất 639 ms cho 4 cột
  chữ ngắn, 7,7 s khi có `description`, 19,9 s cho mọi cột; DB không có extension `unaccent` (kết nối chỉ đọc không tạo được).
  Thay bằng biểu thức chính quy từ chuỗi tìm (mỗi chữ cái một lớp mọi dạng hoa / thường / có dấu): 23–43 ms cho cột chữ ngắn,
  383 ms cho mọi cột kể cả `attributes` (`ILIKE` cũ: 610 ms).
- Tìm chung chỉ trên cột chữ ngắn (bỏ cột tên chứa description / content / evidence / url / image / user_agent / checksum) và
  không gồm view (lặp dữ liệu bảng); ô lọc của bảng vẫn tìm mọi cột như trước.
- Nhiều từ: dòng phải có đủ mọi từ (ở cột nào cũng được), vì cụm liền "vinpearl phu quoc" bỏ sót "Vinpearl Resort & Spa Phú Quốc";
  dòng khớp trọn / đầu chuỗi / cả cụm vẫn xếp trước.
- Giữ ràng buộc PRD: chỉ đọc, `statement_timeout` 5 s, cột bí mật không hiện và không tìm (NFR-SEC-01).

## Kiểm tra

- `DBX_TEST_DATABASE_URL=…/vota_dbx_test_20260930 pytest data_collection/tests/test_db_browser.py`: 20 passed (12 cũ + 8 mới).
- `DBX_TEST_DATABASE_URL=… pytest data_collection/tests` (cả nhánh, gồm phần phát hiện nghẽn): 683 passed, 18 skipped;
  `compileall src/data_collection`: ok.
- Phá thử: cho `is_secret` luôn sai → `test_quick_search_never_reads_secret_columns` FAIL.
- `node` kiểm cú pháp script của `monitor_ui/index.html`: ok.
- Monitor local (`.claude/launch.json` `monitor-stall-local`, chỉ đọc, DB nháp), 13/10: gõ "ba na" → 3 kết quả 124 ms, tô sáng
  "Bà Nà", con trỏ giữ ở ô tìm; "vinpearl phu quoc" (mở bằng `#page=db&q=…`) → 10+ sản phẩm, 114 ms, tô sáng từng từ ở tên và
  điểm đến; dán UUID sản phẩm → `cdp.products` 1 + `cdp.events` 5, 61 ms, bấm khoá mở cửa sổ dòng; "Mở bảng, lọc theo chuỗi
  này" → `cdp.products` 46 dòng; gõ "vinpearl phu quoc" vào ô lọc bảng → lọc khi đang gõ, giữ con trỏ; khung 390 px: không cuộn
  ngang (scrollWidth 390).
- Chưa đo trên catalog production (~45 nghìn sản phẩm): DB production tắt từ 13/10 00:45.

## Còn lại / rủi ro

1. PR, Crawler CD — khi người dùng bảo; sau deploy đo thời gian tìm trên production.
2. Từ rất ngắn trong chuỗi nhiều từ khớp nhiều (vd. "ba na" cũng ra "Vé máy bay … Đà Nẵng" ở cuối danh sách vì "bay" chứa "ba").
