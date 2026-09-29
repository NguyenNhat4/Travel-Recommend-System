# L2 phần 1: chuẩn hoá dần Vinpearl bằng cách đọc file tạm của collector

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

L2 của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`: Vinpearl (nguồn chậm nhất) cũng được chuẩn hoá dần trong lúc cào.

## File thay đổi

- `src/data_collection/normalise_stream.py` — sửa:
  - `SourceFollower._open`: chưa có `<nguồn>.jsonl` thì đọc `<nguồn>.jsonl.tmp`;
  - `poll_all` nhận ra nguồn chỉ có file tạm;
  - `finish_source` / `close` xoá checkpoint của nguồn không có file chính (`_drop`).
- `src/data_collection/tests/test_normalise_stream.py` — sửa: thêm 2 test (`PartialFileTests`).
- `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md` — sửa:
  - sửa mô tả Vinpearl ở "Hiện trạng" (bản đầu ghi nhầm);
  - viết lại L2 thành phần 1 (xong) và phần 2 (chờ số đo);
  - cập nhật tiến độ.

## Quyết định

- Không sửa collector: đọc lại `collectors/vinpearl.py` thấy nó đã ghi từng khách sạn/tour vào `vinpearl.jsonl.tmp`
  (`JsonlWriter` flush ngay) và chỉ đổi tên ở cuối. Đổi tên giữ inode nên bộ theo dõi đọc tiếp, không đọc lại từ đầu.
- Nguồn dừng trước khi đổi tên (lỗi, bị dừng) thì bản theo lô không có nguồn đó. Vì vậy checkpoint dựng từ file tạm bị xoá
  lúc chốt hoặc lúc dừng luồng. Catalog nháp trong lúc cào vẫn thấy dữ liệu.
- Vinpearl combo: giữ hết trong bộ nhớ nên phải sửa collector. Chưa làm, chờ số đo thời gian cào. agoda API: giữ nguyên.

## Kiểm tra

- `pytest tests/test_normalise_stream.py` (env `vsf`): **18 passed**. `pytest tests`: **419 passed, 3 skipped**.
  `git diff --check`: sạch.
- Chưa kiểm trong lượt cào thật. Lượt `full-20260928T080824Z-245196` người yêu cầu vừa chạy chưa bật `stream.enabled`.

## Còn lại / rủi ro

- L2 phần 2 (Vinpearl combo), L3–L6. Chưa commit.
