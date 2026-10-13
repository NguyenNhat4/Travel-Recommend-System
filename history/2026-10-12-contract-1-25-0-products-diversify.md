# Contract 1.25.0: GET /products nhiều taxonomy và `diversify=taxonomy`; đóng P3

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (contract đi trước code; backend hiện thực ở `2026-10-12-products-tron-theo-nhom-loai.md`)
- Phạm vi: contract, mock, frontend (type sinh tự động), backend (chuỗi version)
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md`, `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md`

## Mục tiêu

Tab "Tất cả" của kệ "Phổ biến tại các điểm đến Việt Nam" ở trang chủ chỉ hiện vé máy bay. Lý do: lượt mua chuyến bay dồn về 113 tuyến, còn lượt mua khách sạn tản ra khoảng 2.400 property. Người dùng chọn sửa bằng một tham số cộng thêm của `GET /products`, vẫn 1 request cho khối này. Tab "Vé tham quan" gộp cả golf. Theo AGENTS §3, contract sửa trước.

Cùng lần nâng version, đóng mục P3 (cache gợi ý) của contract theo đề xuất đã chốt. Phục vụ FR-REC-01, chỉ số Diversity ở `docs/prd/test-plan.md` §2.5, và NFR-PERF-01 (phần P3).

## File thay đổi

- `src/shared/contracts/paths/catalog.yaml` — sửa:
  - `taxonomy`: mảng `Taxonomy`, `style: form`, `explode: false`, `minItems: 1`. Một giá trị như cũ vẫn hợp lệ.
  - Thêm `diversify`: enum `[taxonomy]`.
  - Thêm một câu vào mô tả operation.
- `src/shared/contracts/schemas/recommendations.yaml` — sửa:
  - Đầu file: P3 chuyển sang "đã áp dụng".
  - Mô tả `userVectorCacheHit` thành "true khi kết quả lấy từ cache gợi ý.".
  - Bỏ tiền tố `[CHỜ DUYỆT: P3]` ở `userVectorNorm`.
- `src/shared/contracts/openapi.yaml` — sửa: version 1.24.0 → 1.25.0.
- `src/backend/app/main.py` — sửa: `version="1.25.0"`.
- `src/backend/tests/contract/test_search_contract.py`, `src/backend/tests/contract/test_search_llm_contract.py` — sửa: chuỗi version.
- `src/shared/mocks/catalog/listProducts.200-diversified.json` — thêm: 8 món theo thứ tự nhóm (khách sạn, vé tham quan, combo, tuyến bay, khách sạn, golf, combo, tuyến bay). Hai combo có tên "Vé máy bay khứ hồi … + …".
- `src/shared/mocks/index.json` — sửa: đăng ký fixture `diversified`.
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `npm run generate:api-types`.
- `history/2026-10-12-contract-1-25-0-products-diversify.md` — thêm: entry này.

## Quyết định

- **Cách gửi nhiều taxonomy:** một tham số, các giá trị cách nhau bằng dấu phẩy (`style: form`, `explode: false`), không đổi sang `taxonomy` lặp lại. Lý do: client và agent đang gửi một chuỗi vẫn hợp lệ, và Web chỉ cần `join(',')`.
- **Quy tắc của `taxonomy`:** giá trị trùng bỏ qua, nên schema không đặt `uniqueItems`. Giá trị lạ hoặc đoạn rỗng trả 400 với `details.fields` có `"taxonomy"`.
- **Quy tắc của `diversify`:**
  - chỉ nhận `taxonomy`, chỉ đi với `sort=popular` và không có `parentProductId`;
  - sai thì trả 400 với `details.fields` có `"diversify"`;
  - trộn trước khi phân trang, nên kết quả là hoán vị, `total` không đổi và các trang nối tiếp nhau;
  - thứ tự nhóm cố định khách sạn → vé tham quan và golf → combo → vé máy bay (người dùng chốt 2026-10-12).
- **Không đụng `ProductSort`/[C7]:** ngữ nghĩa `sort=popular` giữ nguyên; công thức popularity để người dùng chốt riêng.
- **`userVectorNorm`:** bỏ nhãn P3, vì P3 đã đóng và trường này là chỉ số kiểm vector, không phải cache.
- **Contract đi trước code:** backend chưa hiện thực `diversify` hay nhiều taxonomy cho tới bước kế tiếp (cùng nhánh).

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 python src/shared/contracts/tests/validate_contract.py`: PASS, 120 schema, 96 fixture.
- `pytest -q -p no:cacheprovider src/backend/tests/contract`: 114 passed.
- Frontend (sau `npm ci` trong worktree): `npm run generate:api-types` chỉ đổi 3 chỗ: mô tả operation, `listProducts.query.taxonomy` thành mảng và thêm `diversify`, mô tả `userVectorCacheHit`/`userVectorNorm`. `npm run typecheck`: sạch.

## Còn lại / rủi ro

- Backend (bước 2) và frontend (bước 3) hiện thực tham số mới trên cùng nhánh.
- Khi merge, nếu frontend mới chạy với backend cũ, tab "Vé tham quan" (`attraction,golf`) sẽ trả 400. Nên deploy backend trước.
