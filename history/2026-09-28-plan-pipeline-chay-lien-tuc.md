# Plan: pipeline chạy liên tục (chuẩn hoá, gộp, nạp DB, index theo phần trong lúc cào)

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs (data)

## Mục tiêu

Người yêu cầu muốn chuẩn hoá từng phần trong lúc đang cào, và tự động tới hết: "đủ catalog nào thì nạp cái đó".

## File thay đổi

- `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md` — thêm: plan L1–L6:
  - L1: chuẩn hoá từng phần khi interim lớn dần;
  - L2: Vinpearl ghi interim từng bản ghi;
  - L3: gộp nháp liên tục;
  - L4: nạp DB theo phần, kèm sửa `prepare_rows` tra theo `sameAs`;
  - L5: index theo phần;
  - L6: monitor cho các bước liên tục.

## Quyết định

- Người yêu cầu chọn chạy liên tục tới hết, nạp DB theo phần. Việc này thay quy tắc "được cả hoặc không có gì" của CP3.
  Đây là quyết định của nhóm ghi trong `history/`, không nằm trong PRD, nên không cần đề xuất trong `docs/prd/update/`.
- Phát hiện khi đọc code:
  - Vinpearl chỉ ghi interim ở cuối (`collectors/vinpearl.py:746`) → cần L2;
  - `prepare_rows` chỉ tra dòng mới bằng `sourceRef` → nạp theo phần có thể tạo dòng trùng và làm lỗi lượt sau → sửa ở L4.
- Định nghĩa "đủ", hệ quả của việc nạp theo phần, chu kỳ mặc định và thứ tự so với UI3 là **đề xuất của agent**,
  ghi ở mục "Cần chốt" của plan.

## Kiểm tra

- Chỉ viết tài liệu; không chạy test. Đã đọc `fresh_catalog.py` (`crawl_sites`, `Previewer`), `fresh_catalog_db.py`
  (`load_into_db`, `prepare_rows`), `collectors/common.py` (`JsonlWriter`) và cách các collector ghi interim.

## Còn lại / rủi ro

- Chờ người yêu cầu duyệt plan và chốt 4 mục "Cần chốt".
- Chưa commit.
