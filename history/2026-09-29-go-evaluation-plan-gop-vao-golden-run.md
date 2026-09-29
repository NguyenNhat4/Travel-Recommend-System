# Gỡ evaluation-plan.md, gộp phần còn dùng vào golden-run.md

- Ngày: 2026-09-29
- Tác giả: Nguyễn Minh Nhật / Claude Opus 5
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

`docs/spec/agent/evaluation-plan.md` đã lỗi thời: §1–§9 viết cho bộ 12 case chạy tay trên fixture 50 sản
phẩm, và §5.6 + §7 khẳng định "cả 50 sản phẩm đều `priceUnit=UNKNOWN` nên `estimatedTotal` luôn `null`, đây
là kỳ vọng đúng". Mock hiện tại đã có đủ đơn vị giá (23 `PER_NIGHT`, 21 `PER_PERSON`, 5 `PER_PACKAGE`, 1
`UNKNOWN`), nên câu đó khiến người đọc coi `estimatedTotal=null` là bình thường trong khi nguyên nhân thật
bây giờ nằm ở nhánh ép null khi intent có ngân sách (`agents/steps/composition.py:83`). Người dùng chốt xoá
cả file, giữ lại phần còn dùng được.

## File thay đổi

- `docs/spec/agent/evaluation-plan.md` — xóa: toàn bộ file (203 dòng).
- `docs/spec/agent/golden-run.md` — sửa: thêm mục 4 "Luật chấm" (dataset, bốn nhóm quy tắc A–D, cách tính
  Tool Calling Accuracy, `--sweep`), mục 5 "Ngưỡng kết luận" (8 gate cứng + 2 mục tiêu theo dõi), mục 6
  "Khi nào chạy", mục 7.1 "Lỗi đã phát hiện qua bộ golden và trạng thái"; đổi số mục "Lỗi thường gặp"
  4 → 7; sửa link hỏng `golden-dataset.md` → `golden-dataset-how-to-add-more-case.md` (2 chỗ).
- `docs/spec/agent/README.md` — sửa: bỏ dòng bảng của `evaluation-plan.md`, sửa link hỏng
  `golden-dataset.md`, trỏ "chi tiết luật chấm" sang `golden-run.md` mục 4, mô tả lại `golden-run.md`.
- `docs/spec/agent/working-context.md` — sửa: "quality gate ở `evaluation-plan.md`" → `golden-run.md` mục 5;
  hàng "Eval hành vi Agent" trỏ sang `golden-run.md`.
- `docs/plan/2026-09-23-golden-dataset-handoff.md` — sửa: 2 tham chiếu sang vị trí mới.
- `history/2026-09-29-go-evaluation-plan-gop-vao-golden-run.md` — thêm: entry này.

## Quyết định

- Xoá cả file thay vì chỉ sửa 2 câu sai: bộ 12 case chạy tay trên fixture đã bị bộ golden 14 case trên
  catalog thật thay thế, giữ lại hai quy trình song song làm tài liệu tự mâu thuẫn.
- Không xoá trắng: §0 (luật chấm), §8 (ngưỡng kết luận), §9 (khi nào chạy) và §0.1 (lỗi đã biết) được
  chuyển nguyên văn sang `golden-run.md` — đây là phần `README.md` và `working-context.md` đang trỏ tới như
  quality gate của workstream Agent.
- Phần bị bỏ hẳn: §1–§7 (điều kiện chạy fixture, bảng 12 case, checklist chấm tay, mẫu biên bản tay, giới
  hạn của fixture). Lý do: đều gắn chặt với `ITINERARY_DATA_MODE=fixture` và `products.json` 50 sản phẩm,
  không còn phản ánh cách đánh giá hiện tại. Nội dung cũ vẫn tra được trong lịch sử git.
- Không tạo đề xuất `docs/prd/update/`: không có tài liệu nào trong `docs/prd/` tham chiếu
  `evaluation-plan.md`, và ba chỉ số PRD `test-plan.md` §2.4 vẫn được `golden-run.md` phục vụ nguyên vẹn —
  đây là gộp tài liệu, không đổi phạm vi hay tiêu chí nghiệm thu.

## Kiểm tra

- `grep -rn "evaluation-plan\|golden-dataset\.md" docs/ src/ db/` (trừ `history/`): không còn kết quả — mọi
  tham chiếu đã chuyển hướng, không còn link hỏng.
- Không chạm `src/`, contract hay DDL nên không chạy `validate_contract.py` và `db/verify.sql`.

## Còn lại / rủi ro

- `src/evaluation/README.md` chưa tồn tại (AGENTS.md §1.2 đã ghi nhận); chưa bổ sung trong lần này.
- Các entry `history/` cũ vẫn trỏ tên `evaluation-plan.md`. Đúng quy tắc không sửa lịch sử — người đọc sau
  tra entry này để biết nội dung đã chuyển đi đâu.
- Câu chuyện `estimatedTotal=null` chưa xử lý xong ở tầng sản phẩm: frontend vẫn hiển thị null thành `0 ₫`
  (`features/itinerary/widget/widgetPlan.ts:95`), và 300/11.387 sản phẩm trong `cdp.products` có
  `unit_price IS NULL` (299 trong số đó là `attraction` còn `available=true`) nên `priceUnit=UNKNOWN` là
  tình huống thật, không chỉ của fixture. Đang chờ người dùng chốt hướng xử lý.
