# P2: nguồn đã cào xong được nạp theo phần dù dưới `stream.minRecords`

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Sau lượt kiểm P2 (`history/2026-09-29-p2-kiem-that-chay-lien-tuc.md`), người yêu cầu chốt theo đề xuất (2026-09-29):

1. Bật mặc định `stream.enabled` / `stream.db` **sau** lượt VM (bật bằng Cấu hình trên monitor VM trước).
   Không đổi code ở entry này.
2. Nguồn đã cào xong mà dưới `stream.minRecords` bản ghi vẫn được nạp theo phần.
   - Trước đây nguồn nhỏ (ví dụ booking 6 bản ghi ở lượt local) bị giữ tới lần nạp cuối lượt, dù đã cào xong từ lâu.
   - Ngưỡng tỉ lệ lỗi giữ nguyên.
3. Sửa tiêu chí "nạp lại cùng catalog thì 0 dòng ghi" trong plan P2 cho đúng mức `DbFeeder`.

Phục vụ FR-CAT-01..04.

## File thay đổi

- `src/data_collection/stream_feed.py` — sửa: `select_ready` coi site là đủ khi có ≥ `min_records` bản ghi **hoặc** mọi
  checkpoint của site đã chốt `ok`. Vẫn giữ ngưỡng tỉ lệ lỗi và "không checkpoint nào `failed`". Lý do giữ lại ghi rõ là
  "đang cào mà chưa đủ…".
- `src/data_collection/fresh_settings.py` — sửa: thêm giải thích cho `stream.minRecords` (chỉ áp khi nguồn còn đang cào).
- `src/data_collection/tests/test_stream_feed.py` — sửa: test mới
  `test_finished_site_below_minimum_is_ready_but_a_streaming_one_is_not`:
  - nguồn đã chốt, 5 bản ghi → nạp; còn đang cào → giữ;
  - site có một checkpoint đã chốt và một còn đang cào → giữ; cả hai đã chốt → nạp;
  - đã chốt nhưng lỗi vượt ngưỡng → giữ.
- `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md` — sửa: ghi chú quyết định mới ở "Đã chốt 1".
- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — sửa:
  - tiêu chí P2 "0 dòng ghi" → "`DbFeeder` không gửi lại dòng chưa đổi". Bản đầu sai, vì `load_into_db` luôn gắn
    `priceRefreshedAt` mới cho mọi dòng;
  - dòng tiến độ.
- `history/2026-09-29-p2-nguon-xong-khong-can-du-ban-ghi.md` — thêm: entry này.

## Quyết định

- "Xong" = mọi checkpoint của site (theo phần đầu `sourceRef`, ví dụ `trip_flights` + `trip_attractions`) có `status`
  `ok`. Chế độ chạy liên tục ghi `ok` khi chốt nguồn và `streaming` khi đang cào (`normalise_stream.py`).
- Khách sạn Trip và combo vẫn chỉ nạp ở cuối lượt, không đổi.

## Kiểm tra

- `pytest tests` (env `vsf`): **480 passed, 5 skipped** (thêm 1 test so với 479; 5 skip như trước).
- Kiểm test bắt được lỗi: tạm bỏ `or finished` → test mới fail (1 failed, 17 passed); đã khôi phục code.
- `git diff --check`: sạch.
- Chưa chạy lại lượt thật; lượt 1 hôm nay sẽ nạp booking, agoda, Trip ngay khi mỗi nguồn chốt, thay vì đợi Vinpearl.

## Còn lại / rủi ro

- Lượt VM (P2 bước 5) và bật mặc định (P2 bước 6): chờ triển khai.
- Chưa commit.
