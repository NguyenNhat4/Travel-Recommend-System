# Đề xuất chuẩn hoá cấu trúc thư mục backend

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: dang dở
- Phạm vi: backend, docs
- Bị thay thế bởi: 2026-09-23-tai-thiet-lap-cau-truc-backend.md

## Mục tiêu

Người dùng yêu cầu rà cấu trúc thư mục của dự án và đề xuất cách sửa để backend đúng nguyên tắc Clean Architecture ở `docs/prd/architecture.md` §2 (NFR-MAINT-01). Kết quả rà: cách chia theo lớp rồi theo domain trong PRD vẫn hợp lý, nhưng code đang vi phạm quy tắc phụ thuộc ở nhiều chỗ. Một số thay đổi cần bổ sung vào PRD §2 và §6.1, nên theo `AGENTS.md` §8 phải tạo đề xuất và chờ chốt.

## File thay đổi

- `docs/prd/update/2026-09-23-chuan-hoa-cau-truc-backend.md` — thêm: đề xuất, trạng thái `chờ chốt`.

## Quyết định

- Giữ cách chia theo lớp trước, domain sau (PRD §2). Không chuyển sang kiểu mỗi domain một thư mục chứa đủ bốn lớp: tốn công chuyển file mà không thêm giá trị, và cách hiện tại dễ kiểm quy tắc import tự động hơn.
- Đề xuất chỉ bổ sung phần PRD còn thiếu chỗ đặt code: `api/deps.py`, `api/middleware.py`, `api/errors.py`, `api/v1/schemas/`, `infrastructure/contracts/`, `tests/fakes/`, `tests/architecture/`; nguyên tắc mỗi port một file; quy tắc 8–11; xoá `src/main.py` và `src/config.py`.
- Frontend được tách sang đề xuất riêng, vì cần người phụ trách Web review.
- Chưa sửa code: các bước đưa code về đúng PRD phụ thuộc vào cây thư mục trong đề xuất, nên làm một lần sau khi chốt để tránh phải chuyển file hai lần.

## Kiểm tra

- Rà import giữa các lớp trong `src/backend/app` bằng `grep`. Kết quả nằm ở bảng "Lý do" của đề xuất.
- Không chạy test và `validate_contract.py`: chưa đổi code, contract hay mock.

## Còn lại / rủi ro

- Đang chờ người dùng chốt đề xuất. Sau khi chốt: cập nhật `docs/prd/architecture.md` §2 và §6.1, sửa `AGENTS.md` §3, viết plan ở `docs/plan/`, rồi refactor theo mục "Thay đổi source sau khi chốt".
- Chưa quyết định: chế độ `ITINERARY_DATA_MODE=fixture` khi chạy dev lấy fixture clients từ đâu nếu chuyển sang `tests/fakes/`.
- Nhánh khác đang sửa `src/backend/app/infrastructure/clients/*` hoặc `agents/*` sẽ bị conflict khi refactor.
