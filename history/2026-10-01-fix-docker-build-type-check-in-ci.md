# Sửa Docker build fail trong CI vì thiếu file import

- Ngày: 2026-10-01
- Tác giả: User / Claude Haiku 4.5
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Lỗi TypeScript `Cannot find module 'booking-rules-cases.json'` chỉ được phát hiện ở bước Docker build trong CD (publish/deploy), không trong CI. Cần catch lỗi này sớm trong bước CI để CD chỉ là việc deploy, không phải phát hiện lỗi.

## File thay đổi

- `src/frontend/Dockerfile.web` — sửa: thêm `COPY src/shared/contracts/tests` vào builder stage
- `.github/workflows/frontend-ci-cd.yml` — sửa: thêm Docker build test trong job `quality` (trước e2e)

## Quyết định

### 1. Sửa Dockerfile.web (dòng 10)

File `src/frontend/tests/unit/checkoutRules.test.ts` import từ `../../../shared/contracts/tests/booking-rules-cases.json`. Dockerfile chỉ copy `src/shared/mocks`, không copy `src/shared/contracts/tests`. 

**Giải pháp:** Thêm dòng `COPY src/shared/contracts/tests ./src/shared/contracts/tests` vào builder stage (dòng 10) để file được copy vào Docker build context trước khi `npm run build:web` chạy.

Lý do: 
- File này là phần của source code cần để build (test fixture cho checkout rules).
- Nó nằm trong source tree, không phải generated hoặc mock data.
- Dockerfile phải copy tất cả dependencies cần thiết trước build step.

### 2. Thêm Docker build test trong CI (job quality)

Docker build hiện tại chỉ ở job `build_vm` (nhánh CD, chạy sau e2e pass). Nếu Docker fail, nó sẽ fail tại bước CD (publish/deploy).

**Giải pháp:** Thêm step Docker build test trong job `quality`, chạy **sau typecheck và trước e2e**, sử dụng `docker/build-push-action@v6` với `load: false` (chỉ test build, không load/push).

Thứ tự CI sắp xếp lại:
1. Lint → Typecheck → Unit tests → Build Next.js (npm run build) → [NEW] Docker build test
2. E2E (sau khi quality pass)
3. build_vm (CD phase, sau e2e pass)

Lý do:
- Type check (`npm run typecheck`) chạy **bên ngoài Docker**, không gặp lỗi import file vật lý.
- Docker build test sẽ **bắt buộc copy đủ file** vào build context, phát hiện lỗi copy trước CD.
- Fail ở CI (3 phút add Docker build) sẽ tiết kiệm thời gian CD (10+ phút publish/deploy).
- Quy tắc 3 cấp độ kiểm tra: (1) Type check trước Docker, (2) Docker build trong CI, (3) Deploy trong CD.

## Kiểm tra

```bash
# Verify Dockerfile copy statement
grep "COPY src/shared/contracts/tests" src/frontend/Dockerfile.web
# Output: COPY src/shared/contracts/tests ./src/shared/contracts/tests

# Verify workflow changes
grep -A 10 "Build Docker image (test phase" .github/workflows/frontend-ci-cd.yml
# Output: step "Build Docker image (test phase in CI)" exists

# Local test Docker build (optional)
cd src/frontend
docker buildx build -f Dockerfile.web --load -t test:latest /path/to/repo 2>&1 | grep -E "Cannot find|error TS|DONE|FAILED"
```

## Còn lại / rủi ro

Không có. Thay đổi hoàn thành:
- Dockerfile được sửa để copy file cần thiết.
- Workflow được cập nhật để test Docker build trong CI, trước CD.
- History entry được ghi.

Trên lần PR tiếp theo, CI sẽ catch lỗi Docker build ngay trong job `quality`, trước e2e, không để tới bước `publish_vm` hay `deploy_vm`.
