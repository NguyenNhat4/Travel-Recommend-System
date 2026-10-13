# Gỡ luồng phân loại cũ của trợ lý, orchestrator là luồng duy nhất

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13. Người dùng nhắn "code ko dùng thì remove khỏi nodes và graph để ko phải
  đọc trùng". Khi được hỏi chọn giữa "chuyển ra module riêng, giữ cờ quay về" và "gỡ hẳn ngay, bỏ cờ", người dùng chọn
  **gỡ hẳn ngay, bỏ cờ**. Quyết định này thay cho việc hoãn tới sau demo.
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (đoạn cuối phần orchestrator, "Lọc đầu vào trước LLM", "Ngữ cảnh cho
  LLM"); `docs/prd/deployment-plan.md` §2 (dòng `ITINERARY_ORCHESTRATOR`); `docs/prd/requirements.md` §3 (một câu của
  AC-AGT-06)
- Mã FR/NFR: không đổi và không bỏ FR, NFR hay AC nào; liên quan FR-AGT-01, FR-AGT-06, FR-AGT-07, AC-AGT-01, AC-AGT-05
  đến AC-AGT-08, NFR-SEC-04

Tên file giữ "sau-demo" vì đã được tham chiếu trước khi người dùng đổi thời điểm. Phần orchestrator là mặc định nằm ở
`update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`.

## Lý do

Orchestrator đã là luồng mặc định (chốt 13/10). Code của luồng cũ vẫn nằm trong `nodes.py`, `graph.py`, `routing.py` và
các module bước, nên ai đọc luồng chạy cũng phải đọc hai đường. Người dùng muốn gỡ để nhóm không đọc trùng, không test
hay tối ưu nhầm trên luồng cũ.

Ảnh hưởng:
- Không còn đường quay về luồng cũ khi sự cố. Bản cũ vẫn còn trong lịch sử git để tra cứu.
- Không mất hành vi sản phẩm ở luồng mặc định, vì người dùng đã ở orchestrator.
- Ý AC trước đây chỉ luồng cũ đáp ứng không bị bỏ. Ý nào chạm kịch bản demo được kiểm và làm ở D1, D5. Ý còn lại được kiểm
  ở bảng AC (G0), rồi làm ở G3. Muốn tạm bỏ ý nào thì phải có đề xuất riêng.
- Kiểm tra hồi quy bắt buộc: snapshot ghi bằng orchestrator và phát lại được offline; golden.

## Nội dung đề xuất (đã áp dụng)

**1. `architecture.md` §3, đoạn cuối phần orchestrator**

Hiện tại (sau lần chốt sáng 13/10):
> Orchestrator là luồng mặc định (chốt 2026-10-13, `update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`). Luồng
> phân loại cũ (`classify` bằng LLM, các node khám phá và trò chuyện bằng LLM) chỉ còn sau `ITINERARY_ORCHESTRATOR=off`
> để quay về khi sự cố: không dùng, không sửa, không tối ưu, không thêm tính năng, và code của nó được ghi rõ là không
> dùng cho tới khi gỡ.

Thay bằng:
> Orchestrator là luồng duy nhất (chốt 2026-10-13, `update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`,
> `update-archive/2026-10-13-go-luong-cu-sau-demo.md`): không còn cờ bật/tắt, không còn bước phân loại bằng LLM và các
> node khám phá, trò chuyện bằng LLM của luồng cũ; code của luồng cũ đã gỡ để nhóm không phải đọc và sửa trùng. Không ý AC
> nào bị bỏ: ý AC trước đây chỉ luồng cũ đáp ứng được kiểm và làm trên orchestrator.

Các câu về kiểm tra bắt buộc giữ nguyên.

**2. `architecture.md` §3, "Lọc đầu vào trước LLM (NFR-SEC-04)"**

Hiện tại:
> `ClassifyTurn` chạy luật tất định trước khi gọi LLM: …

Thay bằng:
> `precheck` chạy luật tất định trước khi gọi LLM của orchestrator: …

Phần còn lại của câu giữ nguyên.

**3. `architecture.md` §3, "Ngữ cảnh cho LLM"**

Hiện tại:
> mọi lượt gọi LLM (phân luồng, trích intent, chọn điểm đến, lập tool plan, viết câu trả lời) …

Thay bằng:
> mọi lượt gọi LLM (orchestrator, trích intent, chọn điểm đến, lập tool plan, viết câu trả lời) …

**4. `deployment-plan.md` §2**

Xoá dòng `ITINERARY_ORCHESTRATOR`. Giữ các dòng `ITINERARY_ORCHESTRATOR_MODEL`, `ITINERARY_ORCHESTRATOR_PROVIDER`,
`ITINERARY_ORCHESTRATOR_REASONING_EFFORT`.

**5. `requirements.md` §3, AC-AGT-06**

Hiện tại:
> … hành vi này là của orchestrator, luồng mặc định từ 2026-10-13 (`architecture.md` §3,
> `update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`).

Thay bằng:
> … hành vi này là của orchestrator, luồng duy nhất từ 2026-10-13 (`architecture.md` §3,
> `update-archive/2026-10-13-go-luong-cu-sau-demo.md`).

## Thay đổi source sau khi chốt

Theo `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` (bước gỡ, làm trước demo, cùng D3):
- `src/backend/app/agents/graph.py`, `agents/routing.py`, `agents/nodes.py`:
  - Chỉ dựng luồng orchestrator; bỏ `classify`, `explore` và phần LLM của `converse`.
  - Các luật trước LLM nằm ở `precheck`.
  - `extract` không còn đích `explore`, `converse`.
- `agents/steps/classification.py`, `agents/steps/exploration.py`, `agents/steps/conversation.py`,
  `agents/steps/prompts.py`, `agents/models.py`: xoá phần chỉ luồng cũ dùng; chuyển helper dùng chung sang chỗ mới.
- `core/config.py`, `infrastructure/llm/client.py`, `main.py`, `agents/runtime_dependencies.py`, `docker-compose.yml`,
  `.env.example`: bỏ `ITINERARY_ORCHESTRATOR`.
- `src/backend/tests/`: xoá test chỉ của luồng cũ; chuyển test luật dùng chung (guardrail, vé) sang `precheck` và job vé;
  ghi lại snapshot bằng orchestrator.
- `src/evaluation/`, `docs/spec/agent/`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `src/backend/README.md`,
  skill `building-itinerary-agent`, `AGENTS.md` §3: bỏ mô tả luồng cũ, cờ và ghi chú đóng băng.
