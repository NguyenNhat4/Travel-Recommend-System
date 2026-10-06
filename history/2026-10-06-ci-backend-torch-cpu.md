# CI backend cài torch bản CPU

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend (CI)

## Mục tiêu

Trước khi merge PR #119 (e5-small): bước "Install backend test dependencies" của `backend-ci-cd.yml` cài `torch` từ PyPI mặc định — bản CUDA vài GB, chậm và dễ hết đĩa runner. Phục vụ FR-SRC-02.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — sửa: cài `torch>=2.3` từ `https://download.pytorch.org/whl/cpu` trước `requirements.txt` (giống `Dockerfile.backend`).

## Kiểm tra

- YAML parse được. Test backend không tải model (smoke e5 chỉ chạy khi `E5_SMOKE=1`). Crawler CI không cài thư viện Python (chỉ compileall + build image).

## Còn lại / rủi ro

- Chưa chạy trên GitHub Actions; lần chạy của PR #119 sẽ xác nhận.
