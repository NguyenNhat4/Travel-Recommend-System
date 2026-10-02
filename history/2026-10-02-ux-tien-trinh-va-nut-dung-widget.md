# UX tiến trình AI và nút Dừng trong widget trợ lý

- Ngày: 2026-10-02
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khung tiến trình trong widget in nguyên mọi sự kiện `node.completed` kèm chuỗi debug tiếng Anh của backend
(`Nhận yêu cầu · request initialized`, `Phân loại yêu cầu · route travel (intent override)`...). Danh sách cứ dài thêm
và không cho người dùng biết đang ở bước nào. Nút "Dừng xử lý" là link nằm riêng ở footer; sau khi dừng chỉ còn dòng
"Đã dừng yêu cầu." mà không có cách gửi lại. Thay đổi này hiện thực `docs/spec/product.md` §6.1 và §6.6 (3 bước, ✓
theo sự kiện thật). Phục vụ FR-AGT-01, hỗ trợ AC-AGT-01. Không lệch PRD, không đổi contract hay backend.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/widgetProgress.ts` — thêm: hàm thuần chuyển chuỗi `node.completed` thành 3 bước done/active/pending.
- `src/frontend/src/features/itinerary/widget/WidgetProgress.tsx` — thêm: render 3 bước, spinner, dòng "Đang lâu hơn thường lệ…", `role=status` chỉ đọc câu đang làm.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: tiến trình hiện như tin trợ lý đang soạn (avatar + 3 bước); ghi chú đã dừng có nút Gửi lại; bỏ nút Dừng ở footer.
- `src/frontend/src/features/itinerary/widget/WidgetComposer.tsx` — sửa: prop `onStop`; đang chạy thì nút gửi thành nút Dừng, Esc trong ô nhập cũng dừng.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: ngưỡng chậm 12 giây tính từ node xong gần nhất, mỗi `node.completed` đặt lại đồng hồ.
- `src/frontend/src/context/assistantState.ts` — sửa: `node-completed` tắt `isSlow`.
- `src/frontend/src/components/assistant/assistantLabels.ts` — sửa: xoá `NODE_LABEL`/`nodeLabel` (không còn ai dùng).
- `src/frontend/tests/unit/widgetProgress.test.ts` — thêm: bảng ánh xạ, retry, nhánh trò chuyện không ✓ giả, không lộ chuỗi debug.
- `src/frontend/tests/unit/floatingWidgetOpening.test.tsx` — sửa: nút Dừng trong composer, Esc dừng, trạng thái đã dừng có Gửi lại.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: ngưỡng 12 giây; thêm test đồng hồ đặt lại theo từng node.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §9.6 bỏ dòng "Không stream trong v1" đã cũ, mô tả tiến độ theo SSE và nút Dừng/Gửi lại.
- `docs/spec/product.md` — sửa: §6.6 ngưỡng chậm 12 giây theo node; §6.1 dòng "Hiện trạng code".
- `history/2026-10-02-ux-tien-trinh-va-nut-dung-widget.md` — thêm: entry này.

## Quyết định

- Bước tính theo node có ánh xạ **gần nhất**, không theo bước cao nhất: `evaluate → retry` là tìm lại thật nên bước 2 chạy lại (phụ đề "Đang thử phương án khác…"). Sau `compose`, bước 3 hiện "Đang viết lời tư vấn…".
- Node intake, classify, converse, clarify, narrate, finalize không đẩy bước lên, nên lượt trò chuyện hay hỏi lại không có ✓ giả.
- Không hiện `message` của sự kiện: đó là chuỗi debug của backend. Nhãn do Web sở hữu (hợp đồng frontend §6).
- Ngưỡng chậm 12 giây tính theo từng node, theo yêu cầu người dùng: thời gian dồn vào các node gọi LLM, nên lượt dài mà vẫn tiến đều thì không báo chậm.
- Chưa làm link "Xem kết quả tìm kiếm trước" ở trạng thái Chậm (`product.md` §6.6). Đây là luồng fallback song song, ngoài phạm vi sửa UX này.

## Kiểm tra

- `node_modules/.bin/vitest run` (src/frontend) — PASS: 54 file, 532 test, chạy trước bước gộp nhãn cuối. Sau khi gộp nhãn, chạy lại 3 file liên quan (`widgetProgress`, `floatingWidgetOpening`, `assistantProvider`) — PASS: 36 test.
- `node_modules/.bin/tsc --noEmit` — PASS. ESLint trên các file widget, context và test đã sửa — PASS.
- `npm run build:web` rồi `playwright test tests/e2e/widget-opening.spec.ts tests/e2e/widget-detail.spec.ts` — PASS 8/8 (API mô phỏng; cảnh báo proxy ECONNREFUSED vì backend local không chạy).
- Chụp màn hình 1024 px bằng một spec tạm (đã xoá), dùng stream SSE giả phát node theo thời gian: thấy 3 bước ✓ dần, dòng chậm sau 12 giây, nút Dừng trong ô nhập, ghi chú đã dừng kèm Gửi lại. Ảnh chụp trước bước gộp nhãn cuối.
- Chưa kiểm với backend và LLM thật.

## Còn lại / rủi ro

- Chưa kiểm end-to-end với backend thật. Nên gửi "Đi Đà Nẵng 3 ngày 2 người" và "chào bạn" để xem thứ tự ✓ trên trace thật.
- `src/frontend/next-env.d.ts` bị build sinh lại; đã khôi phục, không thuộc thay đổi này.
- Chưa commit.
