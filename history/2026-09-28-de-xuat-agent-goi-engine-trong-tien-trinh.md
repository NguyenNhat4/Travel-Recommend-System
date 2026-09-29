# Đề xuất: agent gọi engine trong tiến trình và tool Similar

- Ngày: 2026-09-28
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: dang dở
- Phạm vi: docs
- Đề xuất: docs/prd/update/2026-09-28-agent-goi-engine-trong-tien-trinh.md, docs/prd/update/2026-09-28-tool-similar-cho-agent.md
- Bị thay thế bởi: 2026-09-29-ap-dung-de-xuat-agent-goi-engine-va-tool-similar.md

## Mục tiêu

Người dùng muốn Itinerary Agent gọi thẳng các engine Search, Recommendation và Similar như tool trong cùng tiến trình, thay vì `ItineraryHttpClients` gọi ngược HTTP API của chính Backend, và muốn thêm tool Similar cho lượt đổi món. Hai việc này chạm chữ PRD (`requirements.md` FR-AGT-02, FR-AGT-05; `architecture.md` §2, §3; `deployment-plan.md` §2), nên theo `AGENTS.md` §8 bước 1 phải có đề xuất chờ người dùng chốt.

## File thay đổi

- `docs/prd/update/2026-09-28-agent-goi-engine-trong-tien-trinh.md` — thêm: P-A, làm rõ FR-AGT-02 (gọi engine trong tiến trình qua port của application, không gọi ngược HTTP của chính Backend), ghi chú cây thư mục `architecture.md` §2 cho `application/itinerary/engine_tools.py` và `infrastructure/clients/`, ba dòng biến môi trường cho `deployment-plan.md` §2 (`ITINERARY_DATA_MODE`, `ITINERARY_SERVICE_BASE_URL`, `ITINERARY_TOOL_TIMEOUT_SECONDS`); kèm mục "Phần đã làm song song" và danh sách file cần hoàn tác nếu bị từ chối.
- `docs/prd/update/2026-09-28-tool-similar-cho-agent.md` — thêm: P-B, tool `get_similar_products` cho lượt đổi món (FR-AGT-02, FR-AGT-05, nhãn chuyển trạng thái `architecture.md` §3 và câu nguồn grounding), quy tắc tool ở mức spec, danh sách file Phase B và ba câu hỏi mở.

## Quyết định

- Tách thành hai đề xuất vì mẫu `AGENTS.md` §8 chỉ có một trạng thái và một lần lưu trữ cho mỗi đề xuất: P-A (transport) và P-B (Similar) có thể được chốt ở hai thời điểm khác nhau.
- P-A chỉ làm rõ chữ PRD. `architecture.md` §1 (`LG → Tools → Ports`), quy tắc 7 và §6.3 mục 3 đã cho phép gọi trong tiến trình, nên code Phase 0/A làm song song, không chờ chốt (`AGENTS.md` §8: "Phần không lệch vẫn làm tiếp được"). Code đó ghi ở `2026-09-28-agent-goi-engine-trong-tien-trinh.md` và `2026-09-28-recsys-strategy-enum-va-cdp-fallback.md`.
- P-B thêm hành vi mới ngoài FR-AGT-02 hiện hành, nên toàn bộ Phase B (tool Similar) bị chặn tới khi P-B "đã chốt". Chưa có code Phase B nào trong nhánh.
- Sau review cuối, P-A được sửa bốn chỗ: câu "mode `http` (mặc định của `make chat`/`make web`)" chuyển sang thì quá khứ vì hai lệnh nay mặc định `inprocess`; thêm đoạn yêu cầu người review chốt rõ vị trí `engine_tools.py` so với dòng `infrastructure/ # LỚP 3: hiện thực port` của `architecture.md` §2; mục "Nếu bị từ chối" liệt kê file cụ thể phải hoàn tác (Makefile, `engine_tools.py` và nhánh `inprocess`, các đoạn spec/README); bullet "Quan sát" ghi đúng rằng lời gọi quá hạn chỉ ghi `itinerary.tool.timeout`.
- Không sửa `docs/prd/` ngoài hai file trong `docs/prd/update/` (`AGENTS.md` §8 bước 3 chỉ áp dụng sau khi chốt).

## Kiểm tra

- Chỉ là tài liệu, không có test tự động riêng.
- Bước review đã kiểm bằng script: mọi đoạn PRD trích ở mục "Hiện tại" khớp nguyên văn (sau khi chuẩn hoá khoảng trắng) với `requirements.md:40`, `:43` và `architecture.md:110`, `:114`, `:178`, `:191`; cả hai đề xuất đủ các trường header và ba mục của mẫu `AGENTS.md` §8.
- Bước review cũng xác nhận các khẳng định của P-B: route `/products/{productId}/similar` trả 400/409/503 trong khi contract chỉ khai báo 200/404/500.

## Còn lại / rủi ro

- Chờ người dùng chốt P-A và P-B (`đã chốt`, yêu cầu sửa, hoặc `từ chối`). Agent không tự chốt.
- Khi P-A được chốt: sửa `requirements.md` FR-AGT-02, `architecture.md` §2, `deployment-plan.md` §2 đúng nội dung đã chốt, đổi trạng thái sang `đã áp dụng`, `git mv` sang `docs/prd/update-archive/`, tạo entry mới ghi `Thay thế:` entry này.
- Khi P-B được chốt: cập nhật PRD trước (bước B0), rồi mới làm Phase B (contract 400/409/503, `tool_contracts.OPERATIONS`, port, ba adapter, gateway, planner, test, golden case đổi món); entry mới ghi `Thay thế:` entry này. Việc thêm operation vào `tool_contracts.OPERATIONS` sẽ mở rộng chỗ lệch còn mở của `2026-09-23-tai-thiet-lap-cau-truc-backend.md`.
- Câu hỏi mở của P-B: compose có ưu tiên kết quả similar cho slot đang đổi không; có thêm `destination` hoặc `cross_taxonomy` về sau không; có xử lý chỗ lệch `tool_contracts` trước khi thêm tool không.
