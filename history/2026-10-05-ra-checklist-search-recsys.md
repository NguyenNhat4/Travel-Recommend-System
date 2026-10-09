# Rà checklist Search + RecSys cho khớp thực tế (Day 6)

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu cập nhật checklist cho đúng thực tế trước khi làm tiếp Day 5–6 của Search. Ba file plan có ô tick lệch thực tế: nhiều việc đã xong nhưng chưa tick, cột "Có?" của checkpoint tuần còn trống. Checklist bench cũ (23/09) không còn được dùng. Phục vụ FR-SRC-01..04, FR-REC-01..04, NFR-PERF-01.

## File thay đổi

- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa:
  - tick Day 1–4 theo history (gold track A, baseline recsys B, cache + prewarm C);
  - ghi chú các ô Day 1 bị thay bằng quyết định 28/09 (drafts 132 câu) và 30/09 (quy ước guide sau khi gán);
  - điền bảng baseline v0 từ spec recsys §4.4;
  - ghi chú các ô còn mở: `stages.yaml`, tiêu chí 20–23, S0–S9, quyết định model, mentor;
  - thêm việc Day 6 "RecSys chạy bằng vector e5";
  - log Day 4–5 (S) ghi bù và log Day 6.
- `docs/plan/2026-10-01-plan-day4-5.md` — sửa:
  - điền cột "Có?" §2.5 cho các dòng 1, 2, 3, 8;
  - bổ sung ghi chú 05/10 vào dòng 6, 7 (giữ nguyên phần R đã điền).
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa:
  - §5.5: split dev/test đã chốt (tick);
  - ghi nhận bge-m3 đã chạy fp32;
  - owner `/search` cloud vẫn trống, kèm nguyên nhân đã đo.
- `docs/spec/bench/search-eval-checklist.md` — sửa: thêm ghi chú đầu file rằng checklist không còn cập nhật, trỏ tới hai file plan.
- `history/2026-10-05-ra-checklist-search-recsys.md` — thêm: entry này.

## Quyết định

- Chỉ tick khi có bằng chứng trong `history/`, report hoặc spec; mỗi ô tick kèm nguồn. Ô có một phần xong thì giữ `[ ]` và ghi phần nào xong.
- Ô bị thay bằng quyết định khác của người dùng thì đóng kèm ghi chú "không làm theo dạng này". Không xoá nội dung gốc.
- Ô R đã điền ở plan Day 4–5 §2.5 (dòng 4–7) giữ nguyên, chỉ thêm ghi chú.
- Quyết định của người dùng ngày 05/10:
  - split dev/test ~65/66 phân tầng theo slice;
  - regress bản gọn theo plan (ngưỡng 1 / 3 điểm);
  - F1 đo cả smoke filter lẫn arm BM25 fallback.

## Kiểm tra

- `git diff --check` trên các file docs: PASS.
- Không đổi code, không chạy test.

## Còn lại / rủi ro

- **Tag `gold_v1` không có trên git** (local lẫn remote chỉ có `gold_v2`, `gold_v3`), dù `history/2026-09-30-gold-merge-import-retire-tag-v1.md` ghi tag sau commit `6fb5053`. Cần kiểm sha `gold.jsonl` tại `6fb5053` khớp changelog rồi gắn lại tag; chưa làm vì tag là thao tác đẩy ra remote.
- Người dùng báo 05/10: nhóm chốt model embedding **e5-small / 384**, bỏ Cohere. PRD FR-SRC-02 và backend vẫn ghi Cohere v3 / 1024 → cần đề xuất `docs/prd/update/` được chốt trước khi sửa code. Vector e5-small + e5-base (gói ngoài repo, có sha256) đã gửi bên RecSys để chạy lại bench. ADR 3 chưa có; gate P chưa có owner.
- `src/evaluation/search_bench/devtest.py`, `regress.py` và khối `regression.regress_v1` trong `config/sbench.yaml` đang viết dở trong working tree (chưa nối CLI, chưa test). Không thuộc entry này; khi làm tiếp sẽ có entry riêng.
