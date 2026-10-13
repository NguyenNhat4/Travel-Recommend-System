# Đề xuất trần 5 thẻ mỗi loại và trả lời câu hỏi số lượng

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng muốn hạ trần thẻ gợi ý xuống tối đa 5, orc tự quyết trong trần, xin nhiều hơn thì nói rõ giới hạn; câu hỏi
"có bao nhiêu khách sạn ở Hà Nội" trả lời ước lượng theo kết quả tìm. Lệch AC-AGT-06 (trần 10 mỗi loại) nên cần đề xuất.

## File thay đổi

- `docs/prd/update/2026-10-14-tran-5-the-va-cau-hoi-so-luong.md` — thêm: đề xuất chờ chốt.
- `history/2026-10-14-de-xuat-tran-5-the-va-cau-hoi-so-luong.md` — thêm: entry này.

## Quyết định

- Rà các chỗ giới hạn thẻ của v2: `MAX_CARDS_PER_TAXONOMY = 10` ở `orc_contracts.py` và `orc_guardrails.py`, câu
  "Tối đa mười thẻ mỗi loại" trong `PROMPT` của `orc_v2.py`, `maxItems: 10` ở `assistant-v2.yaml`. Con số 3 thẻ
  thuộc luồng v1 (`steps/prompts.py`, spec khám phá cũ), không phải v2.
- `fact` chỉ đọc `data` của lời gọi, không đọc `coverage`, nên hiện orc không nêu được tổng số lượng; đề xuất thêm
  `data.total_rounded` cho duyệt Catalog. Kiểm tra local: Catalog có 136 khách sạn Hà Nội (availableOnly).
- Chưa sửa source: chờ người dùng chốt theo AGENTS.md mục 8.

## Kiểm tra

- Không chạy test: chưa đổi code.

## Còn lại / rủi ro

- Chờ chốt hai điểm: trần 5 mỗi loại hay tổng cả lượt; cách làm tròn số lượng.
- Sau khi chốt: cập nhật PRD trước, rồi code/contract/test/spec theo mục "Thay đổi source" của đề xuất.
