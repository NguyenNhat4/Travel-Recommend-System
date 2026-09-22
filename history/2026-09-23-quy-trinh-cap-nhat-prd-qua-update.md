# Nguyên tắc: mọi thay đổi lệch PRD phải chốt qua docs/prd/update

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng đặt nguyên tắc: PRD là chuẩn. Bất kỳ thay đổi nào lệch khỏi PRD, không riêng nội dung file PRD, đều phải có đề xuất trong `docs/prd/update/` và được chốt trước. Chỉ sau khi chốt mới được sửa source.

## File thay đổi

- `AGENTS.md` — sửa:
  - Câu mở đầu: nêu nguyên tắc lệch PRD thì phải chốt trước.
  - §1.1: thêm bước luôn đọc `docs/prd/update/`.
  - §1.3: trước khi code phải xác nhận thay đổi có lệch PRD không; nếu lệch mà chưa có đề xuất đã chốt thì không được code.
  - §4: phần lệch PRD phải trỏ tới đề xuất đã chốt, và PRD phải được cập nhật trước.
  - §7: thêm dòng `docs/prd/update/`; spec không được lệch PRD nếu chưa chốt.
  - Thêm §8: định nghĩa "lệch PRD", quy trình đề xuất → chốt → cập nhật PRD → sửa source, xử lý lệch tồn đọng, mẫu đề xuất.
- `docs/prd/update/2026-09-23-nguyen-tac-lech-prd-phai-chot.md` — thêm: đề xuất đồng bộ `docs/prd/README.md` nguyên tắc 3 và `docs/prd/architecture.md` §6.1 với nguyên tắc mới. Người dùng **từ chối**: PRD là tài liệu để người review, quy tắc agent chỉ nằm trong `AGENTS.md`.
- `AGENTS.md` §8 — sửa thêm: ghi rõ `docs/prd/` và `docs/prd/update/` để con người review; không đề xuất đưa quy tắc agent vào PRD.

## Quyết định

- Folder đề xuất đặt ở `docs/prd/update/` theo yêu cầu người dùng. Bản nháp trước đặt ở `docs/update/` chưa từng được commit, đã bỏ.
- Chỉ người dùng được chốt; im lặng không tính là đồng ý. Thay đổi chỉ hiện thực đúng điều PRD đã ghi thì không cần đề xuất.
- Sau khi chốt: cập nhật PRD trước, rồi mới sửa source.
- Lệch đã có từ trước (`AGENTS.md` §2 — `api-contract.md`; §6.4 — persona) được coi là tồn đọng: không mở rộng thêm, muốn xử lý thì cũng phải qua đề xuất.
- Không sửa `docs/prd/README.md` và `docs/prd/architecture.md` dù đang lệch nguyên tắc mới; phần sửa được ghi thành đề xuất, đúng quy trình vừa đặt.

## Kiểm tra

- Không có lệnh kiểm tra tự động cho tài liệu. Đã chạy `grep -n "docs/update" AGENTS.md`: không còn tham chiếu tới đường dẫn cũ.

## Còn lại / rủi ro

- `docs/prd/README.md` nguyên tắc 3 (thêm ở `d23b682`) vẫn ghi "cập nhật PRD trong cùng thay đổi". Người dùng giữ nguyên PRD; agent làm theo `AGENTS.md` §8.
- Commit `d23b682` đã sửa thẳng `docs/prd/`, trước khi có nguyên tắc này. Không hoàn tác.
