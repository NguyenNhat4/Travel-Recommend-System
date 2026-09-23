# Đưa nguyên tắc "lệch PRD phải chốt qua docs/prd/update" vào PRD

- Ngày: 2026-09-23
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: từ chối
- Chốt bởi / ngày: mihhquan, 2026-09-23
- PRD bị ảnh hưởng: `docs/prd/README.md` mục "Nguyên Tắc Vận Hành & Quản Trị Tài Liệu" (nguyên tắc 3); `docs/prd/architecture.md` §6.1
- Mã FR/NFR: không có — quy tắc quản trị, không đổi phạm vi sản phẩm

## Lý do

`AGENTS.md` §8 đặt nguyên tắc: mọi thay đổi lệch khỏi PRD (code, spec, contract, DDL, cấu hình, nội dung PRD) phải có đề xuất trong `docs/prd/update/` và được người dùng chốt trước khi sửa source. PRD hiện vẫn ghi quy tắc cũ:

- `README.md` nguyên tắc 3 ghi "Thay đổi làm lệch PRD phải cập nhật PRD trong cùng thay đổi". Quy tắc này cho phép sửa thẳng PRD, ngược với `AGENTS.md` §8.
- `architecture.md` §6.1 không nhắc thư mục `docs/prd/update/`.

## Nội dung đề xuất

**`docs/prd/README.md`, nguyên tắc 3**

Hiện tại:

> 3. **PRD là tài liệu gốc — đặt tài liệu đúng chỗ:** Thay đổi làm lệch PRD phải cập nhật PRD trong cùng thay đổi. Spec chi tiết ghi vào `docs/spec/`, kế hoạch triển khai ghi vào `docs/plan/`; không tạo tài liệu ở thư mục khác (`AGENTS.md` §7).

Thay bằng:

> 3. **PRD là chuẩn — lệch PRD phải chốt trước:** Bất kỳ thay đổi nào lệch khỏi PRD (code, spec, contract, DDL, cấu hình hay nội dung PRD) phải có đề xuất trong [`update/`](update/) và được chốt trước khi sửa source. Sau khi chốt, cập nhật PRD trước rồi mới sửa source (`AGENTS.md` §8). Spec chi tiết ghi vào `docs/spec/`, kế hoạch triển khai ghi vào `docs/plan/`; không tạo tài liệu ở thư mục khác (`AGENTS.md` §7).

**`docs/prd/architecture.md` §6.1, câu "Ngoài `src/`"**

Hiện tại:

> `docs/` (`prd/`, `spec/`, `plan/` — xem `AGENTS.md` §7)

Thay bằng:

> `docs/` (`prd/` kèm `prd/update/` cho đề xuất thay đổi, `spec/`, `plan/` — xem `AGENTS.md` §7–8)

## Thay đổi source sau khi chốt

- Chỉ sửa hai file PRD nêu trên. Không đổi code, spec, contract hay DDL.

## Kết quả chốt

Từ chối. PRD và `docs/prd/update/` là tài liệu để con người review; quy tắc làm việc của agent chỉ nằm trong `AGENTS.md`, không đưa vào PRD. Không sửa `docs/prd/README.md` và `docs/prd/architecture.md` theo đề xuất này.
