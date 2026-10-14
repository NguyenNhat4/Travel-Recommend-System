# Bỏ kiểm tra snapshot hành vi khỏi PRD

- Ngày: 2026-10-13
- Người đề xuất: người dùng yêu cầu / Claude Code
- Trạng thái: đã áp dụng (2026-10-13)
- Chốt bởi / ngày: người dùng, 2026-10-13 (trong chat, sau khi được cảnh báo rằng xoá là lệch PRD: "xóa đoạn code chạy cái test đó")
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3, đoạn "Kiểm tra bắt buộc gồm"
- Mã FR/NFR: không có mã riêng. Liên quan gián tiếp NFR-REL-01 (grounding).

## Lý do

Sau khi prompt orchestrator đổi (commit `cab5e728`), snapshot hành vi trên CI fail vì cassette không khớp payload mới. Ghi lại
cassette cần LLM thật, Postgres và Weaviate local. Đã thử ba lần:

- Lần 1 (prompt cũ, model mặc định): test pass, nhưng baseline có 3 lượt HTTP 500, 19 dừng `ROUND_LIMIT`, 72 fallback grounding.
- Lần 2 (thêm luật vào prompt): vi phạm grounding tăng từ 124 lên 140. Đã hoàn tác.
- Lần 3 (model orchestrator `gpt-6-luna`): bị huỷ theo yêu cầu.

Người dùng quyết định bỏ test này để CI không bị chặn bởi baseline chưa ổn định. Hệ quả: mất lưới kiểm tra offline chống đổi
hành vi của orchestrator. Các kiểm tra còn lại: unit test agent và domain, và kịch bản demo chạy với LLM thật.

## Nội dung đề xuất

Trích hiện tại:

> Kiểm tra bắt buộc gồm: các kịch bản demo chạy với LLM thật; ý AC mà kịch bản chạm tới đạt; snapshot hành vi
> ghi bằng orchestrator và phát lại được offline.

Thay bằng:

> Kiểm tra bắt buộc gồm: các kịch bản demo chạy với LLM thật; ý AC mà kịch bản chạm tới đạt.

## Thay đổi source sau khi chốt

- Xoá `src/backend/tests/unit/agents/test_behavior_snapshot.py` (code chạy test).
- Giữ `src/backend/tests/unit/agents/behavior_snapshot/` (`harness.py`, `record.py`, dữ liệu). `test_turn_limits.py` vẫn
  import `harness` và `record`; `record` vẫn là công cụ ghi lại khi cần.
- `docs/spec/agent/working-context.md` §5A: bỏ mô tả test snapshot chạy cùng unit test.
- Entry `history/2026-10-13-bo-kiem-tra-snapshot-hanh-vi.md`.
