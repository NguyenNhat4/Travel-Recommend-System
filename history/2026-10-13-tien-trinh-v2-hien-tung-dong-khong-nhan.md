# Tiến trình v2: bỏ nhãn Think/Act/Observe, gộp việc thành câu, hiện từng dòng

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs
- Mã FR/NFR: FR-AGT, AC-AGT-09

## Mục tiêu

Người dùng xem ảnh widget (lượt "lên plan 3 ngày 2 đêm đi Vũng Tàu"): UI in nhãn "Think", "Act · Tra danh mục", "Observe · Tra danh mục"; Act và Observe của cùng việc thành hai dòng lặp; cả khối hiện ra một lúc. Yêu cầu: không hiện nhãn, việc viết thành câu liền mạch kiểu "tìm khách sạn ở Vũng Tàu", hiện từng dòng một.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: nhánh timeline gộp Act + Observe theo groupId thành một bước; Think là câu thường (`tone: 'think'`); nhãn câu theo loại việc/taxonomy/điểm đến; dòng kết quả "14/20 kết quả phù hợp, chọn 3 để giới thiệu."; tóm tắt thu gọn liệt kê tối đa hai việc.
- `src/frontend/src/features/itinerary/widget/WidgetProgress.tsx` — sửa: hiện lần lượt từng bước (450 ms), dòng chờ có spinner khi chưa có việc đang chạy; Think không biểu tượng.
- `src/frontend/src/features/itinerary/widget/WidgetProgressSummary.tsx` — sửa: truyền `steps` cho `ProgressSteps`.
- `src/frontend/src/app/globals.css` — sửa: animation `progress-step-in`, tắt khi reduced motion.
- `src/frontend/tests/unit/widgetV2.test.ts` — sửa: kiểm câu, gộp Act/Observe, không còn nhãn.
- `src/frontend/tests/e2e/widget-v2-progress.spec.ts` — sửa: kỳ vọng theo giao diện mới.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: mô tả cách hiển thị (không nhãn, gộp dòng, nhịp hiện).
- `history/2026-10-13-tien-trinh-v2-hien-tung-dong-khong-nhan.md` — thêm.

## Quyết định

- Kiểm nguyên nhân "hiện một lúc" trước khi sửa: backend `orc_v2.py` phát Think sau quyết định, Act trước khi gọi tool, Observe khi từng tool xong; route v2 dùng queue + `StreamingResponse` (`X-Accel-Buffering: no`); proxy Next chuyển tiếp stream. Không có buffer. Cảm giác dồn khối do LLM quyết định vài giây không có gì trên màn hình, rồi Think + các Act đến cùng lúc và tool catalog local trả trong vài ms. Vì vậy sửa ở UI, không đổi backend/contract.
- Nhịp hiện từng dòng chỉ là trình bày; trạng thái mỗi dòng vẫn là trạng thái thật từ stream, không giả lập "đang chạy".
- PRD AC-AGT-09 vẫn giữ: vòng Think → Act → Observe thật, Think do LLM viết, Act/Observe từ call/result. Chỉ đổi cách hiển thị, không lệch PRD; không cần đề xuất.
- Nhánh v1 (understand/search/arrange/write) giữ nguyên.

## Kiểm tra

- `npx vitest run` widgetV2, progressModel, assistantState, assistantProvider, assistantProviderV2: 48 passed; widgetProgress + progressModel: 15 passed.
- `npx tsc --noEmit -p .`: PASS. ESLint các file sửa: PASS.
- `npm run build:web`: PASS.
- `PLAYWRIGHT_PORT=3118 npm exec -- playwright test tests/e2e/widget-v2-progress.spec.ts`: 2 passed (390, 1024 px).
- Spec tạm (đã xoá) giả lập stream theo đợt như backend cho ca Vũng Tàu, chụp màn hình: Think hiện trước, sau đó từng việc; không nhãn; có dòng "Đang cân nhắc bước tiếp theo…" khi chờ LLM.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Thời gian chờ quyết định LLM đầu tiên vẫn như cũ (chỉ có dòng chờ "Đang đọc yêu cầu…"); rút ngắn cần đổi backend/model, ngoài phạm vi.
- Chưa thử với backend + model thật trong trình duyệt.
