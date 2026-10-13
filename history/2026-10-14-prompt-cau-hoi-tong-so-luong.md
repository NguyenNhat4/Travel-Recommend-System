# Prompt orc: câu hỏi tổng số lượng nói thật là chưa đếm được

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng yêu cầu: trong lúc orc chưa nêu được tổng số lượng ("có bao nhiêu khách sạn ở Hà Nội"), thêm vào prompt
như một giới hạn, báo cho khách biết bằng câu tự nhiên, không cứng nhắc.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa: thêm một gạch đầu dòng trong `PROMPT` mục "Nguồn và câu trả lời".
- `history/2026-10-14-prompt-cau-hoi-tong-so-luong.md` — thêm: entry này.

## Quyết định

- Không lệch PRD: áp dụng đúng quy tắc đã có "điều không kiểm được thì nói thật" (AC-AGT-07) và grounding NFR-REL-01;
  `fact` chưa trích được `coverage.total` nên orc không có dữ kiện tổng.
- Chỉ sửa prompt, không thêm luật cứng trong code. Câu trả lời: nói chưa đếm được tổng, giới thiệu vài lựa chọn đã tra,
  gợi ý khách nêu thêm nhu cầu để lọc; không dùng câu mẫu.
- Phương án trả số ước lượng nằm trong đề xuất chờ chốt `docs/prd/update/2026-10-14-tran-5-the-va-cau-hoi-so-luong.md`;
  khi chốt và làm thì thay gạch đầu dòng này.

## Kiểm tra

- `pytest src/backend/tests/unit/agents/test_orc_loop.py src/backend/tests/unit/agents/test_orc_contracts.py`:
  28 passed (model giả). Chưa thử trên model thật.

## Còn lại / rủi ro

- Cần thử câu "Hà Nội có bao nhiêu khách sạn" trên model thật để xem câu trả lời có tự nhiên không.
