# Gộp giao diện trợ lý về một widget, xóa trang `/assistant`

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (chọn "Chốt: xóa, chia sẻ mở widget")
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §2 (bảng route, dòng `/assistant`), §3.2 (luồng, nút "Mở màn hình /assistant"), §4.2 (wireframe màn `/assistant`, lặp hai lần), §1.2 (tên mục "Trợ lý Lịch trình")
- Mã FR/NFR: FR-AGT-01, AC-AGT-01 (không đổi yêu cầu; đổi nơi hiển thị)

## Lý do

Người dùng kiểm tay: trang `/assistant` là giao diện trợ lý cũ, không phải agent mà team đang phát triển. Giao diện hiện hành là widget nổi (`features/itinerary/widget`, có chế độ toàn màn hình, lịch sử, form chuyến đi, bản đồ). Hai giao diện cùng tồn tại làm hệ thống có hai trợ lý khác nhau. Yêu cầu: chỉ giữ một giao diện trợ lý chung.

## Nội dung đề xuất

- `user-flow.md` §2: bỏ dòng `/assistant`. Trợ lý là widget nổi có ở mọi trang (trừ `/checkout`), mở toàn màn hình khi cần.
- §3.2: điểm bắt đầu luồng đổi từ "Mở màn hình /assistant" thành "Mở widget trợ lý".
- §4.2: thay wireframe `/assistant` bằng mô tả widget (chế độ toàn màn hình: chat bên trái, lịch trình và bản đồ bên phải). Giữ đoạn "Form gợi ý thông tin chuyến đi" (đã áp dụng cho widget).
- Các nút vốn dẫn tới `/assistant` (tab "Trợ lý" của tab bar mobile, giỏ hàng, kết quả tìm kiếm, xác nhận đơn, banner trang danh mục) chuyển sang mở widget kèm câu điền sẵn; liên kết chia sẻ lịch trình `/assistant?share=` cần một đích thay thế (mở widget hoặc bỏ tính năng chia sẻ; cần chốt).

## Ảnh hưởng và rủi ro

- Mất trang có URL riêng cho trợ lý; liên kết chia sẻ cũ hỏng nếu không có đích thay.
- Không đổi contract, DB, backend (các endpoint `/assistant/*` giữ nguyên).
- Phải xóa hoặc sửa test e2e/unit gắn với trang: `routes.spec.ts`, `assistant-live.spec.ts`, `assistantConversationStarter.test.tsx` và các test của component chỉ trang này dùng.

## Thay đổi source sau khi chốt

- Xóa `src/app/(storefront)/assistant/`, `components/assistant/AssistantView.tsx` và các component chỉ trang này dùng (kiểm từng file trước khi xóa; giữ `AssistantTripStarter`, `TripDetailsForm`, `AssistantResultPanel`, `assistantLabels` nếu widget còn import).
- Sửa `AppShell.tsx`, `MobileTabBar.tsx`, `CartView.tsx`, `SearchView.tsx`, `ConfirmationView.tsx`, `PromoBanner.tsx`, `services/assistantShare.ts`, `shareService.ts` để mở widget.
- Cập nhật `docs/spec/hop-dong-tich-hop-frontend.md` §3, §4.8; `docs/spec/product.md` §3.1, §4.8, §7.2.
