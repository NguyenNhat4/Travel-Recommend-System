# Weaviate của staging là Weaviate Cloud, không phải local

- Ngày: 2026-10-09
- Người đề xuất: Khoa15 / Claude Code (theo chỉ đạo trực tiếp của người vận hành trong phiên)
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: người vận hành (Khoa15), 2026-10-09 (chỉ đạo: "Weaviate đang dùng cloud, cập nhật các tài liệu nói Weaviate đang dùng ở local")
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §1 (bảng môi trường, dòng "Cơ sở dữ liệu vector"), §2 (biến `WEAVIATE_URL`)
- Mã FR/NFR: không đổi (NFR-PERF-03, FR-SRC-02 giữ nguyên)

## Lý do

Môi trường staging trên GCP (`staging-ha`) đang trỏ `WEAVIATE_URL` tới Weaviate Cloud của nhóm (cluster ở `eu-central-1`, collection `Product`), không có VM Weaviate riêng (`create_weaviate = false`). PRD ghi staging là "Weaviate dùng chung" và `WEAVIATE_URL` mô tả chỉ có local. Câu này dễ khiến người đọc tưởng Weaviate staging nằm trong hạ tầng GCP hoặc chạy local.

## Nội dung đề xuất

1. `deployment-plan.md` §1, dòng "Cơ sở dữ liệu vector":
   - Trước: `| Weaviate local qua Docker (volume riêng) | Weaviate dùng chung | Weaviate Cloud hoặc self-host có backup |`
   - Sau: `| Weaviate local qua Docker (volume riêng) | Weaviate Cloud (cluster chung của nhóm, eu-central-1) | Weaviate Cloud hoặc self-host có backup |`
2. `deployment-plan.md` §2, biến `WEAVIATE_URL`:
   - Trước: `Endpoint Weaviate (local: http://localhost:8080)`
   - Sau: `Endpoint Weaviate (dev: http://localhost:8080; staging: URL cluster Weaviate Cloud, dạng https://<cluster>.weaviate.cloud)`

## Thay đổi source sau khi chốt

- `README.md` (gốc repo): câu "Weaviate và Redis vẫn là local" được sửa để nói rõ Weaviate là Cloud khi `.env` trỏ staging.
- Không đổi code. Cấu hình thực tế đã đúng: secret `vota-ha-backend-env` có `WEAVIATE_URL` của cluster Cloud; Terraform có `create_weaviate = false`.
