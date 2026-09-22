# Cập nhật đường dẫn tài liệu trong AGENTS.md sau đợt tái cơ cấu docs/

- Ngày: 2026-09-22
- Tác giả: mihhquan / Claude Sonnet 5
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu cập nhật các file hướng dẫn agent (`AGENTS.md`/`CLAUDE.md`). Đối chiếu với commit `0763443` (tái cơ cấu `docs/` thành `docs/prd/` + `docs/spec/`) và `ce8147e` (xoá `docs/spec/ux-research-brief.md` sau khi đã dùng để tạo `product.md`) cho thấy `AGENTS.md` vẫn trỏ tới nhiều đường dẫn cũ trước khi tái cơ cấu — agent đọc theo mục 1.1/1.2 sẽ ra lệnh đọc file không tồn tại.

## File thay đổi

- `AGENTS.md` — sửa:
  - `docs/hop-dong-tich-hop-auth.md` → `docs/spec/hop-dong-tich-hop-auth.md` (dòng mục 1.2 Auth).
  - `docs/agent/README.md` → `docs/spec/agent/README.md` (dòng mục 1.2 Itinerary Agent).
  - Thêm `docs/spec/hop-dong-tich-hop-search-recommendation.md` vào dòng Search/Recommendation — đây là hợp đồng chi tiết nhất cho hai engine, trước đó AGENTS.md chỉ trỏ tới mục Search/Recommendation trong `hop-dong-tich-hop-backend.md`.
  - `docs/spec/ux-research-brief.md` (đã bị xoá ở `ce8147e` vì là brief một lần, đã hoàn thành mục tiêu) → thay bằng `docs/spec/product.md` ở dòng Frontend.
  - `docs/DATABASE_SCHEMA.md`, `docs/PRODUCT_SCHEMA.md`, `docs/MOCK_DATA_SPEC.md` → thêm tiền tố `docs/spec/` ở mọi chỗ xuất hiện (mục 1.2, mục 6, mục 6.5).
  - `docs/product.md` → `docs/spec/product.md` (mục 1.2 dòng cuối, mục 2 thứ tự ưu tiên).
  - Thêm `docs/spec/hop-dong-tich-hop-insider.md` vào dòng Insider clone (file này tồn tại từ trước nhưng chưa từng được liệt kê).
  - Ghi chú `src/evaluation/README.md` hiện chưa tồn tại — yêu cầu hỏi người dùng thay vì agent tự bịa nội dung.
- `db/migrations/run.py`, `db/migrations/README.md` — khôi phục (`git checkout 617bb90 -- db/migrations/run.py db/migrations/README.md`): hai file bị xoá thuần (không đổi tên) trong commit `0763443` dù `Makefile` (`make db-migrate`, `make db-migrate-status`) và `docs/prd/deployment-plan.md` (§4) vẫn tham chiếu chạy `python db/migrations/run.py`. Người dùng xác nhận khôi phục thay vì viết lại.

## Quyết định

- Chỉ sửa đường dẫn tham chiếu trong `AGENTS.md`; hỏi người dùng trước khi động tới hai vấn đề "đứt gãy" phát hiện được (đúng theo mục 2 AGENTS.md: không tự chọn phương án khi tài liệu/code mâu thuẫn).
- Người dùng chọn: khôi phục `db/migrations/run.py` + `README.md` từ `617bb90` (bản ngay trước khi bị xoá ở `0763443`) — không viết lại vì bản cũ đã tương thích với migration mới nhất (`0001_auth_p0.sql`, script đọc file `.sql` theo tên, không hardcode danh sách).
- Người dùng chọn: **chưa** tạo `src/evaluation/README.md` — để dành cho lần sau khi ai đó thực sự chạm vào workstream Evaluation; giữ nguyên ghi chú trong `AGENTS.md` để agent sau hỏi trước khi giả định nội dung.
- `CLAUDE.md` (gốc và `src/frontend/`) không đổi vì chỉ chứa `@AGENTS.md` — không có đường dẫn cứng nào để sửa. `src/frontend/AGENTS.md` là file do `next dev` tự sinh, không thuộc phạm vi.

## Kiểm tra

- `grep -nE "docs/(DATABASE_SCHEMA|PRODUCT_SCHEMA|MOCK_DATA_SPEC|product\.md|agent/|hop-dong-tich-hop)" AGENTS.md | grep -v "docs/spec/"` — không còn kết quả (không còn đường dẫn thiếu tiền tố `spec/`).
- Đối chiếu thủ công từng file được liệt kê trong bảng mục 1.2 và mục 6 với `ls`/`find` thực tế trên đĩa — tất cả đường dẫn còn lại đều tồn tại.
- `git show 617bb90:db/migrations/run.py`, `git show 617bb90:db/migrations/README.md` — cả hai tồn tại ở commit đó, khôi phục thành công bằng `git checkout`.
- Đọc lại `db/migrations/run.py` đã khôi phục: script quét file `NNNN_*.sql` trong `db/migrations/` theo pattern, không hardcode tên file — tương thích ngay với `0001_auth_p0.sql` hiện có, không cần sửa gì thêm.
- Chưa chạy `validate_contract.py` vì không đổi contract/mock.

## Còn lại / rủi ro

- `src/evaluation/README.md` vẫn chưa tồn tại (chủ ý, theo lựa chọn của người dùng) — `AGENTS.md` đã ghi chú rõ để agent sau hỏi thay vì tự bịa.
- Chưa thử chạy thật `make db-migrate` với database cục bộ để xác nhận script khôi phục hoạt động đúng trong môi trường hiện tại (chỉ kiểm tra tĩnh bằng đọc code).
