# Ô lọc bảng ở tab DB bỏ cột JSON / chữ dài mặc định (sau khi đo trên production)

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`). Người dùng 13/10: "tôi muốn push lên nhánh
  test new crawl thôi" → commit ee7b4201 của `fix/crawl-stall-watchdog` (phát hiện nghẽn, tìm nhanh tab DB, tên Sota; ba
  entry lịch sử 13/10 của nó) được cherry-pick sang test/newcrawl thành 4291da3c, rồi commit thay đổi của entry này.
- Trạng thái: dang dở — commit + push lên test/newcrawl; chưa PR vào release-mvp-v2, chưa deploy
- Phạm vi: data
- Liên quan: `history/2026-10-13-tim-nhanh-tab-db-monitor.md`, đề xuất
  `docs/prd/update-archive/2026-10-13-tim-nhanh-tab-db-monitor.md` (ô lọc "không phân biệt dấu và tìm khi đang gõ"; PRD không
  quy định ô lọc tìm những cột nào)

## Mục tiêu

Người dùng mở tunnel và nhờ "kiểm tra giúp". Đo ô tìm nhanh / ô lọc mới (commit ee7b4201) trên DB production bằng code của
nhánh chạy ở máy local, chỉ đọc: ô lọc `cdp.products` gồm mọi cột sát giới hạn 5 giây, chưa "ra ngay" như người dùng muốn.

## File thay đổi

- `src/data_collection/db_browser.py` — sửa: `_where(…, deep=False)` mặc định bỏ cột `jsonb`/`json` và cột chữ dài (`LONG_TEXT`:
  description, content, evidence, url, image…); bảng chỉ có cột nặng thì vẫn tìm mọi cột; `rows(…, deep=False)`;
  hằng `HEAVY_TYPES`.
- `src/data_collection/monitor.py` — sửa: `/api/dbx/rows` nhận `deep=1`.
- `src/data_collection/monitor_ui/index.html` — sửa: ô chọn "Tìm cả mô tả và JSON (chậm hơn)" cạnh ô lọc bảng; gửi `deep`;
  đổi ô chọn thì tải lại bảng.
- `src/data_collection/tests/test_db_browser.py` — sửa: test ô lọc: mặc định khớp trên cột nhẹ, `deep` khớp thêm (≥), các từ
  không cần đứng liền nhau.
- `src/data_collection/README.md` — sửa: đoạn "Tìm nhanh ở tab DB" thêm tuỳ chọn tìm sâu và số đo production.
- `history/2026-10-13-loc-bang-db-bo-cot-nang.md` — thêm: entry này.

## Quyết định

- Số đo production 13/10 09:25 (30.935 sản phẩm, 40.269 event; `EXPLAIN ANALYZE`, không tính mạng):
  - Tìm chung: tổng ~280 ms trong DB cho 19 bảng (`cdp.products` 187 ms, `cdp.events` 66 ms). Qua tunnel đo 2,7–3,3 s vì RTT
    70–200 ms × ~20 câu lệnh và mở kết nối; monitor trên VM cùng VPC với DB không chịu phần này. Không đổi.
  - Ô lọc `cdp.products` gồm mọi cột: đếm 1,7–2,5 s + trang tới 1,7 s → mặc định bỏ cột nặng: đếm ~0,2 s, trang ≤ 0,2 s.
    "vinpearl phu quoc": 164 dòng (cột nhẹ) / 416 dòng (cả mô tả, JSON).
- Giữ đường tìm cũ bằng ô chọn thay vì bỏ hẳn: đôi khi cần tìm trong mô tả / `attributes`.
- Không đổi entry `history/2026-10-13-tim-nhanh-tab-db-monitor.md` (đã commit, `history/README.md` không cho sửa entry cũ).

## Kiểm tra

- `DBX_TEST_DATABASE_URL=…/vota_dbx_test_20260930 pytest data_collection/tests/test_db_browser.py`: 20 passed.
- `DBX_TEST_DATABASE_URL=… pytest data_collection/tests`: 683 passed, 18 skipped.
- `node` kiểm cú pháp script của `monitor_ui/index.html`: ok.
- Production (tunnel, chỉ đọc): số đo ở mục Quyết định. Trang 50 sản phẩm ~240 KB (attributes 174 KB).
- Monitor local (DB nháp): bảng `cdp.products`, gõ "vinpearl phu quoc" → 116 dòng; bật ô chọn → 348 dòng, chuỗi lọc giữ nguyên.

## Còn lại / rủi ro

- Commit / PR khi người dùng bảo; sau deploy đo lại trên monitor production (không qua tunnel).
