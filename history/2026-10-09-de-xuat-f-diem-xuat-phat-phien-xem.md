# Đề xuất [F]: chuyến bay theo điểm xuất phát (O1) và gộp các lượt xem gần đây (O4)

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng chốt 09/10: gộp chuỗi O vào PR-A và viết đề xuất mới cho phần còn lệch PRD (O1, O4). FR-REC-02, FR-REC-04.

## File thay đổi

- `docs/prd/update/2026-10-09-recsys-diem-xuat-phat-va-phien-xem.md` — thêm: đề xuất [F] (chờ chốt), trích số từ `src/evaluation/reports/eval-2026-10-09-recsys-cong-thuc-oph.md`

## Quyết định

- Viết theo `feat/recSys_update` sau PR-A (FR-REC-02 đã có ô khám phá + loại combo). Đề xuất chưa có hiệu lực tới khi người dùng chốt; engine chưa đổi cho O1/O4.

## Kiểm tra

- Không có lệnh chạy (tài liệu).

## Còn lại / rủi ro

- Chờ người dùng chốt [F]; sau đó: PRD FR-REC-02/04, engine (`infer_origin`, `W_ORIGIN = 0.15`, chuyến ảo), spec §4.4/§4.7, test, parity bench `B0+orig:pen:0.15+sess` = engine.
