# Kế hoạch và sơ đồ thanh toán Stripe cho booking, kèm đề xuất PRD

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: dang dở — tài liệu xong; đề xuất PRD chờ chốt, triển khai chưa bắt đầu
- Phạm vi: docs

## Mục tiêu

Người dùng muốn dùng Stripe làm phương thức thanh toán cho booking, theo mô hình Merchant of Record (MoR), và yêu cầu xử lý bốn tình huống: booking thành công, thanh toán thất bại, khách huỷ booking, trạng thái giữ chỗ. Đầu ra gồm plan trong `docs/plan/`, sequence diagram (request giữa frontend, backend, database, service) và UML activity diagram (logic xử lý) trong `docs/spec/booking/`. Activity phải có start/end, action bắt đầu bằng động từ, decision có điều kiện kiểm được, swimlane, data, error path, loop, state; phân biệt lỗi nghiệp vụ với lỗi kỹ thuật và qua được checklist người dùng đưa ra.

## File thay đổi

- `docs/prd/update/2026-09-24-thanh-toan-stripe-mor.md` — thêm: đề xuất `chờ chốt`; tám quyết định Q1–Q8 cần chốt; nội dung thay thế cho `project-brief.md`, `requirements.md` (sửa FR-BKG-02…04, AC-BKG-01; thêm FR-BKG-05…07, NFR-SEC-03, AC-BKG-02…04), `data-model.md`, `architecture.md`, `deployment-plan.md`, `user-flow.md`, `test-plan.md`; danh sách source sẽ sửa sau khi chốt.
- `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` — thêm: 19 khối Mermaid gồm sơ đồ dòng tiền MoR, sơ đồ thành phần, chú giải ký hiệu, 2 máy trạng thái (đơn, thanh toán), 8 sequence, 6 activity; bảng lỗi API, bảng lý do thất bại, bảng log, bảng trả lời checklist.
- `docs/plan/2026-09-24-booking-thanh-toan-stripe.md` — thêm: hiện trạng, quyết định thiết kế, 11 bước (bước 1 làm ngay được, bước 0 và 2–10 khoá chờ chốt), 15 kịch bản kiểm thử với thẻ test Stripe, rủi ro và câu hỏi mở.
- `history/2026-09-24-ke-hoach-thanh-toan-stripe.md` — thêm: entry này.

## Quyết định

- **Stripe lệch PRD nên phải đi qua đề xuất.** `project-brief.md` §4.1 chỉ có "thanh toán mô phỏng", §4.2 để cổng thanh toán thật ngoài phạm vi; FR-BKG không có giữ chỗ, huỷ, hoàn tiền; contract để `status` luôn `CONFIRMED`; DDL chỉ có `confirmed | cancelled`. Theo `AGENTS.md` §8, agent tạo đề xuất và dừng phần lệch. Plan và spec được viết cùng lúc, ghi rõ "chờ chốt" và khoá các bước lệch PRD, theo tiền lệ auth (`history/2026-09-23-ke-hoach-auth-p0.md`, `history/2026-09-23-so-do-luong-xac-thuc.md`). Không sửa `docs/prd/`, contract, DDL hay code.
- **Chỉ dùng Stripe test mode.** Đã kiểm trang stripe.com/global: Việt Nam không có trong danh sách quốc gia mở tài khoản Stripe. Điều này cũng giữ tinh thần "không có giao dịch tiền thật" của PRD.
- **Giữ chỗ 30 phút.** Theo tài liệu API Stripe, `expires_at` của Checkout Session chỉ được từ 30 phút đến 24 giờ sau khi tạo; hạn giữ chỗ bằng hạn phiên để Stripe tự đóng trang thanh toán đúng lúc.
- **Checkout hosted page** thay cho Payment Element: V-OTA không chạm dữ liệu thẻ, Web không cần Stripe.js, 3DS do Stripe lo. Đánh đổi là khách rời trang V-OTA khi trả tiền.
- **Tách trạng thái đơn và trạng thái thanh toán** (`app.bookings.status`, bảng mới `app.payments`), để khi đã thu tiền mà CDP lỗi, hệ thống vẫn biết tiền đã về và không để job hết hạn đóng nhầm đơn.
- **Đường xác nhận sau khi thu tiền không huỷ event CDP khi commit lỗi**, khác với bù trừ ở checkout cũ. Lý do: `hop-dong-tich-hop-cdp.md` §3.3 mục 4 — ghi lại một `eventId` đã huỷ vẫn là `duplicate` và event vẫn bị huỷ, nên huỷ rồi thử lại sẽ tạo đơn `CONFIRMED` mà gợi ý không thấy.
- **Giới hạn 3 lần thẻ bị từ chối** để chặn card testing; đếm bằng webhook `payment_intent.payment_failed`, không đếm ở Web.
- **Chính sách huỷ mặc định** (huỷ cả đơn, hoàn 100% nếu trước 00:00 giờ VN của ngày liền trước `usingDate` sớm nhất) là phương án đề xuất, để người dùng chốt ở Q5; PRD chưa có chính sách huỷ nào.
- **Không trừ tồn kho khi giữ chỗ**: hệ thống không có bảng tồn kho và tồn kho thời gian thực ngoài phạm vi. Ghi rủi ro hai khách cùng giữ một phòng vào plan.
- **Contract sửa trong v1** (Q6): ý nghĩa `201` của `POST /bookings` đổi, nhưng hiện chưa client nào gọi endpoint này (backend chưa có route booking, Web dùng state local). Để người dùng chốt, phương án khác là `/api/v2`.
- Không có swimlane Admin: RBAC ngoài phạm vi; việc tay của vận hành chỉ xuất hiện qua log `ERROR`.

