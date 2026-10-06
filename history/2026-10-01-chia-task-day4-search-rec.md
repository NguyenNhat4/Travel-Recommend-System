# Chia task Day 4 cho 2 người (Search / Rec) trên nhánh `bench_search_recomSys`

- Ngày: 2026-10-01
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chuyển sang nhánh bench, muốn biết nhánh có gì mới, recsys còn việc gì của Day 4, và chia Day 4 thành task chi
tiết cho 2 người: 1 người làm search, 1 người làm rec. Plan Day 4–5 (`docs/plan/2026-10-01-plan-day4-5.md`) đang viết cho 4
vai (A1, A2, B, C). Phục vụ FR-SRC-01..04, FR-REC-01..04.

## File thay đổi

- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — thêm: hiện trạng nhánh so với plan Day 4 (search, rec); 8 task S và
  8 task R, mỗi task có lệnh và tiêu chí xong; checkpoint 17:15 từng người; điểm nối giữa hai người; 4 điểm chưa rõ.

## Quyết định

- Người dùng chốt: **merge M6 trước** (`origin/bench/m6-trip-ended`, đề xuất category exclusion theo chuyến đã áp dụng),
  mốc engine cho bảng recsys Day 4–5 là **v5**, không phải v0 như plan viết.
- Gộp 4 vai thành 2: S nhận Track A + phần search của Track C (index model, latency embed); R nhận Track B + phần recsys của
  Track C (kiểm exclusion/diagnostics, đối chiếu contract).
- Việc Track A Day 4 đã xong theo đường khác (`gold_v1` 30/09, vòng hole D4a → `gold_v2` 01/10) nên không lặp lại; task S bắt
  đầu từ cổng SAN, README gold và bảng Search v1.
- PR contract của plan §1.3 #5 phần lớn đã có trong contract 1.12.0 → chỉ đối chiếu, không mở PR mới.

## Kiểm tra

- Không chạy lệnh nào ngoài đọc: `git fetch`, `git log` / `git diff` giữa nhánh và `main` / `test/newcrawl` / nhánh M6 /
  `khoa/recsys-research`; grep code `recsys_bench`, `search_bench`, contract.
- `bench_search_recomSys` (= `fe7e04d`) đã nằm trong `test/newcrawl` → không có commit mới so với chỗ người dùng đứng trước đó.

## Còn lại / rủi ro

- 4 điểm chưa rõ ở §4 của plan (file research `TRAINING_FREE_RECSYS.md` / `serve_bench.py` không có trong repo; bge-m3 int8
  hay fp32; tên tag gold sau top-up; `/search` cloud 500 chưa ai nhận).
- Plan này và entry chưa commit.
