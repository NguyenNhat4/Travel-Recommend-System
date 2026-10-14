# `/search`: thời lượng chỉ lọc cứng khi câu chỉ có thời lượng

- Ngày: 2026-10-14
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã chốt (PRD đã cập nhật 2026-10-14; source sửa cùng thay đổi này — chuyển `update-archive/` khi plan 2026-10-13 làm xong)
- Chốt bởi / ngày: tqanh123, 2026-10-14 (trong phiên làm việc, sau khi xem bench gold_v7)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.2 FR-SRC-03 (ý thời lượng, chốt 2026-10-13)
- Mã FR/NFR: FR-SRC-03
- Sửa đổi: `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md` mục 2

## Lý do

Bench gold_v7 (`src/evaluation/reports/eval-2026-10-14-search-evidence-gate-gold-v7.md`): lọc cứng thời lượng làm "2 ngày 1 đêm"
tốt hơn nhiều (duration_only +42 dev / +15 test nDCG) nhưng làm mất vé VinWonders đúng mà tên không ghi số ngày ở câu
"VinWonders 3 ngày 2 đêm" (duration_false_positive −25,7 dev / −7,0 test). Catalog chỉ có số ngày cho ~42 vé/combo (theo tên) và
không có số đêm, nên lọc cứng khi câu còn nội dung khác loại nhầm sản phẩm đúng.

## Nội dung đề xuất

FR-SRC-03, ý thời lượng (chốt 13/10):

> Thời lượng trong câu ("2 ngày 1 đêm", "3N2Đ") lọc **vé tham quan và combo** theo số ngày/đêm suy từ tên hoặc thời lượng gợi ý
> của sản phẩm; không có sản phẩm khớp thì trả rỗng với `emptyReason: duration`. …

→ thay bằng:

> Thời lượng trong câu lọc **vé tham quan và combo** … **chỉ khi câu chỉ nêu thời lượng** (ngoài điểm đến, loại dịch vụ); không có
> sản phẩm khớp thì trả rỗng với `emptyReason: duration`. Câu còn nội dung khác ("VinWonders 3 ngày 2 đêm") thì thời lượng chỉ được
> ghi nhận, không lọc. (Câu lưu trú giữ như cũ: không loại khách sạn.)

## Thay đổi source sau khi chốt

- `src/backend/app/domain/search/query_plan.py`: vai trò `soft` (câu còn nội dung) — không mask; `gate` chỉ khi không còn nội dung.
- `src/shared/contracts/schemas/search.yaml`: `queryPlan.duration.role` enum `[gate, soft, stay]` (1.30.0 chưa phát hành).
- Test: `src/backend/tests/unit/application/test_search_v128_evidence_gate.py`.
