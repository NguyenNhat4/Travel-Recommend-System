# Tiến trình bám lượt chat hiện tại và giải thích các quyết định có căn cứ

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, frontend, docs
- Phục vụ: FR-AGT-06/07, NFR-REL-01, AC-AGT-09
- Thay thế một phần: `2026-10-13-hoan-thien-ui-tien-trinh-agent.md` — cách đọc dữ kiện mục Hiểu yêu cầu ở lượt khám phá/vé.

## Mục tiêu

Người dùng đưa hai lượt tìm/xem thêm điểm tham quan và khách sạn ở Huế nhưng khung vẫn nhắc “Nha Trang · 17/10 · từ Nghệ An”, yêu cầu thấy reasoning của agent. Sửa thông tin của chính lượt chat và giải thích công việc, mốc so sánh, mục đích loại thẻ từ quyết định có cấu trúc và số đếm thật.

## Nguyên nhân

`steps/progress._understood` đọc `state.intent` cho mọi loại lượt. Đây là chuyến đi được giữ qua hội thoại, nên có thể vẫn là Nha Trang khi Job đang tìm Huế. `understoodLabels` lại luôn render intent trước các job, dẫn tới hai phạm vi trái nhau. Plan §3.3 đã quy định khám phá/vé lấy Job/FareQuestion, chỉ lập lịch/hỏi lại chuyến lấy intent.

## File thay đổi

- `src/backend/app/agents/steps/progress.py` — sửa: chỉ đọc intent, missing fields và giả định chuyến cho plan/clarify; explore/fare dùng công việc của lượt, bỏ nhóm superseded. Quyết định execute đầu tiên có công việc trong understood ngay trước khi tool xong.
- `src/backend/tests/unit/agents/test_progress.py` — sửa: test saved trip Nha Trang/ngày/nơi đi/thiếu thông tin không lọt vào khám phá/vé; plan vẫn giữ; quyết định tìm Huế hiện trước khi tra xong.
- `src/frontend/src/features/itinerary/widget/widgetProgressLabels.ts` — sửa: bảo vệ cả stream backend cũ còn gắn intent; giải thích tìm mới, tìm thêm, tra lại thẻ, so giá, gần mốc và thứ tự giá từ dữ kiện cấu trúc. SEEN/DUPLICATE nói mục đích tránh lặp/gộp bản trùng.
- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: truyền loại lượt vào nhãn, dùng thứ tự bước chuẩn, không render key lạ thành bước rỗng; bước viết của khám phá ghi Giải thích và trả lời, nhắc dữ kiện vừa tra/kiểm nguồn.
- `src/frontend/src/features/itinerary/widget/WidgetProgressSummary.tsx` — sửa: có khoảng trắng thật giữa tóm tắt và Xem các bước/Thu gọn khi sao chép text.
- `src/frontend/tests/unit/widgetProgress.test.ts` — sửa: payload cũ có Nha Trang/17/10/Nghệ An vẫn chỉ hiện việc Huế, lựa chọn mới và lý do tránh lặp.
- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: hai lượt Huế liên tiếp với payload cố tình mang intent cũ; mở các bước và kiểm không còn thông tin cũ ở cả hai lượt, ảnh 390 px.
- `docs/spec/product.md` — sửa: ghi rõ dữ kiện lượt hiện tại và phần giải thích quyết định có căn cứ.
- `history/2026-10-13-tien-trinh-bam-luot-chat-hien-tai.md` — thêm: entry này.

## Quyết định

- Đây là sửa đúng AC-AGT-09 và plan đã chốt, không lệch PRD, không cần đề xuất mới. Không thay prompt, payload LLM, tham số tool, trí nhớ chuyến, lựa chọn sản phẩm hay response cuối.
- Phần giải thích do Web viết từ Job/FareQuestion, scope, mã loại và số đếm thực tế. Không dựng lý do chọn “tốt nhất” khi chưa có bằng chứng; không đưa reasoning thô, prompt hoặc output thô LLM ra stream. Phần B chẩn đoán mức 2 vẫn chưa chốt.
- Không dùng skill. Giữ các thay đổi đang có của phiên trước.
- Đã đọc lại PRD README, history README, entry triển khai tiến trình và plan §3.3; các tài liệu backend/frontend/agent/contract/PRD theo phạm vi đã đọc trong cùng phiên trước lần sửa ban đầu. Đối chiếu trực tiếp code đang chạy.

## Kiểm tra

- Test tái hiện trước sửa: 2 backend fail, 1 frontend fail, đúng stale intent và thiếu công việc trước khi search xong.
- `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_progress.py src/backend/tests/unit/agents/test_behavior_snapshot.py`: 12 passed; snapshot phát lại offline xanh, không ghi lại.
- Assistant contract + architecture: 24 passed, 1 cảnh báo Starlette/AnyIO deprecation có sẵn.
- Frontend widgetProgress/progressModel/assistantProvider/debugPanelAssistant: 38 passed. TypeScript và ESLint các file UI đã sửa: exit 0.
- `npm run build:web`: PASS.
- Playwright ca hai lượt Huế: 1 passed; nhận cả intent cũ từ fixture nhưng không hiện Nha Trang/ngày/nơi đi. Ảnh `/tmp/travel-progress-hue-current-turn.png`. Sau đồng bộ loại sản phẩm của notices trong fixture, chạy lại cùng ca để giữ ảnh đúng ngữ cảnh.
- `validate_contract.py`: PASS, 129 schemas, 104 fixtures. Không thay contract.
- `git diff --check`: sạch. Không commit. Không chạy lại toàn bộ backend/frontend vì sửa phần hiển thị/collector, đã có focused regression, snapshot, contract và trình duyệt phù hợp; số toàn bộ từ entry trước không được coi là chạy mới.
- Một lần automatic permission review quá hạn khi xin chạy test ngoài sandbox; retry được duyệt và kiểm thử hoàn tất. Một lệnh E2E đầu viết sai đường dẫn theo cwd nên không tạo ca, build xanh nhưng No tests found; đã sửa đường dẫn, thêm ca và chạy đạt, không coi lần đầu là pass.

## Còn lại / rủi ro

- Chưa kiểm staging/LLM thật trong lượt sửa này; trình duyệt dùng fixture stream để tái hiện chính xác lỗi. Không sửa các lỗi agent D4/D5 hoặc triển khai Phần B.
- Các tin nhắn đã chụp ProgressView trước bản sửa không được tái tính trong phiên đang mở; lượt mới dùng cách dựng đúng ngữ cảnh. Sau tải lại, tiến trình cũ không được khôi phục từ server, theo giới hạn A/Q7 đã chốt.
