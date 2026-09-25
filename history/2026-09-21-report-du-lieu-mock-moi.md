# Báo cáo bộ dữ liệu mock mới

- Ngày: 2026-09-21
- Tác giả: nhatnm / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Viết báo cáo có thể tái lập cho dữ liệu mới được tích hợp từ nhánh mockdata, dùng số liệu chạy thật trên snapshot 10.320 sản phẩm thay vì chỉ tóm tắt commit. Báo cáo cần phân biệt dữ liệu catalog, dữ liệu hành vi tổng hợp, Insider clone và bằng chứng chất lượng Recommendation.

## File thay đổi

- `src/data_collection/README.md` — sửa: mở rộng khối `seed-report` với lệnh tái lập, phân bố catalog, combo, CDP history, Insider, baseline Recall@20 và giới hạn bằng chứng.
- `history/2026-09-21-report-du-lieu-mock-moi.md` — thêm: entry lịch sử cho task report.

## Quyết định

- Giữ report trong khối `<!-- seed-report:start -->`…`<!-- seed-report:end -->` theo `docs/MOCK_DATA_SPEC.md`; không tạo thêm nguồn báo cáo cạnh tranh.
- Dùng `--as-of 2026-09-21 --seed 42`, đúng seed demo đã chốt, để số liệu tái lập được.
- Chạy `--generate-only` để thu số liệu mà không thay đổi PostgreSQL đang phục vụ demo.
- Ghi Recall@20 = 58,4% là baseline most-popular-in-destination để sanity-check dữ liệu, không gọi đó là chất lượng model Recommendation.
- Ghi rõ `catalog.product_vectors = 0`; catalog và lịch sử mock sẵn sàng không đồng nghĩa embedding/ranking đã được chứng minh.

## Kiểm tra

- `cd src && PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m data_collection.seed --products data_collection/snapshots/2026-09-21/products.jsonl.gz --as-of 2026-09-21 --seed 42 --generate-only` → PASS, exit code 0.
- Kết quả chính: 10.320 products; 2.000 profiles; 7.131 events; 93 combo/218 thành phần; Recall@20 58,4%; Insider 2.000 profiles/4.155 events/19.517 channel events; 8 nhóm vi phạm Insider đều bằng 0.
- PostgreSQL không bị thay đổi trong lần chạy này.

## Còn lại / rủi ro

- Chưa chạy `db/verify.sql` và `db/verify_insider.sql` trong task report vì dùng `--generate-only`, không nạp database.
- Chưa nạp product vectors và chưa chạy evaluation của model Recommendation; không dùng report này làm bằng chứng ranking model hoạt động đúng.
- Số liệu ngày và availability phải được sinh lại với `--as-of` mới trước demo.
