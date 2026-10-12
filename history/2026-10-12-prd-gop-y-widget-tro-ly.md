# Áp dụng đề xuất PRD: góp ý widget trợ lý sau chat thử 11/10

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng gom 11 góp ý sau khi chat thử widget trợ lý (vé máy bay mở tab mới và đúng hạng, form ngay lượt hỏi đầu, sở
thích nơi ở theo dữ liệu + gợi ý bằng AI, nút vị trí, lời diễn giải không nhắc giá và không gọi điểm miễn phí là vé, ngân
sách bỏ dòng 0 ₫, phóng to ảnh, thẻ khách sạn rõ tiêu chí và số tuyệt đối, thẻ combo nổi bật). Một phần trái với câu chữ PRD
hiện hành, nên phải có đề xuất đã chốt và PRD cập nhật trước khi sửa source (AGENTS.md §8). Người dùng uỷ quyền cho agent
tự duyệt plan và tự chốt đề xuất (12/10).

## File thay đổi

- `docs/prd/update-archive/2026-10-12-gop-y-widget-tro-ly-11-10.md` — thêm: đề xuất, chốt theo uỷ quyền, đã áp dụng vào
  PRD (tạo ở `docs/prd/update/` rồi `git mv` sang archive).
- `docs/prd/requirements.md` — sửa: AC-AGT-01 (form kèm ngay lượt hỏi gộp đầu; ô sở thích nơi ở theo dữ liệu của điểm đến,
  ô tự điền, nút "Gợi ý bằng AI"), AC-AGT-03 (nạp sẵn sân bay, quá 5 giây/từ chối/lỗi có nút chọn nhanh), AC-AGT-04 (thẻ
  phương án ghi tổng tiền, tổng km, nhãn tiêu chí; chênh ở dòng phụ).
- `docs/prd/user-flow.md` — sửa §4.2: lời diễn giải không nhắc giá/tổng, điểm miễn phí không gọi là vé, thẻ combo; ngân
  sách bỏ nhóm 0 ₫; ô ngày–giá mở tab mới với `fare=<productId>`, trang vé chọn sẵn đúng hạng hoặc hạng rẻ nhất; trình xem
  ảnh phóng to; form ngay lượt hỏi gộp đầu, ô sở thích mới.
- `docs/prd/architecture.md` — sửa §3: grounding của gợi ý sở thích nơi ở bằng AI.
- `history/2026-10-12-prd-gop-y-widget-tro-ly.md` — thêm: entry này.

## Quyết định

- Nguyên nhân hạng Thương gia đã kiểm trên DB local: 971 vé giá gốc không ghi hạng đứng sau 1.505 vé Thương gia mô phỏng
  trong `fareClasses` (thứ tự ECO, PRE, BUS, FST, chưa rõ), trang vé chọn sẵn phần tử đầu. Sửa ở Web (chọn theo `fare`, mặc
  định rẻ nhất), không đổi thứ tự của contract.
- Nhãn tiêu chí thẻ khách sạn và nhãn nổi bật thẻ combo do code tính từ số liệu catalog (tổng tiền, km, hạng sao, giá gốc,
  lượt đánh giá), không do LLM; `soldQuantity` của combo toàn 0 nên không dùng. "Được yêu thích nhất" chỉ khi có dữ liệu
  đánh giá đủ (≥ 50 lượt, nhiều nhất câu trả lời) — theo tiền lệ không gắn nhãn "tốt nhất" cho thứ luật chọn.
- Câu hỏi trực tiếp về giá vẫn được trả lời bằng giá (câu trả lời vé máy bay FR-AGT-07, "có mất vé không").
- Thẻ vẫn ghi "Tham quan tự do" ở chỗ giá (architecture §3 giữ nguyên); chỉ lời diễn giải đổi.
- Gợi ý bằng AI dùng endpoint riêng (contract 1.26.0, làm ở phần việc 3) vì cần chạy theo điểm đến đang chọn trong form,
  không phải một lượt chat.

## Kiểm tra

- Chỉ sửa tài liệu; đối chiếu từng đoạn thay thế đúng một chỗ (script thay thế kiểm `count == 1`).

## Còn lại / rủi ro

- Source theo 8 phần việc batch cùng ngày (mỗi phần một entry `history/2026-10-12-<slug>.md`).
- Spec `docs/spec/agent/nghiep-vu/*.md`, `docs/spec/hop-dong-tich-hop-*.md` cập nhật trong từng phần việc.
