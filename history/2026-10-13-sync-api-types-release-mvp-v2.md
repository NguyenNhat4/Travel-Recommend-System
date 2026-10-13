# Đồng bộ api.gen.ts với contract sau PR #209

- Ngày: 2026-10-13
- Tác giả: Khoa15 (người yêu cầu) / Claude agent
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Sau khi merge PR #209 (`8b13808d`), Frontend CI trên `release-mvp-v2` đỏ ở bước "Check generated OpenAPI types are committed": contract `src/shared/contracts/` đã đổi nhưng `src/frontend/src/types/api.gen.ts` chưa được sinh lại. Sửa để release xanh trở lại, từ đó PR #207 (`khoa/perf-lcp-mobile`) có thể chạy CI trên base mới và merge.

## File thay đổi

- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types` (openapi-typescript 7.13.0). Thêm `entryPolicy` và `freeOnly`, đổi mô tả `run.preview` thành deprecated 2026-10-14.
- `history/2026-10-13-sync-api-types-release-mvp-v2.md` — thêm: entry này.

## Quyết định

- Sinh lại bằng script của dự án, không sửa tay file sinh tự động (AGENTS.md §3).
- Không đổi `openapi.yaml`: nguồn sự thật là contract mà PR #209 đã cập nhật. Chỉ đồng bộ phần sinh ra.
- Không đụng code khác. Test `productDetailView.test.tsx` từng fail trên release lúc 14:25 UTC được ghi nhận là flake do timing, không sửa trong thay đổi này.

## Kiểm tra

- `validate_contract.py` (dependency lấy từ `scripts/ci/py-deps.sh contract-validator`, chạy bằng Python có `jsonschema`): PASS.
- `npm run lint` (Node 22): 0 lỗi, 3 warning có sẵn.
- `npm run typecheck` (Node 22): pass.
- `npm run test` (Node 22): 89 file, 935 test, tất cả pass.
- `npm run build` (Node 22): pass.
- E2E smoke tests chưa chạy cục bộ; CI của PR #207 sẽ chạy lại trên base mới.

## Còn lại / rủi ro

- Push lên `release-mvp-v2` kích hoạt `Staging-HA App CD`; CD dùng Frontend CI làm gate trước khi build và deploy.
- PR #207 cần chạy lại CI trên base mới trước khi merge.
