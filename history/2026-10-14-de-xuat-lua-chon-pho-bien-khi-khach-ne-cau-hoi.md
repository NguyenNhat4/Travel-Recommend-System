# Khách né câu hỏi thông tin chuyến: đề xuất lựa chọn phổ biến; lịch không lưu với trường orc tự điền

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, docs, evaluation
- Mã FR/NFR: FR-AGT-01, AC-AGT-01, AC-AGT-07
- Đề xuất: `docs/prd/update-archive/2026-10-14-de-xuat-lua-chon-pho-bien-khi-khach-khong-tra-loi.md`

## Mục tiêu

Sau `2026-10-14-lich-v2-ke-theo-ngay-va-cau-cut.md`: khách đáp "ko biết", "tùy bạn", "k" thì trợ lý v2 hỏi lại gần y
nguyên câu cũ. Người dùng không muốn đưa form ("stop sent the form") và chọn "the assistant proposes a common choice".

## File thay đổi

- `docs/prd/update-archive/2026-10-14-de-xuat-lua-chon-pho-bien-khi-khach-khong-tra-loi.md` — thêm: đề xuất, ghi
  chốt của người dùng trong chat, trạng thái đã áp dụng.
- `docs/prd/requirements.md` — sửa AC-AGT-07 đoạn **Cộc lốc**: đề xuất lựa chọn phổ biến + một câu có/không + nút
  đồng ý thay cho form.
- `src/backend/app/agents/orc_v2.py` — sửa PROMPT: né câu hỏi → đề xuất mọi trường thiếu kèm một nút; "ok" thì
  update_trip + tra + plan_itinerary ngay lượt đó; chỉ đề xuất sau khi khách né; giải thích trường trong
  `needs_update_trip`; guard truyền `trip=context` vào `final_issues`.
- `src/backend/app/domain/itinerary/orc_guardrails.py` — thêm `TRIP_FIELDS`, `unconfirmed_trip_fields`; `final_issues`
  nhận `trip` và trả `TRIP_FIELD_UNCONFIRMED` khi lịch thay mới dùng trường bắt buộc khác ngữ cảnh đã lưu.
- `src/backend/app/application/itinerary/orc_dispatch.py` — sửa: `needs_update_trip` gồm cả trường bắt buộc chưa
  khớp ngữ cảnh; `commit_allowed` chỉ khi danh sách rỗng.
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa ngữ cảnh 3 test cho có đủ trường chuyến; thêm
  `test_plan_with_trip_fields_the_user_never_gave_is_not_saved`.
- `src/backend/tests/unit/agents/test_orc_tool_dispatch.py` — sửa `test_plan_feedback_requires_consent_without_granting_it`:
  ngữ cảnh có trường chuyến, thêm ca adults orc tự điền.
- `src/evaluation/agent/assistant_v2_cases.py` — sửa ca `short-unknown`, `short-whatever`, `short-k`: thêm lượt "ok".
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa §v2: quy ước đề xuất và luật kiểm trường chuyến.
- `history/2026-10-14-de-xuat-lua-chon-pho-bien-khi-khach-ne-cau-hoi.md` — thêm: entry này.

## Quyết định

- Lệch PRD (AC-AGT-07 ghi hiện form) nên viết đề xuất; người dùng đã chọn rõ phương án trong chat, ghi làm chốt rồi
  áp dụng PRD trước source (AGENTS.md §8).
- Luật code ở `domain`: bằng chứng đo trước (đo lần 1 với prompt mới, 9 lần) có 2 lần orc tự điền giá trị khách chưa
  nói (lịch 3 ngày khi chưa hỏi số ngày; "hai người lớn" ở lượt đầu), 1 lần "ok" chỉ ghi nhận không lập lịch. Dữ kiện
  chuyến là phạm vi thực thi nên code kiểm; câu chữ vẫn do LLM.
- Không đổi luật evidence (chuỗi con của tin hiện tại): "ok" xác nhận đề xuất cần dùng chính câu đó làm căn cứ.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/application
  src/backend/tests/unit/domain`: 2650 passed, 3 xfailed. `src/backend/tests/architecture`: 8 passed.
- LLM thật, backend local :8001 cùng env :8000, `assistant_v2_cases --repeat 3`:
  - `short-unknown`: 3/3 đề xuất + nút, "ok" ra lịch.
  - `short-whatever`, `short-k`: mỗi ca 2/3 đề xuất + nút rồi "ok" ra lịch; 1/3 lập lịch ngay ở lượt né với giá trị
    phổ biến (3 ngày, 2 người lớn) mà lời đáp không nêu giá trị đã chọn.
  - `plan-by-day`: 3/3 không lập lịch trước khi biết số người lớn, ra lịch adults=3 ở lượt 3.
  - `kids-short-no`: 3/3 không hỏi trẻ em, ra lịch adults=10.
  - Log :8001: `TRIP_FIELD_UNCONFIRMED` không bắn lần nào trong lượt đo này (prompt đã đủ); 1 `MISSING_DISCLOSURE`,
    1 `UNSUPPORTED_FACT` được orc sửa.
- Chưa chạy cả bộ backend, chưa chạy frontend (không đổi frontend).

## Còn lại / rủi ro

- 2/9 lần orc lấy chính câu né ("tùy bạn", "k") làm căn cứ cho giá trị phổ biến và lập lịch luôn, không nói đã chọn
  3 ngày, 2 người lớn. Luật evidence chuỗi con không chặn được; muốn chặn cần ghi đề xuất đang chờ vào ngữ cảnh.
- Từ chối lịch vì `TRIP_FIELD_UNCONFIRMED` hai lần liền thành `ITINERARY_VALIDATION_FAILED` như mọi issue khác.
- Backend :8000 của demo cần khởi động lại để nhận thay đổi.
