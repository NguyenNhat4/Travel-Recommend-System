# Hướng dẫn: cách tìm ra lỗi loại danh mục sai thành phố

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng hỏi lỗi trong `docs/plan/2026-10-05-fix-category-exclusion-other-city.md` được tìm ra thế nào và muốn có một file md. Phục vụ FR-REC-02, AC-AGT-01.

## File thay đổi

- `docs/guide/how-the-category-exclusion-bug-was-found.md` — thêm: dòng thời gian (sơ đồ Mermaid), 9 bước tìm và chứng minh lỗi (đọc phía ghi → phía đọc field `excludedVerticals`, tái hiện unit, tra history, đo dữ liệu thật, kiểm hàm tất định của agent, rà các nơi đọc khác, chọn phương án sửa), bài học mỗi bước và checklist dùng lại.
- `history/2026-10-05-huong-dan-cach-tim-loi-loai-danh-muc.md` — thêm: entry này.

## Quyết định

- Đặt ở `docs/guide/` vì là hướng dẫn quy trình cho người phát triển, không chứa quy tắc hay spec.
- Viết tiếng Anh thường (không ép STE100 vì người dùng không yêu cầu). Ghi thật cả bước bỏ sót lỗi khi viết guide recsys và lần tái hiện đầu không ra lỗi.
- Số liệu lấy nguyên từ các lần chạy đã ghi ở `history/2026-10-05-bao-cao-loi-loai-danh-muc-sai-thanh-pho.md`; không chạy lại.

## Kiểm tra

- Parse sơ đồ Mermaid bằng `mermaid@11` + `jsdom`: 1/1 OK.
- Không đổi code nên không chạy test.

## Còn lại / rủi ro

- Không có.
