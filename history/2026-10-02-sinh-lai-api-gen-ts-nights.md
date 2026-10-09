# Sinh lại api.gen.ts sau khi contract thêm giới hạn nights

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI `frontend-ci-cd` fail ở bước `git diff --exit-code -- src/frontend/src/types/api.gen.ts`: `src/shared/contracts/schemas/booking.yaml` đã có mô tả `nights` "Tối đa 30 đêm." nhưng file sinh tự động chưa được tái sinh và commit.

## File thay đổi

- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `openapi-typescript`, chỉ đổi comment mô tả của `nights` (thêm "Tối đa 30 đêm.").

## Quyết định

- Không sửa tay file sinh tự động; chạy đúng lệnh của script `generate:api-types` để kết quả khớp CI.
- Không đổi contract, không lệch PRD.

## Kiểm tra

- `./node_modules/.bin/openapi-typescript ../shared/contracts/openapi.yaml -o src/types/api.gen.ts` (tương đương `npm run generate:api-types`): thành công; `git diff` chỉ có đúng một dòng comment khớp với diff CI báo.
- `validate_contract.py`: chưa chạy được trên máy này (thiếu module `jsonschema`); contract không bị sửa trong thay đổi này.

## Còn lại / rủi ro

- Không có. Khi sửa `paths/` hoặc `schemas/`, chạy `npm run generate:api-types` trong `src/frontend` và commit cùng `api.gen.ts`.
