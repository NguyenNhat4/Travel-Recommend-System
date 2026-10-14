# Plan + đề xuất PRD: cổng bằng chứng theo cụm, trả rỗng khi câu chỉ có tên lạ, lọc thời lượng vé/combo cho `/search`

- Ngày: 2026-10-13
- Tác giả: tqanh123 / Claude Code
- Nhánh: docs/search-evidence-gate-plan (từ release-mvp-v2 @3d059212)
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Hybrid `/search` trả kết quả chỉ trùng một âm tiết khi câu không có đáp án ("Nguyễn Khắc Tiệp", "2 ngày 1 đêm" → "Chợ Đêm", "Trần Thị Mai" → "Thị trấn Hoàng Hôn"). Người dùng cần phương án xử lý cả lớp lỗi, không vá từng câu; lần này chỉ ghi plan và đề xuất PRD, phần code để máy khác làm.

## File thay đổi

- `docs/plan/2026-10-13-search-evidence-gate-no-answer.md` — thêm: plan P0 (cổng bằng chứng cụm giữ dấu cho nhánh lexical, embed residual, thời lượng theo vai trò gate/stay, phục hồi dấu thay nới cutoff, residual không giải thích được, nhãn "gần nhất", contract 1.28.0) và P1 (trường BM25 riêng qua backfill, ablation text builder T0–T5).
- `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md` — thêm: đề xuất `chờ chốt` sửa FR-SRC-03, FR-SRC-04, dòng `SEARCH_CUTOFF` ở deployment-plan §2; thay thế `2026-10-06-search-hybrid-min-coverage-rrf.md`.

## Quyết định

- Người dùng chốt hướng ngày 13/10 (bảng Q1–Q7 trong plan): lọc thời lượng chỉ cho attraction/combo, khách sạn không bao giờ bị loại vì thời lượng; trả rỗng chỉ khi residual toàn bộ là cụm dạng tên riêng không giải thích được hoặc cả câu vô nghĩa; cổng bằng chứng chỉ cho nhánh lexical, dense giữ nguyên; không thêm vector; đề xuất 2026-10-06 bị thay thế; contract 1.28.0 trên nền `release-mvp-v2`.
- Căn cứ: probe live read-only 13/10 trên backend `vota-backend-release`; report `eval-2026-10-06-search-query-plan-gold-v4.md` (cutoff tuyệt đối không làm câu ngoài catalog rỗng, 7/7); plan tiền lệ `docs/plan/2026-10-07-search-duration-entity-poi.md` (vai trò entity gate/location).
- Đề xuất cũ 2026-10-06 **chưa** chuyển sang `update-archive/`: chỉ chuyển khi đề xuất mới được chốt (AGENTS §8).

## Kiểm tra

- Chỉ đổi tài liệu; không chạy test. Đã diff code search giữa `fix/search-count` @1873f4d5 và `release-mvp-v2` @3d059212 để xác nhận trích dẫn file:line trong plan còn đúng (chỉ khác `StageTimer.record`, cấu hình recsys/agent, preload vector).

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md`.
- Máy khác làm tiếp từ Bước 0 của plan: đo `attributes.nights` / số unit suy được thời lượng, đo chặn nhầm của cổng trên gold_v6 (≤ 2 %), probe baseline; Bước 2–3 (gold_v7, arm bench) làm được trước khi chốt; Bước 4–10 chờ chốt.
- Số dòng `main.py`/`config.py` trong plan lấy từ `fix/search-count`; đọc lại ở Bước 0.1.
