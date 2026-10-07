# Đề xuất PRD: đổi embedding Cohere v3 / 1024 → multilingual-e5-small / 384

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành (đề xuất chờ chốt; chưa commit)
- Phạm vi: docs
- Phục vụ: FR-SRC-02, NFR-PERF-01, NFR-PERF-03

## Mục tiêu

Nhóm chốt e5-small (05/10) nhưng PRD FR-SRC-02 vẫn ghi Cohere v3 / 1024 → theo `AGENTS.md` §8 cần đề xuất được chốt trước khi sửa PRD, backend,
contract, cấu hình (lịch 10 ngày Day 5 C).

## File thay đổi

- `docs/prd/update/2026-10-05-doi-embedding-e5-small.md` — thêm: đề xuất (lý do có số, đoạn PRD hiện tại → thay thế cho requirements, architecture,
  data-model, deployment-plan, project-brief, implementation-plan; rủi ro; danh sách source sửa sau khi chốt), trạng thái `chờ chốt`.
- `history/2026-10-05-de-xuat-prd-embedding-e5-small.md` — thêm: entry này.

## Quyết định

- Chỉ soạn đề xuất; không sửa `docs/prd/`, code, contract, `.env.example` (chưa chốt).
- Gộp cutoff 0,85 vào cùng đề xuất vì là hệ quả trực tiếp của đổi model (ngưỡng 0,62 không lọc với e5).
- Ghi rõ đề xuất không giải quyết latency Cloud.

## Kiểm tra

- `grep` PRD tìm mọi chỗ nhắc Cohere / 1024 / `embed-multilingual` (requirements, architecture, data-model, deployment-plan, project-brief,
  implementation-plan); `grep` backend/frontend: Cohere chỉ dùng ở search / vector / prewarm (không ở agent).

## Còn lại / rủi ro

- Người dùng (hoặc tqanh123) chốt / sửa / từ chối. Sau khi chốt: cập nhật PRD trước, rồi source theo mục "Thay đổi source", chuyển đề xuất sang
  `docs/prd/update-archive/`.
Bị thay thế bởi: `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md` (hợp nhất 06/10, xem `history/2026-10-06-hop-nhat-de-xuat-e5-va-bao-cao-tong-hop.md`; file đề xuất của entry này đã xoá)
