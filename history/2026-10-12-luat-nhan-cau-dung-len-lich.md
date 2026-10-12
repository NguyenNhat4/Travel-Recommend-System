# Luật nhận câu dừng chắc chắn ("ko đi nữa") trước LLM classify

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/agent-end
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Thay thế: `history/2026-10-12-dung-len-lich-cam-on-hen-gap-lai.md` (riêng quyết định "không thêm lưới luật")

## Mục tiêu

Lượt "không đi nữa" chạy đúng nhưng chậm: phải gọi LLM hai lần nối tiếp (`classify` rồi `converse`). Người dùng chọn cách A:
thêm luật tất định nhận các câu dừng chắc chắn, bỏ qua LLM `classify`; lời chào ở `converse` vẫn do LLM viết. Câu dừng nói
cách khác vẫn do LLM `classify` gắn `stop` như trước. Phục vụ FR-AGT-01, AC-AGT-01, NFR-PERF-02.

Đo trước khi làm (backend local, `fixture`, Gemini free tier, xem "Kiểm tra"): thời gian chủ yếu nằm ở phía dịch vụ. Một lời
gọi 7 token vào, 2 token ra của `gemini-3.1-flash-lite` mất 22,8 giây; kết nối IPv4/IPv6 tới API 0,05–0,07 giây; model không
sinh token thinking. Mỗi lời gọi LLM của agent mất 8–24 giây với `gemini-3.1-flash-lite`, 3,6–22 giây với `gemini-3.5-flash`.

## File thay đổi

- `src/backend/app/agents/steps/classification.py` — sửa: thêm `_STOP`, `_STOP_TAIL`, `says_stop` (khớp nguyên câu sau `fold` và
  bỏ từ đệm cuối câu, câu có "?" không tính) và `stopped` (update của lượt `stop`, dùng chung cho luật và nhãn LLM);
  `route_result` gọi `stopped()`.
- `src/backend/app/agents/nodes.py` — sửa: `_stop_rule` chạy trước `_option_pick` và `changes.detected` trong `classify_node`
  (sync, async), event `route stop (rule)`; docstring `classify_node`.
- `src/backend/tests/unit/agents/test_classify.py` — sửa: thêm `StopRuleTests` (16 câu phải khớp, 18 câu ý khác phải không khớp,
  luật bỏ qua LLM, câu dừng ngoài danh sách vẫn qua LLM).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: lượt "ko đi nữa" chỉ còn một lời gọi LLM (`ConversationalAnswer`)
  và có event `route stop (rule)`.
- `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md` — sửa: bước 4 của thứ tự kiểm trong `classify` (luật câu dừng, từ vựng, các
  câu cố ý không nhận).
- `docs/spec/agent/langgraph-nodes.md` — sửa: hàng `classify` của bảng node.
- `history/2026-10-12-dung-len-lich-cam-on-hen-gap-lai.md` — sửa: thêm dòng `Bị thay thế bởi`.
- `history/2026-10-12-luat-nhan-cau-dung-len-lich.md` — thêm: entry này.

## Quyết định

- Khớp **nguyên câu** trên từ vựng đóng, không tìm từ khoá trong câu: câu có thêm tên nơi, số, ngày hay chữ ngoài danh sách tự
  rơi về LLM, nên không cần dò riêng "giá trị chuyến đi".
- Từ vựng: `[thôi | vậy thôi] [mình | tôi | tui | tao | em | anh | chị]` + phủ định (không, ko, k, kh, khg, hong, hok, hk, hem,
  chẳng, chả) + `[muốn | cần]` + đi / đi du lịch / du lịch / đi chơi / lên lịch / lập lịch / lên kế hoạch + **nữa**;
  `[thôi] huỷ chuyến [đi] / lịch trình [này]`; `thôi khỏi lên/lập lịch`; `[ok | cảm ơn | thanks] tạm biệt / bye / goodbye / hẹn gặp
  lại`. Từ đệm cuối câu bỏ trước khi so: nhé, nha, đâu, luôn, rồi, mà, bạn.
- Cố ý không nhận: "thôi khỏi", "thôi cảm ơn", "cảm ơn" đứng riêng (hay là từ chối một gợi ý hoặc còn nói tiếp), "không đi" thiếu
  "nữa", câu có "?" hay đuôi "à", "hả" (câu hỏi), "không đi được nữa".
- Lời chào vẫn do LLM viết (cách A), nên lượt dừng còn một lời gọi LLM. Hành vi theo PRD không đổi, chỉ đổi cách nhận diện nên không
  cần đề xuất PRD; quyết định "không thêm lưới luật" ở entry trước được thay bằng entry này theo yêu cầu người dùng.
- Câu khớp luật thì LLM `classify` không chạy, không có bước đọc lại: rủi ro duy nhất là nhận nhầm, nên danh sách giữ hẹp; câu dừng
  ngoài danh sách vẫn được LLM xử lý. Mở rộng danh sách bằng câu thật LLM đã gắn `stop` (event `route stop`) mà luật chưa nhận, mỗi
  cụm thêm kèm test khớp và test không khớp.

## Kiểm tra

- Test mới chạy trước khi có luật: `test_classify.py` lỗi import `says_stop`; test graph "ko đi nữa" fail (còn gọi `TurnRoute`).
  Sau khi thêm luật: pass.
- `pytest -q -p no:cacheprovider src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture`: 2009
  passed.
- `pytest -q -p no:cacheprovider src/evaluation/tests/test_golden.py`: 79 passed.
- Nhận nhầm trên dữ liệu thật: chạy `says_stop` qua 169 câu người dùng trong `src/evaluation/datasets/*` — chỉ khớp "ko đi du lịch
  nữa" và "thôi không đi nữa đâu" (hai câu dừng của TC-15), không khớp câu nào khác.
- Chạy thật (backend local 8010, `fixture`, `ITINERARY_LLM_MODEL=gemini-3.1-flash-lite`): "ko đi nữa" → node `classify` 1 ms (trước
  8,5–24 giây với cùng model), chỉ còn `ConversationalAnswer` 14,3 giây; câu trả lời cảm ơn, hẹn gặp lại, không form.
- Đo độ trễ dùng script tạm (không commit): lời gọi 7 token 22,8 s; prompt `classify` dạng text 10,4 s, có JSON schema 15,5 s; qua
  LangChain có và không `thinking_budget=0`: 21,1 s / 20,1 s, `output_tokens=11`, không token thinking.

## Còn lại / rủi ro

- Lượt dừng vẫn chờ một lời gọi LLM viết lời chào; muốn gần 0 giây thì dùng câu mẫu cố định (cách B), cần người dùng chốt.
- Các lượt khác (lập lịch 5–6 lời gọi LLM nối tiếp, khám phá, giá vé) không nhanh hơn; nguyên nhân chính là gói free của Gemini
  (hạn mức 20 request/ngày/model với `gemini-3.x-flash`, xếp hàng phía dịch vụ). Thư viện Gemini tự retry khi 429 nên người dùng
  chờ đủ `ITINERARY_LLM_TIMEOUT_SECONDS` (30 giây) mới thấy lỗi.
- "ko đi nữa" ngay sau câu mời "đi thêm X không?" có thể là từ chối phần thêm nhưng luật coi là dừng; hiếm, chưa chặn.
