# Next.js dùng assistant v2 mặc định để kiểm thử

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành (đổi mặc định web và kiểm kỹ thuật)
- Phạm vi: frontend, docs, cấu hình mẫu
- Mã FR/NFR: FR-AGT-01/02/06, NFR-REL-01; AC-AGT-09
- Thay thế phần “chưa chuyển mặc định web”: `2026-10-13-think-act-observe-va-tu-van-co-nguon.md`.

## Mục tiêu

Người dùng yêu cầu tìm luồng v1 đang dùng và chuyển, sau đó thu hẹp: chỉ Next.js mặc định NEXT_PUBLIC_ASSISTANT_API=v2 để tự test, Streamlit không dùng nữa. Thực hiện phạm vi sau cùng, không mở rộng sang archive/backend/runner/Streamlit.

## File thay đổi

- `docs/prd/architecture.md` — sửa: web mặc định v2 để kiểm thử, E12 chưa được coi là đạt và không tự ngừng backend v1.
- `docs/prd/update-archive/2026-10-13-nextjs-mac-dinh-assistant-v2.md` — thêm qua `update/`, áp dụng/lưu trữ theo chỉ đạo chốt trực tiếp của người dùng.
- `.env.example` — sửa: NEXT_PUBLIC_ASSISTANT_API=v2; không sửa ASSISTANT_API_BASE_URL của Streamlit.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: thiếu env cũng dùng v2; chỉ v1 tường minh mới chọn compatibility client. Chọn khách sạn từ thẻ lưu kiểu v1 trên web v2 gửi tin nhắn cho orc v2 để tra lại, không gọi mutation v1.
- `src/frontend/tests/unit/assistantProviderV2.test.tsx` — sửa: kiểm default khi thiếu env và lựa chọn khách sạn cũ đi qua v2.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: các ca wire v1 đặt override v1 tường minh, khôi phục env sau test.
- `src/frontend/tests/e2e/widget-v2-progress.spec.ts` — sửa: ca mặc định v2 không cần env, thêm tag assistant-v2 để tách fixture cũ.
- `src/frontend/package.json` — sửa: test:e2e chạy pha compatibility v1 và pha v2 với phiên bản build tường minh, tránh fixture v1 bị gửi sang endpoint v2 khi mặc định đổi.
- `src/frontend/README.md` — sửa: default và lệnh kiểm hai pha.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: ghi default web và lựa chọn khách sạn từ hội thoại cũ.
- `docs/plan/2026-10-13-cai-thien-agent-tien-trinh-gia-phong-va-loi-goi-y.md` — sửa: chỉ đạo mới thay phần chưa chuyển mặc định.
- `history/2026-10-13-nextjs-mac-dinh-assistant-v2.md` — thêm: entry này.

## Quyết định

- Đọc/đối chiếu PRD architecture §3, deployment-plan §1–2, plan v2 E11–E13, source provider/Streamlit/replay/archive và history theo phạm vi; các tài liệu frontend/contract đã đọc trong cùng phiên ở các task trước.
- User chốt trực tiếp phạm vi “mặc định v2, chỉ Next.js để test”; ghi đề xuất và cập nhật PRD trước source, không hỏi lại điều đã được chỉ đạo rõ.
- Không dùng skill. Không đổi backend/API/contract/storage, không sửa Streamlit, Makefile hoặc các runner sau khi người dùng thu hẹp. Những chỉnh sửa của các task trước trong worktree được giữ nguyên.
- V1 còn cho compatibility override/test và endpoints đọc dùng chung; frontend thường dùng v2 cả khi không có env hoặc giá trị không phải v1. Không coi tên helper v2AsV1Response là gọi engine v1: đây chỉ là phép đổi cấu trúc để tái dùng widget.
- Không commit/push/deploy, sửa VM/secret hay tự restart dịch vụ người dùng.

## Kiểm tra

- TypeScript: PASS.
- Vitest provider default/compatibility, widgetV2, floatingWidgetOpening: 45 passed, 4 files.
- ESLint provider và các test đã sửa: PASS.
- Build `env -u NEXT_PUBLIC_ASSISTANT_API npm run build:web`: PASS. Không có giá trị NEXT_PUBLIC_ASSISTANT_API trong src/frontend/.env.local hay root .env khi kiểm đúng khóa này.
- Browser `env -u NEXT_PUBLIC_ASSISTANT_API PLAYWRIGHT_PORT=3118 npm exec -- playwright test tests/e2e/widget-v2-progress.spec.ts`: 2 passed ở 390/1024 px; intercept chỉ endpoint v2 và thấy Think/Act/Observe. Tầng bằng chứng: fixture stream, không LLM/catalog thật.
- Tách danh sách test theo tag: 2 ca v2, 44 ca compatibility/giao diện cũ; không nhận listing là 44 ca PASS. Chưa chạy lại toàn bộ E2E hai pha.
- `git diff --check`: PASS trước tạo entry; kiểm tài liệu mới trước bàn giao.
- Không chạy backend/contract vì task này không đổi backend hay contract; không lấy số kiểm task trước làm số mới.

## Còn lại / rủi ro

- E12 model/catalog thật và archive/khôi phục v2 vẫn là việc khác; việc chuyển default để user test không chứng minh các phần đó đã xong.
- Web chạy từ bundle cũ cần khởi động với bản build mới hoặc dev server nạp lại source. Biến public được chốt tại build, không đổi bằng cách chỉ refresh trang cũ.
- Tests compatibility v1 được chạy tường minh; không tự ngừng backend v1. Chưa sửa mọi test fixture/runner cũ thành nghiệp vụ v2 vì ngoài phạm vi người dùng đã thu hẹp.