## Kiểm tra

- Đã đọc: `AGENTS.md`; `docs/prd/README.md`, `requirements.md` (toàn bộ), `project-brief.md` §3–§6, `data-model.md` §1, §2.2, §4, §5, `architecture.md` §1–§6, `deployment-plan.md` §1–§2, `implementation-plan.md`, `test-plan.md`, `user-flow.md` §2, §3.3, §4.3; đề xuất đang chờ `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` (không liên quan booking); `history/README.md`, 10 entry mới nhất, các entry auth/đề xuất làm tiền lệ; `hop-dong-tich-hop-backend.md` §1.3, §7, §8.2, §8.7; `hop-dong-tich-hop-frontend.md` §4.4–§4.6, §8; `hop-dong-tich-hop-cdp.md` §3.2–§3.5, §5, §6; `product.md` mục lục và các dòng về thanh toán; `docs/spec/auth/so-do-luong-xac-thuc.md` §1–§3; contract `paths/booking.yaml`, `schemas/booking.yaml`; DDL `db/vota_schema.sql` phần `app.carts`…`app.booking_items` và role; `db/verify.sql`; `src/backend/README.md`; `application/booking/purchase_events.py`, `application/ports/cdp_client.py`; danh sách route backend; `CheckoutView.tsx`.
- Đã kiểm thông số Stripe trên docs.stripe.com: giới hạn `expires_at` (30 phút–24 giờ), `expire` chỉ áp dụng cho phiên `open`, các tham số `client_reference_id`, `metadata`, `submit_type=book`, `locale=vi`, `ui_mode=hosted_page`; giới hạn số tiền tối thiểu/tối đa; VND nằm trong danh sách tiền tệ không có số lẻ (HTML của docs.stripe.com/currencies, mục "Zero-decimal currencies"), nên `amount` gửi Stripe là số đồng, không nhân 100.
- Parse toàn bộ khối Mermaid bằng `mermaid@12.0.0` + `jsdom`, cài tạm trong scratchpad: **34 khối, 0 lỗi** (19 khối spec booking, 1 khối trong đề xuất, 14 khối spec auth làm đối chứng). Chưa kiểm phần hiển thị trên GitHub hay VS Code bằng mắt.
- Không chạy `validate_contract.py`, test hay `db/verify.sql`: chỉ thêm tài liệu, không đổi contract, mock, DDL hay code.

## Còn lại / rủi ro

- Đề xuất `docs/prd/update/2026-09-24-thanh-toan-stripe-mor.md` chờ người dùng chốt Q1–Q8 và cấp mã FR-BKG-05…07, NFR-SEC-03. Chốt khác đề xuất thì phải sửa spec sơ đồ và plan trước khi triển khai.
- Bước 1 của plan (giỏ hàng server-side theo contract hiện có) không lệch PRD, làm được ngay.
- Câu hỏi mở trong plan: URL công khai cho webhook ở staging; tài khoản Stripe test chung của nhóm; `eventGroupId` lệch sẵn giữa contract (mỗi nhóm điểm đến một mã) và DDL (một mã mỗi booking).
