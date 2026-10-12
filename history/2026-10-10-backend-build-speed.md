# Tăng tốc build image backend và tách build khỏi khoá deploy staging-ha

- Ngày: 2026-10-10
- Tác giả: Khoa15 / Claude Code (agent)
- Nhánh: release-mvp-v2 (commit từ khoa/backend-build-speed-v2, base 524b7d4a)
- Trạng thái: hoàn thành (code). Chưa kiểm chứng trên CI thật, xem "Còn lại / rủi ro".
- Phạm vi: backend

## Mục tiêu

Build image backend staging-ha mất tới ~7,5 phút khi cache miss, và job images có thể chờ ~33 phút trong hàng đợi
concurrency `staging-ha-app` (run 37951309601, 2026-10-09). Mỗi lần push lên release-mvp-v2 build cùng image ba lần.
Mục tiêu: giảm thời gian build khi cache miss, bỏ build trùng, và để build không phải xếp hàng sau deploy.

Nguyên nhân đã đo:
- Cache miss do digest của `python:3.11-slim` đổi (0dd364… → e88e97…). Dockerfile và requirements giống hệt giữa run
  nhanh (18 s) và run chậm.
- Bước export cache GHA mất 212 s, push image 76 s, cài torch 44 s, requirements 57 s.

## File thay đổi

- `Dockerfile.backend` — sửa: hai dòng FROM ghim digest trực tiếp (để Dependabot cập nhật được); stage `model` tải e5-small
  độc lập với requirements; torch ghim đúng bản trong requirements-embed ngay lần cài đầu; bỏ bước cài requirements-embed
  thứ hai.
- `.dockerignore` — sửa: thêm `.claude` (2,5 GB ở máy local).
- `src/backend/requirements.txt` — sửa: `transformers>=4.44,<5` → `transformers==5.18.0`.
- `src/backend/requirements-embed.txt` — sửa: chỉ còn `torch==2.14.1`; transformers chuyển sang requirements.txt.
- `.github/workflows/backend-ci-cd.yml` — sửa: job build chỉ chạy trên PR; job publish tắt bằng `if: ${{ false }}`.
- `.github/workflows/staging-ha-backend-build.yml` — thêm: workflow tái sử dụng (workflow_call), build và push image,
  không có concurrency group.
- `.github/workflows/staging-ha-backend-cd.yml` — sửa: job `build` gọi workflow build; job `deploy` gộp apply, verify và
  rollback vào một job có `concurrency: staging-ha-app`; cache chuyển sang registry `:buildcache`.
- `.github/workflows/staging-ha-frontend-build.yml` — thêm: tương tự backend, cho frontend.
- `.github/workflows/staging-ha-frontend-cd.yml` — sửa: cùng cấu trúc với backend CD.
- `.github/dependabot.yml` — thêm: ecosystem docker cho `/` và `/src/frontend`.

## Quyết định

- Khoá deploy đặt ở job, không đặt ở workflow, và gộp apply/verify/rollback vào một job. Lý do: nếu tách verify ra job khác,
  lock được nhả sau apply và deploy của run khác có thể xen vào trước khi verify chạy.
- Tên group giữ nguyên `staging-ha-app` (backend và frontend dùng chung). Crawler dùng group `staging-ha-crawler` riêng,
  không đổi.
- `publish` trong backend-ci-cd không xóa mà tắt, vì `scripts/tests/test-backend-vm-cd-sync.sh` kiểm chuỗi
  `needs.publish.outputs.backend_digest` trong file này. Hệ quả: tag `:latest` không còn được đẩy; chỉ compose của VM cũ
  (đã tắt) dùng tag này.
- Transformers được ghim một chỗ (requirements.txt) với phiên bản đã đo parity (5.18.0), thay vì `<5` ở một file và
  `==5.18.0` ở file khác.
- Base image ghim digest `e88e9763…` (digest đang dùng trong CI ngày 2026-10-09 15:56). Tag không đổi; khi cần đổi thì
  Dependabot mở PR.
- Không có thay đổi PRD: không đổi hành vi sản phẩm, không đổi phiên bản dependency so với PRD (PRD không ghi phiên bản
  transformers). Deploy vẫn tuần tự qua `staging-ha-app`.

## Kiểm tra

- YAML của sáu file workflow và dependabot: parse được.
- `actionlint` (v1.7.7) trên năm workflow đã đổi: không lỗi, trừ cảnh báo nhãn runner `vota-staging-ha` không có trong
  danh sách mặc định (baseline cũng báo đúng lỗi này).
- `bash scripts/tests/test-backend-vm-cd-sync.sh`: "backend VM CD sync checks passed".
- `docker buildx build --check -f Dockerfile.backend .`: không cảnh báo.
- `docker build -f Dockerfile.backend .` (cache nguội, local): thành công. Bước verify embedder ra 384 chiều.
- Đổi `src/backend/requirements.txt` rồi build lại: bước tải model (`[model 2/2]`), cài torch và `COPY --from=model`
  đều CACHED (trên bản Dockerfile trước khi gộp; xem dưới).
- Build lại với bố cục mới: `pip check` → "No broken requirements found"; `transformers 5.18.0`, `torch 2.14.1+cpu`.
- Chạy pytest trong image: 2607 passed, 36 skipped, 1 failed. Lỗi là `test_no_agent_test_case_query_is_blocked` vì
  `.dockerignore` loại `src/evaluation` (file YAML của test được track trong repo). Chạy lại đúng test đó với
  `src/evaluation` mount vào: passed.
- Smoke test chạy image bằng user `10001`, `HF_HUB_OFFLINE=1`: nạp model và embed ra 384 chiều.

## Còn lại / rủi ro

- Chưa có run CI thật nào cho bố cục mới. Lần chạy đầu sau khi merge sẽ là cache miss (requirements-embed.txt đổi nội dung,
  registry cache còn trống), nên có thể chậm hơn trong lần đầu. Từ lần thứ hai mới thấy hiệu quả.
- Cache `type=registry` ghi tag `:buildcache` vào repo GAR. Cần cleanup policy giữ tag này và quyền ghi cho service
  account CI. Chưa kiểm chứng trên GAR.
- Job publish trong backend-ci-cd chỉ tắt, chưa xóa. Nếu VM cũ không còn dùng, có thể xóa job cùng test liên quan.
- Dependabot ecosystem docker: chưa xác nhận trên GitHub là nó nhận file tên `Dockerfile.backend` (không phải `Dockerfile`).
  Cần kiểm sau khi merge.
- Frontend build vẫn dùng cache `type=gha` (scope `staging-ha-frontend`), chưa đổi sang registry như backend.
- Chưa có số đo thời gian trên CI sau thay đổi. Ước lượng cache miss từ ~7,5 phút xuống ~3–4 phút chỉ là ước tính từ
  các bước đã đo, không phải kết quả đo.
- Test `test_no_agent_test_case_query_is_blocked` phụ thuộc `src/evaluation` mà image không có. Không ảnh hưởng quality
  job, nhưng ai chạy pytest trong image cần mount thư mục này.
