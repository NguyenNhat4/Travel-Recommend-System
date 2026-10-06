# Kế hoạch mở rộng gold search bench v3 → v4 (đợt v4a)

- Ngày: 2026-10-05
- Tác giả: tqanh123 / Claude Code
- Nhánh: `feat/gold-v4`
- Trạng thái: hoàn thành (plan là bản nháp, chờ người dùng chốt cổng G0 ở §12 trước khi sửa code hay gán nhãn)
- Phạm vi: evaluation, docs
- Phục vụ: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01, test-plan §2.5

## Mục tiêu

Người dùng yêu cầu đọc đề xuất `docs/spec/bench/gold_v4_bo_sung_va_quy_trinh_gan_nhan.md`, phân tích, brainstorm và lập kế hoạch mở rộng gold. Đề xuất v4 nhắm đúng các lỗi mà nDCG trung bình che mất (chiều bay, lẫn loại sản phẩm, phủ định, không dấu, ngoài catalog), nhưng cần đối chiếu với catalog, code bench, gold v3, PRD và lịch freeze trước khi làm.

## File thay đổi

- `docs/plan/2026-10-05-gold-v4a-mo-rong.md` — thêm: kế hoạch hai track (Track G: guard + 85 probe không cần nhãn; Track L: 23 qid mới có nhãn, tag `gold_v4`), phân tích đề xuất v4 (12 vấn đề có dẫn chứng), cách xử lý từng mục của đề xuất, quy ước rubric 05/10 chờ chốt, thay đổi schema dạng sidecar, thứ tự thay đổi code C0–C8, quy trình gán nhãn, guard và cách xử lý 5 luật WIN của v4, lịch T2–T6, DoD, rủi ro, lộ trình sau freeze, 12 quyết định chờ chốt, đánh giá lệch PRD.
- `history/2026-10-05-ke-hoach-gold-v4a.md` — entry này.

## Quyết định

- Phân tích bằng workflow nhiều agent: 4 agent đọc song song (PRD/lịch sử, năng lực code, khả thi trên catalog, hiệu năng hiện tại + thống kê), 3 bản kế hoạch theo 3 góc (tận dụng v3, guard trước, kinh tế gán nhãn + thống kê), 2 critic đối kháng cho mỗi bản, tổng hợp, critic độ đầy đủ (6 lỗi phải sửa) và một vòng sửa.
- Chọn hướng guard trước. Lý do: làm nguyên văn đề xuất (80 query, 1.500–2.300 quyết định người, rubric mới) không vừa 3 ngày trước code freeze T5 08/10 và phá khả năng so sánh với gold_v3 (≥ 162/1.184 nhãn 1 đổi nghĩa dưới rubric v4; gold append-only).
- Giữ một rubric (gold-guide + quy ước 30/09 + quy ước 05/10 chờ chốt); độ chặt về loại sản phẩm của v4 chuyển thành guard tính từ catalog trên `top_ids`. `GoldRecord` không đổi (`extra="forbid"`); metadata v4 để ở sidecar.
- Đánh giá lệch PRD: plan là công cụ đánh giá, không cần đề xuất `docs/prd/update/`. Bốn ý trong đề xuất v4 mang tính hành vi sản phẩm (filter-first trong `/search`, vé bay trong `/search`, trang rỗng, sao là filter cứng) bị loại khỏi phạm vi; muốn làm phải đi qua đề xuất PRD.
- Không sửa file đề xuất v4 của người dùng (đổi tên `_` → `-`, thêm dòng FR, header trạng thái): chờ người dùng cho phép (D8).

## Kiểm tra

- Tự kiểm lại các khẳng định nền của plan trên repo và snapshot catalog 2026-09-23 (`bench_out/search/data/stats.json`: 11.387 bản ghi, 3.183 search unit): `GoldRecord` có `extra="forbid"` (`gold_schema.py:136`); regex tag `^gold_v(\d+)$` (`holes.py:35`, `runner.py:331`); `search_bench` không có trên `main` (`git ls-tree` ra 0 file); `test_config.py:25` assert tổng quota = target 200; `labeling_core.py:357` từ chối nhãn máy cho câu chung; 113 route bay; SGN↔Thanh Hóa có cả hai chiều, HAN↔Thanh Hóa không có; Côn Đảo→TP.HCM có, chiều ngược không; Cần Thơ→Hà Nội có 2 sản phẩm; 776 chuỗi tiện ích bắt đầu bằng "Không có" (gồm 77 "Không có Thang máy") — xác nhận bug đảo nghĩa tiện ích.
- Không chạy test hay bench: không đổi code.

## Còn lại / rủi ro

- Người dùng chốt 12 quyết định ở §12 của plan (cổng G0), nhất là D1 rubric, D2 phạm vi/hạn, D4 quy ước #8–#14, D5–D6 người gán và chính sách nhãn máy (lệch có chủ đích so với v4 §8.6/§10/§13.4).
- Mốc cắt Track L: T3 06/10 12:00. Không có A2 hoặc chưa chốt D2/D3/D5/D6 thì Track L chuyển sang sau freeze.
- Một số số liệu hiệu năng trong plan (vd. c0373 tuyến ngược hạng 1 ở cả 5 arm; nDCG tụt khi bỏ dấu) do agent đọc report/run tính; đọc parquet trên máy này có thể bị Application Control chặn — kiểm lại khi viết report guard.
- File đề xuất v4 vẫn chưa track và tên vi phạm AGENTS.md §7.
