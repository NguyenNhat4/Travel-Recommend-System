# Gán xong nhãn gold 0/1/2 cho A và B

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành — nhãn đủ, κ đạt; chưa merge / import / tag
- Phạm vi: evaluation

## Mục tiêu

Người dùng báo đã gán xong nhãn 0/1/2 và yêu cầu commit, push. Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/gold/labels/labels_A.csv` — sửa: đủ 1.999 cặp của `pool_A.csv`.
- `src/evaluation/search_bench/gold/labels/labels_B.csv` — sửa: đủ 2.000 cặp của `pool_B.csv`.
- `src/evaluation/search_bench/gold/labels/provenance_A.csv`, `provenance_B.csv` — sửa: kết quả duyệt nhãn máy.
- `history/2026-09-30-gan-nhan-gold-xong.md` — thêm: entry này.

Cùng commit có các file docs và history của ngày 29/09, đã có entry riêng: `2026-09-29-gan-nhan-chung-qua-link.md`, `2026-09-29-nhan-may-va-duyet.md`, `2026-09-29-nut-luu-gan-nhan.md`.

## Quyết định

- Commit nhãn như người gán để lại, không sửa tay dòng nào.
- Không đưa `docs/spec/bench/plan_day3.md` vào commit: plan phải nằm ở `docs/plan/`, tên bắt đầu bằng ngày và ghi mã FR/NFR (`AGENTS.md` §7); số gold trong file đã cũ (210 câu, cắt top-15).
- Bản lịch `docs/spec/bench/2026-09-28-lich-10-ngay-3-engine.md` bị bỏ khỏi stage vì người dùng đã xoá: bản đúng nằm ở `docs/plan/` trên nhánh `bench/recsys-harness`.

## Kiểm tra

- Đối chiếu nhãn với pool (pandas, `.venv-sbench`):
  - A: 1.999 / 1.999 cặp, thiếu 0, thừa 0, trùng 0; 0 = 797 · 1 = 433 · 2 = 769.
  - B: 2.000 / 2.000 cặp, thiếu 0, thừa 0, trùng 0; 0 = 656 · 1 = 572 · 2 = 772.
- Nhãn máy: A 670 đã duyệt hết (accepted 642, edited 28); B 882, **492 chưa duyệt** (accepted 390).
- `sb gold kappa gold/labels/labels_A.csv gold/labels/labels_B.csv` (từ `src/`): 640 cặp chung / 25 câu; **κ linear 0,692** (ngưỡng 0,6), không trọng số 0,614, quadratic 0,769; 12 cặp lệch 2 bậc.

## Còn lại / rủi ro

- Duyệt 492 nhãn máy của B nếu muốn cùng chuẩn với A (hợp đồng nhãn không đọc cột duyệt, nên không chặn merge).
- 12 cặp lệch 2 bậc sẽ thành `needs_discussion` khi `merge`. Vài cặp có vẻ là gán nhầm chứ không phải bất đồng quy ước (B cho 2: câu Đà Lạt → khách sạn Hà Nội c0208; câu Pleiku → nhà nghỉ Mũi Né c0433; câu Hà Nội → khách sạn Hà Tĩnh c0229).
- Tiếp theo: `sb gold merge` → sửa `needs_discussion` → `sb gold import` → `sb gold check` → tag `gold_v1`.
