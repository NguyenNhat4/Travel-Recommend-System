# Đề xuất: lấy đủ điểm tham quan của điểm đến, mỗi địa điểm một vé, tour buổi tối

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Lịch TP.HCM (trace `nhat-10-7`, hội thoại `f403f203…`) đi 36,5 km, toàn Grand Park và tour du thuyền trùng nhau, không có
điểm miễn phí. Nguyên nhân gốc là bộ ứng viên điểm tham quan chỉ đến từ Search (7 kết quả, 2 địa điểm).

## File thay đổi

- `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` — thêm: đề xuất thêm nguồn Catalog (code tự gọi
  `list_products`, không qua LLM), mỗi địa điểm một vé, tour buổi tối không xếp sáng/chiều.

## Quyết định

- Lệch PRD: `architecture.md` §3 chỉ cho nguồn Search/Recommendation/Similar; AC-AGT-04 chưa có luật địa điểm và buổi tối.
  Đề xuất trước, chưa sửa source (AGENTS.md §8).
- Chọn code tự gọi `list_products` thay vì đưa thành tool cho LLM: việc này là luật phải chạy ở mọi lượt, `/products`
  không nhận câu truy vấn, và không tăng thời gian lập tool plan (người dùng đồng ý trong phiên).

## Kiểm tra

- Chưa chạy lệnh nào: chỉ thêm tài liệu đề xuất. Bằng chứng số liệu ghi trong đề xuất (catalog local, search
  `localhost:8000`, trace LangSmith).

## Còn lại / rủi ro

- Chờ người dùng chốt. Sau khi chốt: cập nhật PRD, rồi code theo mục "Thay đổi source sau khi chốt".
