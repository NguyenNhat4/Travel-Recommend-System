# Đề xuất RecSys truy vấn Weaviate top-K mỗi request

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: backend, contract, spec

## Mục tiêu

Backend tải toàn bộ vector từ Weaviate Cloud lúc khởi động mất 453 giây (đo bằng `WeaviateClient.fetch`, trang 100), vượt ngưỡng 300 giây của `make web`, nên RecSys không lên. Người dùng yêu cầu chuyển sang truy vấn top-K mỗi request.

## File thay đổi

- `docs/prd/update/2026-09-24-recsys-truy-van-weaviate-top-k.md` — thêm: đề xuất, trạng thái chờ chốt.
- `history/2026-09-24-de-xuat-recsys-weaviate-top-k.md` — thêm.

## Quyết định

- Hướng này khớp PRD (`architecture.md` §5, NFR-PERF-03), nhưng lệch contract/spec `[C4]` (`EXACT_FILTER_SCORE`, ngưỡng lật 50.000 vector) và chạm rủi ro S8 đang mở. Vì vậy phải có đề xuất và chờ chốt trước khi sửa code (AGENTS.md mục 8).

## Kiểm tra

- Đo thực tế: REST `/v1/objects` có kèm vector, 100 object/trang, mất 5–42 giây mỗi trang. Băng thông chung của máy khoảng 180 KB/s. Round-trip `/.well-known/ready` là 1,8 giây.
- Job `embed_products` đã nạp đủ 3.178 vector lên cloud (3.183 search unit).

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất. Chưa sửa code RecSys.
- Trong lúc chờ, RecSys chỉ lên được khi trỏ `.env` sang Weaviate local (`deployment-plan.md` §1).
