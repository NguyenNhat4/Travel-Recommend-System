# Đề xuất PRD: gợi ý tức thì khi gõ ở ô tìm kiếm

- Ngày: 2026-10-05
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu instant search cho ô tìm kiếm ở trang chủ và `/search`: gợi ý ngay khi gõ, chia theo loại, có icon, in đậm chữ khớp, nút "Xem tất cả", kiểm soát số request (tối thiểu 2 ký tự, huỷ request cũ, cache prefix, bỏ chuỗi không hợp lệ, giới hạn kết quả), và ô rỗng hiện tìm kiếm gần đây cùng từ khoá phổ biến. Yêu cầu này lệch PRD (chưa có FR; `docs/spec/product.md` §4.2.1 ghi "MVP: không autocomplete") nên phải có đề xuất được chốt trước (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-10-05-goi-y-tuc-thi-o-tim-kiem.md` — thêm: đề xuất FR-SRC-05, AC-SRC-02, sửa `user-flow.md` §2 và §3.1, thêm ví dụ `GET /search/suggestions` ở `api-contract.md` §2.3; trạng thái `chờ chốt`.

## Quyết định

- Gợi ý dùng endpoint riêng khớp chữ trên `UnitIndex` trong bộ nhớ backend, không dùng `POST /search` (gọi Cohere + Weaviate, p95 4,0 s trên VM theo `docs/spec/hop-dong-tich-hop-search-recommendation.md` §7.1, và ghi event `search`).
- Không gợi ý vé máy bay, theo FR-SRC-03 và đề xuất đã chốt 2026-09-30.
- Gõ để xem gợi ý không ghi event CDP.

## Kiểm tra

- Chưa có code; chưa chạy lệnh kiểm tra nào.

## Còn lại / rủi ro

- **Đang dừng ở bước chờ người dùng chốt đề xuất.** Chưa sửa `docs/prd/`, contract, backend hay frontend.
- Sau khi chốt: làm theo kế hoạch đã duyệt (PRD → contract → backend → frontend → test), đổi trạng thái đề xuất thành `đã áp dụng` và chuyển sang `docs/prd/update-archive/`.
- `src/frontend/src/components/common/Footer.tsx` đang sửa dở trong working tree, không thuộc task này.
Bị thay thế bởi: 2026-10-05-instant-search-goi-y-tuc-thi.md
