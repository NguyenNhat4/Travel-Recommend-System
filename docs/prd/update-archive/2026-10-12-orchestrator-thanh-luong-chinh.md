# Orchestrator là luồng mặc định của trợ lý; luồng phân loại cũ chỉ còn để quay về khi sự cố

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13 ("dùng orchestrator làm mặc định, code cũ nếu chưa xoá thì cần làm rõ
  không dùng"; chấp nhận R1–R3 của plan)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (đoạn cuối phần orchestrator); `docs/prd/deployment-plan.md` §2 (dòng
  `ITINERARY_ORCHESTRATOR`); `docs/prd/requirements.md` §3 (một câu của AC-AGT-06)
- Mã FR/NFR: không đổi và không bỏ FR, NFR hay AC nào; liên quan FR-AGT-01, FR-AGT-06, FR-AGT-07, AC-AGT-01, AC-AGT-05
  đến AC-AGT-08, NFR-SEC-04

Việc gỡ hẳn cờ và code luồng cũ tách sang đề xuất riêng `docs/prd/update/2026-10-13-go-luong-cu-sau-demo.md` (chờ chốt),
vì người dùng hoãn việc đó tới sau demo.

## Lý do

Hiện có hai luồng chạy song song sau cờ `ITINERARY_ORCHESTRATOR`:
- Luồng cũ, đang là mặc định: `classify` gọi LLM để phân loại, rồi `explore` hoặc `converse`.
- Luồng orchestrator.

Nhóm phải test, tune và sửa lỗi trên cả hai. Người dùng quyết định (12/10) orchestrator là luồng chính, và ưu tiên trước
mắt là demo thật tốt. Demo phải chạy orchestrator. PRD hiện ghi "Cờ mặc định tắt; chỉ chuyển sau bộ đo đạt ngưỡng", nên
quyết định này lệch PRD.

Ảnh hưởng:
- Hành vi trả lời thay đổi có chủ ý ở mọi lượt trước đây đi luồng cũ, kể cả trên staging.
- Snapshot hành vi phải ghi lại bằng orchestrator, và người dùng duyệt phần khác biệt.
- Bộ đo so sánh hai kiến trúc (B11–B12 của plan orchestrator) không còn là điều kiện để chuyển. Thay vào đó, kiểm tra bắt
  buộc gồm:
  - Các kịch bản demo chạy với LLM thật.
  - Ý AC mà kịch bản chạm tới đạt trên orchestrator.
  - Snapshot ghi bằng orchestrator và phát lại được offline.
- Luồng cũ còn trong repo tới khi gỡ, nên phải được ghi rõ là không dùng, để không ai test hay tối ưu nhầm trên nó.
- Mỗi lượt có thêm thời gian và chi phí của model orchestrator. Lần chạy thử ngày 12/10 đo 7–39 giây mỗi lượt (một lần,
  máy local).

## Nội dung đề xuất

**1. `architecture.md` §3, đoạn cuối phần orchestrator**

Hiện tại:
> Nhiệt độ, reasoning, ngân sách thời gian đặt bằng số đo. Cờ mặc định tắt; chỉ chuyển sau bộ đo đạt ngưỡng.

Thay bằng:
> Nhiệt độ, reasoning, ngân sách thời gian đặt bằng số đo. Orchestrator là luồng mặc định (chốt 2026-10-13,
> `update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`). Luồng phân loại cũ (`classify` bằng LLM, các node khám
> phá và trò chuyện bằng LLM) chỉ còn sau `ITINERARY_ORCHESTRATOR=off` để quay về khi sự cố: không dùng, không sửa,
> không tối ưu, không thêm tính năng, và code của nó được ghi rõ là không dùng cho tới khi gỡ. Không còn đo so sánh hai
> kiến trúc. Kiểm tra bắt buộc gồm: các kịch bản demo chạy với LLM thật; ý AC mà kịch bản chạm tới đạt; snapshot hành vi
> ghi bằng orchestrator và phát lại được offline.

**2. `deployment-plan.md` §2, dòng `ITINERARY_ORCHESTRATOR`**

Hiện tại:
> | `ITINERARY_ORCHESTRATOR` | `off` (mặc định) hoặc `on`; giữ đường cũ tới bộ đo đạt ngưỡng | Tất cả | Không bí mật |

Thay bằng:
> | `ITINERARY_ORCHESTRATOR` | `on` (mặc định) hoặc `off`. `off` chỉ để quay về luồng phân loại cũ khi sự cố; luồng cũ không dùng, không sửa, không tối ưu | Tất cả | Không bí mật |

**3. `requirements.md` §3, AC-AGT-06, câu gần cuối**

Thêm khi áp dụng ngày 13/10: câu này nói trái với quyết định đã chốt, nên phải đổi cùng lúc để PRD không tự mâu thuẫn.

Hiện tại:
> Thời gian phản hồi đặt lại sau bộ đo; hành vi mới sau cờ mặc định tắt tới khi đạt ngưỡng.

Thay bằng:
> Thời gian phản hồi đặt lại sau bộ đo; hành vi này là của orchestrator, luồng mặc định từ 2026-10-13 (`architecture.md`
> §3, `update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`).

## Thay đổi source sau khi chốt

Theo `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`, phần trước demo:
- D0: ghi chú "luồng cũ đóng băng" ở `AGENTS.md` §3, `docs/spec/agent/working-context.md`, skill
  `building-itinerary-agent`. Trong code: comment ở các hàm, module chỉ luồng cũ dùng, và log cảnh báo khi dựng graph với
  cờ tắt.
- D2: `agents/clock.py` (mới) và mã nguyên nhân cho câu dự phòng; snapshot dùng đồng hồ ảo, ghi cả model orchestrator.
- D3: mặc định `on` ở `src/backend/app/core/config.py`, `docker-compose.yml`, `.env.example`; ghi lại snapshot
  (`src/backend/tests/unit/agents/behavior_snapshot/`) bằng orchestrator, phát lại offline, người dùng duyệt.
