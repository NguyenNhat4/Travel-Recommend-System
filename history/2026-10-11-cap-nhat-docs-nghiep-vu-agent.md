# Cập nhật tài liệu nghiệp vụ Itinerary Agent theo code 11/10

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, agent

## Mục tiêu

`docs/spec/agent/nghiep-vu/` chưa theo kịp các commit agent từ tối 09/10 đến 11/10. Folder cập nhật lần cuối ngày 10/10
(`63a997db`); sau đó 13 commit agent không chạm vào nó. Thiếu FR-AGT-06 (trò chuyện, khám phá trước khi lập lịch), FR-AGT-07
(tư vấn vé máy bay), đổi vé/khách sạn sau khi có lịch (AC-AGT-05), lịch tham khảo khi ngày đi chưa mở bán, ngày đi chung, và
các sửa từ đợt chat thử. Người dùng muốn nắm nghiệp vụ nhanh: ngắn gọn, có sơ đồ.

## File thay đổi

- `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md` — thêm: FR-AGT-06, sơ đồ trạng thái chưa/đã đồng ý lập lịch, bảng câu người dùng → trợ lý làm gì.
- `docs/spec/agent/nghiep-vu/tu-van-ve-may-bay.md` — thêm: FR-AGT-07, sơ đồ nhánh giá vé, bảng câu hỏi vé → câu trả lời.
- `docs/spec/agent/nghiep-vu/README.md` — sửa: FR-AGT-01..07, bản đồ một hình, ba câu cần nhớ, thứ tự đọc thêm 2 file, bỏ ⚠️ "tiền chỗ ở không tính số phòng" (đã sửa 09/10) và "chưa đổi được chuyến bay qua chat" (đã có từ 10/10).
- `docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md` — sửa: sơ đồ 15 node theo `agents/graph.py` (thêm `explore`, `apply_option`, `classify → tool`), ngoài phạm vi là 200, 400 chỉ khi guardrail chặn.
- `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md` — sửa: bảng nhãn `TurnRoute` mới (`explore`, `fare`), luật tất định trước LLM, cổng đồng ý trong sơ đồ hỏi lại, form 7 ô, xin form, "đổi sang chỗ khác", bỏ qua ngân sách.
- `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md` — sửa: mục "Đổi vé, khách sạn" có sơ đồ, thêm trạng thái được nhớ (đồng ý, nơi bị chê, câu hỏi còn dở, chuyến đã chọn), hỏi vé sau lịch giữ nguyên lịch.
- `docs/spec/agent/nghiep-vu/ve-may-bay.md` — sửa: chuyến người dùng chọn được giữ, ngày gần nhất có vé, link tư vấn vé.
- `docs/spec/agent/nghiep-vu/xep-lich.md` — sửa: mục "Ngày đi chưa mở bán" có sơ đồ (lịch tham khảo, ngày đi chung), edge case chuyến bay đêm.
- `docs/spec/agent/nghiep-vu/tim-ung-vien.md` — sửa: search 50 kết quả (bảng còn ghi 10), sở thích khách sạn là lọc mềm, điểm chỉ vướng ngày.
- `docs/spec/agent/nghiep-vu/dien-giai-va-kiem-tra.md` — sửa: `finalize` kiểm `searchResults`, không bịa giờ/giá, câu mở đầu lịch tham khảo, cảnh báo `PRODUCT_NOT_ON_SALE_FOR_DATE`.
- `docs/spec/agent/nghiep-vu/glossary.md` — sửa: thêm mục "Trước khi lập lịch" và các thuật ngữ vé, lịch tham khảo, ngày đi chung.
- `docs/spec/agent/langgraph-nodes.md` — sửa §3: sơ đồ dạng dòng và sơ đồ mermaid §3.1 thêm `explore`, `apply_option`, các cạnh `classify → explore/clarify/tool`, `extract → explore/converse`, `explore → extract`; `explore` vào nhóm node gọi LLM.

## Quyết định

- Chỉ mô tả lại code hiện tại theo PRD đã chốt (FR-AGT-06, FR-AGT-07, AC-AGT-05..08, chốt 10–11/10), nên không lệch PRD và không
  cần đề xuất. Nguồn đối chiếu: `agents/graph.py`, `agents/routing.py`, `steps/classification.py`, `steps/fares.py`,
  `docs/spec/agent/langgraph-nodes.md`, mục 1.4 của `docs/prd/requirements.md`.
- Tách hai file mới cho FR-AGT-06 và FR-AGT-07 thay vì nhồi vào file cũ, để mỗi khái niệm nằm ở một file (quy ước của
  README folder). Chi tiết kỹ thuật vẫn ở `langgraph-nodes.md`; bộ nghiệp vụ chỉ trỏ tới.
- Giữ ⚠️ "vé chọn lại mọi lượt", nhưng ghi thêm là chuyến người dùng đã chọn thì được giữ. Giữ ⚠️ "hai khách sạn" nhưng thu
  hẹp lại: chỉ còn trường hợp lịch không có phương án khác.

## Kiểm tra

- Script Python kiểm mọi link tương đối và anchor trong `nghiep-vu/*.md`: OK, không link hỏng.
- `mermaid@11.4.1` (`mermaid.parse`, cài trong scratchpad, ngoài repo) parse 14/14 sơ đồ trong folder và sơ đồ §3.1 của
  `langgraph-nodes.md`: OK.
- Không chạy test code vì chỉ sửa tài liệu.

## Còn lại / rủi ro

- Bảng "Bảy ví dụ" ở `langgraph-nodes.md` §3 chưa xét lại theo FR-AGT-06. Ví dụ, "gợi ý cho tôi một chuyến đi" khi chưa đồng
  ý lập lịch có thể không còn đi `extract → clarify`. Ngoài ra dòng "Paris 2 ngày → dead_letter" mâu thuẫn với dòng ngoài
  catalog → `clarify` ngay bên dưới. Cần chạy lại trace để sửa bảng.
