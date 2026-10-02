# L5: index Weaviate theo phần trong lúc cào

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

L5 của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`: sản phẩm đã nạp DB theo phần thì tìm được qua Search ngay (FR-SRC-02).

## File thay đổi

- `src/data_collection/stream_feed.py` — thêm `IndexFeeder`.
- `src/data_collection/fresh_catalog.py` — sửa: `Previewer` tạo `Ticker('index', IndexFeeder)` khi bật `stream.index`
  và có nạp DB theo phần.
- `src/data_collection/fresh_settings.py` — sửa: thêm `stream.index` (mặc định tắt), `stream.indexSeconds` (300).
- `src/data_collection/tests/test_stream_feed.py`, `tests/test_normalise_stream.py` — sửa: thêm test.

## Quyết định

- Chỉ chạy khi `DbFeeder.written` tăng từ lần index trước. Gọi đúng `index_catalog` của bước chính thức (tăng dần theo
  `textHash`, chỉ gọi Cohere cho dòng mới/đổi text). Chi tiết ghi `index_detail.stream.jsonl` để không đè
  `index_detail.jsonl` của bước chính thức.
- Mỗi lần ghi một dòng `index_batches.jsonl`. Lỗi chỉ ghi log, thử lại ở chu kỳ sau. Bước index chính thức cuối lượt giữ nguyên.

## Kiểm tra

- `IndexFeeder` không gọi index khi không có dòng DB mới; gọi đúng một lần sau lô nạp (test đơn vị và `PreviewerFeedTests`,
  index giả lập).
- **Chưa** gọi Cohere / Weaviate thật trong test.

## Còn lại / rủi ro

- Cohere bị gọi nhiều lần hơn trong lượt; dòng về sau bị gộp vẫn đã được nhúng một lần.
- Chưa chạy thật. Chưa commit.
