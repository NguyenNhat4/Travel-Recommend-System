# Đề xuất PRD: tìm kiếm ngay tại trang danh mục

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành (tạo đề xuất; chưa chốt)
- Phạm vi: docs

## Mục tiêu

Người dùng thấy bấm Tìm ở khách sạn, tour và trải nghiệm, tiện ích khác đều ra trang gộp `/search` (gọi là "master search") và muốn mỗi mục ra kết quả ở trang riêng của mình. Đã khảo sát: tấm tìm kiếm của `/hotels`, `/experiences`, `/combos` gọi `buildSearchHref` ghi cứng `/search`; ba trang này chỉ là landing, chưa có danh sách kết quả; chỉ `/flights` tìm tại chỗ. PRD (`user-flow.md` §2, §3.1, FR-SRC-03) đang ghi tấm tìm kiếm dẫn sang `/search`, nên đổi hành vi này là lệch PRD và phải có đề xuất đã chốt trước khi sửa source (AGENTS.md mục 8).

Người dùng đã chọn: kết quả hiện ngay tại trang danh mục (không thêm route), giữ `/search` cho tìm tự do, và đã duyệt bản xem trước giao diện.

## File thay đổi

- `docs/prd/update/2026-10-07-tim-kiem-tai-trang-danh-muc.md` — thêm: đề xuất sửa `user-flow.md` §2, §3.1 và FR-SRC-03; trạng thái "chờ chốt".
- `history/2026-10-07-de-xuat-tim-kiem-tai-trang-danh-muc.md` — thêm: entry này.
- Bản xem trước giao diện (ngoài repo): https://claude.ai/artifact/1TW1CyUAmGzAn4sSCHfMse.

## Quyết định

- Không tự chốt đề xuất; chưa sửa PRD, spec, code hay test (AGENTS.md mục 8, bước 2). Việc người dùng duyệt plan và giao diện không được coi là chốt đề xuất.
- Không đổi contract, DDL, backend: `POST /search` đã lọc theo `taxonomy` và `destination`.
- Có `?q=` thì là đang tìm, không có thì giữ landing, để các liên kết `?destination=` hiện có không đổi hành vi.

## Kiểm tra

- Chỉ có thay đổi tài liệu; không chạy lệnh kiểm tra.

## Còn lại / rủi ro

- Chờ mihhquan chốt đề xuất (hoặc yêu cầu sửa). Khi chốt: sửa `docs/prd/` đúng nội dung đã chốt, rồi code frontend, test, spec, README, chuyển đề xuất sang `update-archive/` và ghi entry mới.
- Plan chi tiết đã duyệt: `/home/mihhquan/.claude/plans/hi-n-t-i-kh-ch-s-n-soft-hickey.md` (ngoài repo).
- Băng "kết quả yếu" chưa đưa sang trang danh mục; nếu cần thì thêm vào đề xuất.
