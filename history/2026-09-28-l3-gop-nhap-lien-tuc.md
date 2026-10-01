# L2 phần 2 và L3: gộp catalog đang gộp theo chu kỳ

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

L3 của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`: catalog đang gộp được cập nhật theo chu kỳ khi có nguồn được
chuẩn hoá thêm, không chỉ khi một nhóm site xong. Người yêu cầu yêu cầu làm hết các phần còn lại rồi review một lần,
"nhớ tự test đầy đủ".

## File thay đổi

- `src/data_collection/stream_feed.py` — thêm:
  - `Ticker`: vòng lặp chung đọc lại chu kỳ, tạm dừng, chạy ngay mỗi 0,5 s; lỗi một lô chỉ ghi log;
  - `checkpoint_signature`, `DraftMerger` (L3).
- `src/data_collection/fresh_catalog.py` — sửa: `Previewer` tạo `Ticker('merge', DraftMerger(...))` khi `stream.enabled`,
  gọi `_request_merge` hiện có (không chạy chồng).
- `src/data_collection/fresh_settings.py` — sửa: thêm `stream.mergeSeconds` (mặc định 30).
- `src/data_collection/tests/test_stream_feed.py` — thêm: test `DraftMerger`, `Ticker`.
- `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md` — sửa: L2 phần 2 không áp dụng; tiến độ.

## Quyết định

- L2 phần 2 không áp dụng: `source_command` chỉ gọi `crawl.py vinpearl`, job cào mới không chạy `vinpearl-bundles`.
- Gộp vẫn chạy trong tiến trình con `normalise.py --merge-only` như CP5: tách bộ nhớ khỏi job. Mỗi lần gộp vẫn ghi một bước
  `normalise.preview` trong `run.json`.
- Chỉ gộp khi dấu vân tay checkpoint (tên, mtime, cỡ các `*.meta.json`) đổi.

## Kiểm tra

- `pytest tests/test_stream_feed.py` (env `vsf`): `DraftMerger` chỉ gộp khi checkpoint đổi; `Ticker` áp chu kỳ, tạm dừng,
  chạy ngay khi đang chạy; `close` đợi lô đang chạy.
- `tests/test_normalise_stream.py::PreviewerFeedTests`: checkpoint đổi → gộp thật (tiến trình con) → có
  `preview/products.jsonl`; không đổi → không gộp lại.
- Kết quả cả bộ: xem entry L6.

## Còn lại / rủi ro

- Lượt 20 phút với chu kỳ 30 s tạo tới ~40 bước `normalise.preview` trong `run.json`.
- Chưa chạy trong lượt cào thật. Chưa commit.
