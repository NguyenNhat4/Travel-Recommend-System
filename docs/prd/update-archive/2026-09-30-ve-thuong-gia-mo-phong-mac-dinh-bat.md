# Vé Thương gia mô phỏng: mặc định bật

- Ngày: 2026-09-30
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-09-30 ("OK vậy chốt số 2")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1 FR-CAT-03 (câu ngoại lệ vé mô phỏng), `docs/prd/data-model.md` §3 (mục
  "Vé Thương gia mô phỏng (demo)", dòng bật / tắt)
- Mã FR/NFR: FR-CAT-03; liên quan NFR-REL-01

## Lý do

Đề xuất `2026-09-30-ve-thuong-gia-mo-phong-cho-demo.md` (đã áp dụng) để vé mô phỏng **mặc định tắt**, bật bằng
`SIMULATED_BUSINESS_FARES=1` trong env của job trên VM. CD không sửa file env, và người yêu cầu không có quyền vào VM, nên
push / merge xong web vẫn không có vé Thương gia. Muốn deploy xong là có, không cần ai vào VM.

## Nội dung đề xuất

`docs/prd/requirements.md` FR-CAT-03: "bật bằng cấu hình, tắt thì các vé này không đặt được nữa" → "mặc định bật, tắt bằng
cấu hình; tắt thì các vé này không đặt được nữa".

`docs/prd/data-model.md` §3, dòng "Bật bằng biến môi trường `SIMULATED_BUSINESS_FARES=1` (mặc định tắt) cho job cào trên VM
(fresh và `daily.py`); seed demo local (`make demo-db`) luôn bật." → "Mặc định bật ở mọi bước nạp catalog: seed demo local
(`make demo-db`, luôn bật), `seed --catalog-only` / `daily.py` và job fresh. Tắt bằng `SIMULATED_BUSINESS_FARES=0` trong env
của job (seed demo đầy đủ không tắt được)."

## Ảnh hưởng

- Có lợi: merge vào nhánh CD là staging có vé Thương gia "(giá minh hoạ)" từ lượt nạp kế tiếp, không cần thao tác trên VM.
- Đánh đổi: mọi môi trường chạy job (kể cả môi trường mới) mặc định có giá mô phỏng (đã gắn nhãn, `simulated: true`). Tắt vẫn
  cần sửa env trên VM, hoặc chạy lệnh `--disable` qua tunnel (lượt nạp sau sẽ bật lại nếu env chưa tắt).

## Thay đổi source sau khi chốt

- `src/data_collection/seed/simulated_business.py`: `enabled()` trả `true` khi biến trống / không đặt; chỉ `0`, `false`, `no`,
  `off` là tắt.
- `src/data_collection/tests/test_simulated_business.py`: test cờ mặc định.
- `src/data_collection/.env.example`, `docs/spec/MOCK_DATA_SPEC.md`, `docs/guide/hien-thi-hang-ve-may-bay.md`,
  `docs/guide/ve-thuong-gia-va-index-cho.md`, `docs/guide/trien-khai-job-cao-du-lieu.md`: mô tả mặc định bật.
