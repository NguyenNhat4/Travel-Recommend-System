# Bộ docs nghiệp vụ Itinerary Agent và dọn docs/spec/agent

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, agent

## Mục tiêu

Người dùng cần bộ docs ngắn để dev mới (hoặc chính mình khi quay lại) nắm nhanh nghiệp vụ agent đang thực hiện:
- nguồn sự thật là code hiện tại;
- tổ chức theo domain, mỗi khái niệm mô tả ở một chỗ;
- có Mermaid và glossary;
- chỗ chưa chắc ghi "⚠️ cần xác nhận".

Người dùng chọn đặt bộ docs trong `docs/spec/agent/`, và dọn file thừa ở đó trước. Phục vụ FR-AGT-01..05, AC-AGT-01..03,
NFR-REL-01.

## File thay đổi

**Xoá** (người dùng chọn)
- `docs/spec/agent/presentation-script.md`, `docs/spec/agent/presentation-slides.html` — slide thuyết trình đã cũ (graph 11
  node, số golden 24/09).
- `docs/spec/agent/truong-du-lieu-san-pham-cho-agent.md` — bản trùng của `docs/guide/truong-du-lieu-san-pham-cho-agent.md`.
  27 dòng ví dụ chỉ có ở bản spec đã chép sang bản guide trước khi xoá.
- `docs/spec/agent/field-review.md` — review field đã chốt và áp dụng 2026-09-28; quyết định nằm ở
  `history/2026-09-28-ap-dung-de-xuat-field-review-agent.md`.

**Thêm** `docs/spec/agent/nghiep-vu/` (9 file, 58–107 dòng mỗi file)
- `README.md` — mục lục, bản đồ domain, tổng hợp ⚠️.
- `glossary.md` — thuật ngữ có anchor riêng, mỗi mục trỏ tới file chi tiết.
- `vong-doi-mot-luot.md` — graph, các kết quả và mã HTTP, thử lại.
- `hieu-y-dinh-va-hoi-lai.md` — phân luồng, trường bắt buộc, quyết định hỏi lại, form, lưới an toàn cho LLM.
- `tim-ung-vien.md` — tool plan, query và gợi ý truy xuất, lý do loại, chọn hướng đi.
- `ve-may-bay.md` — tuyến/chuyến, chọn vé, lý do thiếu vé, nơi đi từ vị trí.
- `xep-lich.md` — chỗ ở, hoạt động, buổi theo giờ bay, tiền.
- `dien-giai-va-kiem-tra.md` — narrate, mục hệ thống viết, kiểm ở `finalize`, mã warning.
- `sua-lich-qua-nhieu-luot.md` — cái gì được nhớ, nơi lưu, đổi món.

**Sửa**
- `docs/spec/agent/langgraph-nodes.md` — sửa:
  - phần nghiệp vụ của §1 (form, phân luồng, `clarify`) và toàn bộ luật §5 thay bằng link sang `nghiep-vu/`;
  - sửa câu sai "`dead_letter` cho điểm đến ngoài catalog": code hỏi lại qua `clarify`.
- `docs/spec/agent/working-context.md` — sửa §1 và §2: trỏ tới `nghiep-vu/`.
- `docs/spec/agent/README.md` — sửa: thêm dòng `nghiep-vu/`; bỏ ba dòng của file đã xoá.
- `docs/spec/agent/state-fields.md` — sửa: link `field-review.md` thành entry history.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7 — sửa: con trỏ luật chi tiết sang `nghiep-vu/xep-lich.md`.
- `docs/guide/truong-du-lieu-san-pham-cho-agent.md` — sửa:
  - nhận đoạn ví dụ từ bản spec;
  - ba chỗ còn ghi "chưa quyết định / xem field-review" đổi theo quyết định 2026-09-28.
- Comment trỏ `field-review.md` đổi sang entry history, không đổi logic:
  - `src/backend/app/agents/steps/composition.py`;
  - `src/backend/app/domain/itinerary/planning.py`;
  - `src/backend/tests/unit/agents/test_lab_copy.py`, `test_suggestions.py`, `test_itinerary_runtime.py`;
  - `src/backend/tests/unit/domain/test_itinerary_composition.py`.

## Quyết định

- **Đặt trong `docs/spec/agent/nghiep-vu/`** theo yêu cầu người dùng (đề xuất ban đầu là `docs/guide/`).
- **Giữ file 8 (`sua-lich-qua-nhieu-luot.md`) riêng.** Người dùng không trả lời câu hỏi gộp file, nên giữ mặc định đã đề xuất.
- **Guardrail và ngữ cảnh LLM vẫn ở `langgraph-nodes.md`**, docs mới chỉ link tới. Đó là chi tiết kỹ thuật dài, chuyển đi
  không giúp nắm nghiệp vụ nhanh hơn.
- **⚠️ chỉ ghi khi đọc thấy trong code**, không suy đoán. Sáu chỗ được tổng hợp ở `nghiep-vu/README.md`:
  - lọc ngày chỉ theo ngày khởi hành;
  - vé được chọn lại ở mọi lượt;
  - chưa đổi được một chuyến bay cụ thể;
  - tiền chỗ ở không tính số phòng;
  - buổi không có khung giờ khi không có vé;
  - `expires_at` của hội thoại không được dùng khi khôi phục.

## Kiểm tra

- Link tương đối và anchor trong `nghiep-vu/`, `langgraph-nodes.md`, `working-context.md`, `README.md`, `state-fields.md`
  và bản guide: 0 link hỏng (script Python trong scratchpad).
- Mermaid: 9/9 block parse được bằng `mermaid@11` (script trong scratchpad, không commit). Lần đầu có 1 block lỗi do dấu
  `;` trong sequence diagram; đã sửa.
- Không còn tham chiếu sống tới file đã xoá ngoài `history/` và `docs/prd/update-archive/` (lưu trữ, không sửa).
- `pytest` các file test có comment đổi, cùng test vé và compose → 132 passed.

## Còn lại / rủi ro

- Sáu mục ⚠️ chờ người dùng xác nhận là hành vi muốn có hay cần sửa. Sửa mục nào lệch PRD (vd chọn lại vé) cần đề xuất
  riêng.
- Bộ docs mô tả code tại 2026-10-07. Sửa luật nghiệp vụ thì cập nhật đúng một file trong `nghiep-vu/`.
- `langgraph-nodes.md` vẫn khoảng 42 KB (trước 48 KB); phần còn lại là kỹ thuật (finalize, ví dụ, trace, bảng node, field).
- `git rm` đã stage bốn file bị xoá; các thay đổi còn lại chưa stage, chưa commit.
