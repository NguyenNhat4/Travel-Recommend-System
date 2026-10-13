# E01: contract assistant v2, fixture và types độc lập

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành (E01); toàn plan dang dở
- Phạm vi: contract, frontend types, docs

## Mục tiêu

FR-AGT-01–07, NFR-REL-01, NFR-MAINT-02, AC-AGT-04/06/09; áp dụng đề xuất đã chốt E00 ở update-archive. Contract trước implementation.

## File thay đổi

- `src/shared/contracts/assistant-v2.openapi.yaml` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/contracts/paths/assistant-v2.yaml` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/contracts/schemas/assistant-v2.yaml` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/contracts/scripts/bundle_openapi.py` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/contracts/tests/validate_assistant_v2.py` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/contracts/tests/validate_contract.py` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/frontend/package.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/frontend/src/types/assistant-v2.gen.ts` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `docs/spec/contracts-guide.md` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `docs/spec/shared-assets.md` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/answer-30.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/answer.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/clarification.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/index.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/itinerary-over.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/itinerary-unknown.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/itinerary-zero.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/partial.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/request.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `src/shared/mocks/assistant-v2/stream.json` — thêm/sửa: contract, kiểm/fixture/types/hướng dẫn theo E01.
- `docs/plan/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md` — sửa tiến độ E01.
- `history/2026-10-13-orc-tu-chu-e01-contract.md` — thêm entry.

## Quyết định

Entry /api/v2 riêng, schemas strict cho business data. ProductSummary tái dùng v1. UiAction chỉ server-issued action IDs; server phải resolve/verify owner khi E10 triển khai. Final có planEffect/revision, taxonomy10 không tổng20, cảnh báo over/unknown và 0 đêm/nhiều hoạt động. SSE có discriminator, runId/sequence và preview không actions. Bundler hỗ trợ entry v2/discriminator và schema $ref siblings của OpenAPI 3.1; không sửa bundle sinh tự động.

Schema kiểm tổng số entries cùng taxonomy giữa recommendations/alternatives. Unique productId khác payload, arithmetic/date/grounding/consent/disclosures cần runtime guardrail E07/E10, ghi x-runtime-invariants rõ. Sample thẻ thật 30 = 10 hotel + 10 flight + 5 attraction + 5 combo; tiền và giờ fixture là minh họa, không giá nguồn/evidence runtime.

## Kiểm tra

- validate_contract.py: exit 0, v2 36 schemas/8 fixtures/14 negative; v1 130 schemas/106 fixtures và CDP giữ PASS.
- npm --prefix src/frontend run generate:assistant-v2-types: exit 0.
- npm --prefix src/frontend run typecheck: exit 0.
- git diff --check: PASS.
- Hai lỗi sửa trước pass: import path của validator độc lập; external refs/discriminator mapping phải chỉ đúng entry v2. Types được sinh bằng tool, không sửa tay.

## Còn lại / rủi ro

E02–E13 chưa nghiệm thu. Chưa có endpoint v2/graph/UI v2; không chuyển widget. Cần runtime enforce mọi invariant ghi trên schema. Không commit/push/deploy.
