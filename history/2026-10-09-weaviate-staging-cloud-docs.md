# Sửa tài liệu: Weaviate của staging là Weaviate Cloud, không phải local

- Ngày: 2026-10-09
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: đã hoàn thành
- Phạm vi: docs (`docs/prd/`, `README.md`). Không đổi code hay cấu hình hạ tầng.
- Đề xuất PRD: `docs/prd/update-archive/2026-10-09-weaviate-staging-cloud.md` (đã chốt bởi người vận hành, đã áp dụng)

## Lý do

Người vận hành báo: Weaviate đang dùng là Weaviate Cloud, nhiều tài liệu lại ghi là local. Đối chiếu cấu hình thật:
- Secret `vota-ha-backend-env` (phiên bản 10) có `WEAVIATE_URL` của cluster Cloud `*.c0.eu-central-1.aws.weaviate.cloud` và `WEAVIATE_COLLECTION=Product`. Chỉ kiểm host, không in khoá.
- `infra/terraform/environments/staging-ha/staging-ha.tfvars`: `create_weaviate = false`, nên không có VM Weaviate trong GCP.

## Thay đổi

1. `docs/prd/deployment-plan.md` §1, dòng "Cơ sở dữ liệu vector" cột Staging: "Weaviate dùng chung" → "Weaviate Cloud (cluster chung của nhóm, eu-central-1)".
2. `docs/prd/deployment-plan.md` §2, biến `WEAVIATE_URL`: thêm giá trị cho staging (URL cluster Weaviate Cloud). Giữ `http://localhost:8080` cho dev.
3. `README.md` (gốc repo), mục lưu ý khi dùng `make web`/`make backend-local`: "Weaviate và Redis vẫn là local" → Redis local; Weaviate phụ thuộc `.env` (staging → Weaviate Cloud). Thêm cảnh báo không chạy `embed_products`/`index-vectors` khi `.env` trỏ Weaviate Cloud dùng chung.

## Không đổi (đã đúng)

- `docker-compose.yml`, `src/backend/README.md`, `src/data_collection/README.md` (mô tả đích `local` và `local_crawl.sh`): đều là môi trường dev/local, đúng ngữ cảnh.
- `docs/spec/bench/*` và `docs/plan/*`: ghi nhận cấu hình lúc chạy benchmark (Weaviate local và Cloud đều có). Là lịch sử, không sửa.
- `variables.tf` (`create_weaviate`): mô tả đã đúng.

## Kiểm tra

- `grep` lại các dòng "Weaviate ... local" trong `docs/prd`, `README.md`, `docs/spec` (không gồm bench/plan): không còn dòng nào mô tả Weaviate staging/prod là local.

## Còn lại

- Các tài liệu bench/plan vẫn ghi Weaviate local khi chạy bench. Đây là đúng với ngữ cảnh lúc đó; không sửa.
