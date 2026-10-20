# Sửa plan tiến trình theo review, chỉ làm cho orchestrator; đề xuất và plan gỡ luồng cũ

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs (plan, đề xuất PRD cho agent, contract, frontend)
- Bị thay thế bởi: `2026-10-12-sua-plan-theo-review-3.md` (một phần: trạng thái chốt của các câu hỏi)

## Mục tiêu

Sửa plan `2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` theo 6 điểm review của người dùng. Cũng trong lượt này, người dùng
quyết định orchestrator là luồng chính, và gỡ mọi code chỉ luồng cũ dùng để đồng đội không test hay tối ưu trên luồng
đó, nhưng cần plan trước khi gỡ.

## File thay đổi

- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: chỉ làm cho luồng orchestrator; nhóm tìm kiếm có
  `groupId` và quy tắc cập nhật; số đếm định nghĩa riêng và đếm tại chỗ lọc; chẩn đoán mức 2 dùng khoá và danh sách
  trường cho phép theo tool; B2 vào phạm vi chốt; ghi các quyết định Q2, Q3, Q4, Q6.
- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — thêm: plan gỡ luồng cũ G0–G6.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — thêm: đề xuất AC-AGT-09, `user-flow.md` §4.2,
  `architecture.md` §3, biến `ASSISTANT_STREAM_DEBUG_TOKEN`. Chờ chốt.
- `docs/prd/update/2026-10-12-orchestrator-thanh-luong-chinh.md` — thêm: đề xuất orchestrator là luồng duy nhất, bỏ cờ
  `ITINERARY_ORCHESTRATOR`. Chờ chốt.
- `history/2026-10-12-sua-plan-tien-trinh-theo-review.md` — thêm: entry này.

## Quyết định

- Review điểm 1 (P1, hỏi vé khi cờ tắt đi `explore_node_async` → `fares.answer()`, chưa có activity): đúng với code.
  Không sửa bằng cách thêm tiến trình cho luồng cũ, vì người dùng chốt bỏ luồng cũ. Plan chỉ có đường orchestrator: nút vé
  (`fare_button_turn`) và job `fare`. Bảng đường đi ở mục 1.3 của plan đọc từ `graph.py`, `routing.py`,
  `precheck_node_async`.
- Review điểm 2 (P1, số đếm): đúng với code. `_page` dùng `total` chỉ để tính `source_more`; `excluded` là danh sách thẻ
  đã xem. Plan định nghĩa riêng `sourceTotal`, `received`, `outOfScope`, `inScope`, `dropped`, `eligible`, `chosen`; mỗi
  sản phẩm vào đúng một ô theo thứ tự cố định. Đếm tại chỗ lọc (`collect`, `_preferred_stays`, `flight_options`, `_page`,
  `fares`) bằng cùng hàm điều kiện; không đếm được đúng định nghĩa thì để trống.
- Review điểm 3 (P2, contract nhiều job): `groupId` = `plan:<taxonomy>`, `plan:flight`, `job:<số job gốc>` (job lấy tiếp
  dùng `source_job`). Nhóm thay toàn bộ theo `groupId`, backend gửi số cộng dồn, có `superseded`. `chosen` là giao với
  response cuối. Fixture có hai job cùng loại và một job lấy tiếp.
- Review điểm 4 (P1, cửa chốt PRD): tạo đề xuất riêng trong `docs/prd/update/` ngay lượt này. B2 vào phạm vi chốt (PRD
  không có căn cứ cho `DebugPanel`); chỉ B0 làm trước được.
- Review điểm 5 (P2, chẩn đoán): bỏ cách lọc theo tên khoá. Dùng danh sách trường cho phép theo từng tool, áp theo đường
  dẫn và kiểu; bỏ mọi chuỗi tự do. Chỉ request mang header khớp `ASSISTANT_STREAM_DEBUG_TOKEN` mới nhận `debug`. Có test
  dữ liệu lồng nhau và hai request đồng thời.
- Lý do Q6 sửa lại: ở luồng orchestrator, LLM chọn thẻ sau khi đọc kết quả job; chưa làm preview khám phá là để giới hạn
  phạm vi.
- Gỡ luồng cũ lệch `architecture.md` §3 ("Cờ mặc định tắt; chỉ chuyển sau bộ đo đạt ngưỡng"), nên có đề xuất riêng và
  plan riêng. Thứ tự trong plan gỡ: kiểm kê → bật mặc định và ghi lại snapshot (người dùng duyệt) → chuyển helper dùng
  chung → bỏ cờ và node cũ → xoá → dọn test và bảng độ phủ AC → tài liệu. Chưa xoá code nào.

## Kiểm tra

- Chưa sửa source, chưa chạy test.
- Đọc code để xác nhận review và kiểm kê: `nodes.py` (`explore_node_async`, `precheck_node_async`, guardrail ra
  `simple`), `classification.py:181–184` (`fare_question` với `decision = explore`), `jobs.py` (`_page`, `_one`,
  `execute`, `_brief`), `exploration.py` (`explore`, `search`, `pick`), `routing.py`, `graph.py`, `services/server/proxy.ts`
  (`STRIPPED_REQUEST_HEADERS`), `tool_contracts.py`.
- Grep đếm tham chiếu ký hiệu cũ trong test agent: `test_classify.py` 30, `test_exploration.py` 17, `test_guardrails.py`
  16, `test_itinerary_runtime.py` 8, `test_explore_storytelling.py` 8, `test_fares.py` 6, `test_routing.py` 3,
  `test_open_question.py` 3, `test_explore_asked_place.py` 2.
- Cờ đang mặc định `off` ở `core/config.py`, `.env.example`, `docker-compose.yml`; harness snapshot không bật orchestrator.

## Còn lại / rủi ro

- Chờ người dùng chốt hai đề xuất và trả lời Q1, Q5, Q7 (plan tiến trình) và R1–R3 (plan gỡ luồng cũ).
- G0 (kiểm kê) và B0 (đo) làm được ngay mà không cần chốt.
- Snapshot hiện ghi bằng luồng cũ. Gỡ luồng cũ đổi hành vi ở mọi lượt trước đây đi luồng đó; người dùng phải duyệt khác
  biệt ở G1.
- Chưa commit.
