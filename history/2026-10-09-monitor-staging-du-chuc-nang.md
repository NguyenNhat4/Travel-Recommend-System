# Monitor staging công khai đủ chức năng (bỏ chế độ chỉ đọc khỏi deploy staging-ha)

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra (staging-ha), scripts, data, docs
- Thay thế: `2026-10-09-monitor-chi-doc-deploy-thu-cong.md` (phần chế độ chỉ đọc của deploy staging-ha)

## Mục tiêu

Monitor công khai trên staging phải dùng được đủ chức năng: không API nào bị chặn. Người yêu cầu xác nhận đây là staging; mức bảo mật là quyết định của họ.

## Nguyên nhân

`--read-only` (`src/data_collection/monitor.py`) trả 405 cho mọi POST. Bảy endpoint POST mà UI dùng đều bị chặn:

- `/api/run`, `/api/resume`, `/api/stop`: chạy, tiếp tục, dừng lượt
- `/api/settings`: lưu cấu hình, nút "Áp ngân sách Trip"
- `/api/live`: tạm dừng và đổi delay từng nguồn khi lượt đang chạy
- `/api/storage/cleanup`: xoá lượt cũ
- `/api/embed/query`: ô thử truy vấn

Deploy staging-ha (`scripts/deploy-staging-ha-crawler.sh`) đặt `MONITOR_READ_ONLY=1`, nên bảy chức năng trên không dùng được trên `monitor.praxis.io.vn`.

## File thay đổi

- `scripts/deploy-staging-ha-crawler.sh` — sửa: bỏ `MONITOR_READ_ONLY=1` khỏi lệnh chạy `fresh-monitor` (dòng 67).
- `infra/terraform/environments/staging-ha/crawler_monitor.tf` — sửa comment và mô tả biến `crawler_monitor_public`: bỏ "chỉ đọc / read-only". Không đổi resource.
- `infra/terraform/environments/staging-ha/main.tf` — sửa comment (dòng 217).
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — sửa comment (dòng 27).
- `infra/terraform/environments/staging-ha/staging-ha.tfvars` — sửa comment (dòng 37). File này không được kiểm tra có track trong git hay không.
- `src/data_collection/README.md` — sửa: `MONITOR_READ_ONLY` là tuỳ chọn, mô tả 7 API bị ảnh hưởng; staging-ha công khai đủ chức năng.
- `src/data_collection/monitor.py` — sửa docstring: ghi 7 API bị chặn khi bật `--read-only`. Không đổi code.
- `history/2026-10-09-monitor-chi-doc-deploy-thu-cong.md` — thêm dòng `Bị thay thế bởi` (không sửa nội dung cũ).
- `history/2026-10-09-monitor-staging-du-chuc-nang.md` — thêm: entry này.

## Quyết định

- Giữ cờ `--read-only` và biến `MONITOR_READ_ONLY` làm tuỳ chọn, mặc định tắt. Không xoá tính năng.
- Staging không có xác thực. Người yêu cầu chấp nhận rủi ro này.
- Chưa deploy lại. VM đang chạy image `vota-fresh-catalog:readonly-f23574ed-202610091347` với `--read-only`; thay đổi này chỉ có hiệu lực sau khi deploy lại monitor.

## Kiểm tra

- `bash -n scripts/deploy-staging-ha-crawler.sh` → ok.
- `python3 -m py_compile src/data_collection/monitor.py` → ok.
- Test monitor trong venv tạm (scratchpad, cài `src/data_collection/requirements.txt`): `tests/test_monitor_public.py`, `tests/test_monitor_storage.py`, `tests/test_monitor_backend_calls.py` → 8 tests OK.
- `terraform validate` không chạy; thay đổi Terraform chỉ là comment.
- Tìm lại: không còn chuỗi "chỉ đọc" hoặc "ĐỌC-ONLY" mô tả staging-ha trong `scripts/deploy-staging-ha-crawler.sh`, `infra/terraform/environments/staging-ha/`, và README (các chỗ còn lại là tab DB và role index, đúng thiết kế).

## Còn lại / rủi ro

- **Realtime (`/api/calls`) có thể không chạy trên VM crawler.** Monitor gọi `BACKEND_URL`, mặc định `http://127.0.0.1:8000` ([run_daily_docker.sh:32](../src/data_collection/run_daily_docker.sh)). Deploy staging-ha không truyền `BACKEND_URL`, và trong `infra/terraform/environments/staging-ha/crawler*.tf` không có backend nào chạy trên VM crawler. Cần địa chỉ backend mà VM crawler gọi được. Chưa quyết định.
- **Chưa kiểm trên VM:** tab DB cần `CLOUD_SEED_DATABASE_URL` trong `/etc/vota/fresh-catalog.env`; ô thử truy vấn cần `CLOUD_WEAVIATE_URL` và `CLOUD_WEAVIATE_API_KEY`. Model e5-small đã nằm trong image (`Dockerfile.fresh-catalog`, dòng 26–35), nên không cần tải khi chạy.
- Deploy lại monitor staging-ha chưa chạy. Cần người vận hành quyết định thời điểm.
- Chưa commit. Cờ `--read-only` (`monitor.py`, `run_daily_docker.sh`) vẫn là thay đổi chưa commit.
- CD non-HA (`.github/workflows/crawler-ci-cd.yml`) đã đủ chức năng từ trước; không đổi.
