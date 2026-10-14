# Next.js mặc định assistant v2 để người dùng kiểm thử

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13 (chỉ đạo trực tiếp trong chat)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3, Chuyển phiên bản và nghiệm thu
- Mã FR/NFR: FR-AGT-01/02/06, NFR-REL-01; AC-AGT-09

## Lý do

Người dùng đang thấy tiến trình v1 trên web và yêu cầu “chỉnh mặc định NEXT_PUBLIC_ASSISTANT_API=v2 mặc định mới nhất, chỉ swich tới cái web nextjsst mình test thôi nhé streamlit ko dùng nữa”. Đây là chỉ đạo chốt phạm vi chuyển mặc định web ngay để tự kiểm thử, không cần hỏi lại. Không coi chỉ đạo này là bằng chứng E12 đã đạt.

## Nội dung đề xuất

Hiện tại: “Widget chỉ chuyển v2 sau nghiệm thu model thật và catalog thật (E12), kiểm inventory web/Streamlit/golden/scripts trước khi ngừng v1.”

Thay bằng: “Web Next.js mặc định assistant v2 để người dùng kiểm thử từ 13/10/2026; không đặt NEXT_PUBLIC_ASSISTANT_API cũng dùng v2. Chỉ giá trị v1 tường minh mới chọn client tương thích cũ. Không chuyển Streamlit hoặc các runner khác trong thay đổi này. Nghiệm thu model/catalog thật E12 vẫn chưa được coi là đạt; thực hiện trước nghiệm thu phát hành. Kiểm inventory trước khi ngừng backend v1; không tự ngừng v1.”

## Thay đổi source sau khi chốt

- `src/frontend/src/context/AssistantProvider.tsx`: default v2, giữ v1 chỉ khi cấu hình tường minh; chọn phương án từ hội thoại cũ trên web v2 gửi thành tin nhắn v2, không gọi mutation v1.
- `.env.example`: khai báo giá trị v2 cho web; không sửa ASSISTANT_API_BASE_URL của Streamlit.
- Tests provider v2 kiểm khi thiếu env, tests v1 chọn v1 tường minh; kiểm browser bản build không đặt env.
- Ghi lịch sử và cập nhật tài liệu web/plan. Không deploy, đổi cấu hình VM, sửa Streamlit hay ngừng API v1.
