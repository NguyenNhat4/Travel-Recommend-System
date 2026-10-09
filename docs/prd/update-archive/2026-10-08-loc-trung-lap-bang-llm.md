# Dùng LLM lọc điểm tham quan trùng nhau trước khi xếp lịch

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-08 (đổi tên node `filter` thành `filter`)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (sơ đồ StateGraph, Tiêu chuẩn Grounding); `docs/prd/requirements.md` §3
  (AC-AGT-04)
- Mã FR/NFR: FR-AGT-03, FR-AGT-04, NFR-REL-01, AC-AGT-04

## Lý do

Trace LangSmith 08/10/2026, câu "Lên lịch trình 3 ngày tại Phú Quốc, bắt đầu từ ngày 2026-10-08, cho 2 người lớn, đi từ
trung quoc.": 5/6 buổi của lịch là cùng một nơi.

| Ngày | Sáng | Chiều |
|---|---|---|
| 1 | hòn Thơm | Sun World Hòn Thơm (850.000 ₫) |
| 2 | Kiss of the Sea | Cáp Treo Hòn Thơm (850.000 ₫) |
| 3 | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) | cùng tên, khác mã (182.000 ₫) |

Hiện lịch chỉ bỏ trùng khi cùng `productId` hoặc cùng sản phẩm gốc. Catalog có nhiều sản phẩm khác mã cho cùng một nơi:
cùng tên từ hai nguồn, hoặc tên khác nhau ("Cáp Treo Hòn Thơm", "Sun World Hòn Thơm") với toạ độ khác nhau. Luật theo tên
hoặc toạ độ không bắt hết: đo trên 912 điểm tham quan local, luật "tên lồng nhau" bỏ sót cặp Sun World/Cáp Treo, luật "hai
từ cuối giống nhau" gộp nhầm vé VinWonders với vé Safari, luật "cùng toạ độ" gộp cả 17 hoạt động khác nhau trong Grand World.
Nhận ra hai tên là cùng một nơi là việc hiểu ngôn ngữ, hợp với LLM.

PRD hiện chỉ cho LLM phân tích ý định và viết lời; `compose` chọn sản phẩm bằng luật tất định. Đề xuất này cho LLM thêm một
việc hẹp: **chỉ ra cặp nào trùng**. LLM không thêm, không đổi, không xếp sản phẩm; việc giữ cái nào vẫn bằng luật.

## Nội dung đề xuất

### 1. `docs/prd/architecture.md` §3

Sơ đồ: thêm bước `FilterCandidates` giữa `ValidateAvailability` và `ComposeItinerary`:

> `ValidateAvailability --> FilterCandidates: Bỏ điểm tham quan trùng (luật, rồi LLM chỉ ra cặp trùng)`
> `FilterCandidates --> ComposeItinerary`

Tiêu chuẩn Grounding, câu "LLM chỉ đóng vai trò phân tích ý định ngôn ngữ và sắp xếp lịch trình thời gian." thêm:

> LLM được chỉ ra cặp điểm tham quan trùng nhau trong danh sách ứng viên (chỉ thấy mã và tên); hệ thống chỉ nhận cặp gồm hai
> mã có trong danh sách, và tự chọn giữ mã nào bằng luật. LLM lỗi hoặc quá giờ thì chỉ dùng phần lọc bằng luật.

### 2. `docs/prd/requirements.md` §3, AC-AGT-04 — thêm sau câu "Lịch luôn xếp đủ số điểm…"

> Lịch không có hai điểm tham quan cùng một nơi. Trước khi xếp lịch, hệ thống bỏ trùng theo hai bước: (1) luật: cùng mã, cùng
> sản phẩm gốc, hoặc cùng tên (không phân biệt dấu, chữ hoa); (2) LLM nhận danh sách mã và tên các điểm tham quan còn lại,
> trả các cặp mã cùng một nơi hoặc cùng một trải nghiệm (ví dụ "Cáp Treo Hòn Thơm" và "Sun World Hòn Thơm"). Mỗi cặp giữ
> một mã theo thứ tự ưu tiên đang có (Search trước Recommendation, rồi rẻ hơn, rồi mã nhỏ hơn); mã kia bị bỏ, kể cả khỏi
> các phương án khác. Mỗi mã bị bỏ có một cảnh báo `PRODUCT_DROPPED_DUPLICATE` (mã bị bỏ, tên mã được giữ). Kết quả eval
> có mục "Đã loại" liệt kê các mã bị bỏ, bị bỏ vì trùng với mã nào và do luật hay LLM.

### Không đổi

Grounding 100%: LLM chỉ trả mã đã có trong danh sách; mã lạ, cặp một mã với chính nó, hay cặp sai định dạng bị bỏ qua. Khách
sạn, vé máy bay, combo và gói nhiều ngày không qua bước này. Lượt chọn phương án ("lấy phương án 2") không tìm lại nên không
gọi LLM.

## Thay đổi source sau khi chốt

- `src/backend/app/domain/itinerary/dedupe.py` (mới): bước luật (cùng tên đã `fold`), hàm áp cặp trùng → `(kept, dropped)`
  theo thứ tự ưu tiên, lọc cặp có mã lạ. Hàm thuần, unit test.
- `src/backend/app/agents/steps/prompts.py`: `DEDUPE_PROMPT` theo ý "Bạn là người lọc sản phẩm trùng lặp trước bước sắp xếp
  kế hoạch du lịch. Đây là danh sách truy xuất (mã, tên). Cái nào trùng thì trả cặp mã."; schema `DuplicatePairs`
  (`pairs: [{ids: [a, b], reason}]`).
- `src/backend/app/agents/nodes.py`, `graph.py`, `routing.py`: node `filter` (sync + async, timeout ngắn, LLM lỗi thì chỉ
  dùng luật) chạy trước `compose`; ghi `candidates` đã lọc, `dropped_duplicates`, cảnh báo.
- `src/evaluation/agent/golden.py`: `TurnResult` và báo cáo markdown có mục "Đã loại" (đọc cảnh báo
  `PRODUCT_DROPPED_DUPLICATE`); `streamlit_app.py` hiện mục này cạnh lịch trình.
- Contract: không đổi (`ItineraryWarning.code` là chuỗi tự do); `validate_contract.py` vẫn chạy.
- Spec: `docs/spec/agent/langgraph-nodes.md` (node mới), `docs/spec/agent/nghiep-vu/xep-lich.md`,
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Test: unit domain (hai vé Water Taxi cùng tên → 1; cặp có mã lạ bị bỏ qua; giữ đúng mã theo thứ tự ưu tiên), unit agent
  (node dùng LLM giả trả cặp; LLM lỗi thì chỉ còn luật), golden case câu Phú Quốc 3 ngày ở trên: lịch không có hai điểm
  Hòn Thơm, không có hai vé Water Taxi.

## Ảnh hưởng

- Thêm một lời gọi LLM mỗi lượt lập lịch (ước 1–2 giây; không chạy song song được vì `compose` cần kết quả).
- Cùng một câu có thể ra lịch khác nhau giữa các lần nếu LLM nhận cặp khác nhau; `compose` vẫn tất định với cùng tập ứng
  viên đã lọc. Eval cần `--repeat` cho case trùng lặp.
- Đề xuất `2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` mục 3 ("cùng toạ độ") vẫn chờ chốt riêng; hai đề xuất không
  phụ thuộc nhau.
