# Đưa lịch 10 ngày vào docs/plan, thêm mã FR/NFR và mục đính chính 29/09

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/recsys-harness
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

File lịch 10 ngày (`2026-09-28-lich-10-ngay-3-engine.md`) nằm ở `docs/spec/bench/`, chưa commit, thiếu mã FR/NFR và có vài chỗ lỗi thời so với repo. Máy làm phần B và C của Day 1 cần một bản lịch đúng chỗ để tick và ghi số.

## File thay đổi

- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — thêm (chuyển từ `docs/spec/bench/`, file chưa từng track nên không có `git mv`): thêm dòng "Phục vụ" (FR-SRC-01..04, FR-REC-01..04, NFR-PERF-01/03, test-plan §2.4–2.5); sửa dòng căn cứ trỏ đúng `docs/plan/2026-09-28-summary-search-recsys-benchmark.md`; thêm mục "0.1. Đính chính 29/09 (B, C)".

## Quyết định

- Đặt ở `docs/plan/` theo `AGENTS.md` §7 (plan bắt đầu bằng ngày, phải ghi mã FR/NFR); chính dòng 3 cũ của file cũng đề xuất vị trí này.
- Không viết lại các mục gốc; thêm bảng đính chính để giữ nội dung gốc đối chiếu. Chưa có mục nào bị đóng băng.
- Các đính chính: nhánh B tách từ `bench/embed-search` và port có chọn lọc thay vì merge `origin/khoa/recsys-research` (nhánh đó dựng trên nền 21/09, merge sẽ vỡ: `ports/recsys.py` đã đổi thành `ports/unit_index.py`, `UnitIndex` không còn `E`, `PostgresVectorStore.load()` trả tuple, `SentenceTransformersEmbedder` đã comment); nhánh C tách từ `release-mvp-v2` (nhánh deploy, đã chứa bench); mốc test 651 passed thay 495; lọc gid chỉ áp purchase; Zipf 0,8; `eval/report.md` → `docs/spec/bench/recsys-offline-eval.md`; `docs/decisions/` → `docs/prd/update/` nếu đổi embedding; 3 lệch handbook so bản gốc `e33bdb6^`; "bật SEARCH_HYBRID" thực chất là backfill + xác nhận; kỳ vọng P1 có thể trượt ở `nextVertical`; ngưỡng p95 250 ms theo PRD.

## Kiểm tra

- `grep -n "FR-REC" docs/plan/2026-09-28-lich-10-ngay-3-engine.md`: có dòng "Phục vụ".
- Không còn file `.md` chưa track trong `docs/spec/bench/`.

## Còn lại / rủi ro

- Các số Day 1 của B/C sẽ được tick và ghi vào lịch ở entry `2026-09-29-recsys-harness-day1.md` và `2026-09-29-search-stage-timing.md`.
- Người làm A1/A2 cần biết lịch đã chuyển chỗ; mục A không bị sửa.
