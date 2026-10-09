# Plan bench RecSys với vector e5-small (Day 6 → Day 10)

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Nhóm chốt model embedding e5-small/384 thay Cohere. `report_week_3.md` (D8) yêu cầu chạy lại bench RecSys với model mới và so với `baseline_v1` trước khi deploy. Người dùng muốn tự làm bench này và cần danh sách việc chi tiết theo từng ngày, khớp trạng thái nhánh (`942f5aa`). Phục vụ FR-REC-01..04, FR-SRC-02, NFR-PERF-01.

## File thay đổi

- `docs/plan/2026-10-05-bench-recsys-e5-small.md` — thêm: plan Day 6–10 kèm mục Day 5 (nền đã có trên nhánh và phần chuyển tiếp), gồm:
  - bảng "đã có / còn thiếu" trên nhánh;
  - quy tắc quyết định ghi trước khi nhìn số;
  - việc từng ngày, mỗi việc có lệnh, đầu ra và điều kiện xong;
  - rủi ro.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: ô Day 6 "RecSys chạy bằng vector e5" trỏ tới plan mới.
- `history/2026-10-05-plan-bench-recsys-e5-small.md` — thêm: entry này.

## Quyết định

- Dùng vector có sẵn trong `bench_out/search/data/` (không embed lại). Mốc so sánh là `baseline_v1` (Cohere v3, `configHash b0aee886`, split `asof20260924`).
- Kiểm đường nạp `.npy` bằng chính vector Cohere trước (ids 100 %), rồi mới đo e5. Scorer CF phải trùng ids với run Cohere (kiểm chéo).
- Ngưỡng đạt lấy từ `baseline_v1.thresholds`: tụt ≤ 1,0 điểm tổng, ≤ 3,0 điểm phân khúc n ≥ 20.
- `baseline_v2` và mọi thay đổi production chỉ làm sau khi đề xuất PRD FR-SRC-02 được chốt (AGENTS.md §8).
- Phạm vi thu gọn theo tqanh123 (05/10): chỉ đo và viết report chi tiết (Day 6 → Day 8). Đề xuất PRD, `baseline_v2`, grid ADR 2 và đổi production chuyển sang mục "Ngoài phạm vi".
- Người dùng chốt tiếp (05/10):
  - chạy local, đo **e5-small và e5-base**, không dùng Cohere;
  - bỏ bước tái lập `baseline_v1` và so với Cohere;
  - kiểm đường nạp bằng ids các scorer CF trùng giữa hai model;
  - không cần Weaviate (chế độ `.npy` trong RAM);
  - Δ giữa hai model tính bằng script ở phụ lục report, không sửa `compare`.

## Kiểm tra

- Đối chiếu nhánh: không có commit mới trên remote. Code trên nhánh xác nhận:
  - `--vectors` chỉ có `none` / `weaviate` / `numpy`;
  - `compare` chỉ so hai arm trong cùng run, `regress --ref-run-id` so được giữa hai run;
  - Makefile có `RECSYS_VECTORS` và mặc định `CATALOG_SNAPSHOT` 2026-09-30;
  - `targetInOwnHistory` chưa có trong code.
- Máy local: chưa có `bench_out/recsys/`; `vsf2` thiếu `implicit`.
- Không đổi code, không chạy test.

## Còn lại / rủi ro

- Sửa `recsys_bench/` (chế độ `npy`, `compare` giữa hai run) cần tqanh123 đồng ý trước (việc 6.1).
- Đề xuất PRD đổi model (track Search) chưa soạn.
