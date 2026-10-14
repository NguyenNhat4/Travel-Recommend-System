# Bỏ kiểm tra snapshot hành vi của orchestrator

- Ngày: 2026-10-13
- Tác giả: người dùng yêu cầu / agent (Claude Code)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Snapshot hành vi (`test_behavior_snapshot.py`) làm Backend CI đỏ sau commit `cab5e728`: cassette không khớp prompt orchestrator
mới. Ghi lại cassette không đạt được chất lượng ổn định (xem `2026-10-13-ghi-lai-behavior-snapshot.md` và
`2026-10-13-thu-sua-prompt-orchestrator-khong-giu.md`). Người dùng chốt bỏ test này. Đề xuất đã chốt:
`docs/prd/update-archive/2026-10-13-bo-kiem-tra-snapshot-hanh-vi.md`.

## File thay đổi

- `src/backend/tests/unit/agents/test_behavior_snapshot.py` — xoá: code chạy test snapshot.
- `docs/prd/architecture.md` — sửa: §3, bỏ "snapshot hành vi ghi bằng orchestrator và phát lại được offline" khỏi danh sách
  kiểm tra bắt buộc.
- `docs/spec/agent/working-context.md` — sửa: §5A, ghi rõ test đã gỡ, `harness.py`/`record.py` còn lại.
- `docs/prd/update-archive/2026-10-13-bo-kiem-tra-snapshot-hanh-vi.md` — chuyển từ `docs/prd/update/`, trạng thái đã áp dụng.
- `history/2026-10-13-bo-kiem-tra-snapshot-hanh-vi.md` — thêm: entry này.
- Không đổi: `behavior_snapshot/harness.py`, `record.py`, `scenarios.json`. `test_turn_limits.py` vẫn dùng `harness` và `record`.

Lưu ý: `cassette.json`, `snapshot.json`, `tools.json.gz` còn là bản ghi lần 1 (chưa commit). Không còn test nào đọc chúng.

## Quyết định

- Xoá code test thay vì skip: một test skip vẫn để lại đường dẫn và dữ liệu không ai kiểm tra.
- Giữ `behavior_snapshot/` vì `test_turn_limits.py` import từ đó, và `record.py` là công cụ ghi lại.
- Không xoá dữ liệu cassette/snapshot trong lần này: chờ quyết định về baseline.

## Kiểm tra

- `pytest -q src/backend/tests`: 2969 passed, 40 skipped, 3 xfailed (trước đó 2973 passed, trong đó có 4 test snapshot).
- Không chạy `validate_contract.py`: không đổi contract.

## Còn lại / rủi ro

- Không còn lưới kiểm tra offline cho hành vi orchestrator. Thay đổi prompt hoặc model sẽ không báo lỗi tự động.
- Lỗi 500 `explore_grounding` trong `steps/validation.py` vẫn còn: thẻ fallback từ lượt trước khác `availableFrom`/`availableTo`
  so với bản tóm tắt của lượt này. Chưa sửa; cần quyết định về cửa sổ đặt chỗ chuẩn.
- `harness._prompt_key` không đưa tên model vào khoá cache (chỉ có hằng `orchestrator`), trái với docstring của harness. Khi
  đổi model, phải xoá cassette LLM trước khi ghi lại, nếu không sẽ tái dùng câu trả lời của model cũ.
- Quyết định còn mở: chọn model orchestrator (`.env` hiện đặt `ITINERARY_ORCHESTRATOR_MODEL=gpt-6-luna`), và có xoá dữ liệu
  `behavior_snapshot/` (cassette, snapshot, tools) hay không.
