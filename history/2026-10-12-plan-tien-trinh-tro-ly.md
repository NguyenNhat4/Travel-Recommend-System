# Plan: tiến trình của trợ lý hiện kết quả từng bước

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs (plan cho agent, contract, frontend)

## Mục tiêu

Khung tiến trình của widget chỉ ghi tên bước chung chung ("Đang hiểu yêu cầu", "Tìm sản phẩm"). Người dùng muốn mỗi bước
ghi kết quả thật của chính lượt đó: những gì agent đã hiểu, số sản phẩm tìm thấy và đã chọn theo loại, tiêu chí xếp lịch,
lỗi và ngoại lệ. Khi xong, khung thu gọn thành một dòng. Lượt chạy quá khoảng 5 giây thì hiện kết quả từng phần. Người
dùng cũng cần xem chi tiết kỹ thuật khi làm nhà phát triển. Task này chỉ viết plan cho người thực thi sau.

## File thay đổi

- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — thêm: bằng chứng từ code; thiết kế (bước theo loại lượt,
  dữ kiện từng bước, việc con, kết quả từng phần, thu gọn, chẩn đoán hai mức, contract 1.27.0, frontend); các bước B0–B10
  kèm test viết trước và lệnh kiểm tra; ma trận kiểm thử; invariant; bản nháp đề xuất PRD (AC-AGT-09); 7 câu hỏi cần chốt.
- `history/2026-10-12-plan-tien-trinh-tro-ly.md` — thêm: entry này.

## Quyết định

- Nguyên nhân ảnh chụp kẹt ở "Đang hiểu yêu cầu": bảng `AFTER_NODE` của `widgetProgressView.ts` chỉ biết node của nhánh
  lập lịch. Các node `classify`, `converse`, `explore`, `clarify`, `precheck`, `orchestrate`, `run_jobs`, `gatekeep` không
  đẩy bước lên. Kết luận này đọc từ code; test tái hiện sẽ viết ở B7.
- Dữ kiện do code tính trong một module thuần (`agents/steps/progress.py`), gọi từ `timed()`. Không sửa node, nên snapshot
  hành vi phải xanh mà không ghi lại. Backend gửi mã và số; Web viết câu chữ, theo quy ước nhãn do Web sở hữu.
- Không ghi điều agent không làm. Thiếu ngân sách thì hiện "không giới hạn theo giá", không hiện "dùng mức trung bình".
  `compose` không dùng `pace`, nên không ghi "buổi chiều nghỉ ngơi". Hai điểm này đưa vào Q2, Q3 để người dùng chốt.
- Việc con trong node dùng `get_stream_writer()` của LangGraph. Đã thử trên LangGraph 1.2.11 bằng script ở scratchpad:
  node sync và async đều phát được; `ainvoke` vẫn chạy; gọi ngoài graph ném `RuntimeError`, nên helper phải nuốt lỗi này.
- Kết quả từng phần chỉ có ở nhánh lập lịch, phát sau `compose`, chỉ để xem, và Web hiện sau 5 giây. Lượt khám phá không
  có, vì LLM chọn thẻ theo giới hạn của AC-AGT-06.
- Chẩn đoán mức 1 nằm trong `DebugPanel` sẵn có (Shift+D) và không đổi hành vi người dùng, nên làm trước khi chốt. Mức 2
  cần cờ server `ASSISTANT_STREAM_DEBUG` và không bao giờ gửi prompt, output thô của LLM hay JWT.
- Lệch PRD: PRD chưa mô tả khung tiến trình. Plan có bản nháp đề xuất (AC-AGT-09, `user-flow.md` §4.2, `architecture.md`
  §3, `deployment-plan.md` §2). Người thực thi tạo đề xuất ở B1 và dừng chờ chốt. Làm như plan orchestrator trước đó: bản
  nháp nằm trong plan.

## Kiểm tra

- Chưa sửa source, chưa chạy test.
- Script thử `get_stream_writer` + `stream_mode=["values","custom"]` trên `.venv` (Python 3.11.9, LangGraph 1.2.11): phát
  được từ node sync và async; `ainvoke` chạy; gọi ngoài graph ném `RuntimeError`.
- Đã kiểm tồn tại các file và lệnh plan nhắc tới: `application/itinerary/flights.py::flight_options`, `.env.example`,
  `npm run generate:api-types`, `npm run build:web`, `tests/architecture/test_import_rules.py`.

## Còn lại / rủi ro

- Toàn bộ B0–B10. Chờ người dùng review plan và trả lời Q1–Q7 (mục 8 của plan).
- Câu yêu cầu của người dùng về dòng tóm tắt bị cắt (Q1).
- Hai đề xuất đang chờ chốt chạm cùng file hoặc cùng mục PRD: `2026-10-12-the-khach-san-chon-mot-cham.md`,
  `2026-10-12-lich-trinh-ban-do-man-hep.md`.
- Chưa commit.
