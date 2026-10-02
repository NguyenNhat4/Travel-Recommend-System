# Đề xuất vòng ReAct có chặn cho node `tool` (chờ chốt)

- Ngày: 2026-09-29
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng muốn node `tool` của Itinerary Agent hoạt động theo kiểu ReAct như `langchain-ai/react-agent`: LLM suy luận từ query, biết có tool gì, gọi tool, **quan sát kết quả**, hiểu còn thiếu gì rồi gọi thêm khi cần. Hiện `tool` chỉ hỏi LLM một lần để phát toàn bộ lời gọi, và không bao giờ cho LLM xem kết quả trả về.

Thay đổi này lệch PRD nên theo AGENTS.md §8 phải có đề xuất được chốt trước. Task này **chỉ tạo đề xuất**, chưa sửa source.

## File thay đổi

- `docs/prd/update/2026-09-29-vong-react-co-chan-cho-node-tool.md` — thêm: đề xuất cho phép lập lại tool plan tối đa một lần sau khi quan sát kết quả, trạng thái `chờ chốt`.
- `history/2026-09-29-de-xuat-vong-react-co-chan-node-tool.md` — thêm: entry này.

Không chạm `src/` và `db/`. (Trong `git status` có sẵn thay đổi frontend chưa commit của người dùng: `src/frontend/src/components/assistant/AiFloatingWidget.tsx`, `src/frontend/src/features/`, `src/frontend/tests/unit/floatingWidgetOpening.test.tsx` — không liên quan task này, không chạm tới.)

## Quyết định

Bốn quyết định do người dùng chốt trong phiên (chọn phương án khuyến nghị cho cả bốn câu hỏi):

- **Có chặn, không phải ReAct thuần:** tối đa 2 lượt tool (1 lần lập lại plan) cộng deadline. Lý do: vòng lặp không chặn sẽ vỡ NFR-PERF-02 và làm điều kiện dừng không test được.
- **Loop là cạnh `evaluate → tool`, không thêm node.** Giữ đúng 11 node nên `test_eleven_node_topology` và node id trên SSE không đổi. Đánh đổi: `evaluate` gánh hai vai (lọc grounding + quyết định lặp).
- **Điều kiện dừng tất định:** LLM chỉ đề nghị lời gọi mới, luật Python ở `evaluate` mới quyết lặp hay sang `compose`. Giữ được grounding và ngưỡng Tool Calling Accuracy ≥ 95%.
- **Gộp việc gỡ mâu thuẫn latency vào đề xuất:** PRD `NFR-PERF-02` ghi tổng ≤ 4.0s trong khi `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` ghi p95 < 5s ở ba chỗ (dòng 410, 451, 519). Với trần 4.0s thì predicate deadline gần như luôn chặn, tính năng sẽ không bao giờ chạy. Đề xuất nâng PRD lên 5.0s cho khớp spec.

Ba phát hiện kỹ thuật đã xác minh trong code, ghi lại để lúc triển khai không bỏ sót:

- `tool_planning.py:106` và `:110` đánh id `call-{index}` đếm lại từ 0 mỗi lần lập plan, còn `run_calls` (`:149`) memo kết quả theo `tool_call_id`. Vòng 2 sẽ trả kết quả vòng 1 cho một lời gọi hoàn toàn khác → **bắt buộc** đổi thành `call-{iteration}-{index}`.
- `evaluation.py:77` xóa `details: {}` sau khi `collect()` tiêu thụ. Vòng 2 chấm lại toàn bộ `tool_results` tích lũy mà thiếu `details` sẽ loại oan khách sạn đã hợp lệ (`PRODUCT_DROPPED_ATTRIBUTES`) → khi `decision == "replan"` phải giữ `details`.
- `tool_planning.py:121` bỏ qua LLM khi đã có `tool_plan` — đây là ngữ nghĩa **retry vận chuyển** hiện hành, phải giữ. Cần cờ riêng (`replan_requested`) để phân biệt với vòng lập lại plan.

Payload quan sát cố tình **không** chứa `productId`, `title`, `price`, `imageUrl`, `description` hay chuỗi nào từ upstream — chỉ số nguyên, tên taxonomy và mã `PRODUCT_DROPPED_*` của hệ thống. Nhờ vậy LLM vẫn chưa từng thấy dữ liệu sản phẩm nên NFR-REL-01 (grounding 100%) không đổi, và không mở bề mặt prompt-injection mới.

## Kiểm tra

- Chưa chạy test hay `validate_contract.py`: task này chỉ thêm tài liệu, không chạm `src/`, `db/` hay contract.
- Đã đối chiếu `git status` trước khi viết mục "File thay đổi".
- Đã xác minh bằng cách đọc code, không suy đoán: id lời gọi và memo (`tool_planning.py:106,110,149`), xóa `details` (`evaluation.py:77`), điều kiện bỏ qua LLM (`tool_planning.py:121`), `NFR-PERF-02` (`docs/prd/requirements.md:90`), p95 5 giây trong spec (dòng 410, 451, 519).

## Còn lại / rủi ro

- **Chờ người dùng chốt đề xuất.** Chưa chốt thì không được sửa `docs/prd/` hay `src/`.
- Sau khi chốt, thứ tự bắt buộc: sửa `docs/prd/` → sửa spec (`docs/spec/agent/langgraph-nodes.md` bỏ câu "chỉ cho retry một lần", `state-fields.md`, `hop-dong-tich-hop-itinerary-assistant.md` §4.1/§7.2 và ba dòng p95) → sửa code → chuyển đề xuất sang `docs/prd/update-archive/` bằng `git mv`.
- Rủi ro test chập chờn: predicate có deadline nên test phải tiêm `started_at`/clock giả, không dựa thời gian thật, nếu không sẽ fail ngẫu nhiên trên CI chậm.
- Đề xuất `docs/prd/update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` vẫn chờ chốt, không liên quan tới đề xuất này.
